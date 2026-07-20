"""Config flow for MDI Power Demand."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
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
    DEFAULT_POWER_UNIT,
    DOMAIN,
    MODE_COMBINED,
    MODE_SIGNED,
    MODE_SPLIT,
    POWER_UNIT_KW,
    POWER_UNIT_W,
    is_combined_mode,
)
from .util import normalize_config, parse_time

_LOGGER = logging.getLogger(__name__)

DEFAULT_READING_TIME = "18:00:00"

_SENSOR_ENTITY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor"),
)

_MODE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=MODE_COMBINED, label="Combine"),
            selector.SelectOptionDict(value=MODE_SPLIT, label="Split"),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    ),
)


_POWER_UNIT_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=POWER_UNIT_W, label="Watts"),
            selector.SelectOptionDict(value=POWER_UNIT_KW, label="Kilowatts"),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    ),
)


def _power_unit_default(defaults: dict[str, Any]) -> str:
    """Return display power unit, migrating legacy auto → kW."""
    value = str(defaults.get(CONF_POWER_UNIT, DEFAULT_POWER_UNIT))
    if value == "auto":
        return DEFAULT_POWER_UNIT
    if value not in {POWER_UNIT_W, POWER_UNIT_KW}:
        return DEFAULT_POWER_UNIT
    return value


def _reading_time_default(defaults: dict[str, Any]) -> str:
    """Return a string default suitable for TimeSelector."""
    reading_time_default = defaults.get(CONF_READING_TIME, DEFAULT_READING_TIME)
    if isinstance(reading_time_default, str):
        return reading_time_default
    return parse_time(reading_time_default).strftime("%H:%M:%S")


def _block_duration_default(defaults: dict[str, Any]) -> str:
    """Return a string default suitable for the block-duration SelectSelector."""
    value = defaults.get(CONF_BLOCK_DURATION_MINUTES, DEFAULT_BLOCK_DURATION_MINUTES)
    try:
        duration = int(value)
    except (TypeError, ValueError):
        duration = DEFAULT_BLOCK_DURATION_MINUTES
    if duration not in (15, 30, 60):
        duration = DEFAULT_BLOCK_DURATION_MINUTES
    return str(duration)


def _mode_default(defaults: dict[str, Any]) -> str:
    """Return Combine/Split mode default, migrating legacy signed → combined."""
    mode = str(defaults.get(CONF_MODE, MODE_COMBINED))
    if mode == MODE_SIGNED:
        return MODE_COMBINED
    if mode not in {MODE_COMBINED, MODE_SPLIT}:
        return MODE_COMBINED
    return mode


def _general_settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the shared general settings schema using HA selectors."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=str(defaults.get(CONF_NAME, "MDI Power Demand")),
            ): selector.TextSelector(),
            vol.Required(
                CONF_MODE,
                default=_mode_default(defaults),
            ): _MODE_SELECTOR,
            vol.Required(
                CONF_POWER_UNIT,
                default=_power_unit_default(defaults),
            ): _POWER_UNIT_SELECTOR,
            vol.Required(
                CONF_RESET_DAY,
                default=int(defaults.get(CONF_RESET_DAY, 1)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=28,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Required(
                CONF_READING_DAY,
                default=int(defaults.get(CONF_READING_DAY, 14)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=28,
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Required(
                CONF_AUTO_SNAPSHOT,
                default=bool(defaults.get(CONF_AUTO_SNAPSHOT, False)),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_BLOCK_DURATION_MINUTES,
                default=_block_duration_default(defaults),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["15", "30", "60"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Required(
                CONF_READING_TIME,
                default=_reading_time_default(defaults),
            ): selector.TimeSelector(),
        }
    )


def _entity_field(key: str, suggested_value: str | None) -> vol.Required:
    """Build an entity selector field with optional default."""
    if suggested_value:
        return vol.Required(key, default=suggested_value)
    return vol.Required(key)


def _current_config(entry: config_entries.ConfigEntry) -> dict[str, Any]:
    """Merge config entry data and options."""
    return {**entry.data, **entry.options}


class MdiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MDI Power Demand."""

    VERSION = 1

    def __init__(self) -> None:
        self._context: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow.

        Do not pass config_entry into OptionsFlow — HA 2025.12+ injects it.
        """
        return MdiOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """First step: choose mode and general timing settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                reset_day = int(user_input[CONF_RESET_DAY])
                reading_day = int(user_input[CONF_READING_DAY])
                if reading_day < reset_day:
                    errors[CONF_READING_DAY] = "reading_day_before_reset_day"
                else:
                    self._context.update(normalize_config(user_input))
                    self._context[CONF_NAME] = str(user_input[CONF_NAME]).strip()

                    if is_combined_mode(user_input[CONF_MODE]):
                        return await self.async_step_combine()
                    return await self.async_step_split()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in MDI config user step")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_general_settings_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_combine(self, user_input: dict[str, Any] | None = None):
        """Combine mode: one sensor with positive import and negative export."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                signed_power_entity = user_input[CONF_SIGNED_POWER_ENTITY]
                if not _entity_exists(self.hass, signed_power_entity):
                    errors[CONF_SIGNED_POWER_ENTITY] = "entity_not_found"
                else:
                    entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                        signed_power_entity
                    )
                    self._context[CONF_MODE] = MODE_COMBINED
                    self._context[CONF_SIGNED_POWER_ENTITY] = signed_power_entity
                    self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                    self._context.pop(CONF_IMPORT_POWER_ENTITY, None)
                    self._context.pop(CONF_EXPORT_POWER_ENTITY, None)

                    return self.async_create_entry(
                        title=str(self._context[CONF_NAME]),
                        data=normalize_config(self._context),
                    )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in MDI config combine step")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="combine",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SIGNED_POWER_ENTITY): _SENSOR_ENTITY_SELECTOR,
                    vol.Optional(CONF_ENTITY_ID_BASE): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_split(self, user_input: dict[str, Any] | None = None):
        """Split power mode: separate import and export sensors."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                import_entity = user_input[CONF_IMPORT_POWER_ENTITY]
                export_entity = user_input[CONF_EXPORT_POWER_ENTITY]
                if not _entity_exists(self.hass, import_entity):
                    errors[CONF_IMPORT_POWER_ENTITY] = "entity_not_found"
                elif not _entity_exists(self.hass, export_entity):
                    errors[CONF_EXPORT_POWER_ENTITY] = "entity_not_found"
                else:
                    entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                        import_entity
                    )
                    self._context[CONF_MODE] = MODE_SPLIT
                    self._context[CONF_IMPORT_POWER_ENTITY] = import_entity
                    self._context[CONF_EXPORT_POWER_ENTITY] = export_entity
                    self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                    self._context.pop(CONF_SIGNED_POWER_ENTITY, None)

                    return self.async_create_entry(
                        title=str(self._context[CONF_NAME]),
                        data=normalize_config(self._context),
                    )
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in MDI config split step")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="split",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IMPORT_POWER_ENTITY): _SENSOR_ENTITY_SELECTOR,
                    vol.Required(CONF_EXPORT_POWER_ENTITY): _SENSOR_ENTITY_SELECTOR,
                    vol.Optional(CONF_ENTITY_ID_BASE): selector.TextSelector(),
                }
            ),
            errors=errors,
        )


