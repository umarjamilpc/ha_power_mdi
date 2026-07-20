"""Coordinator for time-synced MDI demand block tracking."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import async_track_point_in_time, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import now as dt_now

from .util import parse_time
from .const import (
    BLOCK_DURATION_OPTIONS,
    COMP_COMBINED,
    COMP_EXPORT,
    COMP_IMPORT,
    CONF_AUTO_SNAPSHOT,
    CONF_BLOCK_DURATION_MINUTES,
    CONF_ENTITY_ID_BASE,
    CONF_EXPORT_POWER_ENTITY,
    CONF_IMPORT_POWER_ENTITY,
    CONF_MODE,
    CONF_NAME,
    CONF_POWER_UNIT,
    CONF_READING_DAY,
    CONF_READING_TIME,
    CONF_RESET_DAY,
    CONF_SIGNED_POWER_ENTITY,
    DEFAULT_BLOCK_DURATION_MINUTES,
    MODE_SPLIT,
    ONE_MINUTE_BLOCK_SECONDS,
    POWER_UNIT_AUTO,
    POWER_UNIT_KW,
    POWER_UNIT_W,
    DOMAIN,
    STORAGE_VERSION,
    is_combined_mode,
)

_LOGGER = logging.getLogger(__name__)


def _power_to_energy_kwh(power_kw: float, elapsed_seconds: float) -> float:
    """Convert constant power over elapsed time to energy in kWh."""
    return power_kw * elapsed_seconds / 3600.0


def _interval_demand_kw(energy_kwh: float, interval_seconds: float) -> float:
    """Utility interval demand: kW = kWh / interval_hours."""
    interval_hours = interval_seconds / 3600.0
    if interval_hours <= 0:
        return 0.0
    return energy_kwh / interval_hours


def _safe_float(value: Any) -> float | None:
    """Convert value to float if possible."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    # Avoid NaN propagation
    if f != f:  # noqa: PLR0124 (NaN check)
        return None
    return f


def _normalize_to_kw(power_value: float, unit: str, power_scaling_mode: str) -> float | None:
    """Normalize a power reading to kW.

    power_value is assumed to be in the unit described by unit/power_scaling_mode.
    """
    unit_clean = (unit or "").strip().lower()
    if power_scaling_mode == POWER_UNIT_KW:
        return power_value
    if power_scaling_mode == POWER_UNIT_W:
        return power_value / 1000.0
    # AUTO
    if unit_clean in {"kw", "kilowatt", "kilowatts"}:
        return power_value
    # Some sensors report "W" or "w"
    if unit_clean in {"w", "watt", "watts"}:
        return power_value / 1000.0
    # Unknown unit: default to W behavior
    return power_value / 1000.0


@dataclass
class MdiState:
    cycle_id: str

    # Last completed configurable-duration block averages (kW)
    last_completed_import_kw: float | None = None
    last_completed_export_kw: float | None = None
    last_completed_combined_kw: float | None = None

    # Last completed fixed 1-minute block averages (kW)
    last_completed_1min_import_kw: float | None = None
    last_completed_1min_export_kw: float | None = None

    # Current cycle (month based on reset_day) maxima (kW)
    mdi_import_max_kw: float = 0.0
    mdi_export_max_kw: float = 0.0
    mdi_combined_max_kw: float = 0.0

    # Snapshot at meter reading (kW)
    mdi_import_at_reading_kw: float | None = None
    mdi_export_at_reading_kw: float | None = None
    mdi_combined_at_reading_kw: float | None = None
    mdi_at_reading_timestamp: datetime | None = None

    # Block currently in progress (best-effort, kW)
    current_block_start: datetime | None = None
    current_block_end: datetime | None = None
    current_import_block_avg_kw: float | None = None
    current_export_block_avg_kw: float | None = None
    current_combined_block_avg_kw: float | None = None

    # Availability
    source_ok: bool = False


