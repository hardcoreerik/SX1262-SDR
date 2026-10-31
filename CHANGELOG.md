# Changelog

SX1262-SDR is currently an **experimental research project**, not a released product. This log records repository changes and physical bench milestones. Firmware version numbers below are **bench firmware identities**, not GitHub releases. For detailed data, methods, uncertainty and artifact hashes, follow the linked reports.

## [Unreleased] — 2026-10-31: V4.3 integration preparation

### Added
- Consolidated ESP-IDF **Heltec WiFi LoRa 32 V4.3 (ESP32-S3 / SX1262 / KCT8103L)** bench firmware and serial profile on the V4.3 development branch.
- Introduced V4.3 RX probing, fixed-frequency measurements, selectable GFSK filters, rapid timestamped RSSI/envelope captures and bounded front-end LNA controls.
- Integrated Pluto-compatible AD9361 RX/relay and experimental modulation-analysis tools into the existing **single** `harness/run_sweep.py` workflow; added dedicated host regression tests.
- Imported the dated, evidence-led V4.3 bench reports, source/LO offset investigations, AM/FM tests and REA research notes.
- Updated the landing-page [README](README.md) to reflect *physical test evidence*, distinguish valid measurements from unresolved claims and link directly to the experiment records.

### Fixed / clarified
- Added **SciPy** to the host test dependency/install instructions. GitHub Actions had failed during `test_pluto_relay.py` collection with `ModuleNotFoundError: No module named 'scipy'`; the first post-fix push and PR CI runs passed (October 31).
- Preserved typed RF arming, source-off controls, power-level/attenuation gates, board identity checks and current-working-directory `SX1262-SDR.log` logging.
- Explicitly documented that **1.7/1.8 GPIO7 FEM power changes qualify all earlier RF measurements**, and that no SX1262 raw I/Q, 2.4 GHz unlock or calibrated off-band receive coverage is established.
- Retained GitHub Sponsors, Ko-fi and PayPal development-support links from `main`.

### Release status
- No firmware release package or calibrated receiver certification.
- Hardware firmware builds/flashes and original RF evidence came from the recorded local October 16–17 sessions. GitHub host CI validates Python tests, **not** a fresh ESP-IDF firmware build or real RF performance.
- Raw bench session artifacts are held in local results paths and/or REA records, not bundled in this repository.

## 2026-10-17 — Heltec V4.3 experimental modulation and front-end work

### Firmware 1.8: controllable onboard LNA
- Added optional bounded **auto/LNA** receive path selection for selected 88–108 MHz capture tests, tied to the V4.3 KCT8103L FEM.
- **Twelve RX-only captures / 96,000 records** compared bypass and enabled-LNA modes at 89.7, 98.1 and 99.1 MHz with 58.6 / 467 kHz GFSK filters.
- Reported total RSSI increased by **21.5–23.5 dB**. This is **not** a calibrated wanted-signal gain measurement and did not verify station audio.
- [Detailed LNA / GPIO7 report](docs/HELTEC_LNA_COMPARISON_2026-10-17.md).

### Firmware 1.7: front-end power provenance correction
- Enabled and verified V4.3 front-end regulator GPIO7 state before receiver experiments.
- Important limitation: firmware up to and including **1.6** did **not** explicitly drive or read back this rail. Historical tests have an **unknown**, not demonstrably off, FEM power state. Preserve their data and repeat critical results under known conditions.
- [Front-end qualification](docs/HELTEC_LNA_COMPARISON_2026-10-17.md).

### Firmware 1.6: experimental off-air FM-band captures
- Extended bounded RSSI capture testing across **88–108 MHz** and retained the 250.001 MHz control setting.
- Recorded **400 survey points and 30 one-second captures / 240,000 records** using an antenna, with Pluto transmission disabled. **No verified broadcast-FM station audio** was obtained.
- [Off-air FM record](docs/HELTEC_OFFAIR_FM_2026-10-17.md).

### Firmware 1.5: controlled AM/FM envelope experiments
- Added capture support for a programmed **250.001 MHz** receiver setting and host-side bounded modulation modes.
- **AM:** Five repetitions met predeclared criteria at **300, 1000 and 2500 Hz**, with carrier and source-off controls: **30 captures / 240,000 records**. Demonstrates detected amplitude-envelope response, not a general AM decoder.
- **FM filter slope:** Five selected-slope confirmations met criteria at **1000 and 2500 Hz**, with offset dependence and negative controls: **43 captures / 344,000 records**. Demonstrates experimental FM-to-RSSI-envelope response, **not** independently validated physical FM purity or a broadcast-FM decoder.
- [AM report](docs/HELTEC_AM_RESPONSE_2026-10-17.md) · [FM slope report](docs/HELTEC_FM_SLOPE_2026-10-17.md).

