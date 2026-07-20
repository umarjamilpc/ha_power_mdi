"""Sensor platform for MDI Power Demand."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MdiCoordinator
from .util import device_info

# (metric_key, name, suggested_object_id)
SENSOR_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("last_completed_import_kw", "IMPORT-MDI", "import_mdi"),
    ("last_completed_export_kw", "EXPORT-MDI", "export_mdi"),
    ("mdi_import_max_kw", "IMPORT-MONTHLY-MDI", "import_monthly_mdi"),
    ("mdi_export_max_kw", "EXPORT-MONTHLY-MDI", "export_monthly_mdi"),
    ("mdi_import_at_reading_kw", "IMPORT-MONTHLY-MDI-AT-READING", "import_monthly_mdi_at_reading"),
    ("mdi_export_at_reading_kw", "EXPORT-MONTHLY-MDI-AT-READING", "export_monthly_mdi_at_reading"),
)


class MdiValueSensor(CoordinatorEntity[MdiCoordinator], SensorEntity):
    """A sensor backed by coordinator state."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = "kW"
    _attr_state_class = "measurement"

    def __init__(
        self,
        coordinator: MdiCoordinator,
        metric_key: str,
        name: str,
        object_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._metric_key = metric_key
        self._attr_name = name
        self._attr_suggested_object_id = object_id
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{object_id}"
        self._attr_device_info = device_info(coordinator.entry)

    @property
    def native_value(self) -> float | None:
        value = getattr(self.coordinator.data, self._metric_key, None)
        if value is None:
            return None
        return float(value)

    @property
    def available(self) -> bool:
        if getattr(self.coordinator.data, self._metric_key, None) is not None:
            return True
        return bool(self.coordinator.data.source_ok)


async def async_setup_entry(hass, entry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensors from config entry."""
    coordinator: MdiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MdiValueSensor(coordinator, metric_key, name, object_id)
            for metric_key, name, object_id in SENSOR_DEFINITIONS
        ]
    )
