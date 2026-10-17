---
title: "Heltec V4.3 apparent frequency offsets include Pluto DDS quantization"
date: "2026-10-16"
targets: ["sx1262-sdr"]
tags: ["sx1262", "heltec-v4.3", "pluto", "frequency-offset", "conducted-rf", "unverified"]
sources:
  - "F:/Ai/SX1262-SDR/docs/HELTEC_V43_OFFSET_MAP_2026-10-16.md"
  - "F:/Ai/SX1262-SDR/harness/results/20261016-offset-map-session/analysis.json"
  - "https://analogdevicesinc.github.io/hdl/library/common/ad_dds/index.html"
key_findings:
  - "494 conducted points across ten runner exits 0; analysis.json point_count and run-index.json."
  - "LO/DDS split control moved strong centers +299/+333 Hz against a +312.5 Hz digital-model prediction; analysis.json lo_dds_control."
  - "A fixed-absolute-grid source shift of +5000 Hz moved the sampled peak +5000 Hz; analysis.json wide_fixed_grid_source_shift."
  - "Earlier -1 kHz coarse peak offset is not a receiver calibration; five-repeat medians are approximately -141/-207/-250 Hz versus programmed source at 200/250/315 MHz."
caveats:
  - "500 Hz fine grid and 0.5 dB RSSI quantization; interpolated centers are not calibrated frequency accuracy."
  - "Unfiltered conducted exception authorized; source purity and absolute frequency unverified; digital predictions are not physical RF measurements."
  - "No firmware change, measured-temperature sweep, bandwidth/calibration comparison, packet recovery, full suites or Linux CI in this stage."
---

Prepared file for the private REA-Results inbox; no generated REA files changed
and no publication performed.

Source HEAD/base: 9f9bfcfd2a5f3ec01e93c6bd14fc92c38a0d8b83 plus local edits.
Firmware 1.2 unchanged. Exact source and evidence hashes:
F:/Ai/SX1262-SDR/harness/results/20261016-offset-map-session/source-sha256.json
and sha256.txt. Raw run directories are listed in run-index.json.

Report SHA-256: c32ed63a7051af96e7b7cb961317015eedba22912b5b7b10a29939cbf08e5638

Analysis SHA-256: ae627961ad379bfb423b8bdc9a5ef6de986053e50a2ba4c27c24e2b03e552c99
