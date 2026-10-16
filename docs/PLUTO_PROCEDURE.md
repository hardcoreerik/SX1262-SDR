# Pluto-compatible AD9361 conducted RF oracle

## Purpose
Prove or disprove *actual* RF reception at the requested tuned frequency. Pluto acts as a test-signal source and optionally a measurement receiver; it is NOT an assumed laboratory-grade calibrated power source. Use a second reference receiver or power meter when available.

## Equipment and preflight
Heltec V4 SX1262; Pluto-compatible Zynq-7020+AD9361; known-good USB data/power; shielded coax; compatible SMA/U.FL adapters as applicable; verified fixed attenuation chain; DC block if appropriate; 50-ohm terminators; optional directional coupler and RF power meter. Photograph the hookup. Document port labeling and power limits from actual clone PCB/documentation, not a nominal Pluto spec sheet.

1. Disable all RF outputs and identify exact Pluto clone RX/TX connectors.
2. Inspect Heltec RF frontend and antenna-switch path. Confirm its input is not inadvertently powered by bias or attached to an antenna.
3. Calculate and independently verify a conservative maximum input level including Pluto worst-case output, software gain, front-end gains and all attenuator tolerances. Do not prescribe one unverified fixed number across all clone boards.
4. Assemble RF chain while TX is disabled and physically isolated. Confirm no accessible radiating branch.
5. Verify Pluto transport, frequency programming, TX path availability and spectral purity using its own RX or another SDR before connecting to Heltec.
6. Begin at known nominal RX frequencies (e.g. 915 MHz; appropriately adapted board front end). Run baseline with source OFF, then a known weak CW tone at a declared frequency offset within selected RX filter.
7. Record Pluto source frequency, programmed/output attenuation, frequency offset, duty cycle, exact coax path, RF source on/off state, SRC control verification, and device error/status/RSSI.
8. Repeat at multiple offsets (e.g. ±10/±25 kHz after verifying filter supports them). Move the RX tuning independently to distinguish real external RF, LO images and internally generated spurs.
9. Use source-off controls between tests. Require source-on/off differences, timing correlation and frequency tracking, not a single RSSI increase.
10. Edge sweeps first: ~1400–1500 MHz, then ~2600–2680 MHz, followed by interior 1800/2100/2400 MHz only if setup has been validated.
11. If signal generator power is not traceable/calibrated at the test frequency, report relative detectability, not dBm sensitivity.
12. Stop on abnormal status, level uncertainty, damaged cable, PLL error that cannot be recovered, or overloaded signal path. RF TX OFF on exit.

## Data artifacts
Log RX commands, resulting errors/status and RSSI; source-control commands/ack, power assumptions; source-off and source-on pairs; frequency offsets; uncertainty; signal-path diagram; raw screenshot or power meter observations; measured and expected signal movements. Treat inability to measure actual RF level as explicit limitation.

## Acceptance
To mark frequency as externally verified, require reproducible carrier-vs-source-off difference, signal movement with known TX-frequency variation, and (where possible) independent second RF receiver cross-check. Ordinary SX1262 status/RSSI alone never reaches this classification.
