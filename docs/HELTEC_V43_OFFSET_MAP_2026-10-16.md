# Heltec V4.3 frequency-offset investigation — 2026-10-16

## Findings

**494 new conducted points** support separating source error from receiver
correction. The earlier -1 kHz sampled peak difference on a 2.5 kHz grid did
not establish a -1 kHz receiver correction. Automatic correction remains off.

Five 500 Hz-grid repeats gave these interpolated response centers relative to
the programmed Pluto source:

| Programmed source | Median difference | Observed range |
|---|---:|---:|
| 200.001 MHz | -141 Hz | -483 to -115 Hz |
| 250.001 MHz | -207 Hz | -250 to -207 Hz |
| 315.001 MHz | -250 Hz | approximately -251 to -250 Hz |

The estimator subtracts OFF power in linear units, then takes the midpoint of
the half-power crossings. RSSI quantization is 0.5 dB. Repeated quantized curves
can produce identical interpolated centers; that does not establish sub-hertz
accuracy. The weak 200 MHz response varies more. Uncertainty is not calibrated.

A descriptive fit to the 200/315 MHz medians, with f in MHz, is
`c_observed_Hz = 49.7 - 0.95248*f_MHz`. The 250 MHz repetitions and new
225/275/330 MHz points were held out; largest center residual was about 214 Hz.
330 MHz is outside the endpoints. The fitted endpoint change is only 110 Hz,
less than the 500 Hz grid: **-0.95 ppm is not an established clock correction**.

## Source-side explanation and falsification

Read-only DDS auditing found a reported 30.72 MHz clock and these I/Q register
increments. Using the documented 16-bit DDS model `f_DDS = N*f_sample/65536`:

| DDS request | Increment | Predicted digital frequency | IIO frequency readback |
|---|---:|---:|---:|
| 1,000,000 Hz | 2133 / 0x0855 | 999,843.75 Hz | 999,859 Hz |
| 2,000,000 Hz | 4267 / 0x10AB | 2,000,156.25 Hz | 2,000,186 Hz |

The nominal DDS increment is 468.75 Hz. Current upstream Linux conversion also
forces the low increment bit and uses 65535 in its conversion, so its attribute
readback differs from the ideal digital calculation. TX LO readbacks were about
2 Hz below requests. These are register/driver observations and digital-domain
predictions, not independent measurements of physical RF frequency or clock
accuracy. The clone's entire HDL/kernel implementation is not certified.

Changing the DDS request 1 -> 2 MHz and lowering LO by 1 MHz holds the requested
RF frequency fixed but predicts a **+312.5 Hz generated-tone shift**. Measured
curve-center changes were +195 Hz at 200 MHz, +299 Hz at 250 MHz and +333 Hz at
315 MHz. The stronger two responses support this source-side explanation.
The predicted -156.25 Hz source contribution at the 1 MHz setting explains much
of the small observed offset; the residual is not a proven Heltec correction.

