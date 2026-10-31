# Fixed Heltec tuning / adjusted Pluto source — 2026-10-16

## Units: 156 Hz is an adjustment, not a receive frequency

**These tests did not receive an RF carrier at 156 Hz.** The fixed receiver
frequencies were **250.001 MHz and 315.001 MHz** (250,001,000 and 315,001,000 Hz).
The approximately 156 Hz quantity is a small change to the source frequency
around those RF carriers. It is not a new lower tuning limit, bandwidth or data rate.

Earlier lower-band experiments showed a clearer source-dependent RSSI response
at 200 MHz and weaker responses near 185-195 MHz. They showed no clear response
at 100/169.4 MHz under the tested settings. A clear-error synthesizer state near
36 MHz did not establish RF reception there. See the
[lower-band measurements](HELTEC_V43_LOWER_BAND_2026-10-16.md).

## Outcome

The previous findings were committed first as **841daf7** (`docs: record Heltec
offset measurements and Pluto DDS contribution`), three documentation/evidence
files. The broader existing bench changes remain in the working tree. No push,
PR or merge was performed.

The next bounded batch completed **228 real conducted points**, twelve runner
invocations, every exit code 0. All twelve response curves were bracketed,
source-OFF returns passed, and RX/status/error checks passed.

| Fixed programmed Heltec RX | Paired repeats | Median requested-source center shift, adjusted minus baseline | Predicted shift | Median pairwise difference on DDS-model axis |
|---|---:|---:|---:|---:|
| 250.001 MHz | 5 | -164 Hz | -156 Hz | -7 Hz |
| 315.001 MHz | 1 | -182 Hz | -156 Hz | -26 Hz |

The five 250 MHz requested-axis shifts range from -191 to -118 Hz. On the
modeled axis the five pairwise center differences range approximately -35 to
+39 Hz. These are interpolated curve-center estimates from a **250 Hz source
grid and 0.5 dB RSSI**, not demonstrated single-hertz physical accuracy.

This is a different control from the earlier experiment: receiver frequency
programming stays identical at every point and the source frequency changes.
Each firmware probe re-enters RX, so this is not a continuously held PLL test.

The approximately 156 Hz source adjustment produces the predicted direction
and scale of movement, while the modeled curves mostly overlap. This supports
the DDS contribution explanation without changing receiver firmware or applying
a receiver offset. It does not establish a new receive-range limit or absolute
frequency calibration.

## Adjustment and assumptions

The audited DDS has reported clock 30.72 MHz and I/Q increment 2133. Under the
16-bit DDS model its digital tone is `2133 * 30720000 / 65536 = 999843.75 Hz`.

- Baseline config: DDS request 1,000,000 Hz; LO request = desired RF - 1,000,000.
  Predicted DDS contribution to source error: -156.25 Hz.
- Adjusted config: DDS request 999,844 Hz, selecting the same increment; LO
  request = desired RF - 999,844. Predicted contribution: -0.25 Hz.
- Thus LO moves +156 Hz; the requested-source center should move -156 Hz for
  fixed receiver tuning. Actual per-point LO readbacks are used in the modeled
  frequency axis to retain driver rounding differences.
- IIO I/Q DDS frequency attributes remained 999,859 Hz at every point; read-only
  register audits confirmed increment 2133 before/during/after the batch.
- Model-axis frequency is `LO_readback + 999843.75`. It remains a prediction at
  a nominal clock, not an independently measured RF frequency. Driver DDS
  frequency readback is stored separately and not treated as the exact digital
  tone. These settings are specific to the audited bench configuration.

Residual receiver corrections versus this model, pooled over configurations,
are approximately -50 Hz at 250 MHz and -79 Hz at 315 MHz. Their size is below
the source-grid spacing and absolute source accuracy remains unverified. They
are candidate observations, not approved automatic compensation values.

## Method and safety

- Identified COM38 HTIT-WB32LAF V4.3 / KCT8103L, firmware 1.2 unchanged. No flash.
- Same approved conducted TX1 -> 30 dB, 10 W, 3 GHz pad -> 1 ft SMA -> Heltec.
  Source drive fixed -60 dB; no Heltec TX or cable change.
- GFSK 4.8 kHz, XOSC standby, eight RSSI reads, 20 ms dwell; FEM bypass and
  calibration policy unchanged. Each point is OFF/ON/OFF with valid status/errors.
- Nineteen source settings span +/-2250 Hz about fixed RX, 250 Hz spacing.
  The runner's listed base frequencies are source RF minus 1 kHz.
- Five baseline/adjusted pairs at 250 MHz: 190 points. Source ordering alternates
  ascending/descending; final pair uses seeded shuffled order (1262). Pair order
  also alternates to reduce warm-up bias. This is not a measured-temperature test.
- One baseline/adjusted validation pair at 315 MHz: 38 points, not a repeatability
  claim at that frequency.
- No independent source-purity, absolute frequency or power calibration; all
  runner verdicts stay `UNVERIFIED`. No packet-demodulation proof or new PLL window.

