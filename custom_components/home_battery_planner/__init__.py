from typing import Any, Dict
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import aiohttp

from .const import (
    DOMAIN,
    CONF_SYSTEM_ID,
    CONF_API_TOKEN,
    PLAN_API_URL,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Battery Planner from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    async def create_plan(call: ServiceCall) -> Dict[str, Any]:
        """Handle the service call."""
        system_id = entry.data[CONF_SYSTEM_ID]
        api_token = entry.data[CONF_API_TOKEN]

        power_kw = call.data["power_kw"]
        battery_current_soc = call.data["battery_current_soc"]
        allow_export = call.data["allow_export"]

        # Prepare request data
        data = {
            "power_kw": power_kw,
            "battery_current_soc": battery_current_soc,
            "allow_export": allow_export,
        }

        # Make API request
        async with aiohttp.ClientSession() as session:
            url = PLAN_API_URL.format(system_id=system_id)
            async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {api_token}"},
                    json=data,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"API request failed with status {response.status}")

    # Register service
    hass.services.async_register(
        DOMAIN,
        "create_plan",
        create_plan,
        schema=vol.Schema({
            vol.Required("power_kw"): vol.All(list, [vol.Coerce(float)]),
            vol.Required("battery_current_soc"): vol.All(
                vol.Coerce(float),
                vol.Range(min=0, max=100)
            ),
            vol.Required("allow_export"): bool,
        })
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True