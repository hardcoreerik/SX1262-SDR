---
title: "Heltec V4.3 SX1262: conducted response at 1300/1400 MHz; upper-band RX unproven"
date: "2026-10-16"
targets: ["sx1262-sdr", "esp-sdr"]
tags: ["sx1262", "heltec-v4.3", "lakeshark", "conducted-rf", "gfsk", "pll", "unverified"]
sources:
  - "F:/Ai/SX1262-SDR/docs/HELTEC_V43_BENCH_2026-10-16.md"
  - "https://github.com/SAMS0N1TE/LakeShark/blob/8586c6de0c40fd019b3e21eb2c05a48b35e099d3/components/lakeshark/board/ls_lora_sx126x.c"
  - "https://github.com/ESPARGOS/esp-sdr/blob/e2b35dc593a378e4c5eb69cb8db59313117c9838/docs/rx-controls.md"
key_findings:
  - "GFSK 4.8 kHz: 1300/1400 MHz source-ON RSSI rises of 40.5/35.5 dB at Pluto hardwaregain -60 dB; see the bench record and run 20261016-195502-446730_heltec-v43-gfsk-conducted."
  - "No consistent drive-dependent response at 2400, 2450, 2624, 2700 or 3000 MHz in the tested conducted setup."
  - "Mode/history-sensitive PLL errors near the edges prevent declaring stable lock windows; clear flags alone did not predict conducted response."
caveats:
  - "Unfiltered source explicitly authorized; no independent source-purity check, calibrated input level, receiver-frequency tracking or packet decode."
  - "FEM/matching, narrow-filter frequency alignment and 915-only image calibration limit negative-result interpretation."
  - "Local dirty firmware build; no CI, publication or merge."
---

Draft file for the private REA-Results inbox, prepared under its AGENTS.md format.
The REA generated index/targets were consulted read-only and not modified.

Firmware 1.1 image SHA-256:
`42E2F2CE63D095FD7B204635EDFDDAB401D40F7E9E437C7642BDCE2E65170855`.
Build provenance and exact source hashes:
`F:/Ai/SX1262-SDR/harness/results/20261016-heltec-v43-session/firmware-provenance.json`.
Complete-run artifacts include `sha256.txt`; the final session manifest is
`F:/Ai/SX1262-SDR/harness/results/20261016-heltec-v43-session/final-sha256.txt`.

The aborted LoRa edge test was preserved in
`harness/results/20261016-194740-958773_heltec-v43-conducted-ranges/run.log`,
with original-log SHA-256 and 33 completed measurements in `recovered_partial.json`.
This partial run must not be represented as a successful full sweep.

The source review motivated a bounded GFSK comparison mode. ESP-SDR's ESP32
Wi-Fi RF mechanisms were not transplanted to the separate SX1262 RF path.
Upstream revisions and license/derivation notes are in the main bench record.
No third-party source code or vendor firmware is included in this inbox draft.


Lower-band continuation: `docs/HELTEC_V43_LOWER_BAND_2026-10-16.md` records 117 conducted points. At 200 MHz a 5 kHz source shift moved the sampled peak 5 kHz on an identical absolute RX grid. The 1.1 offset/gain data are separate from firmware 1.2 source-OFF tests: one no-error RX state appeared at 36.3 MHz, but 36.4 failed, so there is no stable minimum or proven sub-37 MHz reception. Firmware 1.2 SHA-256: `71b283f50a2fde36df7558ce1fe7ad39ed319069f31c96b02aa915efb42954c9`. No independent source purity, absolute calibration or packet decode was established.
