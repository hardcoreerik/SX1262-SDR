# Heltec V4.3 lower-band experiments — 2026-10-16

## Scope and controls

The user asked to examine the lower end and develop stronger evidence than the
existing upstream experiments. Used the established TX1 -> 30 dB pad -> cable
-> Heltec V4.3 path, COM38, unchanged firmware 1.1 (image SHA-256
`42E2F2CE63D095FD7B204635EDFDDAB401D40F7E9E437C7642BDCE2E65170855`).
Every measured point had OFF/ON/OFF probes. GFSK bandwidth was 4.8 kHz, XOSC
standby, eight RSSI reads, 20 ms dwell. Default center tests used a source
1 kHz above the nominal RX frequency. Drive remained at -80/-70/-60 dB;
offset scans used only -60 dB. Those conducted tests used no stronger source,
firmware change or undocumented register change. A subsequent RX-only firmware
extension and source-OFF survey are recorded separately below.

The existing runner now accepts `--rx-offsets-khz` only with
`--receive-check --gfsk-probe`. It permits <=19 signed offsets within +/-400 kHz,
<=3 source frequencies <=340 MHz, fixed -60 dB drive, and retains the RF arming,
identity, minimum attenuation, preflight and shutdown checks.

## Offset comparison

[LakeShark's published lower-band observations](https://github.com/SAMS0N1TE/lr2021-sdr/blob/main/research/sx1262-range/README.md)
motivated checking displaced responses. With an external fixed source at each
of 100.001, 169.401 and 315.001 MHz, receiver tuning sampled nominal center and
the +125..145 / +215..235 kHz windows at 2.5 kHz spacing: 19 offsets per source.

100 and 169.4 MHz showed no clear source-dependent response at those tested
settings. At 315 MHz, nominal tuning produced a 25.5 dB rise, while no sampled
displaced response exceeded 1 dB. This does not reproduce the stronger displaced
response reported on the other board under its settings; it does not rule out
other offsets, bandwidths, calibration states or signal levels.

## Lower response transition

At the strongest tested Pluto hardwaregain (-60 dB):

| Nominal RX | ON minus OFF RSSI |
|---|---:|
| 175 MHz | 0.5 dB |
| 180 MHz | 1.0 dB |
| 185 MHz | 3.0 dB |
| 190 MHz | 2.5 dB |
| 195 MHz | 5.0 dB |
| 200 MHz | 9.0 dB |
| 225 MHz | 20.5 dB |
| 250 MHz | 29.0 dB |
| 275 MHz | 25.5 dB |
| 290 MHz | 24.0 dB |
| 300 MHz | 25.0 dB |
| 315 MHz | 25.5 dB |
| 330 MHz | 26.0 dB |
| 350 MHz | 27.5 dB |

These are sampled responses at the chosen drive, not a hard lower tuning limit
or sensitivity curve. Source output/path loss are not calibrated by frequency,
and many background readings hit the chip's -127.5 dBm floor. The 200 MHz point
is within the SX1262's documented tuning range; this is not an extension below
the chip's datasheet range. Its relevance here is the 915 MHz Heltec RF path and
the controlled response experiment.

## Fixed-grid source-shift experiment at 200 MHz

Two independent runs used the identical nine-point absolute RX grid:
199.990000..200.010000 MHz, 2.5 kHz spacing. Pluto changed from 200.001000 to
200.006000 MHz at fixed -60 dB drive. The strongest sampled RX point moved
from 200.000000 MHz (+9 dB) to 200.005000 MHz (+8 dB): **5 kHz source shift,
5 kHz observed peak shift**. OFF controls returned near the floor.

The host checked the equality of the absolute RX grids from the saved CSVs.
Both source and receiver centers were not simply shifted together: the second
run adjusted its relative RX offsets to preserve that same absolute grid.
This strengthens source-dependent frequency-response evidence. Independent
source-spectrum verification is still missing, so fundamental-frequency RX,
image rejection, packet recovery and calibrated sensitivity remain unproven.
Formal exploratory verdicts remain UNVERIFIED.

![Lower-band response and fixed-grid tracking](../harness/results/20261016-lower-band-summary/lower-band-results.png)

The plot is a local artifact under ignored results; those files must accompany
this document when sharing it. Dashed connections are visual guides between
sampled points, not proof of continuous band coverage.

## Evidence and commands

All five hardware runs returned exit 0, with 117 completed points total:

| Run under `harness/results/` | Points |
|---|---:|
| `20261016-200407-481081_heltec-v43-lower-offsets` | 57 |
| `20261016-200552-653217_heltec-v43-lower-transition` | 30 |
| `20261016-200707-656131_heltec-v43-200mhz-track-a` | 9 |
| `20261016-200719-809899_heltec-v43-200mhz-track-b` | 9 |
| `20261016-200818-305768_heltec-v43-lower-bracket` | 12 |

Every complete run has raw serial/source logs, CSV, metadata and verified
`sha256.txt`. Analysis, input hashes, image and final shutdown are in
`harness/results/20261016-lower-band-summary/`. The root `SX1262-SDR.log` was
appended. The source-shift calculations come from those immutable measurements.

Representative exact options; each hardware invocation also supplied
`--arm-rf --port COM38 --uri ip:fishball.local --no-plot` and the session
`--config harness/results/20261016-heltec-v43-session/bench.json`:

```powershell
python harness/run_sweep.py --receive-check --gfsk-probe --freqs 175,200,225,250,275,290,300,315,330,350
python harness/run_sweep.py --receive-check --gfsk-probe --freqs 180,185,190,195
python harness/run_sweep.py --receive-check --gfsk-probe --freqs 200 --rx-offsets-khz=-10,-7.5,-5,-2.5,0,2.5,5,7.5,10
python harness/run_sweep.py --receive-check --gfsk-probe --freqs 200.005 --rx-offsets-khz=-15,-12.5,-10,-7.5,-5,-2.5,0,2.5,5
```

Host verification:
`python -m pytest -q harness/tests/test_pluto_receiver.py harness/tests/test_unified_guardrails.py`
returned **21 passed**, exit 0. The new regression checks that receiver tuning
changes while the source remains fixed, and checks unsupported-mode/frequency
rejection. The full host suite was not repeated for this narrow extension.

Final hardware readback: Pluto TX LO powerdown=1, gain=-89.75 dB, all four DDS
scales zero; Heltec passed a 915 MHz LoRa probe, then confirmed `stop`.
No commit, push, merge or Linux CI occurred.

## Removing the artificial 37 MHz firmware floor

Firmware 1.1 rejected requests below 37 MHz, the published boundary, so it
could not test a lower result. Its binary and source were archived first.
Firmware **1.2** changes that RX attempt floor to 1 MHz and updates the firmware
identity. TX is still limited to the same armed one-shot packet in 902-928 MHz.
The command range remains separate from guaranteed operating capability.

ESP-IDF 6.0.2 build returned exit 0. The 207,152-byte image SHA-256 is
`71b283f50a2fde36df7558ce1fe7ad39ed319069f31c96b02aa915efb42954c9`.
Esptool app0 write on COM38 returned exit 0 and verified the hash. Exact source,
image, build provenance and flash log are under
`harness/results/20261016-lower-synth-v12-session/`.

Pluto TX stayed OFF for both new surveys:

- `20261016-201419-210812_heltec-v43-below37-pll`: exit 0, 23 requests.
  Nominal 915 MHz control passed. Sampled 1, 5, 10, 15, 20, 25 and 30-36 MHz
  reported PLL error `0x0040` / status `0x3A`; 37-45 MHz returned RX status
  `0x52` / no device error in that pass.
- `20261016-201444-393315_heltec-v43-lower-pll-refine`: exit 0, nine requests
  at 36.1-36.9 MHz, 100 kHz spacing. 36.1/36.2 failed; 36.3 cleared; 36.4 failed;
  36.5-36.9 cleared. No further edge refinement was attempted after the
  non-monotonic result.

Thus one sampled clear-error RX state occurred below 37 MHz, at **36.3 MHz**,
but a stable minimum is not established. These are synthesizer observations,
not evidence of conducted reception below 37 MHz. With the current 1 MHz DDS
offset, the detected Pluto TX LO range only permits RF sources from about
47.875 MHz, so a different verified source/path is needed to test RX at 36 MHz.

After the identity/range extension, the same targeted host command returned
**22 passed**, exit 0. The new regression rejects the older firmware identity
and confirms that below-boundary surveys cannot call the source-enable method.
No Linux CI was run. The final device is firmware 1.2, restored to a checked
915 MHz probe and standby; final shutdown evidence is in the new session folder.

## Next experiments with the strongest value

1. Compare band-appropriate image calibration against the current 915-only
   calibration policy at 175/185/195/200 MHz, recording calibration errors
   separately from errors after frequency programming and RX. Keep drive fixed.
2. Compare documented 4.8 and 58.6 kHz GFSK filters and normal/boosted gain,
   with readback and restoration. Test whether any displaced peak changes with
   bandwidth. Do not treat an RSSI offset alone as an improvement in sensitivity.
3. Independently verify source frequency/power at the pad output, then recover a
   known externally generated FSK payload at a positive lower-band point. Payload
   recovery would establish useful reception more strongly than RSSI alone.

Those are proposals, not completed firmware changes. ESP-SDR's ESP32 Wi-Fi
receiver is a different RF path; comparing these SX1262 results with it as a
single receive-range contest would not be meaningful. The immediate opportunity
is better controlled evidence and usable operation on this Heltec hardware.
