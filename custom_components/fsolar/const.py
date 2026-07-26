"""Constants for the Fsolar Cloud integration."""

from typing import Final

DOMAIN: Final = "fsolar"
PLATFORMS: Final = ["binary_sensor", "number", "select", "sensor"]

CONF_INVERTERS: Final = "inverters"
CONF_RESERVE_ENABLED: Final = "reserve_enabled"
CONF_RESERVE_SOC_ENTITIES: Final = "reserve_soc_entities"
CONF_RESERVE_POINT_A_TIME: Final = "reserve_point_a_time"
CONF_RESERVE_POINT_A_LOW: Final = "reserve_point_a_low"
CONF_RESERVE_POINT_A_HIGH: Final = "reserve_point_a_high"
CONF_RESERVE_POINT_B_TIME: Final = "reserve_point_b_time"
CONF_RESERVE_POINT_B_LOW: Final = "reserve_point_b_low"
CONF_RESERVE_POINT_B_HIGH: Final = "reserve_point_b_high"

API_BASE_URL: Final = "https://shine-api.felicitysolar.com"
WEB_BASE_URL: Final = "https://shine.felicitysolar.com"

DEFAULT_SCAN_INTERVAL: Final = 60
DEFAULT_RESERVE_ENABLED: Final = False
DEFAULT_RESERVE_POINT_A_TIME: Final = "08:00:00"
DEFAULT_RESERVE_POINT_A_LOW: Final = 50
DEFAULT_RESERVE_POINT_A_HIGH: Final = 55
DEFAULT_RESERVE_POINT_B_TIME: Final = "18:00:00"
DEFAULT_RESERVE_POINT_B_LOW: Final = 50
DEFAULT_RESERVE_POINT_B_HIGH: Final = 55
RESERVE_EVALUATION_INTERVAL: Final = 60
RESERVE_RETRY_INTERVAL: Final = 120

SOURCE_PRIORITY_FIELD: Final = "cspri"
SOURCE_PRIORITY_VALUES: Final = {
    "CSO": 1,
    "SNU": 2,
    "OSO": 3,
}
SOURCE_PRIORITY_BY_VALUE: Final = {
    value: option for option, value in SOURCE_PRIORITY_VALUES.items()
}

OUTPUT_SOURCE_PRIORITY_FIELD: Final = "ospri"
OUTPUT_SOURCE_PRIORITY_VALUES: Final = {
    "UTI": 0,
    "SUB": 1,
    "SBU": 2,
}
OUTPUT_SOURCE_PRIORITY_BY_VALUE: Final = {
    value: option for option, value in OUTPUT_SOURCE_PRIORITY_VALUES.items()
}

MAX_GRID_CHARGE_CURRENT_FIELD: Final = "maccurr"
MAX_GRID_CHARGE_CURRENT_MIN: Final = 10
MAX_GRID_CHARGE_CURRENT_MAX: Final = 240
