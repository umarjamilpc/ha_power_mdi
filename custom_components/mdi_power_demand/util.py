"""Utility helpers for MDI Power Demand."""

from __future__ import annotations

from datetime import time as dt_time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_READING_TIME, DOMAIN

MANIFEST_VERSION = "0.1.8"


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return shared device info for MDI entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "MDI Power Demand",
        manufacturer="MDI Power Demand",
        model="Maximum Demand Indicator",
        sw_version=MANIFEST_VERSION,
        configuration_url="https://github.com/umarjamilpc/ha_power_mdi",
    )


def parse_time(value: Any) -> dt_time:
    """Parse a config value into a datetime.time."""
    if isinstance(value, dt_time):
        return value
    if isinstance(value, str):
        parts = value.split(":")
        if len(parts) < 2:
            raise ValueError(f"Invalid time value: {value}")
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        return dt_time(hour, minute, second)
    raise TypeError(f"Unsupported time value type: {type(value)!r}")


def serialize_time(value: Any) -> str:
    """Serialize a time value for config entry storage."""
    return parse_time(value).strftime("%H:%M:%S")


def normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize config dict for JSON-serializable config entry storage."""
    result = dict(data)
    if CONF_READING_TIME in result and result[CONF_READING_TIME] is not None:
        result[CONF_READING_TIME] = serialize_time(result[CONF_READING_TIME])
    return result
