# Source provenance and evidence audit â€” 2026-10-16

Primary SX1262 published results: https://github.com/SAMS0N1TE/lr2021-sdr/blob/main/research/sx1262-range/README.md

Actual implementation: https://github.com/SAMS0N1TE/LakeShark/blob/main/components/lakeshark/board/ls_lora_sx126x.c

Secondary claimed out-of-spec range: https://github.com/ibelinp/SX1262_CHIRP

Espressif receiver research: https://github.com/ESPARGOS/esp-sdr

The independently maintained Heltec BSP and its exact revision-specific schematic MUST be identified before touching chip/RF/TCXO GPIO.

Published observations were from ONE LilyGO T-Display-P4 SX1262 board:
- PLL lock windows ~37â€“1447 MHz and ~2624â€“3494 MHz; failure near 1448â€“2622 MHz.
- Responses from onboard 40 MHz clock harmonics, RSSI only; NOT calibrated sensitivity or external-tone proof across high window.
- Approx 360â€“1080 MHz strongest direct markers; 1120â€“1400 MHz weak and uneven.
- Some low-frequency responses move with GFSK filter settings, indicating image/IF response rather than exact tuning.
- ~910 kHz measured maximum GFSK filter using undocumented bandwidth register codes.
- ~1 ms per RSSI retune in a 58.6 kHz filter on that developer board; faster than full recalibration.
- No SX1262 raw I/Q stream demonstrated; LakeShark's LR2021 I/Q work is on a DIFFERENT silicon architecture.
- Calibration helper in the published code clamps CalibrateImage values at the representable 4-MHz unit boundary of ~1020 MHz. Distinguish this from the separately cleared PLL_LOCK result after frequency programming.

Independent SX1262_CHIRP project claims ~50 MHz to 1.3 GHz PLL operation as a chirp source. Treat it as a developer claim; this does NOT corroborate the high receive window or close 2.4 GHz gap.

Working hypothesis ranking:
1. Initialization/calibration sequencing or state retained across tunes â€” TESTABLE.
2. Unexposed VCO/divider regime or special image mode â€” SPECULATIVE.
3. Board matching, antenna, LNA/SAW behavior â€” impacts response, cannot make a genuinely unlocked PLL lock.
4. Receiver images/harmonics â€” possible apparent off-frequency energy, NOT proof of a true gap closure.
5. External mixer/transverter â€” can shift known RF outside gap into a supported IF, but does NOT extend direct SX1262 tuning.

Any eventual success claim must include a known externally controlled reference signal, matched source-off control, calibrated or clearly relative power levels, shift with receiver LO, and repeat evidence.


## Pinned source review and Heltec experiment — 2026-10-16

LakeShark source pinned at `8586c6de0c40fd019b3e21eb2c05a48b35e099d3`,
`components/lakeshark/board/ls_lora_sx126x.c:1006` onward: GFSK probing,
XOSC standby, separate calibration/RX errors, checked RSSI reads and restoration.
Our firmware 1.1 adds a fixed GFSK comparison mode using documented command
fields; it does not reproduce arbitrary register/gain commands or all calibration
variants. Attribution is recorded in the implementation. Root license: GPL-3.0.

ESPARGOS/esp-sdr pinned at `e2b35dc593a378e4c5eb69cb8db59313117c9838`,
`docs/rx-controls.md` and `main/targets/esp32s3/receiver.c`: tuning/calibration
and alternate LO control operate on the ESP32 Wi-Fi receiver, a separate silicon
RF path from the SX1262. No ESP-SDR code or Wi-Fi PHY initialization was added.
The upstream README specifies GPL-3.0-or-later. Do not apply its divider constants
to the SX1262. Saved source/license SHA-256 values are in the ignored
`harness/results/upstream-research-20261016/manifest.json`.

The current LoRa and GFSK source-OFF surveys do not establish a stable PLL window.
Both conducted modes show source-dependent RSSI at tested 1300/1400 MHz points;
the tested 2.4–3.0 GHz points did not show consistent drive-dependent response.
See `HELTEC_V43_BENCH_2026-10-16.md` for exact points, source commits, artifact
paths and limits. These data cannot be pooled with LilyGO results as identical
hardware/configuration, or promoted to direct-RF/continuous-band proof.