## Narrow implementation and verification

The existing `harness/run_sweep.py` now accepts `--fixed-rx-mhz` only with
`--receive-check --gfsk-probe`, no simultaneous RX offsets. It caps source count
at 20, source/RX at 340 MHz, separation at 400 kHz and drive at -60 dB. Existing
arming, typed interlock, attenuation, identity and shutdown checks remain active.
Metadata explicitly records `fixed_rx_hz`, `scan_axis=source-frequency`, requested
source frequency, raw serial data and source LO/DDS readbacks.

Exact host command:
`python -m pytest -q harness/tests/test_pluto_receiver.py harness/tests/test_unified_guardrails.py`
returned **24 passed**, exit 0. The new regression verifies fixed RX, changing
source, fixed drive and invalid-mode/span rejection. Its first attempt failed
because the simulator used the stock Pluto range; the fixture was corrected to
the detected clone range before the passing run. Full suites and Linux CI were
not run. No test-ready/merge-ready claim is made.

Exact live invocations and experiment plan:
`harness/results/20261016-fixed-rx-source-session/commands.ps1` and `plan.json`.
Every invocation uses the existing runner, explicit `--arm-rf`, confirmed typed
interlock, COM38/`ip:fishball.local`, matching baseline/adjusted JSON and
`--fixed-rx-mhz 250.001` or `315.001`. No competing runner was introduced.

Offline audit command:
`python harness/results/20261016-fixed-rx-source-session/analyze_fixed_rx.py`
returned exit 0. Numerical checks include known centers, descending/shuffled
order handling and clipped-response rejection. Input hash, fixed-tuning,
status/error and matching-DDS assertions passed. Root `SX1262-SDR.log` appended.

## Evidence and final state

Session folder `harness/results/20261016-fixed-rx-source-session/` contains
analysis JSON, comparison CSV, figure, exact configs/commands/plan, preflight,
read-only DDS audit, host-test record, input hashes, source hashes and final
session SHA-256 manifest. Raw run folders are listed in `run-index.json`.
Raw captures remain local and are not added to Git.

Final independently opened source check: TX LO powerdown=1, gain=-89.75 dB,
all four DDS scales zero. Heltec still reports firmware 1.2; 915 MHz LoRa probe
returned status 0x52/errors 0, followed by successful `stop` and closed serial.

The first findings commit is complete. This stage's harness extension and new
results report are uncommitted. Absolute calibration, filter/calibration-mode
comparisons and known packet recovery remain open experiments.

## Next planned test: lower-band filter/image comparison

**Plan only; no new RF test or firmware change has been run for this section.**
Question: is missing lower-band response partly a displaced filter/image
response, rather than lack of synthesizer operation or a small clock error?
The measured approximately 156 Hz source contribution is much smaller than the
published 135-335 kHz displaced responses; they need separate controls.

1. Add a bounded choice of documented 4.8/58.6 kHz GFSK bandwidths to the same
   firmware/profile/runner. Record the selected bandwidth and errors. Build the
   exact board target and run targeted parser/guardrail checks before flashing.
   Hold RX gain, FEM policy, calibration policy, dwell and source drive constant
   so this first comparison changes bandwidth alone. Keep TX bounds unchanged.
2. Validate both widths at the strong 250 MHz control first. Then survey
   169.4, 185 and 200 MHz with the adjusted source configuration and per-point
   LO/DDS readbacks. Use the same approved pad/cable and fixed -60 dB drive.
   For 4.8 kHz, sample RX offsets around 0, +/-135 and +/-225 kHz, each at
   center and +/-2.5 kHz (15 offsets). For 58.6 kHz, sample 0, +/-135, +/-200,
   +/-225 and +/-335 kHz (9 offsets). Split calls to retain existing count limits.
   This is a bounded 96-point first survey over the four RF frequencies.
3. Refine any promising displaced peak, then repeat it at least five times.
   Shift the source with an unchanged absolute RX grid, choose a source shift
   resolvable at that bandwidth, and compare -70/-60 dB drive. Require valid
   RX/status/errors and OFF/ON/OFF correlation. Stop on inconsistent PLL/error
   behavior or source shutdown failure. Check source fundamental/purity with an
   independently verified reference before upgrading the evidence label.
4. Compare peak position across bandwidths. A large offset that moves with
   bandwidth supports a filter/image explanation; a small smooth offset can be
   considered for a clock model. No response remains limited to this board,
   path, drive and calibration policy. It is not proof of an absolute chip limit.

Keep automatic receiver correction disabled. No new source-power increase or
claim of raw I/Q is part of this plan. Testing actual reception near the
approximately 36 MHz synthesizer edge needs another verified source arrangement;
the present DDS/Pluto setup cannot supply that RF carrier.

The original report matching the completed session's recorded source hash is
preserved at `harness/results/20261016-fixed-rx-report-clarification/original-report.md`.
This units clarification and plan are subsequent documentation, not additions
to the completed batch's raw measurements.
