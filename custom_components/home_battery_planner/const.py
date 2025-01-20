from typing import Final

DOMAIN: Final = "battery_planner"
CONF_SYSTEM_ID: Final = "system_id"
CONF_API_TOKEN: Final = "api_token"

BASE_API_URL: Final = "https://bp.stenite.com/api"
AUTH_API_URL: Final = f"{BASE_API_URL}/auth/api/validate-token"
PLAN_API_URL: Final = f"{BASE_API_URL}/battery_planner/{{system_id}}/plan"