Primary explanatory sources: [ADI DDS documentation](https://analogdevicesinc.github.io/hdl/library/common/ad_dds/index.html)
and [ADI Linux driver](https://github.com/analogdevicesinc/linux/blob/main/drivers/iio/frequency/cf_axi_dds.c).
A source copy, URL and SHA-256 are preserved in the session folder. This current
upstream source is not asserted identical to the clone kernel. No upstream code
was copied into the new implementation.

Use the model `c_observed(f,mode,BW) ≈ a + b*f + e_source(LO,DDS)`;
subtract the source contribution before proposing receiver compensation.
Filter/image branches may need separate tables. Neither a table nor a small
clock correction forces operation inside a PLL unlock region.

## Controls, scope and evidence

- Same approved TX1 -> 30 dB, 10 W, 3 GHz pad -> 1 ft SMA -> Heltec path.
  Pluto gain stayed -60 dB. Source purity, input power and absolute frequency
  remain uncalibrated; all runner verdicts remain `UNVERIFIED`.
- COM38 identity matched HTIT-WB32LAF V4.3 / KCT8103L / firmware 1.2. No flash or
  firmware change. GFSK 4.8 kHz, XOSC, eight reads, 20 ms dwell; FEM bypass at
  these lower frequencies. Calibration policy unchanged. No Heltec TX.
- Five alternating forward/reverse repeats: 285 points. They were not five
  randomized repetitions. Temperature was not measured; no cold-start claim.
  Bandwidth and calibration policy were held fixed, not compared in this stage.
- Narrow +5 kHz source-shift pass: 57 points. Its three shifted responses were
  not fully bracketed; those centers were rejected and raw evidence retained.
- LO/DDS control: 57 points. Held-out 225/275/330 MHz run: 57 points.
- Wider paired fixed-grid control at 250.001/250.006 MHz: 38 points. Both used
  the identical absolute RX grid 249.994..250.012 MHz, 1 kHz spacing. Source
  movement +5,000 Hz; sampled peak movement +5,000 Hz; interpolated center
  movement +5,023 Hz. The extra 23 Hz is not an absolute accuracy claim.
- All ten live invocations returned exit 0: 494 points, 26 response curves,
  23 accepted centers. Every point includes OFF/ON/OFF and RX/status/error
  checks. The offline audit verified each completed run's evidence hashes.

Branch `ai/heltec-v4-rx-bringup`, HEAD/base
`9f9bfcfd2a5f3ec01e93c6bd14fc92c38a0d8b83` plus local edits. Start-of-stage fetch
showed HEAD equal to origin/main. Existing dirty files were preserved.

Session: `harness/results/20261016-offset-map-session/`. Raw runner folders:
`harness/results/*_heltec-v43-fine-offset-*`. Session artifacts include:

- `commands.ps1`, `wide-control-commands.ps1`: exact existing-runner commands,
  with RF arming, typed interlock, identity and attenuation guards retained.
- First run: `--receive-check --gfsk-probe --freqs 200,250,315`, offsets
  -3.5..+5.5 kHz in 0.5 kHz steps; same port/URI/arming/no-plot arguments as the
  command files; prior firmware-1.2 bench config and label `heltec-v43-fine-offset-forward-1`.
- `analysis.json`, `candidate-corrections.csv`, `input-sha256.json`, figures,
  read-only DDS snapshots, explanatory source provenance, preflight/shutdown
  logs, test output, harness source hashes and final SHA-256 manifest.
- `analyze_offsets.py` is offline only. Exact command:
  `python harness/results/20261016-offset-map-session/analyze_offsets.py`
  (exit 0). Numerical self-checks cover known centers, descending grids, weak
  responses and clipped responses. Root `SX1262-SDR.log` was appended.

The narrow harness change records driver LO/DDS frequency readbacks in each raw
probe's `source_state`, without relabeling requested CSV frequency as measured.
Other backends return no readback. No competing runner or automatic tuning was added.

Host command:
`python -m pytest -q harness/tests/test_pluto_receiver.py harness/tests/test_unified_guardrails.py`
returned **23 passed**, exit 0; includes the new quantization/readback regression.
Full suites and Linux CI were not run. No test-ready/merge-ready claim is made.

Final independent readback: Pluto TX LO powerdown=1, gain=-89.75 dB, all four
DDS scales zero. Heltec firmware 1.2 nominal 915 MHz probe returned status 0x52,
errors 0, then successful `stop`. Image SHA-256 remains
`71b283f50a2fde36df7558ce1fe7ad39ed319069f31c96b02aa915efb42954c9`.

Next: hold Heltec tuning fixed and walk the source frequency, then independently
verify the fundamental/clock before enabling compensation. Bandwidth/calibration
and measured-temperature comparisons remain unperformed. No commit, push, PR,
merge or firmware flash occurred in this stage.
