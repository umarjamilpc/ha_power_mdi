"""Config flow for MDI Power Demand."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_SNAPSHOT,
    CONF_ENTITY_ID_BASE,
    CONF_EXPORT_POWER_ENTITY,
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
from .util import normalize_config, parse_time

_LOGGER = logging.getLogger(__name__)

DEFAULT_READING_TIME = "18:00:00"


def _mode_selector(default: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=MODE_SIGNED, label="Signed power (import + / export -)"),
                selector.SelectOptionDict(value=MODE_SPLIT, label="Split import and export sensors"),
            ],
        )
    )


def _power_unit_selector(default: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=POWER_UNIT_AUTO, label="Auto detect"),
                selector.SelectOptionDict(value=POWER_UNIT_W, label="Watts (W)"),
                selector.SelectOptionDict(value=POWER_UNIT_KW, label="Kilowatts (kW)"),
            ],
        )
    )


def _general_settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the shared general settings schema."""
    reading_time_default = defaults.get(CONF_READING_TIME, DEFAULT_READING_TIME)
    if not isinstance(reading_time_default, str):
        reading_time_default = parse_time(reading_time_default).strftime("%H:%M:%S")

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=str(defaults.get(CONF_NAME, "MDI Power Demand"))): cv.string,
            vol.Required(CONF_MODE, default=str(defaults.get(CONF_MODE, MODE_SIGNED))): _mode_selector(
                str(defaults.get(CONF_MODE, MODE_SIGNED))
            ),
            vol.Required(
                CONF_POWER_UNIT,
                default=str(defaults.get(CONF_POWER_UNIT, POWER_UNIT_AUTO)),
            ): _power_unit_selector(str(defaults.get(CONF_POWER_UNIT, POWER_UNIT_AUTO))),
            vol.Required(
                CONF_RESET_DAY,
                default=int(defaults.get(CONF_RESET_DAY, 1)),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=28)),
            vol.Required(
                CONF_READING_DAY,
                default=int(defaults.get(CONF_READING_DAY, 14)),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=28)),
            vol.Required(
                CONF_AUTO_SNAPSHOT,
                default=bool(defaults.get(CONF_AUTO_SNAPSHOT, False)),
            ): cv.boolean,
            vol.Required(CONF_READING_TIME, default=reading_time_default): cv.time,
        }
    )


class MdiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MDI Power Demand."""

    VERSION = 1

    def __init__(self) -> None:
        self._context: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return MdiOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """First step: choose mode and general timing settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reset_day = int(user_input[CONF_RESET_DAY])
            reading_day = int(user_input[CONF_READING_DAY])
            if reading_day < reset_day:
                errors[CONF_READING_DAY] = "reading_day_before_reset_day"
            else:
                self._context.update(normalize_config(user_input))
                self._context[CONF_NAME] = user_input[CONF_NAME].strip()

                if user_input[CONF_MODE] == MODE_SIGNED:
                    return await self.async_step_signed()
                return await self.async_step_split()

        return self.async_show_form(
            step_id="user",
            data_schema=_general_settings_schema({}),
            errors=errors,
        )

    async def async_step_signed(self, user_input: dict[str, Any] | None = None):
        """Signed power mode: one sensor with positive import and negative export."""
        errors: dict[str, str] = {}

        if user_input is not None:
            signed_power_entity = user_input[CONF_SIGNED_POWER_ENTITY]
            if not _entity_exists(self.hass, signed_power_entity):
                errors[CONF_SIGNED_POWER_ENTITY] = "entity_not_found"
            else:
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                    signed_power_entity
                )
                self._context[CONF_SIGNED_POWER_ENTITY] = signed_power_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                self._context.pop(CONF_IMPORT_POWER_ENTITY, None)
                self._context.pop(CONF_EXPORT_POWER_ENTITY, None)

                return self.async_create_entry(
                    title=str(self._context[CONF_NAME]),
                    data=normalize_config(self._context),
                )

        return self.async_show_form(
            step_id="signed",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SIGNED_POWER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_split(self, user_input: dict[str, Any] | None = None):
        """Split power mode: separate import and export sensors."""
        errors: dict[str, str] = {}

        if user_input is not None:
            import_entity = user_input[CONF_IMPORT_POWER_ENTITY]
            export_entity = user_input[CONF_EXPORT_POWER_ENTITY]
            if not _entity_exists(self.hass, import_entity):
                errors[CONF_IMPORT_POWER_ENTITY] = "entity_not_found"
            elif not _entity_exists(self.hass, export_entity):
                errors[CONF_EXPORT_POWER_ENTITY] = "entity_not_found"
            else:
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                    import_entity
                )
                self._context[CONF_IMPORT_POWER_ENTITY] = import_entity
                self._context[CONF_EXPORT_POWER_ENTITY] = export_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                self._context.pop(CONF_SIGNED_POWER_ENTITY, None)

                return self.async_create_entry(
                    title=str(self._context[CONF_NAME]),
                    data=normalize_config(self._context),
                )

        return self.async_show_form(
            step_id="split",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IMPORT_POWER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Required(CONF_EXPORT_POWER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
                }
            ),
            errors=errors,
        )


