# Source provenance and evidence audit — 2026-10-16

Primary SX1262 published results: https://github.com/SAMS0N1TE/lr2021-sdr/blob/main/research/sx1262-range/README.md

Actual implementation: https://github.com/SAMS0N1TE/LakeShark/blob/main/components/lakeshark/board/ls_lora_sx126x.c

Secondary claimed out-of-spec range: https://github.com/ibelinp/SX1262_CHIRP

Espressif receiver research: https://github.com/ESPARGOS/esp-sdr

The independently maintained Heltec BSP and its exact revision-specific schematic MUST be identified before touching chip/RF/TCXO GPIO.

Published observations were from ONE LilyGO T-Display-P4 SX1262 board:
- PLL lock windows ~37–1447 MHz and ~2624–3494 MHz; failure near 1448–2622 MHz.
- Responses from onboard 40 MHz clock harmonics, RSSI only; NOT calibrated sensitivity or external-tone proof across high window.
- Approx 360–1080 MHz strongest direct markers; 1120–1400 MHz weak and uneven.
- Some low-frequency responses move with GFSK filter settings, indicating image/IF response rather than exact tuning.
- ~910 kHz measured maximum GFSK filter using undocumented bandwidth register codes.
- ~1 ms per RSSI retune in a 58.6 kHz filter on that developer board; faster than full recalibration.
- No SX1262 raw I/Q stream demonstrated; LakeShark's LR2021 I/Q work is on a DIFFERENT silicon architecture.
- Calibration helper in the published code clamps CalibrateImage values at the representable 4-MHz unit boundary of ~1020 MHz. Distinguish this from the separately cleared PLL_LOCK result after frequency programming.

Independent SX1262_CHIRP project claims ~50 MHz to 1.3 GHz PLL operation as a chirp source. Treat it as a developer claim; this does NOT corroborate the high receive window or close 2.4 GHz gap.

Working hypothesis ranking:
1. Initialization/calibration sequencing or state retained across tunes — TESTABLE.
2. Unexposed VCO/divider regime or special image mode — SPECULATIVE.
3. Board matching, antenna, LNA/SAW behavior — impacts response, cannot make a genuinely unlocked PLL lock.
4. Receiver images/harmonics — possible apparent off-frequency energy, NOT proof of a true gap closure.
5. External mixer/transverter — can shift known RF outside gap into a supported IF, but does NOT extend direct SX1262 tuning.

Any eventual success claim must include a known externally controlled reference signal, matched source-off control, calibrated or clearly relative power levels, shift with receiver LO, and repeat evidence.
