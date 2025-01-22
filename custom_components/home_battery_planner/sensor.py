from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import aiohttp

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    SENSOR_BATTERY_PLAN,
    SENSOR_BATTERY_PLAN_ACTION,
    SENSOR_BATTERY_PLAN_COST_DELTA,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Battery Planner sensors."""
    _LOGGER.debug("Starting async_setup_entry for Battery Planner sensors")

    coordinator = BatteryPlanCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass.data for the entry
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    entities = [
        BatteryPlanSensor(coordinator, entry),
        BatteryPlanCostDeltaSensor(coordinator, entry),
        BatteryPlanActionSensor(coordinator, entry),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Added %d Battery Planner entities", len(entities))

    # Register callback for manual updates
    @callback
    def handle_update_data(data: dict[str, Any]) -> None:
        """Handle manual data updates."""
        _LOGGER.debug("Handling manual data update: %s", data)
        coordinator.update_from_manual_data(data)

    # Store the update callback in hass.data for access from other components
    hass.data[DOMAIN][entry.entry_id]["update_callback"] = handle_update_data

class BatteryPlanCoordinator(DataUpdateCoordinator):
    """Class to manage battery plan data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator with polling."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # No automatic polling
        )
        self.entry = entry
        self.api_token = entry.data["api_token"]
        self.system_id = entry.data["system_id"]
        self.base_url = entry.data["base_url"]
        self.power_kw = entry.data["power_kw"]
        self.allow_export = entry.data["allow_export"]
        self.battery_current_soc = entry.data["battery_current_soc"]
        self._current_data = None

    @callback
    def update_from_manual_data(self, data: dict[str, Any]) -> None:
        """Update data from a manual update (e.g., after service call)."""
        _LOGGER.debug("Updating coordinator with manual data")
        self._current_data = data
        self.async_set_updated_data(data)

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from API endpoint."""
        if self._current_data is not None:
            return self._current_data

        try:
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            headers = {
                "Authorization": f"Token {self.api_token}",
                "Content-Type": "application/json",
            }

            payload = {
                "power_kw": self.power_kw,
                "battery_current_soc": self.battery_current_soc,
                "allow_export": self.allow_export,
            }

            _LOGGER.debug("Requesting battery plan with payload: %s", payload)

            async with session.post(
                f"{self.base_url}/api/battery_planner/{self.system_id}/plan",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _LOGGER.debug("Received battery plan data: %s", data)
                    self._current_data = data
                    return data
                _LOGGER.error(
                    "Failed to fetch battery plan data. Status: %s, Response: %s",
                    resp.status,
                    await resp.text(),
                )
                return None
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching battery plan data: %s", err)
            return None
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching battery plan data: %s", err)
            return None

class BatteryPlanBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Battery Planner sensors."""

    def __init__(
        self,
        coordinator: BatteryPlanCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Battery System {entry.data['system_id']}",
            manufacturer="Battery Planner",
        )
        self._attr_name = name
        self._attr_has_entity_name = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from SCM."""
        self.async_write_ha_state()

class BatteryPlanSensor(BatteryPlanBaseSensor):
    """Representation of a Battery Plan sensor."""

    entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BatteryPlanCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, SENSOR_BATTERY_PLAN, "Status")

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return "active" if self.coordinator.data else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data:
            return {"schedule": self.coordinator.data.get("schedule", [])}
        return {}


class BatteryPlanCostDeltaSensor(BatteryPlanBaseSensor):
    """Representation of a Battery Plan Cost Delta sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BatteryPlanCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, SENSOR_BATTERY_PLAN_COST_DELTA, "Cost Delta")

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        baseline = float(self.coordinator.data.get("baseline_cost", 0))
        optimized = float(self.coordinator.data.get("optimized_cost", 0))
        return baseline - optimized

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or not self.coordinator.data.get("schedule"):
            return {}

        return {
            "baseline_cost": float(self.coordinator.data.get("baseline_cost", 0)),
            "optimized_cost": float(self.coordinator.data.get("optimized_cost", 0)),
        }


class BatteryPlanActionSensor(BatteryPlanBaseSensor):
    """Representation of a Battery Plan Action sensor."""

    def __init__(self, coordinator: BatteryPlanCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, SENSOR_BATTERY_PLAN_ACTION, "Current Action")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or not self.coordinator.data.get("schedule"):
            return None
        first_action = self.coordinator.data["schedule"][0]
        return first_action.get("action", {}).get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or not self.coordinator.data.get("schedule"):
            return {}

        first_action = self.coordinator.data["schedule"][0]
        return {
            "power": first_action.get("action", {}).get("power"),
            "cost": first_action.get("cost", {}),
            "price": first_action.get("price", {}),
            "soc": first_action.get("soc", {}),
            "time": first_action.get("time"),
        }