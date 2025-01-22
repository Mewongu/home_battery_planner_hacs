"""The Battery Planner integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import DOMAIN, DEFAULT_BASE_URL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Battery Planner component from YAML configuration (not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Battery Planner from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Verify we can connect to the battery planner service
    session = async_get_clientsession(hass)
    api_token = entry.data["api_token"]
    base_url = entry.data.get("base_url", DEFAULT_BASE_URL)

    try:
        async with session.get(
                f"{base_url}/auth/api/validate-api-token",
                headers={"Authorization": f"Token {api_token}"},
        ) as response:
            if response.status != 200:
                raise ConfigEntryNotReady(
                    f"Invalid authentication for Battery Planner: {response.status}"
                )
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to Battery Planner: {err}"
        ) from err

    # Store the session and configuration
    hass.data[DOMAIN][entry.entry_id] = {
        "session": session,
        "api_token": api_token,
        "base_url": base_url,
        "system_id": entry.data["system_id"],
    }

    @callback
    def find_coordinator_by_device_id(device_id: str):
        """Find the coordinator for a given device ID."""
        device_registry = async_get_device_registry(hass)
        entity_registry = async_get_entity_registry(hass)

        # Get all entities for this device
        entity_entries = async_get_entity_registry(hass).entities.values()
        device_entities = [
            entry for entry in entity_entries
            if entry.device_id == device_id
        ]

        # Find the coordinator from any of the device's entities
        for entity_entry in device_entities:
            if entity_entry.platform == DOMAIN:
                entry_id = entity_entry.config_entry_id
                if entry_id and entry_id in hass.data[DOMAIN]:
                    return hass.data[DOMAIN][entry_id].get("coordinator")

        return None

    async def create_battery_plan(call):
        """Handle the service call and return the plan as response data."""
        _LOGGER.debug("Service called with data: %s", call.data)
        power_kw = call.data["power_kw"]
        battery_current_soc = call.data["battery_current_soc"]
        allow_export = call.data["allow_export"]
        update_sensors = call.data.get("update_sensors", True)

        headers = {
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "power_kw": power_kw,
            "battery_current_soc": battery_current_soc,
            "allow_export": allow_export,
        }

        try:
            async with session.post(
                    f"{base_url}/api/battery_planner/{entry.data['system_id']}/plan",
                    headers=headers,
                    json=payload,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    _LOGGER.debug("Received API response: %s", result)

                    response_data = {
                        "baseline_cost": float(result["baseline_cost"]),
                        "optimized_cost": float(result["optimized_cost"]),
                        "schedule": result["schedule"],
                        "success": True
                    }

                    if update_sensors:
                        # Use the stored update callback to update the sensors
                        update_callback = hass.data[DOMAIN][entry.entry_id].get("update_callback")
                        if update_callback:
                            _LOGGER.debug("Updating sensors with new data")
                            update_callback(result)
                        else:
                            _LOGGER.warning("Update callback not found")

                    return response_data

                _LOGGER.error(
                    "Failed to create battery plan. Status: %s, Response: %s",
                    resp.status,
                    await resp.text(),
                )
                return {
                    "success": False,
                    "error": f"Failed to create battery plan: HTTP {resp.status}"
                }
        except Exception as err:
            _LOGGER.error("Error creating battery plan: %s", err)
            return {
                "success": False,
                "error": f"Error creating battery plan: {str(err)}"
            }    # Register service with response support
    hass.services.async_register(DOMAIN, "create_plan", create_battery_plan, supports_response=True)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)