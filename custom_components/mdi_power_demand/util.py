"""Utility helpers for MDI Power Demand."""

from __future__ import annotations

from datetime import time as dt_time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    BLOCK_DURATION_OPTIONS,
    CONF_BLOCK_DURATION_MINUTES,
    CONF_MODE,
    CONF_POWER_UNIT,
    CONF_READING_TIME,
    CONF_SOURCE_POWER_UNIT,
    DEFAULT_BLOCK_DURATION_MINUTES,
    DEFAULT_POWER_UNIT,
    DEFAULT_SOURCE_POWER_UNIT,
    DOMAIN,
    MODE_COMBINED,
    MODE_SIGNED,
    MODE_SPLIT,
    POWER_UNIT_KW,
    POWER_UNIT_W,
)

MANIFEST_VERSION = "0.2.6"


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
    if CONF_MODE in result:
        mode = str(result[CONF_MODE])
        if mode == MODE_SIGNED:
            mode = MODE_COMBINED
        if mode not in {MODE_COMBINED, MODE_SPLIT}:
            mode = MODE_COMBINED
        result[CONF_MODE] = mode
    if CONF_POWER_UNIT in result:
        unit = str(result[CONF_POWER_UNIT])
        if unit == "auto":
            unit = DEFAULT_POWER_UNIT
        if unit not in {POWER_UNIT_W, POWER_UNIT_KW}:
            unit = DEFAULT_POWER_UNIT
        result[CONF_POWER_UNIT] = unit
    if CONF_SOURCE_POWER_UNIT in result:
        source_unit = str(result[CONF_SOURCE_POWER_UNIT])
        if source_unit == "auto":
            source_unit = DEFAULT_SOURCE_POWER_UNIT
        if source_unit not in {POWER_UNIT_W, POWER_UNIT_KW}:
            source_unit = DEFAULT_SOURCE_POWER_UNIT
        result[CONF_SOURCE_POWER_UNIT] = source_unit
    elif CONF_POWER_UNIT in result:
        # Existing installs: default source to Watts (typical meter sensors)
        result[CONF_SOURCE_POWER_UNIT] = DEFAULT_SOURCE_POWER_UNIT
    return result
