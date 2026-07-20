"""Button platform for MDI Power Demand."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MdiCoordinator
from .util import device_info


class MdiCaptureReadingButton(CoordinatorEntity[MdiCoordinator], ButtonEntity):
    """Manual capture button for meter reading day."""

    _attr_has_entity_name = True
    _attr_name = "CAPTURE-MDI-READING"
    _attr_suggested_object_id = "capture_mdi_reading"

    def __init__(self, coordinator: MdiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_capture_mdi_reading"
        self._attr_device_info = device_info(coordinator.entry)

    async def async_press(self) -> None:
        await self.coordinator.async_snapshot_now(reason="manual")


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up button from config entry."""
    coordinator: MdiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MdiCaptureReadingButton(coordinator)])
