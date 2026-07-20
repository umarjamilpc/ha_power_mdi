"""Sensor platform for MDI Power Demand."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITY_ID_BASE, DOMAIN
from .coordinator import MdiCoordinator


class MdiValueSensor(CoordinatorEntity, SensorEntity):
    """A sensor backed by coordinator state."""

    def __init__(self, coordinator: MdiCoordinator, metric_key: str, name_suffix: str) -> None:
        super().__init__(coordinator)
        self._metric_key = metric_key
        self._name_suffix = name_suffix

        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = "measurement"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{metric_key}"

    @property
    def name(self) -> str | None:
        base = str(self.coordinator.config.get(CONF_ENTITY_ID_BASE, "MDI"))
        return f"{base} {self._name_suffix}"

    @property
    def native_value(self) -> float | None:
        value = getattr(self.coordinator.data, self._metric_key, None)
        if value is None:
            return None
        return float(value)

    @property
    def available(self) -> bool:
        # Keep it available if we have a value; otherwise fall back to source_ok.
        if getattr(self.coordinator.data, self._metric_key, None) is not None:
            return True
        return bool(self.coordinator.data.source_ok)


async def async_setup_entry(hass, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensors from config entry."""
    coordinator: MdiCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        MdiValueSensor(coordinator, "last_completed_import_kw", "Import 30-min avg"),
        MdiValueSensor(coordinator, "last_completed_export_kw", "Export 30-min avg"),
        MdiValueSensor(coordinator, "last_completed_combined_kw", "Combined 30-min avg"),
        MdiValueSensor(coordinator, "mdi_import_max_kw", "Import MDI (monthly max)"),
        MdiValueSensor(coordinator, "mdi_export_max_kw", "Export MDI (monthly max)"),
        MdiValueSensor(coordinator, "mdi_combined_max_kw", "Combined MDI (monthly max)"),
        MdiValueSensor(coordinator, "mdi_import_at_reading_kw", "Import MDI at reading"),
        MdiValueSensor(coordinator, "mdi_export_at_reading_kw", "Export MDI at reading"),
        MdiValueSensor(coordinator, "mdi_combined_at_reading_kw", "Combined MDI at reading"),
    ]

    async_add_entities(entities)

