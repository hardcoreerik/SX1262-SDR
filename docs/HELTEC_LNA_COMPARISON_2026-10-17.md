# Heltec built-in LNA comparison — October 17, 2026 (Pacific)

## Result

The approved **12 RX-only captures completed**, comparing bypass with the
documented KCT8103L receive-LNA state, at 89.7, 98.1 and 99.1 MHz and two filters.
The relocated vertical monopole remained on the Heltec; its conducted cable
was disconnected. **Neither radio transmitted.**

| Programmed RX | GFSK filter | Bypass RSSI | LNA RSSI | Reported level change |
|---|---|---:|---:|---:|
|89.7 MHz|58.6 kHz|−111.0|−88.0|+23.0 dB|
|89.7 MHz|467 kHz|−102.5|−79.0|+23.5 dB|
|98.1 MHz|58.6 kHz|−92.5|−69.0|+23.5 dB|
|98.1 MHz|467 kHz|−82.0|−60.5|+21.5 dB|
|99.1 MHz|58.6 kHz|−110.0|−88.0|+22.0 dB|
|99.1 MHz|467 kHz|−101.0|−79.5|+21.5 dB|

RSSI values are uncalibrated dBm readouts. **This is a change in reported total
level, not a calibrated measurement of wanted-signal gain or noise figure.**
The LNA state produced higher levels, but no recognizable broadcast audio has
been established. The 89.7/99.1 MHz envelope spectra remained close to noise-like
flatness in both modes. The optional local speech screen yielded low-confidence
fragments (maximum about0.24), not a reliable transcript or station identity.
One sample per setting is exploratory and does not establish repeatability.

All 96000 records were CRC-valid. All 49 entries in the original artifact
manifest were rehashed; every device PCM value was independently recomputed
from raw RSSI and matched. Device audio is experimental RSSI envelope PCM,
not raw I/Q. No host FM decoder or program-audio substitution was used.

The highest-value next diagnostic is a known conducted signal near98 MHz,
with the now-explicit front-end power and LNA controls, to distinguish a usable
FM-band signal path from amplified noise or interference. That needs physical
recabling with TX OFF before any source enable. No such test has run in this batch.

## Firmware and safety boundaries

Firmware **1.8** adds an optional capture RX-mode argument:
`capture <frequency_hz> <58600|467000> <1000|2000|4000|8000> <auto|lna>`.
Default `auto` retains bypass outside860–930 MHz. Forced `lna` is bounded to
88–108 MHz; it is rejected at the250.001 MHz anchor. Requested mode is recorded
and checked against each capture response. These GPIO settings are documented
receive states; the LNA's off-band gain, noise and linearity are unverified.

FEM regulator enable GPIO7 remains high, CSD GPIO2=1; CTX GPIO5=1 for FM-band
bypass or0 for forced receive LNA. SX1262 DIO2 controls CPS and stays in receive
state during the capture. No PA register or transmit command was added. Each
capture clears the one-shot TX arm and returns SX1262 to standby before dumping.
The existing stop command restores its default front-end setup.

Firmware1.7 and its sources were preserved before editing. Fresh COM38 USB
identity was checked before flashing. Only the app partition at0x10000 changed.
ESP-IDF6.0.2/esp32s3 final build and esptool flash both exited0; write hash verified.
Image209520bytes, SHA256:
`783bff501a09064c694126515667200bbabbbe261e38b3fca167d6e28bd4961e`.
Source base `841daf7` plus archived local changes, not a clean committed image.

```powershell
python -m pytest -q harness/tests/test_heltec_audio.py harness/tests/test_unified_guardrails.py harness/tests/test_pluto_receiver.py harness/tests/test_pluto_relay.py
# exit0;46passed
idf.py -C firmware/esp-idf build
# exit0; final exact source/image archived
python -m esptool --chip esp32s3 --port COM38 --baud 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 16MB --flash-freq 80m 0x10000 firmware/esp-idf/build/sx1262_sdr_heltec_v43.bin
# exit0
python harness/run_sweep.py --heltec-audio --offair-fm --config harness/results/20261017-heltec-lna-comparison-session/bench.json --profile heltec_v4_3_sx1262 --port COM38 --uri ip:fishball.local --label heltec-fm-lna-comparison --no-plot
# exit0; exactly12captures
```

No LinuxCI/full suite, commit/push/merge or additional firmware experiment.
Final independent query confirmed firmware1.8, GPIO7 enable readback1, Heltec
stop acknowledged, Pluto powerdown1 and all eight exposed DDS scales zero.

## Provenance correction for previous tests

While checking the official V4.3 schematic, firmware through1.6 was found not
to explicitly drive the front-end regulator enable GPIO7. Firmware1.7 corrected
that and required a high enable-pin readback in the profile. Actual rail voltage
was not measured, so **do not assume the earlier rail was necessarily OFF**.
Earlier raw captures remain valid records of their setup; their front-end power
state was uncontrolled. They do not establish performance with a confirmed
powered front end. This qualification also applies to earlier250MHz AM/FM tests.
The subsequent1.7 powered receive captures still did not verify a broadcast.

## Evidence

- `harness/results/20261017-heltec-lna-comparison-session/`: operator approval,
  preserved1.7 sources/image,1.8 source hashes/image, build/flash/test logs,
  firmware/boundary checks, bench config and final shutdown.
- `harness/results/20261017-204453-497114_heltec-fm-lna-comparison/`: original
  serial/binary/CSV/device PCM, `offair.json`, `verified-comparison.json`, audio
  statistics and speech-screen outputs. Original hashes preserved separately
  from post-analysis hashes. `981-bypass-then-lna-unverified.wav` contains the
  two device recordings without normalization and is not verified station audio.
- `SX1262-SDR.log`: appended session/runner/analysis records.

Hardware mapping source: [Heltec board definitions](https://github.com/HelTecAutomation/Heltec_ESP32/blob/master/src/driver/board-config.h)
and [official V4.3 schematic](https://resource.heltec.cn/download/WiFi_LoRa_32_V4/Schematic/HTIT-WB32LAF_V4.3.pdf).
No upstream implementation was copied; existing harness/firmware licensing retained.
