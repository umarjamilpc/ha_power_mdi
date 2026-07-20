"""MDI Power Demand integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MdiCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MDI Power Demand from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if entry.entry_id in hass.data[DOMAIN]:
        return True

    coordinator = MdiCoordinator(hass, entry)
    await coordinator.async_initialize()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    _LOGGER.debug("MDI Power Demand set up for %s", entry.entry_id)
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates without uninstalling."""
    coordinator_obj: MdiCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator_obj is None:
        return
    await coordinator_obj.async_handle_update(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: MdiCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if coordinator is not None:
        await coordinator.async_shutdown()
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration."""
    return True

