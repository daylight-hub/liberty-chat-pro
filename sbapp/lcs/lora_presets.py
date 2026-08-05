# Liberty Chat Pro — LoRa modem presets
#
# Columba's preset list mirrors the Meshtastic modem presets, on an assumed US
# default of 914.875 MHz (see torlando-tech/columba issue #916). This table
# reproduces that mapping so Liberty Chat Pro users land on the same air
# parameters as Columba / Liberty Chat users and can actually hear each other.
#
# IMPORTANT: frequency, bandwidth and spreading factor must match on both ends
# for two nodes to link. Coding rate and TX power may differ.

DEFAULT_FREQUENCY_HZ = 914_875_000     # 914.875 MHz — LCS US default

TX_POWER_DEFAULT_DBM = 22
TX_POWER_MIN_DBM     = 0
TX_POWER_MAX_DBM     = 28              # ceiling raised per LCS spec

# name, bandwidth (Hz), spreading factor, coding rate
PRESETS = [
    {"key": "short_turbo",    "name": "Short Turbo",    "bandwidth": 500_000, "sf": 7,  "cr": 5},
    {"key": "short_fast",     "name": "Short Fast",     "bandwidth": 250_000, "sf": 7,  "cr": 5},
    {"key": "short_slow",     "name": "Short Slow",     "bandwidth": 250_000, "sf": 8,  "cr": 5},
    {"key": "medium_fast",    "name": "Medium Fast",    "bandwidth": 250_000, "sf": 9,  "cr": 5},
    {"key": "medium_slow",    "name": "Medium Slow",    "bandwidth": 250_000, "sf": 10, "cr": 5},
    {"key": "long_fast",      "name": "Long Fast",      "bandwidth": 250_000, "sf": 11, "cr": 5},
    {"key": "long_moderate",  "name": "Long Moderate",  "bandwidth": 125_000, "sf": 11, "cr": 8},
    {"key": "long_slow",      "name": "Long Slow",      "bandwidth": 125_000, "sf": 12, "cr": 8},
    {"key": "very_long_slow", "name": "Very Long Slow", "bandwidth": 62_500,  "sf": 12, "cr": 8},
    {"key": "custom",         "name": "Custom",         "bandwidth": None,    "sf": None, "cr": None},
]

# LCS ships on Long Fast: BW 250 kHz / SF 11 / CR 5 at 914.875 MHz.
DEFAULT_PRESET_KEY = "long_fast"


def lora_bitrate(bandwidth, sf, cr):
    """Nominal LoRa symbol bitrate in bits/sec. Useful for the preset picker
    subtitle so operators can see what they are trading away."""
    if not all((bandwidth, sf, cr)):
        return None
    return (sf * (4.0 / cr)) / (2.0 ** sf / float(bandwidth))


def preset_summary(preset):
    """'250 kHz · SF11 · CR5 · ~1.34 kbps' for the dropdown row."""
    if preset["key"] == "custom":
        return "Set bandwidth, spreading factor and coding rate manually"
    br = lora_bitrate(preset["bandwidth"], preset["sf"], preset["cr"])
    return (f"{preset['bandwidth'] // 1000} kHz · SF{preset['sf']} · "
            f"CR{preset['cr']} · ~{br / 1000:.2f} kbps")


def get_preset(key):
    return next((p for p in PRESETS if p["key"] == key), None)


def match_preset(bandwidth, sf, cr):
    """Reverse lookup so the picker shows the right row when a device reports
    its live config, rather than silently defaulting to Custom."""
    for p in PRESETS:
        if (p["bandwidth"], p["sf"], p["cr"]) == (bandwidth, sf, cr):
            return p["key"]
    return "custom"


LCS_RNODE_DEFAULTS = {
    "frequency":       DEFAULT_FREQUENCY_HZ,
    "bandwidth":       250_000,
    "txpower":         TX_POWER_DEFAULT_DBM,
    "spreadingfactor": 11,
    "codingrate":      5,
}

if __name__ == "__main__":
    for p in PRESETS:
        mark = "  <- default" if p["key"] == DEFAULT_PRESET_KEY else ""
        print(f"{p['name']:<16} {preset_summary(p)}{mark}")
