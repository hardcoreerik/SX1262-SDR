# SX1262-SDR

Receive-only, evidence-driven RF research on the Semtech SX1262 using a **Heltec WiFi LoRa 32 V4 / ESP32-S3** and a **Pluto-compatible AD9361 SDR** as the conducted signal reference.

## Status

**Research scaffold only.** The firmware adapter and real-device tests are not yet implemented; no Heltec or Pluto was flashed. The offline parser handles the published LakeShark sxprobe row format and has six tests based on synthetic examples.

Our question: can the published SX1262 PLL no-lock window near **1,448–2,622 MHz** be reproduced, narrowed, or explained? The previously published windows of 37–1,447 and 2,624–3,494 MHz were measured on one *LilyGO* SX1262 board, **not** this Heltec. PLL lock and RSSI do **not** establish sensitivity, packet decoding, or genuine on-channel RF reception.

## Source evidence

- Research: https://github.com/SAMS0N1TE/lr2021-sdr/blob/main/research/sx1262-range/README.md
- Actual probe: https://github.com/SAMS0N1TE/LakeShark/blob/main/components/lakeshark/board/ls_lora_sx126x.c
- Other experiment: https://github.com/ibelinp/SX1262_CHIRP
- Our private research archive: https://github.com/hardcoreerik/REA-Results
- Full local starter bundle and a longer session handoff exist separately; this branch is the collaborative source of truth after review.

## First steps

1. Read AGENTS.md, docs/SAFETY.md, docs/TEST_PLAN.md, and docs/PLUTO_PROCEDURE.md.
2. Identify exact Heltec revision and SX1262 pin/TCXO/front-end design. Do not assume LilyGO pins or LNA behavior.
3. Run offline tests before writing any hardware-driver code:

       python -m unittest discover -s tests -v
       python tools/analyze_sweep.py examples/synthetic_sxp.csv --out results/first_synthetic.json --origin synthetic

4. Logs go to SX1262-SDR.log in the directory **where the command is run**; results/ contains generated JSON. None of the example data is from a radio.
5. Implement a guarded RX-only SX1262 adapter on a development branch, with data capture and versioned CSV/JSON.
6. Start bench validation with a characterized, adequately attenuated, **conducted** Pluto source. Use source-off control measurements and independent reference observations.

## Required measurement classifications

- **command_accepted**: no SPI/command error
- **pll_locked**: RX status shows no lock error
- **rssi_observed**: radio provides RSSI; RF identity not proven
- **tone_detected**: source-on/off RF difference exceeds an explicitly defined threshold and passes control checks
- **frequency_tracked**: independently transmitted tone moves according to planned offset and receiver retuning
- **sensitivity_characterized**: calibrated level sweep, confidence and uncertainty recorded

Never relabel an RSSI reading as RF evidence or confuse 2.4 GHz ESP32-S3 Wi-Fi with SX1262 reception.

## Project layout

- src/sx1262_sdr/ — pure-Python analysis helpers.
- tools/ — CLI scripts that save an execution-directory log.
- tests/ and examples/ — synthetic, reproducible parser tests.
- configs/ — measurement session schema and proposed sweep points.
- firmware/ — future receive-only Heltec integration, no flashable firmware today.
- docs/ — bench setup, test phases, evidence sources, collaboration prompt and handoff.

## Hardware and legal boundary

No TX firmware is included in this scaffold. **Do not attach the Pluto transmitter directly to SX1262 antenna pins without verified attenuation, appropriate DC isolation and level budgeting.** Isolate transmitted RF, begin with RF output disabled, and record absolute power and signal-path uncertainties. All off-band tests are RX-only. 
