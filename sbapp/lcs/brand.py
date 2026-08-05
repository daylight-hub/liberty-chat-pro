# Liberty Chat Pro — brand tokens
# Palette sampled directly from LCS_Logo_4x4_300dpi_transparent_interiorallwhite.png
# Liberty Communication Systems, Inc. — https://www.lcs.network

BRAND = {
    # Core identity — pulled from the logo itself
    "navy":         "#003C6C",   # 219,933 px in logo — the primary ring
    "navy_deep":    "#00284A",   # pressed / elevated navy
    "navy_black":   "#071626",   # app background (field-readable at night)
    "gold":         "#C8983C",   # the bell — accent, CTAs, active states
    "gold_bright":  "#E4C06C",   # highlight / focus ring
    "silver":       "#A9AFB6",   # the yoke — secondary text, dividers
    "white":        "#FCFCFC",   # logo interior

    # Derived surfaces
    "surface":         "#0E1C2B",
    "surface_raised":  "#152738",
    "surface_sunken":  "#08121C",
    "divider":         "#1E3549",

    # Text
    "text_primary":   "#F2F5F8",
    "text_secondary": "#A9AFB6",
    "text_disabled":  "#5C6B7A",
    "text_on_gold":   "#0A1520",

    # Status — signal states, not decoration
    "ok":       "#3FA45B",   # link established / message delivered
    "pending":  "#C8983C",   # in flight (reuses gold deliberately)
    "warn":     "#D98A2B",   # degraded path / high airtime
    "fail":     "#C0392B",   # delivery failed / no path
    "offline":  "#5C6B7A",
}

# Radio-state colour ramp for RSSI/SNR bars and the link-quality pill
SIGNAL_RAMP = ["#C0392B", "#D98A2B", "#C8983C", "#7FA85B", "#3FA45B"]

TYPE_SCALE = {
    "display":  {"size": "34sp", "weight": "700", "tracking": "-0.5"},
    "title":    {"size": "22sp", "weight": "600", "tracking": "0"},
    "subtitle": {"size": "17sp", "weight": "500", "tracking": "0"},
    "body":     {"size": "15sp", "weight": "400", "tracking": "0"},
    "label":    {"size": "13sp", "weight": "600", "tracking": "0.8"},   # ALL-CAPS eyebrows
    "mono":     {"size": "14sp", "weight": "400", "family": "IBM Plex Mono"},
}

# Monospace is not cosmetic here: destination hashes, frequencies and RSSI
# values are read character-by-character and compared against hardware.
MONO_CONTEXTS = ["destination_hash", "identity_hash", "frequency", "rssi", "snr", "callsign"]

RADIUS  = {"card": "14dp", "control": "10dp", "pill": "999dp", "sheet": "24dp"}
SPACING = {"xs": "4dp", "sm": "8dp", "md": "16dp", "lg": "24dp", "xl": "32dp"}

# KivyMD 1.x expects a named palette + hex overrides.
KIVYMD_THEME = {
    "theme_style": "Dark",
    "primary_palette": "Blue",
    "accent_palette": "Amber",
    "primary_hue": "800",
    "hex_primary": BRAND["navy"],
    "hex_accent": BRAND["gold"],
    "hex_bg_darkest": BRAND["navy_black"],
    "hex_bg_dark": BRAND["surface"],
    "hex_bg_normal": BRAND["surface_raised"],
}


def rgba(hex_str, alpha=1.0):
    """'#003C6C' -> (0.0, 0.235, 0.424, 1.0) for Kivy canvas instructions."""
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (alpha,)
