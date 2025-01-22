"""Battery Planner sensor platform."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    UPDATE_INTERVAL,
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

    entities = [
        BatteryPlanSensor(coordinator, entry),
        BatteryPlanCostDeltaSensor(coordinator, entry),
        BatteryPlanActionSensor(coordinator, entry),
    ]

    async_add_entities(entities)
    _LOGGER.debug("Added %d Battery Planner entities", len(entities))


class BatteryPlanCoordinator(DataUpdateCoordinator):
    """Class to manage fetching battery plan data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        # Note: Converting UPDATE_INTERVAL from seconds to timedelta
        update_interval = timedelta(seconds=UPDATE_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.entry = entry
        self.api_token = entry.data["api_token"]
        self.system_id = entry.data["system_id"]
        self.base_url = entry.data["base_url"]
        self.power_kw = entry.data["power_kw"]
        self.allow_export = entry.data["allow_export"]
        self.battery_current_soc = entry.data["battery_current_soc"]

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from API endpoint."""
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