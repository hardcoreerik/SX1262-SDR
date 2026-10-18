# Heltec V4.3 rapid RSSI capture with 50-ohm load — 2026-10-17

## Result

Custom firmware **1.4** collected **30,000** timestamped instantaneous RSSI
readings in eight bounded captures at programmed 99.1 MHz. The user reconfirmed
the nominal NanoVNA 50-ohm LOAD on the Heltec LoRa connector. The antenna and
Pluto TX cable remained disconnected; Pluto TX was disabled throughout.

This establishes a usable short-burst RSSI read path. It does **not** establish
FM decoding, internal RSSI measurement bandwidth, calibrated sensitivity,
frequency accuracy, or external reception at 99.1 MHz. Timestamps describe SPI
read completion on the ESP32 clock, whose accuracy was not independently measured.

| Filter | Requested reads/s | Records | Measured reads/s | Interval range, microseconds | Median RSSI, uncalibrated dBm |
|---|---:|---:|---:|---:|---:|
|58.6 kHz|1,000|1,000|1,000.009|991–1001|−122.5|
|58.6 kHz|2,000|2,000|2,000.000|499–501|−122.5|
|58.6 kHz|4,000|4,000|4,000.000|249–251|−122.5|
|58.6 kHz|8,000|8,000|7,999.968|121–130|−122.5|
|467 kHz|1,000|1,000|1,000.000|999–1001|−113.5|
|467 kHz|2,000|2,000|2,000.000|499–501|−114.0|
|467 kHz|4,000|4,000|4,000.000|249–251|−114.0|
|467 kHz|8,000|8,000|7,999.968|121–130|−113.5|

All intervals meet the selected +/-10% cadence tolerance, and all requested
records arrived with matching CRC32. Both 8k captures span 999,879 microseconds
between first and last completion timestamps: four microseconds longer than
the nominal 7,999 intervals. The prewritten strict `voice_timing_gate` requires
measured rate >=8,000 and consequently reports **false**, even at this small
difference. Original metadata and threshold are preserved; no post hoc pass.
The lower rates also report false because the same gate targets 8k voice timing.

Firmware computes fixed-gain, DC-blocked RSSI envelope PCM on the ESP32. All
30,000 PCM values were independently recomputed from saved raw RSSI and matched.
These are experimental envelope samples, **not recovered FM audio**. WAV files
use the explicitly named requested playback clock; raw timestamps are authoritative.
Nonidentical readings do not prove the internal RSSI estimator's update rate.

## Implementation and checks

`capture <58600|467000> <1000|2000|4000|8000>` is fixed to 99.1 MHz, samples
for at most one second before cleanup, clears any TX arm, and returns standby
before serial output. SPI timeout/cleanup may add wall time beyond the sample
window. It uses documented GFSK configuration and GetRssiInst; no raw I/Q,
undocumented registers, or new transmit mode. Firmware 1.3 sources/image were
preserved before editing. Only the app partition at 0x10000 was flashed.

Commands and outcomes:

```powershell
python -m pytest -q harness/tests/test_heltec_audio.py harness/tests/test_unified_guardrails.py harness/tests/test_pluto_receiver.py harness/tests/test_pluto_relay.py
# exit 0; 34 passed
idf.py -C firmware/esp-idf build
# exit 0; ESP-IDF 6.0.2, esp32s3, 209024-byte image
python -m esptool --chip esp32s3 --port COM38 --baud 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 16MB --flash-freq 80m 0x10000 firmware/esp-idf/build/sx1262_sdr_heltec_v43.bin
# exit 0; device write hash verified
python harness/run_sweep.py --heltec-audio --config harness/results/20261017-heltec-rapid-load-session/bench.json --profile heltec_v4_3_sx1262 --port COM38 --uri ip:fishball.local --label heltec-rapid-rssi-load50 --no-plot
# exit 0; eight real RX-only captures
```

Firmware image SHA-256:
`948997116614329f6fa6aea2d3f3389fe40cdaf3464f769860d500cbb11b3126`.
Source base is `841daf7` plus the archived local changes; this is not a clean
committed firmware build. Exact source hashes and copies are retained locally.
Fresh COM38 USB identity was VID 0x303A / PID 0x1001; firmware identified
HTIT-WB32LAF-V4.3 / KCT8103L. Final `stop` succeeded, Pluto `powerdown=1`,
all eight exposed DDS scales zero. No TX command was used.

Evidence directories, relative to repository root:

- `harness/results/20261017-heltec-rapid-load-session/`: archived sources,
  old/new images, build/flash logs, bench config, preflight and final shutdown.
- `harness/results/20261017-115316-674744_heltec-rapid-rssi-load50/`: full raw
  serial, binary packed records, CSV, experimental envelope WAV, metadata,
  and SHA-256 manifest. All 33 manifest entries were verified after capture.
- `SX1262-SDR.log`: appended runner/session log.

No Linux CI or full suite was run; merge readiness is not claimed.

## Next useful experiment

Use a known amplitude-modulated conducted source around the previously responsive
250 MHz region to measure **RSSI temporal response** against a known audio tone.
That distinguishes rapid SPI reads from actual audio-band measurement response.
It requires the operator to restore the attenuated TX1-to-Heltec cable before
TX can be enabled. A later antenna comparison at 99.1 MHz is still needed, and
would remain an RSSI envelope experiment until actual FM discrimination is proven.
Keep the LOAD installed until the next physical setup is agreed.
