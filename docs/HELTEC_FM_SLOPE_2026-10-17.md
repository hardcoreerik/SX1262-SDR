# Heltec conducted FM slope test — 2026-10-17

## Measured result

**The selected slope recovered both known FM tones in five of five confirmations.**
The runner exited0 with43captures/344000records. Original174artifact hashes,
all capture CRCs and all device-generated PCM values were independently checked.
Firmware stayed1.5; the host does not run an FM decoder on these audio files.

The centered1kHzFM signal had0.023dB fitted1kHz RSSI amplitude and did not meet
the screen thresholds. Moving the source to-30kHz relative to fixed Heltec RX
gave5.87dB; the+30kHz side gave5.40dB. This offset dependence supports filter
slope conversion in the conducted setup. It is not an independent proof that
all conversion occurs inside SX1262, because source/path incidental AM was
not measured with an independent receiver.

| Source offset | Carrier median RSSI, uncalibrated | FM1kHz fitted amplitude | Screen result |
|---|---:|---:|---|
|-40kHz|-121.5dBm|not run|carrier below6dB rise threshold|
|-30kHz|-113.5dBm|5.87dB|pass, selected|
|-20kHz|-109.0dBm|0.90dB|below1dB amplitude threshold|
|-10kHz|-106.5dBm|1.05dB|pass|
|0|-105.5dBm|0.023dB|no qualifying fundamental tone|
|+10kHz|-106.5dBm|1.13dB|pass|
|+20kHz|-109.0dBm|0.90dB|below1dB amplitude threshold|
|+30kHz|-113.5dBm|5.40dB|pass|
|+40kHz|-122.0dBm|not run|carrier below6dB rise threshold|

The screen was not monotonic; do not infer a calibrated transfer function from
these nine offsets. The same amplitude threshold was retained throughout.

Selected source is nominal249.971MHz; RX remains250.001MHz. Five repeated
confirmations at that setting:

| FM tone | Passing repeats | Median RSSI tone amplitude | Minimum peak above nearby envelope spectral floor | Minimum amplitude / source-OFF and carrier controls |
|---|---:|---:|---:|---:|
|1000Hz|5/5|5.94dB|39.65dB|36.7x|
|2500Hz|5/5|5.61dB|40.14dB|57.3x|

These floor ratios describe the envelope spectrum, **not calibrated RF SNR**.
All completion intervals were121–130microseconds, within+/-10% of125us.
Measured average rate7999.968reads/s on the ESP32 clock; complete8000-record
bursts. The strict old>=8000 voice timing flag remains separate and false here.
Source-OFF controls recovered within3dB; final powerdown1 and all eight exposed
DDS scales0 independently confirmed, Heltec stop acknowledged. Conducted cable
remains connected, no antenna; **TX OFF**.

Artifacts:
`harness/results/20261017-150341-600633_heltec-fm-slope/` includes
`fm-slope.json`, `verified-summary.json`, complete serial/binary/CSV/PCM captures,
`fm-slope-screen.png`, `device-pcm-tone-check.json`, and
`heltec-fm-center-then-slope-tones.wav`. Demo sequence: centered1kHzFM, then
selected-slope1kHzFM, then selected-slope2.5kHzFM. PCM is computed on the ESP32;
the concatenated clip has no host decoding, amplitude normalization or gain.
Original manifest preserved; post-analysis manifest hashes derived additions.

This is a repeatable **FM-to-RSSI/audio response in this conducted setup**.
It does not demonstrate full broadcastFM bandwidth/deviation, speech quality,
independent RF-frequency accuracy, pure physicalFM, arbitrary tuning, or direct
99.1MHz reception. Absolute power and source purity remain UNVERIFIED.

Next useful stage: test the same controlled response around99.1MHz, starting
with source-OFF/carrier controls. Prior direct99.1MHz source checks were negative;
the250MHz slope result does not establish a working99.1MHz RF path.

## Protocol

Firmware1.5 unchanged, fixed RX250.001MHz/58.6kHz GFSK/8000RSSIreads/s.
Same user-confirmed conducted TX1->reported30dB10W3GHz pad->1ftSMA cable->Heltec,
no antennas. User requested moving to the next FM test. No flash in this step.

Generate constant digital envelope at100kHzIF,5kHz peak FM deviation,12000
maximum DMA component. Sample clock2.5MHz; digital amplitude ripple from
integer quantization<1.5/12000. This is **not a physical RF AM/purity measurement**.
Pluto gain-60dB; independent host timer requests shutdown after2seconds per
burst, with checked powerdown after each capture and on error. The host timer
is not a hardware RF watchdog.

Screen source carrier offsets0,-10,+10,-20,+20,-30,+30,-40,+40kHz while keeping
Heltec RX fixed. At each eligible offset compare steady carrier with1kHz FM;
include source-OFF before/after the screen. Only offsets whose carrier raises
RSSI>=6dB over source-OFF receive an FM screen. These deliberately negative
screen outcomes are recorded, not presented as positive reception evidence.

Predeclared FM screen: complete CRC-valid8000records,>=99% read intervals
within+/-10%; expected-tone fit amplitude>=1dB on logarithmic RSSI scale,
>=3times both source-OFF and same-offset steady-carrier fits, spectral peak
>=10dB above local floor. Select largest passing fit, then five repetitions
of source-OFF, same-offset carrier,1kHzFM,2.5kHzFM, source-OFF. Stop confirmation
on any failed tone/control, communication, cadence, or shutdown check.
Source-OFF must return within3dB of its preceding baseline.

Selection is exploratory; confirmations follow selection, not a preregistered
independent validation split. Readings use the ESP32 timestamp clock, not an
independently calibrated clock. No shared source/ESP32 phase reference exists,
so opposite-flank phase inversion cannot be claimed. Even positive FM response
in this setup cannot isolate SX1262 filter conversion from incidental source/path
AM without a suitable independent RF reference. No99.1MHz/broadcastFM proof.

## Commands and evidence

```powershell
python -m pytest -q harness/tests/test_heltec_audio.py harness/tests/test_unified_guardrails.py harness/tests/test_pluto_receiver.py harness/tests/test_pluto_relay.py
# exit0;41passed
python harness/run_sweep.py --heltec-modulation --fm-slope --arm-rf --config harness/results/20261017-heltec-fm-slope-session/bench.json --profile heltec_v4_3_sx1262 --port COM38 --uri ip:fishball.local --label heltec-fm-slope --no-plot
```

Runner retains typed `ARM MODULATION CHECK`, RF-arm flag, minimum attenuation,
exact firmware/board/FEM checks, source-OFF and standby cleanup. Pure waveform
tests check FM instantaneous deviation and constant envelope; cleanup tests
cover bothAM/FM source context failures. No firmware build or broad suites.
No LinuxCI, commit, push or merge in this step.

Session artifacts: `harness/results/20261017-heltec-fm-slope-session/`, including
pre-change snapshots, current source/hashes, bench config, operator-context,
targeted test log and runner console. Raw run outputs remain ignored local
evidence. Root `SX1262-SDR.log` is appended by the runner.