### Firmware 1.4: rapid RSSI capture
- Added bounded timestamped capture at **99.1 MHz** with 58.6 / 467 kHz filter options, CRC-protected records and device-derived envelope PCM.
- Captured **30,000 records** in RX-only loaded-input tests. Strict voice-rate test was **not** met; audio/fidelity and actual internal RSSI update bandwidth remain unverified.
- [Rapid RSSI report](docs/HELTEC_RAPID_RSSI_LOAD_2026-10-17.md).

## 2026-10-16 — First V4.3 firmware and physical RF bench

### Firmware 1.1–1.3: bring-up and receiver controls
- Implemented and flashed board-specific ESP-IDF firmware for the **Heltec V4.3**, with USB serial commands, LoRa/GFSK RX probing, device errors, RSSI and bounded TX arming.
- Added source-OFF PLL boundary surveys, source/LO offset testing, return-to-standby checks and conducted Pluto stimulus controls.
- Firmware **1.2** widened the *accepted RX probe-command floor* from 37 MHz to 1 MHz; **this did not prove sub-37 MHz reception**.
- Firmware **1.3** introduced 58.6 kHz and 467 kHz GFSK filter modes, beyond the narrow 4.8 kHz comparison mode.
- [V4.3 bench report](docs/HELTEC_V43_BENCH_2026-10-16.md) · [Lower band](docs/HELTEC_V43_LOWER_BAND_2026-10-16.md) · [99.1 MHz checks](docs/HELTEC_DIRECT_991_2026-10-16.md).

### Conducted RF findings
- Documented source-correlated responses at **200–250 MHz**, the **915 MHz** control and selected **1300/1400 MHz** settings.
- In recorded high-band probes (2400, 2450, 2624, 2700 and 3000 MHz), there was **no consistent, convincing source-dependent reception**. PLL/status outcomes were mode- and history-sensitive; a continuous upper tuning band was **not** established.
- Fixed-RX and LO/DDS split experiments characterized small apparent frequency offsets; identified source DDS quantization as an important contributor rather than claiming a calibrated SX1262 tuning error.
- A 99.1 MHz conducted experiment did **not** prove direct reception; Pluto FM relay audio was **Pluto-originated, not Heltec-demodulated**.
- [RF bench](docs/HELTEC_V43_BENCH_2026-10-16.md) · [Offset map](docs/HELTEC_V43_OFFSET_MAP_2026-10-16.md) · [Fixed RX record](docs/HELTEC_V43_FIXED_RX_2026-10-16.md) · [Pluto relay](docs/PLUTO_FM_RELAY_2026-10-16.md).

## 2026-10-16 — Initial research foundation

- Created the SX1262-SDR repository with a conservative measurement plan and synthetic/offline sweep parser.
- Consolidated the Grok test harness into **one authoritative live runner**: Pluto source, RTL reference, DUT serial profiles, simulation, plotting and CSV/JSON evidence.
- Added RF interlocks, negative source-OFF controls, logging, no-silent-overwrite protection, unit tests and the local research handoff.
- Established scientific evidence categories: **command accepted ≠ PLL locked ≠ RSSI observed ≠ external tone correlated ≠ frequency tracked ≠ calibrated sensitivity**.
- Published the original external research review and a test plan for the reported **1448–2622 MHz** apparent PLL gap. Other boards' published tuning claims were explicitly **not** treated as confirmed V4.3 results.
- [Research provenance](docs/RESEARCH_EVIDENCE.md) · [Test plan](docs/TEST_PLAN.md) · [Handoff](docs/HANDOFF.md).

---

### Evidence / reproduction conventions

Tests of radio behavior must preserve the **actual board revision, FEM configuration, firmware identity, source configuration, attenuation, controls, calibrated-vs-relative readings, raw logs and source-OFF outcome**. Host unit tests and synthetic passes are not hardware proof. Every harness run appends `SX1262-SDR.log` in the invocation directory; generated evidence stays in timestamped results directories. See [harness verification guidance](harness/VERIFY.md) and [RF safety](docs/SAFETY.md).