class MdiOptionsFlow(config_entries.OptionsFlow):
    """Options flow for MDI Power Demand.

    On HA 2025.12+/2026.x, ``self.config_entry`` is injected by the framework.
    Do not assign it in ``__init__``.
    """

    def __init__(self) -> None:
        self._context: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Edit general MDI configuration after install."""
        errors: dict[str, str] = {}
        current = _current_config(self.config_entry)

        if user_input is not None:
            try:
                reset_day = int(user_input[CONF_RESET_DAY])
                reading_day = int(user_input[CONF_READING_DAY])
                if reading_day < reset_day:
                    errors[CONF_READING_DAY] = "reading_day_before_reset_day"
                else:
                    self._context.update(normalize_config(user_input))
                    if is_combined_mode(user_input[CONF_MODE]):
                        return await self.async_step_combine()
                    return await self.async_step_split()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in MDI options init step")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="init",
            data_schema=_general_settings_schema(user_input or current),
            errors=errors,
        )

    async def async_step_combine(self, user_input: dict[str, Any] | None = None):
        """Edit the combined power source."""
        errors: dict[str, str] = {}
        current = _current_config(self.config_entry)
        default_entity = current.get(CONF_SIGNED_POWER_ENTITY)

        if user_input is not None:
            try:
                signed_power_entity = user_input[CONF_SIGNED_POWER_ENTITY]
                if not _entity_exists(self.hass, signed_power_entity):
                    errors[CONF_SIGNED_POWER_ENTITY] = "entity_not_found"
                else:
                    entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                        signed_power_entity
                    )
                    self._context[CONF_MODE] = MODE_COMBINED
                    self._context[CONF_SIGNED_POWER_ENTITY] = signed_power_entity
                    self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                    self._context.pop(CONF_IMPORT_POWER_ENTITY, None)
                    self._context.pop(CONF_EXPORT_POWER_ENTITY, None)
                    return self.async_create_entry(title="", data=normalize_config(self._context))
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in MDI options combine step")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="combine",
            data_schema=vol.Schema(
                {
                    _entity_field(CONF_SIGNED_POWER_ENTITY, default_entity): _SENSOR_ENTITY_SELECTOR,
                    vol.Optional(CONF_ENTITY_ID_BASE): selector.TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_split(self, user_input: dict[str, Any] | None = None):
        """Edit split import/export power sources."""
        errors: dict[str, str] = {}
        current = _current_config(self.config_entry)
        default_in = current.get(CONF_IMPORT_POWER_ENTITY)
        default_out = current.get(CONF_EXPORT_POWER_ENTITY)

        if user_input is not None:
            try:
                import_power_entity = user_input[CONF_IMPORT_POWER_ENTITY]
                export_power_entity = user_input[CONF_EXPORT_POWER_ENTITY]

                if not _entity_exists(self.hass, import_power_entity):
                    errors[CONF_IMPORT_POWER_ENTITY] = "entity_not_found"
                elif not _entity_exists(self.hass, export_power_entity):
                    errors[CONF_EXPORT_POWER_ENTITY] = "entity_not_found"
                else:
                    entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                        import_power_entity
                    )
                    self._context[CONF_MODE] = MODE_SPLIT
                    self._context[CONF_IMPORT_POWER_ENTITY] = import_power_entity
                    self._context[CONF_EXPORT_POWER_ENTITY] = export_power_entity
                    self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                    self._context.pop(CONF_SIGNED_POWER_ENTITY, None)
                    return self.async_create_entry(title="", data=normalize_config(self._context))
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in MDI options split step")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="split",
            data_schema=vol.Schema(
                {
                    _entity_field(CONF_IMPORT_POWER_ENTITY, default_in): _SENSOR_ENTITY_SELECTOR,
                    _entity_field(CONF_EXPORT_POWER_ENTITY, default_out): _SENSOR_ENTITY_SELECTOR,
                    vol.Optional(CONF_ENTITY_ID_BASE): selector.TextSelector(),
                }
            ),
            errors=errors,
        )


def _derive_entity_id_base(entity_id: str) -> str:
    """Derive a stable entity-id base from the chosen power sensor."""
    base = entity_id.split(".", 1)[-1]
    return base.replace("-", "_").replace(" ", "_")


def _entity_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if the entity exists in Home Assistant state machine."""
    return hass.states.get(entity_id) is not None
