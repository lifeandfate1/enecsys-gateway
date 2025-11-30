import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 5040

class EnecsysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Enecsys."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Enecsys Gateway", data=user_input)

        schema = vol.Schema({
            vol.Required("port", default=DEFAULT_PORT): int,
        })

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EnecsysOptionsFlowHandler(config_entry)

class EnecsysOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the options flow (Settings button)."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        # FIX: Do not set self.config_entry manually.
        # Pass it to super().__init__ if required by your HA version,
        # but for OptionsFlow in 2024/2025, just initializing is usually enough
        # or relying on the base class property.
        pass

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Use config_entry from the property, not self-assigned
        current_port = self.config_entry.options.get("port", self.config_entry.data.get("port", DEFAULT_PORT))

        schema = vol.Schema({
            vol.Required("port", default=current_port): int,
        })

        return self.async_show_form(step_id="init", data_schema=schema)