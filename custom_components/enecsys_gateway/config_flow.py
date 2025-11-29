import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging

DOMAIN = "enecsys_gateway"
_LOGGER = logging.getLogger(__name__)

# Default Port
DEFAULT_PORT = 5040

class EnecsysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Enecsys."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Check if this is already configured
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Enecsys Gateway", data=user_input)

        # The Form Schema
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
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Default to current setting or fallback to 5040
        current_port = self.config_entry.options.get("port", self.config_entry.data.get("port", DEFAULT_PORT))

        schema = vol.Schema({
            vol.Required("port", default=current_port): int,
        })

        return self.async_show_form(step_id="init", data_schema=schema)