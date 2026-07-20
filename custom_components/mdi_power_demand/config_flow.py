"""Config flow for MDI Power Demand."""

from __future__ import annotations

import logging
from datetime import time as dt_time

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_AUTO_SNAPSHOT,
    CONF_EXPORT_POWER_ENTITY,
    CONF_ENTITY_ID_BASE,
    CONF_IMPORT_POWER_ENTITY,
    CONF_MODE,
    CONF_NAME,
    CONF_POWER_UNIT,
    CONF_READING_DAY,
    CONF_READING_TIME,
    CONF_RESET_DAY,
    CONF_SIGNED_POWER_ENTITY,
    DOMAIN,
    MODE_SIGNED,
    MODE_SPLIT,
    POWER_UNIT_AUTO,
    POWER_UNIT_KW,
    POWER_UNIT_W,
)

_LOGGER = logging.getLogger(__name__)


class MdiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MDI Power Demand."""

    VERSION = 1

    def __init__(self) -> None:
        self._context: dict[str, object] = {}

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return MdiOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """First step: choose mode and general timing settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mode = user_input[CONF_MODE]
            name = user_input[CONF_NAME].strip()

            reset_day = int(user_input[CONF_RESET_DAY])
            reading_day = int(user_input[CONF_READING_DAY])
            if reading_day < reset_day:
                errors[CONF_READING_DAY] = "reading_day_before_reset_day"
            else:
                self._context.update(user_input)
                self._context[CONF_NAME] = name

                if mode == MODE_SIGNED:
                    return await self.async_step_signed()
                return await self.async_step_split()

        if user_input is None:
            # Provide defaults when starting the flow
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="MDI Power Demand"): cv.string,
                vol.Required(
                    CONF_MODE,
                    default=MODE_SIGNED,
                ): vol.In([MODE_SIGNED, MODE_SPLIT]),
                vol.Required(
                    CONF_POWER_UNIT,
                    default=POWER_UNIT_AUTO,
                ): vol.In([POWER_UNIT_AUTO, POWER_UNIT_W, POWER_UNIT_KW]),
                vol.Required(CONF_RESET_DAY, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=28)),
                vol.Required(CONF_READING_DAY, default=14): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=28)
                ),
                vol.Required(CONF_AUTO_SNAPSHOT, default=False): cv.boolean,
                vol.Required(CONF_READING_TIME, default=dt_time(18, 0, 0)): cv.time,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_signed(self, user_input=None):
        """Signed power mode: one sensor that reports positive (import) and negative (export) in W or kW."""
        errors: dict[str, str] = {}
        if user_input is not None:
            signed_power_entity = user_input[CONF_SIGNED_POWER_ENTITY]
            if not self._entity_exists(signed_power_entity):
                errors[CONF_SIGNED_POWER_ENTITY] = "entity_not_found"
            else:
                # Derive entity id base by default
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or self._derive_entity_id_base(
                    signed_power_entity
                )
                self._context[CONF_SIGNED_POWER_ENTITY] = signed_power_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base

                return self.async_create_entry(title=self._context[CONF_NAME], data=self._context)

        schema = vol.Schema(
            {
                vol.Required(CONF_SIGNED_POWER_ENTITY): cv.entity_id,
                vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
            }
        )

        return self.async_show_form(step_id="signed", data_schema=schema, errors=errors)

    async def async_step_split(self, user_input=None):
        """Split power mode: separate sensors for import and export magnitudes."""
        errors: dict[str, str] = {}
        if user_input is not None:
            import_entity = user_input[CONF_IMPORT_POWER_ENTITY]
            export_entity = user_input[CONF_EXPORT_POWER_ENTITY]
            if not self._entity_exists(import_entity):
                errors[CONF_IMPORT_POWER_ENTITY] = "entity_not_found"
            elif not self._entity_exists(export_entity):
                errors[CONF_EXPORT_POWER_ENTITY] = "entity_not_found"
            else:
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or self._derive_entity_id_base(
                    import_entity
                )
                self._context[CONF_IMPORT_POWER_ENTITY] = import_entity
                self._context[CONF_EXPORT_POWER_ENTITY] = export_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base

                return self.async_create_entry(title=self._context[CONF_NAME], data=self._context)

        schema = vol.Schema(
            {
                vol.Required(CONF_IMPORT_POWER_ENTITY): cv.entity_id,
                vol.Required(CONF_EXPORT_POWER_ENTITY): cv.entity_id,
                vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
            }
        )

        return self.async_show_form(step_id="split", data_schema=schema, errors=errors)

    def _derive_entity_id_base(self, entity_id: str) -> str:
        """Derive a stable entity-id base from the chosen power sensor."""
        # entity_id looks like sensor.grid_main_smart_energy_meter...
        base = entity_id.split(".", 1)[-1]
        # Only keep safe characters for entity ids
        base = base.replace("-", "_").replace(" ", "_")
        return base

    def _entity_exists(self, entity_id: str) -> bool:
        """Check if the entity exists (domain is validated by entity_id format)."""
        hass: HomeAssistant = self.hass  # type: ignore[assignment]
        state = hass.states.get(entity_id)
        return state is not None


