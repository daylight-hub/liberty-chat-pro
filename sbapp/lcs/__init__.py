# Liberty Chat Pro — LCS customisation layer
# Liberty Communication Systems, Inc.  https://www.lcs.network
#
# Modifications to Sideband (c) Mark Qvist, licensed CC BY-NC-SA 4.0.
# See NOTICE.md in the repository root.

from .brand import BRAND, KIVYMD_THEME, rgba
from .lora_presets import (
    PRESETS, DEFAULT_PRESET_KEY, LCS_RNODE_DEFAULTS,
    get_preset, match_preset, preset_summary,
)

LCS_PROFILE_VERSION = 1
LCS_TCP_HOST = "public.lcs.network"
LCS_TCP_PORT = "4244"
LCS_STORE_URL = "https://www.lcs.network"
