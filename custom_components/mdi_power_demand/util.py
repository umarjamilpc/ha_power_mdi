"""Utility helpers for MDI Power Demand."""

from __future__ import annotations

from datetime import time as dt_time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    BLOCK_DURATION_OPTIONS,
    CONF_BLOCK_DURATION_MINUTES,
    CONF_READING_TIME,
    DEFAULT_BLOCK_DURATION_MINUTES,
    DOMAIN,
)

MANIFEST_VERSION = "0.2.0"


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
    if CONF_BLOCK_DURATION_MINUTES in result:
        duration = int(result[CONF_BLOCK_DURATION_MINUTES])
        if duration not in BLOCK_DURATION_OPTIONS:
            duration = DEFAULT_BLOCK_DURATION_MINUTES
        result[CONF_BLOCK_DURATION_MINUTES] = duration
    return result