class MdiOptionsFlow(config_entries.OptionsFlow):
    """Options flow for MDI Power Demand."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._context: dict[str, object] = {}

    async def async_step_init(self, user_input=None):
        """Edit general MDI configuration after install."""
        errors: dict[str, str] = {}

        current = {**self.config_entry.data, **self.config_entry.options}
        current.setdefault(CONF_NAME, "MDI Power Demand")
        current.setdefault(CONF_MODE, MODE_SIGNED)
        current.setdefault(CONF_POWER_UNIT, POWER_UNIT_AUTO)
        current.setdefault(CONF_RESET_DAY, 1)
        current.setdefault(CONF_READING_DAY, 14)
        current.setdefault(CONF_AUTO_SNAPSHOT, False)
        current.setdefault(CONF_READING_TIME, dt_time(18, 0, 0))

        if user_input is not None:
            reset_day = int(user_input[CONF_RESET_DAY])
            reading_day = int(user_input[CONF_READING_DAY])
            if reading_day < reset_day:
                errors[CONF_READING_DAY] = "reading_day_before_reset_day"
            else:
                self._context.update(user_input)
                mode = str(user_input[CONF_MODE])
                if mode == MODE_SIGNED:
                    return await self.async_step_signed()
                return await self.async_step_split()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=str(current.get(CONF_NAME, "MDI Power Demand"))): cv.string,
                vol.Required(CONF_MODE, default=str(current.get(CONF_MODE, MODE_SIGNED))): vol.In(
                    [MODE_SIGNED, MODE_SPLIT]
                ),
                vol.Required(CONF_POWER_UNIT, default=str(current.get(CONF_POWER_UNIT, POWER_UNIT_AUTO))): vol.In(
                    [POWER_UNIT_AUTO, POWER_UNIT_W, POWER_UNIT_KW]
                ),
                vol.Required(CONF_RESET_DAY, default=int(current.get(CONF_RESET_DAY, 1))): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=28)
                ),
                vol.Required(CONF_READING_DAY, default=int(current.get(CONF_READING_DAY, 14))): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=28)
                ),
                vol.Required(
                    CONF_AUTO_SNAPSHOT,
                    default=bool(current.get(CONF_AUTO_SNAPSHOT, False)),
                ): cv.boolean,
                vol.Required(
                    CONF_READING_TIME,
                    default=current.get(CONF_READING_TIME, dt_time(18, 0, 0)),
                ): cv.time,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_signed(self, user_input=None):
        """Edit the signed power source."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        default_entity = str(current.get(CONF_SIGNED_POWER_ENTITY, ""))

        if user_input is not None:
            signed_power_entity = user_input[CONF_SIGNED_POWER_ENTITY]
            hass = self.hass
            if not self._entity_exists(hass, signed_power_entity):
                errors[CONF_SIGNED_POWER_ENTITY] = "entity_not_found"
            else:
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE)
                if not entity_id_base:
                    entity_id_base = self._derive_entity_id_base(signed_power_entity)
                self._context[CONF_SIGNED_POWER_ENTITY] = signed_power_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                # Clear split sensors to avoid confusion (optional; mode gate makes them unused)
                self._context.pop(CONF_IMPORT_POWER_ENTITY, None)
                self._context.pop(CONF_EXPORT_POWER_ENTITY, None)
                return self.async_create_entry(title="", data=self._context)

        schema = vol.Schema(
            {
                vol.Required(CONF_SIGNED_POWER_ENTITY, default=default_entity): cv.entity_id,
                vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
            }
        )
        return self.async_show_form(step_id="signed", data_schema=schema, errors=errors)

    async def async_step_split(self, user_input=None):
        """Edit the split import/export power sources."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        default_in = str(current.get(CONF_IMPORT_POWER_ENTITY, ""))
        default_out = str(current.get(CONF_EXPORT_POWER_ENTITY, ""))

        if user_input is not None:
            import_power_entity = user_input[CONF_IMPORT_POWER_ENTITY]
            export_power_entity = user_input[CONF_EXPORT_POWER_ENTITY]
            hass = self.hass

            if not self._entity_exists(hass, import_power_entity):
                errors[CONF_IMPORT_POWER_ENTITY] = "entity_not_found"
            elif not self._entity_exists(hass, export_power_entity):
                errors[CONF_EXPORT_POWER_ENTITY] = "entity_not_found"
            else:
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE)
                if not entity_id_base:
                    entity_id_base = self._derive_entity_id_base(import_power_entity)
                self._context[CONF_IMPORT_POWER_ENTITY] = import_power_entity
                self._context[CONF_EXPORT_POWER_ENTITY] = export_power_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                self._context.pop(CONF_SIGNED_POWER_ENTITY, None)
                return self.async_create_entry(title="", data=self._context)

        schema = vol.Schema(
            {
                vol.Required(CONF_IMPORT_POWER_ENTITY, default=default_in): cv.entity_id,
                vol.Required(CONF_EXPORT_POWER_ENTITY, default=default_out): cv.entity_id,
                vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
            }
        )
        return self.async_show_form(step_id="split", data_schema=schema, errors=errors)

    @staticmethod
    def _derive_entity_id_base(entity_id: str) -> str:
        """Derive a stable entity-id base from the chosen power sensor."""
        base = entity_id.split(".", 1)[-1]
        base = base.replace("-", "_").replace(" ", "_")
        return base

    @staticmethod
    def _entity_exists(hass, entity_id: str) -> bool:
        """Check if an entity exists in Home Assistant state machine."""
        return hass.states.get(entity_id) is not None