class MdiOptionsFlow(config_entries.OptionsFlow):
    """Options flow for MDI Power Demand."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._context: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Edit general MDI configuration after install."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            reset_day = int(user_input[CONF_RESET_DAY])
            reading_day = int(user_input[CONF_READING_DAY])
            if reading_day < reset_day:
                errors[CONF_READING_DAY] = "reading_day_before_reset_day"
            else:
                self._context.update(normalize_config(user_input))
                if user_input[CONF_MODE] == MODE_SIGNED:
                    return await self.async_step_signed()
                return await self.async_step_split()

        return self.async_show_form(
            step_id="init",
            data_schema=_general_settings_schema(current),
            errors=errors,
        )

    async def async_step_signed(self, user_input: dict[str, Any] | None = None):
        """Edit the signed power source."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        default_entity = current.get(CONF_SIGNED_POWER_ENTITY)

        if user_input is not None:
            signed_power_entity = user_input[CONF_SIGNED_POWER_ENTITY]
            if not _entity_exists(self.hass, signed_power_entity):
                errors[CONF_SIGNED_POWER_ENTITY] = "entity_not_found"
            else:
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                    signed_power_entity
                )
                self._context[CONF_SIGNED_POWER_ENTITY] = signed_power_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                self._context.pop(CONF_IMPORT_POWER_ENTITY, None)
                self._context.pop(CONF_EXPORT_POWER_ENTITY, None)
                return self.async_create_entry(title="", data=normalize_config(self._context))

        entity_field: dict[vol.Marker, Any] = {
            vol.Required(CONF_SIGNED_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"])
            )
        }
        if default_entity:
            entity_field = {
                vol.Required(CONF_SIGNED_POWER_ENTITY, default=default_entity): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor"])
                )
            }

        return self.async_show_form(
            step_id="signed",
            data_schema=vol.Schema(
                {
                    **entity_field,
                    vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_split(self, user_input: dict[str, Any] | None = None):
        """Edit split import/export power sources."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        default_in = current.get(CONF_IMPORT_POWER_ENTITY)
        default_out = current.get(CONF_EXPORT_POWER_ENTITY)

        if user_input is not None:
            import_power_entity = user_input[CONF_IMPORT_POWER_ENTITY]
            export_power_entity = user_input[CONF_EXPORT_POWER_ENTITY]

            if not _entity_exists(self.hass, import_power_entity):
                errors[CONF_IMPORT_POWER_ENTITY] = "entity_not_found"
            elif not _entity_exists(self.hass, export_power_entity):
                errors[CONF_EXPORT_POWER_ENTITY] = "entity_not_found"
            else:
                entity_id_base = user_input.get(CONF_ENTITY_ID_BASE) or _derive_entity_id_base(
                    import_power_entity
                )
                self._context[CONF_IMPORT_POWER_ENTITY] = import_power_entity
                self._context[CONF_EXPORT_POWER_ENTITY] = export_power_entity
                self._context[CONF_ENTITY_ID_BASE] = entity_id_base
                self._context.pop(CONF_SIGNED_POWER_ENTITY, None)
                return self.async_create_entry(title="", data=normalize_config(self._context))

        import_field: dict[vol.Marker, Any] = {
            vol.Required(CONF_IMPORT_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"])
            )
        }
        export_field: dict[vol.Marker, Any] = {
            vol.Required(CONF_EXPORT_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor"])
            )
        }
        if default_in:
            import_field = {
                vol.Required(CONF_IMPORT_POWER_ENTITY, default=default_in): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor"])
                )
            }
        if default_out:
            export_field = {
                vol.Required(CONF_EXPORT_POWER_ENTITY, default=default_out): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor"])
                )
            }

        return self.async_show_form(
            step_id="split",
            data_schema=vol.Schema(
                {
                    **import_field,
                    **export_field,
                    vol.Optional(CONF_ENTITY_ID_BASE): cv.string,
                }
            ),
            errors=errors,
        )


def _derive_entity_id_base(entity_id: str) -> str:
    """Derive a stable entity-id base from the chosen power sensor."""
    base = entity_id.split(".", 1)[-1]
    return base.replace("-", "_").replace(" ", "_")


def _entity_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if the entity exists in Home Assistant state machine."""
    return hass.states.get(entity_id) is not None
