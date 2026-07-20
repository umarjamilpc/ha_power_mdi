"""Constants for the MDI Power Demand integration."""

from __future__ import annotations

DOMAIN = "mdi_power_demand"

# Config keys
CONF_NAME = "name"
CONF_MODE = "mode"
CONF_POWER_UNIT = "power_unit"

MODE_SIGNED = "signed"
MODE_SPLIT = "split"

CONF_SIGNED_POWER_ENTITY = "signed_power_entity"
CONF_IMPORT_POWER_ENTITY = "import_power_entity"
CONF_EXPORT_POWER_ENTITY = "export_power_entity"

POWER_UNIT_AUTO = "auto"
POWER_UNIT_W = "W"
POWER_UNIT_KW = "kW"

CONF_RESET_DAY = "reset_day"
CONF_READING_DAY = "reading_day"
CONF_READING_TIME = "reading_time"
CONF_AUTO_SNAPSHOT = "auto_snapshot"
CONF_BLOCK_DURATION_MINUTES = "block_duration_minutes"

DEFAULT_BLOCK_DURATION_MINUTES = 30
BLOCK_DURATION_OPTIONS = (15, 30, 60)

# Entity id base used to build stable entity naming
CONF_ENTITY_ID_BASE = "entity_id_base"

# Components we calculate
COMP_IMPORT = "import"
COMP_EXPORT = "export"
COMP_COMBINED = "combined"

# Storage
STORAGE_VERSION = 1
