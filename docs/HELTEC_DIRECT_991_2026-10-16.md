# Direct Heltec 99.1 MHz investigation — 2026-10-16

## Measured outcome

The user requested direct 99.1 MHz reception and on-device FM decoding. The
first prerequisite, source-correlated RF response, was not established at the
approved conducted drive/settings. **No Heltec audio was recovered.** No claim
is made that all direct reception at 99.1 MHz is impossible.

Three completed runner invocations, all exit 0, contain **74 real points**:

| GFSK filter | Firmware | Tested RX offsets per source | Largest ON-OFF rise at 99.1 MHz | Positive 250 MHz control |
|---|---|---:|---:|---:|
| 4.8 kHz | 1.2 | 19 | 0.5 dB | 26.5 dB |
| 58.6 kHz | 1.3 | 9 | 1.5 dB | 23.0 dB |
| 467 kHz | 1.3 | 9 | 0.5 dB | 17.0 dB |

Sources requested 99.101 and 250.001 MHz (existing GFSK runner's +1 kHz tone
offset), fixed Pluto gain -60 dB, same approved TX1 -> 30 dB pad -> cable ->
Heltec path. Nominal RX tunes 99.1/250 MHz plus bounded offsets within +/-337.5
kHz. The narrow grid checks 0 and both signs of 135/225/335 kHz with +/-2.5 kHz
neighborhoods. Wider grids check 0, +/-135/200/225/335 kHz.

Every complete point had valid RX/error responses, eight RSSI reads and quiet
OFF return. Samples remained `UNVERIFIED`: no independent output fundamental,
spectral purity or frequency-dependent input-power calibration. Values near
the RSSI floor cannot establish calibrated sensitivity or an absolute lower
tuning limit. The matching/FEM bypass and existing calibration policy remain
possible limitations. Source ON/OFF at 99.1 was uncorrelated, so that affected
conducted audio stage was stopped, rather than presenting noise as reception.

The two wider runs use the prior nominal 999844 Hz DDS request. Readbacks after
the previous relay changed the sample clock show a different DDS frequency
than in the earlier offset study. Do not assume the old -156.25 Hz correction
applies unchanged; raw per-point LO/DDS readbacks are preserved. No receiver
correction is installed.

## Firmware and host changes

Firmware **1.3** adds only bounded documented GFSK bandwidth choices, preserving
4.8 kHz as default and all RX/TX limits. Modes are `lora`, `gfsk`, `gfsk58`,
`gfsk467`; outputs report actual bandwidth. No PCM, raw I/Q or FM decoder was
added in this prerequisite stage. TX remains one armed packet at fixed chip
-9 dBm in 902-928 MHz.

The official Semtech driver enumerations specify 58.6 kHz=0x0C and 467 kHz=0x09:
[Semtech driver source](https://github.com/Lora-net/SWL2001/blob/master/lbm_lib/smtc_modem_core/radio_drivers/sx126x_driver/src/sx126x.h).
No upstream implementation was copied. Existing independent configuration was
extended by selecting those documented values.

Host interface: `--gfsk-probe --gfsk-bandwidth-hz 4800|58600|467000` on the single
`harness/run_sweep.py`. Bandwidth option without GFSK is refused. Profile identity
is now exactly 1.3; stale firmware still cannot pass live identity checks.

Archived 1.2 binary/source before mutation. Firmware 1.3 is 207,392 bytes,
SHA-256 `805bb48b716ff7a14d6e0b5bb657eb99c2a0e594125e91fc6f2e55bacf9e6151`.
ESP-IDF 6.0.2 exact build: `idf.py -C firmware/esp-idf build`, exit 0 after one
repair for a printf width/type mismatch. Both original and repaired build logs
are preserved. Esptool 5.3.1 command:

```powershell
python -m esptool --chip esp32s3 --port COM38 --baud 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 16MB --flash-freq 80m 0x10000 firmware/esp-idf/build/sx1262_sdr_heltec_v43.bin
```

Flash exit 0, hash verified. Only app0 was written. User's existing custom
firmware/flash authorization applies to this already-identified board. Live
identity and four mode checks passed after flash; no other COM port was flashed.

Exact targeted command:
`python -m pytest -q harness/tests/test_pluto_receiver.py harness/tests/test_unified_guardrails.py harness/tests/test_pluto_relay.py`
returned **30 passed**, exit 0. A new test first failed for unsupported wide
mode, then passed after implementation. The old positive identity fixture was
updated to 1.3. Full suites/Linux CI were not run; no merge-ready claim.

## Evidence and current state

Session: `harness/results/20261016-direct991-session/`, with preflight, archived
firmware, build/flash logs, exact source hashes, firmware checks, analysis/input
hashes and final shutdown. Raw run directories:

- `20261016-213045-696350_heltec-v43-direct991-offsets` — 38 points, firmware 1.2.
- `20261016-213408-671006_heltec-v43-direct991-bw58` — 18 points, firmware 1.3.
- `20261016-213435-372325_heltec-v43-direct991-bw467` — 18 points, firmware 1.3.

Raw manifests were verified and root `SX1262-SDR.log` appended. The wider runs'
inherited config contains the **old 1.2 image hash** in its metadata; that stale
field does not identify the actual flashed image. Firmware-check, flash log and
`firmware-v1.3-provenance.json` identify the actual 1.3 image. Preserve original
run metadata; the session provenance-correction sidecar records this discrepancy.

Independent final context read: Pluto TX powerdown=1, gain=-89.75 dB, DDS scales
all zero. Heltec info=1.3, 915 MHz LoRa status 0x52/errors 0, then successful stop.

Receive-only off-air check pending user physical change: disconnect the
attenuated source cable from Heltec and attach the monopole to its LoRa RF
connector. No further TX is needed for that stage. Do not attribute Pluto RX
audio to the Heltec. Firmware remains 1.3; no new commit/push/merge.
