---
title: "Heltec fixed-RX source sweep supports Pluto DDS offset contribution"
date: "2026-10-16"
targets: ["sx1262-sdr"]
tags: ["sx1262", "heltec-v4.3", "pluto", "dds", "frequency-offset", "unverified"]
sources:
  - "F:/Ai/SX1262-SDR/docs/HELTEC_V43_FIXED_RX_2026-10-16.md"
  - "F:/Ai/SX1262-SDR/harness/results/20261016-fixed-rx-source-session/analysis.json"
key_findings:
  - "228 conducted points, twelve exits 0; all twelve curves bracketed and source-OFF checks passed."
  - "Five paired 250 MHz sweeps: median requested-source center shift -164 Hz versus -156 Hz prediction; model-axis pairwise median -7 Hz."
  - "One 315 MHz pair: requested-source shift -182 Hz, model-axis shift -26 Hz."
caveats:
  - "250 Hz source grid and 0.5 dB RSSI; interpolated centers are not single-hertz accuracy."
  - "16-bit DDS prediction at nominal clock, not independent physical RF measurement or source-purity verification."
  - "Fixed receiver programming with RX re-entry each probe, not continuous PLL hold."
  - "No firmware change, new receive-range proof, absolute calibration, packet recovery, measured-temperature sweep, full suites or Linux CI."
---

Prepared file for private REA-Results inbox; no generated files edited or publication.
Prior findings committed as 841daf7; new harness/report remain local edits.
Exact current source hashes, raw run directory list and evidence hashes are in
source-sha256.json, run-index.json, input-sha256.json and sha256.txt under the
session path above.

Analysis SHA-256: 230f23bf0c2d252fc3e9d9fc7fc44e9042ce39ec6f867969fc98876c6c469341