class MdiCoordinator(DataUpdateCoordinator[MdiState]):
    """Track MDI using utility interval demand: kW = kWh / hours."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.config = {**entry.data, **entry.options}

        self.hass = hass
        self._reload_runtime_config()

        # State accumulation for the active configurable-duration window
        self._active_block_start: datetime | None = None
        self._active_block_end: datetime | None = None
        self._energy_import_kwh: float = 0.0
        self._energy_export_kwh: float = 0.0
        self._energy_combined_kwh: float = 0.0

        self._last_sample_time: datetime | None = None
        self._last_import_kw: float = 0.0
        self._last_export_kw: float = 0.0
        self._last_combined_kw: float = 0.0
        self._block_valid: bool = False

        # State accumulation for the always-on 1-minute companion window
        self._1m_block_start: datetime | None = None
        self._1m_block_end: datetime | None = None
        self._1m_energy_import_kwh: float = 0.0
        self._1m_energy_export_kwh: float = 0.0
        self._1m_last_sample_time: datetime | None = None
        self._1m_last_import_kw: float = 0.0
        self._1m_last_export_kw: float = 0.0
        self._1m_block_valid: bool = False

        # Scheduled point-in-time unsubscribers
        self._unsub_block_start: Callable[[], None] | None = None
        self._unsub_block_end: Callable[[], None] | None = None
        self._unsub_1m_block_start: Callable[[], None] | None = None
        self._unsub_1m_block_end: Callable[[], None] | None = None
        self._unsub_state_listener: Callable[[], None] | None = None
        self._unsub_reading_snapshot: Callable[[], None] | None = None

        # Storage
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}:{entry.entry_id}",
        )

        # Initialize coordinator with placeholder state
        current_cycle_id = self._compute_cycle_id(dt_now())
        super().__init__(hass, _LOGGER, name=f"MDI Coordinator ({self._entity_id_base})", update_interval=None)
        self.data = MdiState(cycle_id=current_cycle_id)

    async def async_initialize(self) -> None:
        """Initialize coordinator, load state, subscribe, and schedule windows."""
        stored = await self._store.async_load()
        current_cycle_id = self._compute_cycle_id(dt_now())

        if stored and stored.get("cycle_id") == current_cycle_id:
            self.data = MdiState(
                cycle_id=current_cycle_id,
                last_completed_import_kw=stored.get("last_completed_import_kw"),
                last_completed_export_kw=stored.get("last_completed_export_kw"),
                last_completed_combined_kw=stored.get("last_completed_combined_kw"),
                last_completed_1min_import_kw=stored.get("last_completed_1min_import_kw"),
                last_completed_1min_export_kw=stored.get("last_completed_1min_export_kw"),
                mdi_import_max_kw=float(stored.get("mdi_import_max_kw", 0.0)),
                mdi_export_max_kw=float(stored.get("mdi_export_max_kw", 0.0)),
                mdi_combined_max_kw=float(stored.get("mdi_combined_max_kw", 0.0)),
                mdi_import_at_reading_kw=stored.get("mdi_import_at_reading_kw"),
                mdi_export_at_reading_kw=stored.get("mdi_export_at_reading_kw"),
                mdi_combined_at_reading_kw=stored.get("mdi_combined_at_reading_kw"),
                mdi_at_reading_timestamp=self._parse_datetime(stored.get("mdi_at_reading_timestamp")),
                current_block_start=None,
                current_block_end=None,
                current_import_block_avg_kw=None,
                current_export_block_avg_kw=None,
                current_combined_block_avg_kw=None,
                source_ok=False,
            )
        else:
            # New cycle or first install: start fresh
            self.data = MdiState(
                cycle_id=current_cycle_id,
                last_completed_1min_import_kw=(
                    stored.get("last_completed_1min_import_kw") if stored else None
                ),
                last_completed_1min_export_kw=(
                    stored.get("last_completed_1min_export_kw") if stored else None
                ),
            )
            await self._async_save_storage()

        self._subscribe_power_entities()
        await self._schedule_next_block()
        await self._schedule_next_1m_block()
        await self._maybe_schedule_or_take_snapshot(initial=True)

        # Ensure entities get an initial update
        self.async_set_updated_data(self.data)

    def _reload_runtime_config(self) -> None:
        """Load timing, source, and block settings from the config entry."""
        self._reset_day = int(self.config[CONF_RESET_DAY])
        self._reading_day = int(self.config[CONF_READING_DAY])
        self._reading_time = parse_time(self.config[CONF_READING_TIME])
        self._auto_snapshot = bool(self.config[CONF_AUTO_SNAPSHOT])
        block_duration = int(
            self.config.get(CONF_BLOCK_DURATION_MINUTES, DEFAULT_BLOCK_DURATION_MINUTES)
        )
        if block_duration not in BLOCK_DURATION_OPTIONS:
            block_duration = DEFAULT_BLOCK_DURATION_MINUTES
        self._block_duration_minutes = block_duration
        self._block_duration_seconds = block_duration * 60

        self._mode = self.config[CONF_MODE]
        self._signed_power_entity = self.config.get(CONF_SIGNED_POWER_ENTITY)
        self._import_power_entity = self.config.get(CONF_IMPORT_POWER_ENTITY)
        self._export_power_entity = self.config.get(CONF_EXPORT_POWER_ENTITY)
        self._power_unit_mode = self.config[CONF_POWER_UNIT]
        self._entity_id_base = self.config.get(CONF_ENTITY_ID_BASE, "mdi")

    async def async_shutdown(self) -> None:
        """Stop scheduled callbacks."""
        self._unsubscribe_power_entities()
        if self._unsub_block_start:
            self._unsub_block_start()
            self._unsub_block_start = None
        if self._unsub_block_end:
            self._unsub_block_end()
            self._unsub_block_end = None
        if self._unsub_1m_block_start:
            self._unsub_1m_block_start()
            self._unsub_1m_block_start = None
        if self._unsub_1m_block_end:
            self._unsub_1m_block_end()
            self._unsub_1m_block_end = None
        if self._unsub_reading_snapshot:
            self._unsub_reading_snapshot()
            self._unsub_reading_snapshot = None

    async def async_handle_update(self, entry: ConfigEntry) -> None:
        """Reconfigure the coordinator when options change."""
        await self.async_shutdown()

        self.entry = entry
        self.config = {**entry.data, **entry.options}
        self._reload_runtime_config()

        self._active_block_start = None
        self._active_block_end = None
        self._energy_import_kwh = 0.0
        self._energy_export_kwh = 0.0
        self._energy_combined_kwh = 0.0
        self._last_sample_time = None
        self._last_import_kw = 0.0
        self._last_export_kw = 0.0
        self._last_combined_kw = 0.0
        self._block_valid = False

        self._1m_block_start = None
        self._1m_block_end = None
        self._1m_energy_import_kwh = 0.0
        self._1m_energy_export_kwh = 0.0
        self._1m_last_sample_time = None
        self._1m_last_import_kw = 0.0
        self._1m_last_export_kw = 0.0
        self._1m_block_valid = False

        prev_1m_import = self.data.last_completed_1min_import_kw if self.data else None
        prev_1m_export = self.data.last_completed_1min_export_kw if self.data else None
        current_cycle_id = self._compute_cycle_id(dt_now())
        self.data = MdiState(
            cycle_id=current_cycle_id,
            last_completed_1min_import_kw=prev_1m_import,
            last_completed_1min_export_kw=prev_1m_export,
        )

        await self._async_save_storage()
        self._subscribe_power_entities()
        await self._schedule_next_block()
        await self._schedule_next_1m_block()
        await self._maybe_schedule_or_take_snapshot(initial=False)
        self.async_set_updated_data(self.data)

    def _compute_cycle_id(self, local_dt: datetime) -> str:
        """Compute cycle id based on reset_day (defaults to day 1)."""
        # If we're before reset_day, cycle started last month.
        if local_dt.day < self._reset_day:
            year = local_dt.year
            month = local_dt.month - 1
            if month == 0:
                month = 12
                year -= 1
        else:
            year = local_dt.year
            month = local_dt.month
        return f"{year:04d}-{month:02d}"

    def _cycle_start_datetime(self, local_dt: datetime) -> datetime:
        """Return timezone-aware datetime at cycle start (reset_day 00:00)."""
        if local_dt.day < self._reset_day:
            year = local_dt.year
            month = local_dt.month - 1
            if month == 0:
                month = 12
                year -= 1
        else:
            year = local_dt.year
            month = local_dt.month
        return datetime(
            year=year,
            month=month,
            day=self._reset_day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=local_dt.tzinfo,
        )

    def _reading_datetime_for_cycle(self, cycle_start_dt: datetime) -> datetime:
        """Compute auto snapshot datetime for the cycle."""
        # cycle_dt is any datetime inside the cycle; we use its year/month.
        reading = datetime(
            year=cycle_start_dt.year,
            month=cycle_start_dt.month,
            day=self._reading_day,
            hour=self._reading_time.hour,
            minute=self._reading_time.minute,
            second=self._reading_time.second,
            microsecond=0,
            tzinfo=cycle_start_dt.tzinfo,
        )
        return reading

    def _current_window_start(self, local_dt: datetime) -> datetime:
        """Return the start of the demand block containing local_dt."""
        midnight = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elapsed_seconds = int((local_dt - midnight).total_seconds())
        slot_seconds = self._block_duration_seconds
        slot_index = elapsed_seconds // slot_seconds
        return midnight + timedelta(seconds=slot_index * slot_seconds)

    def _next_window_start(self, local_dt: datetime) -> datetime:
        """Get the next demand block boundary start."""
        current_start = self._current_window_start(local_dt)
        if local_dt == current_start:
            return current_start
        return current_start + timedelta(minutes=self._block_duration_minutes)

    def _next_1m_window_start(self, local_dt: datetime) -> datetime:
        """Get the next whole-minute boundary start."""
        slot_start = local_dt.replace(second=0, microsecond=0)
        if local_dt == slot_start:
            return slot_start
        return slot_start + timedelta(seconds=ONE_MINUTE_BLOCK_SECONDS)

    def _preserve_1min_on_cycle_reset(self, new_cycle_id: str) -> None:
        """Start a new monthly cycle while keeping live 1-minute MDI values."""
        self.data = MdiState(
            cycle_id=new_cycle_id,
            last_completed_1min_import_kw=self.data.last_completed_1min_import_kw,
            last_completed_1min_export_kw=self.data.last_completed_1min_export_kw,
        )

    async def _schedule_next_block(self) -> None:
        """Schedule the next window start aligned to the configured block duration."""
        local_now = dt_now()
        next_start = self._next_window_start(local_now)

        # Cancel any existing window callbacks (shouldn't happen often)
        if self._unsub_block_start:
            self._unsub_block_start()
        if self._unsub_block_end:
            self._unsub_block_end()

        self._unsub_block_start = async_track_point_in_time(
            self.hass,
            self._handle_block_start,
            next_start,
        )
        self._unsub_block_end = async_track_point_in_time(
            self.hass,
            self._handle_block_end,
            next_start + timedelta(seconds=self._block_duration_seconds),
        )

    async def _schedule_next_1m_block(self) -> None:
        """Schedule the next 1-minute demand window."""
        local_now = dt_now()
        next_start = self._next_1m_window_start(local_now)

        if self._unsub_1m_block_start:
            self._unsub_1m_block_start()
        if self._unsub_1m_block_end:
            self._unsub_1m_block_end()

        self._unsub_1m_block_start = async_track_point_in_time(
            self.hass,
            self._handle_1m_block_start,
            next_start,
        )
        self._unsub_1m_block_end = async_track_point_in_time(
            self.hass,
            self._handle_1m_block_end,
            next_start + timedelta(seconds=ONE_MINUTE_BLOCK_SECONDS),
        )

    async def _handle_block_start(self, run_at: datetime) -> None:
        """Start a new demand block exactly on boundary."""
        # Ensure cycle is correct at the moment we begin.
        local_now = dt_now()
        new_cycle_id = self._compute_cycle_id(local_now)
        if new_cycle_id != self.data.cycle_id:
            self._preserve_1min_on_cycle_reset(new_cycle_id)
            await self._async_save_storage()
            await self._maybe_schedule_or_take_snapshot(initial=False)

        self._active_block_start = run_at
        self._active_block_end = run_at + timedelta(seconds=self._block_duration_seconds)

        self._energy_import_kwh = 0.0
        self._energy_export_kwh = 0.0
        self._energy_combined_kwh = 0.0
        self._last_sample_time = None
        self._block_valid = False

        # First sample at the block boundary; entity updates continue sampling.
        await self._take_sample(run_at)

        self.data.current_block_start = self._active_block_start
        self.data.current_block_end = self._active_block_end

    async def _handle_block_end(self, run_at: datetime) -> None:
        """Finalize the active window and update monthly maxima."""
        if not self._active_block_start or not self._last_sample_time:
            self._active_block_start = None
            self._active_block_end = None
            await self._chain_next_main_block(run_at)
            return

        # Update cycle id at window end in case reset boundary is between.
        local_now = dt_now()
        new_cycle_id = self._compute_cycle_id(local_now)
        if new_cycle_id != self.data.cycle_id:
            self._preserve_1min_on_cycle_reset(new_cycle_id)
            await self._async_save_storage()
            await self._maybe_schedule_or_take_snapshot(initial=False)

        # Add area until exact window end if valid
        if self._block_valid:
            self._accumulate_main_since_last_sample(run_at)

            avg_import = _interval_demand_kw(self._energy_import_kwh, self._block_duration_seconds)
            avg_export = _interval_demand_kw(self._energy_export_kwh, self._block_duration_seconds)
            avg_combined = _interval_demand_kw(self._energy_combined_kwh, self._block_duration_seconds)
        else:
            avg_import = None
            avg_export = None
            avg_combined = None

        # Update last completed block sensors
        self.data.last_completed_import_kw = avg_import
        self.data.last_completed_export_kw = avg_export
        self.data.last_completed_combined_kw = avg_combined

        # Update monthly maxima
        changed = False
        if avg_import is not None and avg_import > self.data.mdi_import_max_kw:
            self.data.mdi_import_max_kw = avg_import
            changed = True
        if avg_export is not None and avg_export > self.data.mdi_export_max_kw:
            self.data.mdi_export_max_kw = avg_export
            changed = True
        if avg_combined is not None and avg_combined > self.data.mdi_combined_max_kw:
            self.data.mdi_combined_max_kw = avg_combined
            changed = True

        # Clear in-progress main block
        self._active_block_start = None
        self._active_block_end = None
        self.data.current_block_start = None
        self.data.current_block_end = None
        self.data.current_import_block_avg_kw = None
        self.data.current_export_block_avg_kw = None
        self.data.current_combined_block_avg_kw = None

        # Persist if a new max peak was hit
        if changed:
            await self._async_save_storage()

        self.async_set_updated_data(self.data)
        await self._chain_next_main_block(run_at)

    async def _chain_next_main_block(self, next_start: datetime) -> None:
        """Schedule the next configurable-duration block pair."""
        self._unsub_block_start = None
        self._unsub_block_end = None

        self._unsub_block_start = async_track_point_in_time(
            self.hass,
            self._handle_block_start,
            next_start,
        )
        self._unsub_block_end = async_track_point_in_time(
            self.hass,
            self._handle_block_end,
            next_start + timedelta(seconds=self._block_duration_seconds),
        )

    async def _handle_1m_block_start(self, run_at: datetime) -> None:
        """Start a new fixed 1-minute demand block."""
        self._1m_block_start = run_at
        self._1m_block_end = run_at + timedelta(seconds=ONE_MINUTE_BLOCK_SECONDS)
        self._1m_energy_import_kwh = 0.0
        self._1m_energy_export_kwh = 0.0
        self._1m_last_sample_time = None
        self._1m_block_valid = False
        await self._take_sample(run_at)

    async def _handle_1m_block_end(self, run_at: datetime) -> None:
        """Finalize the active 1-minute demand block."""
        if not self._1m_block_start or not self._1m_last_sample_time:
            self._1m_block_start = None
            self._1m_block_end = None
            await self._chain_next_1m_block(run_at)
            return

        if self._1m_block_valid:
            self._accumulate_1m_since_last_sample(run_at)
            avg_import = _interval_demand_kw(self._1m_energy_import_kwh, ONE_MINUTE_BLOCK_SECONDS)
            avg_export = _interval_demand_kw(self._1m_energy_export_kwh, ONE_MINUTE_BLOCK_SECONDS)
        else:
            avg_import = None
            avg_export = None

        self.data.last_completed_1min_import_kw = avg_import
        self.data.last_completed_1min_export_kw = avg_export

        self._1m_block_start = None
        self._1m_block_end = None

        await self._async_save_storage()
        self.async_set_updated_data(self.data)
        await self._chain_next_1m_block(run_at)

    async def _chain_next_1m_block(self, next_start: datetime) -> None:
        """Schedule the next 1-minute block pair."""
        self._unsub_1m_block_start = None
        self._unsub_1m_block_end = None

        self._unsub_1m_block_start = async_track_point_in_time(
            self.hass,
            self._handle_1m_block_start,
            next_start,
        )
        self._unsub_1m_block_end = async_track_point_in_time(
            self.hass,
            self._handle_1m_block_end,
            next_start + timedelta(seconds=ONE_MINUTE_BLOCK_SECONDS),
        )

    def _power_entity_ids(self) -> list[str]:
        """Return the power entity IDs to listen to for instantaneous sampling."""
        if is_combined_mode(self._mode):
            if self._signed_power_entity:
                return [self._signed_power_entity]
            return []
        entity_ids: list[str] = []
        if self._import_power_entity:
            entity_ids.append(self._import_power_entity)
        if self._export_power_entity:
            entity_ids.append(self._export_power_entity)
        return entity_ids

    def _subscribe_power_entities(self) -> None:
        """Sample power on every source entity state change."""
        self._unsubscribe_power_entities()
        entity_ids = self._power_entity_ids()
        if not entity_ids:
            return

        async def _on_state_change(_event: Event) -> None:
            await self._take_sample(dt_now())

        self._unsub_state_listener = async_track_state_change_event(
            self.hass,
            entity_ids,
            _on_state_change,
        )

    def _unsubscribe_power_entities(self) -> None:
        """Stop listening to power entity updates."""
        if self._unsub_state_listener:
            self._unsub_state_listener()
            self._unsub_state_listener = None

    def _get_current_components_kw(self) -> tuple[float | None, float | None, float | None, bool]:
        """Read current sensor values and compute import/export/combined in kW."""
        if is_combined_mode(self._mode):
            entity_id = self._signed_power_entity
            if not entity_id:
                return None, None, None, False
            state = self.hass.states.get(entity_id)
            if state is None:
                return None, None, None, False
            raw = _safe_float(state.state)
            if raw is None:
                return None, None, None, False
            unit = state.attributes.get("unit_of_measurement")  # type: ignore[assignment]
            kw = _normalize_to_kw(raw, unit=str(unit or ""), power_scaling_mode=self._power_unit_mode)
            if kw is None:
                return None, None, None, False
            import_kw = kw if kw > 0 else 0.0
            export_kw = (-kw) if kw < 0 else 0.0
            combined_kw = import_kw + export_kw
            return import_kw, export_kw, combined_kw, True

        # Split mode: import/export sensors represent magnitudes (typically >= 0)
        import_entity = self._import_power_entity
        export_entity = self._export_power_entity
        if not import_entity or not export_entity:
            return None, None, None, False

        s_in = self.hass.states.get(import_entity)
        s_out = self.hass.states.get(export_entity)
        if s_in is None or s_out is None:
            return None, None, None, False
        raw_in = _safe_float(s_in.state)
        raw_out = _safe_float(s_out.state)
        if raw_in is None or raw_out is None:
            return None, None, None, False

        unit_in = s_in.attributes.get("unit_of_measurement")  # type: ignore[assignment]
        unit_out = s_out.attributes.get("unit_of_measurement")  # type: ignore[assignment]

        kw_in = _normalize_to_kw(raw_in, unit=str(unit_in or ""), power_scaling_mode=self._power_unit_mode)
        kw_out = _normalize_to_kw(raw_out, unit=str(unit_out or ""), power_scaling_mode=self._power_unit_mode)
        if kw_in is None or kw_out is None:
            return None, None, None, False

        import_kw = kw_in if kw_in > 0 else 0.0
        export_kw = kw_out if kw_out > 0 else 0.0
        combined_kw = import_kw + export_kw
        return import_kw, export_kw, combined_kw, True

    def _accumulate_main_since_last_sample(self, run_at: datetime) -> None:
        """Add main-block interval energy (kWh) since the previous sample."""
        if not self._block_valid or not self._last_sample_time:
            return
        if not self._active_block_start or not self._active_block_end:
            return
        if run_at > self._active_block_end:
            run_at = self._active_block_end
        elapsed = (run_at - self._last_sample_time).total_seconds()
        if elapsed <= 0:
            return
        self._energy_import_kwh += _power_to_energy_kwh(self._last_import_kw, elapsed)
        self._energy_export_kwh += _power_to_energy_kwh(self._last_export_kw, elapsed)
        self._energy_combined_kwh += _power_to_energy_kwh(self._last_combined_kw, elapsed)

    def _accumulate_1m_since_last_sample(self, run_at: datetime) -> None:
        """Add 1-minute-block interval energy (kWh) since the previous sample."""
        if not self._1m_block_valid or not self._1m_last_sample_time:
            return
        if not self._1m_block_start or not self._1m_block_end:
            return
        if run_at > self._1m_block_end:
            run_at = self._1m_block_end
        elapsed = (run_at - self._1m_last_sample_time).total_seconds()
        if elapsed <= 0:
            return
        self._1m_energy_import_kwh += _power_to_energy_kwh(self._1m_last_import_kw, elapsed)
        self._1m_energy_export_kwh += _power_to_energy_kwh(self._1m_last_export_kw, elapsed)

    def _update_current_block_averages(self, run_at: datetime) -> None:
        """Update in-progress main-block averages after a sample."""
        if not self._active_block_start or not self._block_valid:
            self.data.current_import_block_avg_kw = None
            self.data.current_export_block_avg_kw = None
            self.data.current_combined_block_avg_kw = None
            return
        total_elapsed = (run_at - self._active_block_start).total_seconds()
        if total_elapsed <= 0:
            return
        self.data.current_import_block_avg_kw = _interval_demand_kw(
            self._energy_import_kwh, total_elapsed
        )
        self.data.current_export_block_avg_kw = _interval_demand_kw(
            self._energy_export_kwh, total_elapsed
        )
        self.data.current_combined_block_avg_kw = _interval_demand_kw(
            self._energy_combined_kwh, total_elapsed
        )

    async def _take_sample(self, run_at: datetime) -> bool:
        """Read power and accumulate energy for any active demand windows."""
        main_active = bool(
            self._active_block_start
            and self._active_block_end
            and run_at <= self._active_block_end
        )
        one_min_active = bool(
            self._1m_block_start
            and self._1m_block_end
            and run_at <= self._1m_block_end
        )
        if not main_active and not one_min_active:
            return False

        if main_active:
            self._accumulate_main_since_last_sample(run_at)
        if one_min_active:
            self._accumulate_1m_since_last_sample(run_at)

        import_kw, export_kw, combined_kw, source_ok = self._get_current_components_kw()
        if not source_ok:
            if main_active:
                self._block_valid = False
                self._last_sample_time = run_at
                self.data.current_import_block_avg_kw = None
                self.data.current_export_block_avg_kw = None
                self.data.current_combined_block_avg_kw = None
            if one_min_active:
                self._1m_block_valid = False
                self._1m_last_sample_time = run_at
            self.data.source_ok = False
            self.async_set_updated_data(self.data)
            return False

        self.data.source_ok = True
        if main_active:
            self._block_valid = True
            self._last_sample_time = run_at
            self._last_import_kw = float(import_kw or 0.0)
            self._last_export_kw = float(export_kw or 0.0)
            self._last_combined_kw = float(combined_kw or 0.0)
            self._update_current_block_averages(run_at)
        if one_min_active:
            self._1m_block_valid = True
            self._1m_last_sample_time = run_at
            self._1m_last_import_kw = float(import_kw or 0.0)
            self._1m_last_export_kw = float(export_kw or 0.0)

        self.async_set_updated_data(self.data)
        return True

    async def async_snapshot_now(self, reason: str) -> None:
        """Capture MDI values at the configured meter reading moment."""
        if not self.data:
            return

        # Only capture once per cycle for safety unless manual is pressed.
        if self.data.mdi_at_reading_timestamp is not None:
            # If user presses manual later in same cycle, allow update.
            if reason != "manual":
                return

        self.data.mdi_import_at_reading_kw = float(self.data.mdi_import_max_kw)
        self.data.mdi_export_at_reading_kw = float(self.data.mdi_export_max_kw)
        self.data.mdi_combined_at_reading_kw = float(self.data.mdi_combined_max_kw)
        self.data.mdi_at_reading_timestamp = dt_now()

        await self._async_save_storage()
        self.async_set_updated_data(self.data)

    async def _maybe_schedule_or_take_snapshot(self, initial: bool) -> None:
        """Schedule auto snapshot for the current cycle, or take it immediately."""
        # Cancel old schedule
        if self._unsub_reading_snapshot:
            self._unsub_reading_snapshot()
            self._unsub_reading_snapshot = None

        if not self._auto_snapshot:
            return

        current_local = dt_now()
        cycle_start = self._cycle_start_datetime(current_local)
        reading_dt = self._reading_datetime_for_cycle(cycle_start)

        if current_local > reading_dt and self.data.mdi_at_reading_timestamp is None:
            await self.async_snapshot_now(reason="auto_late_start")
            return

        # Schedule only if it hasn't happened yet
        if current_local <= reading_dt:
            async def _auto_cb(_now_dt: datetime) -> None:
                await self.async_snapshot_now(reason="auto")

            self._unsub_reading_snapshot = async_track_point_in_time(
                self.hass,
                _auto_cb,
                reading_dt,
            )

    async def _async_save_storage(self) -> None:
        """Persist important values across HA restarts."""
        payload: dict[str, Any] = {
            "cycle_id": self.data.cycle_id,
            "last_completed_import_kw": self.data.last_completed_import_kw,
            "last_completed_export_kw": self.data.last_completed_export_kw,
            "last_completed_combined_kw": self.data.last_completed_combined_kw,
            "last_completed_1min_import_kw": self.data.last_completed_1min_import_kw,
            "last_completed_1min_export_kw": self.data.last_completed_1min_export_kw,
            "mdi_import_max_kw": self.data.mdi_import_max_kw,
            "mdi_export_max_kw": self.data.mdi_export_max_kw,
            "mdi_combined_max_kw": self.data.mdi_combined_max_kw,
            "mdi_import_at_reading_kw": self.data.mdi_import_at_reading_kw,
            "mdi_export_at_reading_kw": self.data.mdi_export_at_reading_kw,
            "mdi_combined_at_reading_kw": self.data.mdi_combined_at_reading_kw,
            "mdi_at_reading_timestamp": self.data.mdi_at_reading_timestamp.isoformat() if self.data.mdi_at_reading_timestamp else None,
        }
        await self._store.async_save(payload)

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            # Python 3.11+ can parse ISO directly
            dt = datetime.fromisoformat(value)
            return dt
        except (TypeError, ValueError):
            return None
