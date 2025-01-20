from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import aiohttp

from .const import (
    DOMAIN,
    CONF_SYSTEM_ID,
    CONF_API_TOKEN,
    AUTH_API_URL,
)

class BatteryPlannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Planner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_API_TOKEN]
            )

            if valid:
                return self.async_create_entry(
                    title="Battery Planner",
                    data=user_input,
                )
            else:
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SYSTEM_ID): str,
                    vol.Required(CONF_API_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, api_token: str) -> bool:
        """Test if the credentials are valid."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    AUTH_API_URL,
                    headers={"Authorization": f"Bearer {api_token}"},
                ) as response:
                    return response.status == 200
        except aiohttp.ClientError:
            return False