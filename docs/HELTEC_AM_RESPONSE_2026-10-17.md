# Conducted AM response experiment — completed 2026-10-17

## Measured result

**All five repetitions completed and met the predeclared AM screen criteria.**
The operator confirmed TX1 -> reported30dB/10W/3GHz pad -> SMA cable -> Heltec,
antennas disconnected, and replied "Arm modulation." to the prepared arming
request. The runner received its exact `ARM MODULATION CHECK` interlock.
Full operator replies are retained in `operator-authorization.json`.

Thirty real captures contain **240000 records**, including five steady-carrier
controls, fifteen AM captures, and ten source-OFF controls. All CRCs matched;
122 entries in the original run manifest were independently rehashed. Every
device-generated PCM value was recomputed from the raw RSSI and matched.

| Commanded envelope tone | Repetitions | Median fitted RSSI amplitude | Minimum peak above nearby spectral floor | Minimum tone amplitude / source-OFF fit |
|---|---:|---:|---:|---:|
|300Hz|5/5|6.61dB|37.99dB|19.2x|
|1000Hz|5/5|6.59dB|38.49dB|30.3x|
|2500Hz|5/5|6.66dB|38.49dB|22.6x|

Fitted amplitude is in the logarithmic, uncalibrated RSSI scale. Spectral-floor
ratios are envelope-analysis quantities, **not calibrated RF SNR or sensitivity**.
Carrier median rise was12.5–17dB. Source-OFF returned to within2.5dB of each
repetition's starting median. All intervals met the+/-10% timing tolerance;
completion intervals spanned115–134microseconds, rates7999.968–8000.088reads/s.
The earlier strict `voice_timing_gate` remains a separate result; AM acceptance
uses complete records and the predeclared interval tolerance, not that flag.

This demonstrates **audio-frequency AM envelope response on this Heltec SX1262
configuration**, at a programmed250.001MHz receive setting with the conducted
Pluto stimulus. It does not independently verify the RF fundamental, full
temporal transfer function, arbitrary broadcast AM reception, FM discrimination,
raw I/Q, or direct99.1MHz reception. No absolute power calibration or independent
source-purity check was added. Repetition4's1kHz medianRSSI was3dB higher than
the other1kHz runs; its tone and controls still met thresholds. The response
amplitudes vary across runs; do not infer a calibrated flat passband.

First-repetition device PCM also has peaks near300/1000/2500Hz. The demonstration
WAV concatenates those **device-computed** samples with silence; no host FM
decoder or normalization is used. Playback uses the requested8kHz clock.

Run evidence:
`harness/results/20261017-145102-315210_heltec-am-response/`:
`modulation.json`, `verified-summary.json`, raw serial/binary/CSV/PCM WAVs,
`device-pcm-tone-check.json`, `am-response-controls.png`, and
`heltec-device-envelope-test-tones.wav`. A final post-analysis manifest adds
new derived artifacts without overwriting the original manifest.

The exact runner command below exited0. Independent final query confirmed
firmware1.5, Heltec stop acknowledged, Pluto powerdown1 and all eight exposed
DDS scales zero; see session `final-shutdown.json`. The conducted cable remains
connected; no antenna is attached. **TX is OFF.**

Next useful experiment: a known FM tone at the same programmed receiver setting,
then move the source across the GFSK filter slope while keeping Heltec RX fixed.
That can test FM-to-amplitude conversion before revisiting99.1MHz. It requires
a new bounded waveform/analysis implementation; it has not run.

## Prepared changes

Custom firmware **1.5** is flashed on the freshly identified COM38
HTIT-WB32LAF-V4.3 / KCT8103L. It extends the bounded capture command to exactly
99.1 or 250.001 MHz: `capture <99100000|250001000> <58600|467000> <1000|2000|4000|8000>`.
Other transmit permissions and limits are unchanged. App partition only at
0x10000; firmware1.4 sources/image preserved before edits.

ESP-IDF6.0.2 build and esptool flash both exited0; flash write hash verified.
Image209136bytes, SHA256:
`0a5d52ef43143cffdd28c94fa3bc197f423af60190d84482c5ab8a661e28fc00`.
Local source base `841daf7` plus archived dirty changes; no clean committed
firmware provenance is claimed. Firmware identity1.5 is required by the profile;
older installed versions fail identity checks.

Source-OFF preflight at250.001MHz/58.6kHz GFSK: probe valid, status0x52,
errors0. This is not independent PLL lock or reception evidence. Heltec stop
acknowledged; Pluto powerdown1. No source enable/TX command was issued.

## Fixed protocol

Use the existing single runner:

```powershell
python harness/run_sweep.py --heltec-modulation --arm-rf --config harness/results/20261017-heltec-am-response-session/bench.json --profile heltec_v4_3_sx1262 --port COM38 --uri ip:fishball.local --label heltec-am-response --no-plot
```

Five repetitions, each with source-OFF, steady carrier,300HzAM,1kHzAM,2.5kHzAM,
then source-OFF. Every receive capture requests8000 timestamped RSSI reads
over at most one second,58.6kHz filter,250.001MHz. Fixed ascending tone order
is diagnostic; this is not a randomized frequency-range acceptance test.

Pluto uses2500000samples/s cyclic DMA,100kHz baseband, LO249.901MHz,
fixed gain-60dB, and AM depth0.8. Peak DMA component<=12000. No broadcast
relay or HeltecTX is involved. A separate host timer requests source shutdown
after2seconds per active burst; serial timeout/exception also requests OFF.
This is a host safety timer, not a hardware RF watchdog. Source shutdown must
be read back after every burst. Driver readbacks/waveform construction do not
certify RF frequency, absolute output power or spectral purity.

Predeclared screen thresholds: complete8000-record CRC-valid capture;99% of
intervals within+/-10% cadence; carrier median rise>=6dB; modulation fit
amplitude>=1dB,>=3times source-OFF fit, and spectral peak>=10dB over nearby
floor. Source-OFF must recover within3dB. Stop the affected stage on failed
communications, device status, cadence, source correlation, or shutdown.
Fit modulation on actual timestamps, not an invented uniform sample clock.

This checks AM/RSSI envelope response, not FM discrimination, raw I/Q,
calibrated sensitivity, or99.1MHz reception. All PCM remains experimental.

## Checks and evidence

```powershell
python -m pytest -q harness/tests/test_heltec_audio.py harness/tests/test_unified_guardrails.py harness/tests/test_pluto_receiver.py harness/tests/test_pluto_relay.py
# exit0;38passed
idf.py -C firmware/esp-idf build
# exit0
python -m esptool --chip esp32s3 --port COM38 --baud 460800 --before default-reset --after hard-reset write-flash --flash-mode dio --flash-size 16MB --flash-freq 80m 0x10000 firmware/esp-idf/build/sx1262_sdr_heltec_v43.bin
# exit0
```

Local evidence: `harness/results/20261017-heltec-am-response-session/`, including
build/flash logs, source snapshots/hashes, old/new images, bench config,
firmware-check.json, and targeted-tests.log. Root `SX1262-SDR.log` appended.
No LinuxCI/full suite, push, commit, or merge in this step. RF results are recorded above.


### Later front-end power qualification

Firmware through1.6 did not explicitly drive the V4.3 front-end regulator enableGPIO7; its actual earlierrail state was not measured. Raw results above are retained, but do not establish behavior with confirmed powered front end. Firmware1.7 corrected initialization. See [provenance correction](HELTEC_LNA_COMPARISON_2026-10-17.md).
