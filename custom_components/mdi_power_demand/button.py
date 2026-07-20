"""Button platform for MDI Power Demand."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTITY_ID_BASE, DOMAIN
from .coordinator import MdiCoordinator


class MdiCaptureReadingButton(CoordinatorEntity, ButtonEntity):
    """Manual capture button for meter reading day."""

    def __init__(self, coordinator: MdiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_class = None
        self._attr_unique_id = f"{coordinator.entry.entry_id}_capture_reading"

    @property
    def name(self) -> str | None:
        base = str(self.coordinator.config.get(CONF_ENTITY_ID_BASE, "MDI"))
        return f"{base} Capture Reading"

    async def async_press(self) -> None:
        await self.coordinator.async_snapshot_now(reason="manual")


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up button from config entry."""
    coordinator: MdiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MdiCaptureReadingButton(coordinator)])

