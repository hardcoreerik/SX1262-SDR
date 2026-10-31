# Heltec direct off-air FM attempt — October 17, 2026 (Pacific)

## Current result: station reception unverified

The user removed the conducted cable from the Heltec and fitted the monopole
previously estimated at 27 inches. Location: Springfield-area ZIP 97477.
**Pluto TX remained OFF throughout this attempt.**

Four source-OFF surveys collected **400 RSSI points**: all 100 US FM channel
centers, forward/reverse, with 58.6 and 467 kHz GFSK filters. All rows reported
status 0x52 and zero device errors. This is not independent PLL lock evidence.
Thirty subsequent one-second antenna-only captures collected **240000 records**.
All CRCs and 121 original run-manifest entries were checked; every device PCM
value was recomputed from saved RSSI and matched.

Strong repeated energy occurred around 98 MHz, but **no recognizable station
audio has been established**. Narrow-filter 98.1 MHz readings were -91.5/-91.0
dBm in the two surveys; broad, variable energy extended across nearby channels.
At nominal 99.1 MHz readings were -112/-117 dBm. All RSSI units are uncalibrated.
Energy alone does not distinguish a broadcast from interference, images, or
an out-of-spec receiver artifact. Earlier controlled 99.1 MHz checks were
negative; the positive 250 MHz conducted slope result does not prove this path.

Captures covered 98.1 MHz, nearby slope settings, other persistent peaks and
local-station candidates including 89.7, 91.9 and 99.1 MHz. Most candidate
envelope spectra were noise-like. No host FM decoder or synthesized program
audio was substituted for device PCM.

An optional local Windows speech-recognition screen of eight candidates did
not produce reliable speech (maximum reported confidence about 0.03). The first
recognizer initialization used the wrong overload and failed; its empty JSON
does not represent a successful negative test. The corrected attempt is saved
separately. Short clips/recognition failure cannot prove that no station exists.

## Hardware and software

Custom firmware **1.6** now permits bounded rapid RX capture at 88–108 MHz,
retaining the 250.001 MHz test anchor. Other commands/TX restrictions are
unchanged. Firmware 1.5 source/image preserved before editing. Only the app
partition at 0x10000 was flashed on the freshly identified COM38 V4.3/KCT8103L.
Image: 209136 bytes, SHA-256:
`f2e42b74ae1ef9eb7b3bbcf773a6dc1de943c701b046710f17c30c4bae6c6e67`.
Firmware identity and rejection immediately below/above capture bounds checked.

Source base `841daf7` plus archived dirty changes; not a clean committed image.
Exact source snapshots/hashes retained. No main-branch edit, commit, push or merge.

Commands/outcomes:

```powershell
python -m pytest -q harness/tests/test_heltec_audio.py harness/tests/test_unified_guardrails.py harness/tests/test_pluto_receiver.py harness/tests/test_pluto_relay.py
# exit 0; 44 passed
idf.py -C firmware/esp-idf build
# exit 0; ESP-IDF 6.0.2, esp32s3
python -m esptool --chip esp32s3 --port COM38 --baud 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 16MB --flash-freq 80m 0x10000 firmware/esp-idf/build/sx1262_sdr_heltec_v43.bin
# exit 0; write hash verified
python harness/run_sweep.py --heltec-audio --offair-fm --config harness/results/20261017-heltec-offair-fm-session/capture-candidates.json --profile heltec_v4_3_sx1262 --port COM38 --uri ip:fishball.local --label heltec-offair-fm-candidates --no-plot
# exit 0; 30 real RX-only captures
```

Surveys used existing `--pll-only --gfsk-probe --gfsk-bandwidth-hz` with the two
filters and forward/reverse configurations; console commands/results are saved
in the session. No broad suite/Linux CI; merge readiness not claimed.

Independent final query: firmware 1.6, Heltec stop acknowledged, Pluto powerdown
1 and all eight exposed DDS scales zero. Monopole remains the last confirmed
Heltec connection; source cable disconnected.

## Evidence and next action

- `harness/results/20261017-heltec-offair-fm-session/`: preflight, four survey
  consoles/configs/rankings, old/new firmware, build/flash logs, target tests,
  exact source hashes and final shutdown query.
- Survey runs: `20261017-201449-641640_heltec-offair-fm58-forward`,
  `20261017-201547-356639_heltec-offair-fm58-reverse`,
  `20261017-201648-678546_heltec-offair-fm467-forward`,
  `20261017-201727-625229_heltec-offair-fm467-reverse`, under `harness/results/`.
- `harness/results/20261017-201914-745526_heltec-offair-fm-candidates/`: full
  serial/binary/CSV/device PCM WAVs, audio statistics, speech-analysis derivatives,
  original and post-analysis hash manifests. `offair-candidates-unverified.wav`
  concatenates three candidate device recordings without gain or normalization;
  **it is not a verified FM broadcast recording**.
- Root `SX1262-SDR.log` appended.

A finer 98.0–98.2 MHz slope capture is prepared in `fine-kugn-slope.json`.
Before collecting it, the operator was asked to move the board/attached monopole
away from the PC/USB hubs, keeping the antenna vertical, preferably near a window,
or report cable constraints. That placement response is pending. Nearby digital
interference is a hypothesis to test, not an established cause. The next hardware
capture must record the actual confirmed placement.

## Source checks

Local candidates verified from broadcasters: [KUGN 98.1 FM](https://www.kugn.com/),
[KLCC 89.7 FM](https://www.klcc.org/about-klcc),
[KRVM 91.9 FM](https://krvm.org/),
[99.1 The Beat](https://thebeatofeugene.com/). These identify targets, not received
stations. Channel grid from [47 CFR 73.201](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-C/part-73/subpart-B/section-73.201).
Heltec's [V4.3 FAQ](https://wiki.heltec.org/docs/devices/open-source-hardware/esp32-series/lora-32/wifi-lora-32-v4/frequently-asked-questions)
describes its 868/915 MHz hardware and optional, normally unpopulated SAW filters;
this does not establish the installed board's 100 MHz transfer function. No
board component modification or undocumented register write was made.
