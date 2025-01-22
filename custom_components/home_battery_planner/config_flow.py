"""Config flow for Battery Planner integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_BASE_URL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("api_token"): str,
        vol.Required("system_id"): str,
        vol.Required("base_url", default=DEFAULT_BASE_URL): str,
        vol.Required("power_kw"): str,  # Will be converted to list of floats
        vol.Required("battery_current_soc", default=50): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
        vol.Required("allow_export", default=True): bool,
    }
)

def convert_power_kw_string(power_kw_str: str) -> list[float]:
    """Convert comma-separated string of power values to list of floats."""
    try:
        return [float(x.strip()) for x in power_kw_str.split(',')]
    except ValueError as err:
        raise ValueError("Invalid power_kw format. Please provide comma-separated numbers") from err

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)

    headers = {"Authorization": f"Token {data['api_token']}"}

    try:
        # First validate the power_kw format
        power_kw = convert_power_kw_string(data["power_kw"])

        async with session.get(
            f"{data['base_url']}/auth/api/validate-api-token",
            headers=headers,
        ) as response:
            if response.status != 200:
                raise InvalidAuth

        # Store the converted power_kw in the data
        data["power_kw"] = power_kw

        return {"title": f"Battery System {data['system_id']}"}

    except ValueError as err:
        raise InvalidPowerKW from err
    except aiohttp.ClientConnectionError as err:
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Battery Planner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidPowerKW:
                errors["power_kw"] = "invalid_power_kw"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidPowerKW(HomeAssistantError):
    """Error to indicate invalid power_kw format."""