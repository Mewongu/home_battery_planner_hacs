# Home Battery Planner for Home Assistant

A Home Assistant integration that helps you create and manage battery charge/discharge plans for your home battery system. This integration communicates with the Battery Planner API service to generate optimized charging schedules based on your power requirements.

## Features

- Create battery charge/discharge plans based on power requirements
- Configure system settings through the Home Assistant UI
- Secure API token authentication
- Real-time plan generation with customizable parameters
- Support for power export control

## Prerequisites

- Home Assistant 2024.6.1 or newer
- A valid Battery Planner system ID and API token
- Internet connectivity to access the Battery Planner API service

## Installation

### HACS Installation (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. Click on HACS in the sidebar
3. Click on "Integrations"
4. Click the "+" button in the bottom right corner
5. Search for "Home Battery Planner"
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from the repository
2. Copy the `home_battery_planner` folder to your `custom_components` directory
3. Restart Home Assistant

## Usage

### Service: create_plan

This integration provides a service to create battery charge/discharge plans. You can call this service through the Home Assistant UI or using automation YAML.

#### Service Parameters

| Parameter | Type | Description | Required | Range |
|-----------|------|-------------|-----------|--------|
| system_id | string | Your system identifier | Yes | - |
| api_token | string | Your API authentication token | Yes | - |
| power_kw | list of float | List of power values in kW | Yes | - |
| battery_current_soc | float | Current state of charge of the battery | Yes | 0-100 |
| allow_export | boolean | Whether to allow power export in the plan | Yes | true/false |

#### Example Service Call (YAML)

```yaml
action: battery_planner.create_plan
data:
  power_kw:
    - {{ state_attr('sensor.my_mean_consumption_in_kw') | float }}
  battery_current_soc: {{ state_attr('sensor.my_battery_soc') | float }}
  allow_export: false
  update_sensors: true
target:
  device_id: <configured_device_id>
```

#### Example Service Call (UI)

1. Navigate to Developer Tools → Actions
2. Select "Home Battery Planner: Create Battery Plan"
3. Fill in the required fields:
   - System ID
   - API Token
   - Power Values
   - Current Battery SOC
   - Allow Export
4. Click "Perform Action"

## API Response

The service returns a response with the following structure:

```json
{
  "success": true,
  "message": "Plan created successfully",
  "data": {
    // Plan details from the API
  }
}
```

## Error Handling

If an error occurs, the service will return:

```json
{
  "success": false,
  "message": "Error description",
  "error": {
    // Error details if available
  }
}
```

## Debugging

The integration logs debug information under the `home_battery_planner` component. You can enable debug logging by adding the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.home_battery_planner: debug
```

## Support

- Report bugs and feature requests through the GitHub issue tracker
- For API-specific issues, contact the Battery Planner API support team

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributors

- @Mewongu - Original creator and maintainer

## Changelog

### 0.1.0
- Initial release
- Basic plan creation functionality