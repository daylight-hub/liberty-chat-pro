# Liberty Chat Pro — attribution and licensing

Liberty Chat Pro is a **modified version** of Sideband, created and maintained by
Liberty Communication Systems, Inc. (https://www.lcs.network).

## Upstream work

Sideband — Copyright (c) Mark Qvist
https://github.com/markqvist/Sideband
Licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
(CC BY-NC-SA 4.0) — https://creativecommons.org/licenses/by-nc-sa/4.0/

This derivative is based on Sideband release **2.0.1** (commit `2000d81`, 26 Jul 2026).

Liberty Chat Pro is **not** produced, endorsed, or supported by Mark Qvist. The Sideband
name and marks are not licensed under CC BY-NC-SA (§2(b)(2)) and are not used to identify
this application.

## Licence of this derivative

Because CC BY-NC-SA 4.0 is a ShareAlike licence (§3(b)), **this modified version is also
released under CC BY-NC-SA 4.0**. It cannot be relicensed under other terms. The full
licence text is in `LICENSE`, unchanged from upstream.

## Modifications made by Liberty Communication Systems, Inc.

- Rebranded as "Liberty Chat Pro"; application icon, presplash and colour theme replaced
- Android package identifier changed to `network.lcs.libertychatpro`
- Default TCP interface changed to `public.lcs.network:4244` and enabled by default
- RNode defaults set to 914.875 MHz / 250 kHz / SF11 / CR5 / 22 dBm
- LoRa modem preset picker added (`sbapp/lcs/lora_presets.py`)
- TX power ceiling raised to 28 dBm with clamping
- Voice calling enabled by default
- Bundled RNode Flasher replaced with the LCS RNode Configuration Tool
- "Buy an RNode" link added to Utilities
- TAK/CoT bridge service plugin bundled and auto-installed

## Bundled third-party components

**LCS RNode Configuration Tool** — Copyright (c) 2026 Liberty Communication Systems, Inc.
BSD 3-Clause. Incorporates: RNode Flasher by Liam Cottle (MIT, (c) 2024); RNode Firmware
v1.86 (c) Mark Qvist (GNU GPL v3.0); Vue, Tailwind CSS, crypto-js (MIT); esptool-js,
web-serial-polyfill (Apache-2.0); zip.js (BSD-3-Clause); Space Grotesk, IBM Plex Mono
(OFL-1.1). Full text in the tool's "Licenses & Attribution" section.

**TAK ↔ Reticulum bridge plugin** — from IntelKML/Sideband-ATAK-plugin.
⚠ NO LICENCE GRANT — see "Outstanding" below.

Reticulum (RNS), LXMF and LXST remain under the Reticulum License, (c) Mark Qvist.

## Outstanding — resolve before distributing

1. **NonCommercial (§2(a)(1)).** CC BY-NC-SA permits sharing only for purposes not
   primarily directed toward commercial advantage. Distribution by a hardware vendor,
   with a storefront link, may fall outside that grant. Obtain a separate commercial
   licence from Mark Qvist, or distribute non-commercially. Get legal advice.

2. **ATAK plugin.** `IntelKML/Sideband-ATAK-plugin` publishes no licence, so default
   copyright applies and redistribution rights are absent. Secure written permission,
   or have IntelKML add a licence file, before shipping.
