"""Constants for the Fsolar Cloud integration."""

from typing import Final

DOMAIN: Final = "fsolar"
PLATFORMS: Final = ["number", "select"]

CONF_INVERTERS: Final = "inverters"

API_BASE_URL: Final = "https://shine-api.felicitysolar.com"
WEB_BASE_URL: Final = "https://shine.felicitysolar.com"

DEFAULT_SCAN_INTERVAL: Final = 60

SOURCE_PRIORITY_FIELD: Final = "cspri"
SOURCE_PRIORITY_VALUES: Final = {
    "CSO": 1,
    "SNU": 2,
    "OSO": 3,
}
SOURCE_PRIORITY_BY_VALUE: Final = {
    value: option for option, value in SOURCE_PRIORITY_VALUES.items()
}

MAX_GRID_CHARGE_CURRENT_FIELD: Final = "maccurr"
MAX_GRID_CHARGE_CURRENT_MIN: Final = 10
MAX_GRID_CHARGE_CURRENT_MAX: Final = 240
