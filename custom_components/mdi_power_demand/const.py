"""Constants for the MDI Power Demand integration."""

from __future__ import annotations

DOMAIN = "mdi_power_demand"

# Config keys
CONF_NAME = "name"
CONF_MODE = "mode"
CONF_POWER_UNIT = "power_unit"
CONF_SOURCE_POWER_UNIT = "source_power_unit"

# Power source modes (UI: Combine / Split)
MODE_COMBINED = "combined"
MODE_SPLIT = "split"
# Legacy alias kept for existing config entries
MODE_SIGNED = "signed"

CONF_SIGNED_POWER_ENTITY = "signed_power_entity"
CONF_IMPORT_POWER_ENTITY = "import_power_entity"
CONF_EXPORT_POWER_ENTITY = "export_power_entity"

POWER_UNIT_W = "W"
POWER_UNIT_KW = "kW"
# Legacy value migrated away
POWER_UNIT_AUTO = "auto"
DEFAULT_POWER_UNIT = POWER_UNIT_KW
DEFAULT_SOURCE_POWER_UNIT = POWER_UNIT_W
POWER_UNIT_OPTIONS = (POWER_UNIT_W, POWER_UNIT_KW)

CONF_RESET_DAY = "reset_day"
CONF_READING_DAY = "reading_day"
CONF_READING_TIME = "reading_time"
CONF_AUTO_SNAPSHOT = "auto_snapshot"
CONF_BLOCK_DURATION_MINUTES = "block_duration_minutes"

DEFAULT_BLOCK_DURATION_MINUTES = 30
BLOCK_DURATION_OPTIONS = (15, 30, 60)

# Fixed companion window for 1-minute demand entities
ONE_MINUTE_BLOCK_SECONDS = 60

# Entity id base used to build stable entity naming
CONF_ENTITY_ID_BASE = "entity_id_base"

# Components we calculate
COMP_IMPORT = "import"
COMP_EXPORT = "export"
COMP_COMBINED = "combined"

# Storage
STORAGE_VERSION = 1


def is_combined_mode(mode: str | None) -> bool:
    """Return True for combined/signed single-sensor mode."""
    return mode in {MODE_COMBINED, MODE_SIGNED}
