# SX1262-SDR

**Heltec WiFi LoRa 32 V4 / Semtech SX1262 receive research** using an existing Pluto-compatible AD9361 SDR and RTL-SDR V4 as a test-reference platform. The goal is to determine real direct reception and synthesizer behavior across and outside the SX1262's supported 150–960 MHz range.

## Current state (2026-10-16)

**Heltec V4.3 firmware 1.2 is flashed and responds on COM38. Conducted LoRa RSSI tests show source-dependent responses at discrete frequencies including 200, 1300 and 1400 MHz. Upper-band reception is not demonstrated. Pluto RX capture is working.**

- Grok's `harness/` is our **single authoritative test runner**. ChatGPT's earlier `tools/analyze_sweep.py` remains a separate **offline file parser only**, never an alternative live control workflow.
- The unified runner performs Pluto tone-source control, RTL source cross-checks within its verified range, SX1262 RSSI / LR2021 IQ profile parsing, negative source-OFF controls, simulated failure injection, repetition, randomized order, and CSV/JSON evidence generation.
- The generic `sx1262_sdr_tbd` profile remains **simulation-only**. The Heltec V4.3 profile checks the expected firmware, board and FEM identity before RF phases.
- The user authorized bidirectional conducted TX/RX and explicitly approved bounded unfiltered receive checks using the established SSTV TX1/30 dB pad/1 ft SMA path. Full source-verified sweeps retain the filter/purity requirements; bounded exploratory checks stay UNVERIFIED. See [the bench record](docs/HELTEC_V43_BENCH_2026-10-16.md).

## Start here

- **[Local GPT Luna execution instructions](docs/LOCAL_SESSION_GPT_LUNA.md)** — full task prompt for a locally connected AI session, with hardware identity, permission and test milestones.
- **[Local quickstart](harness/LOCAL_QUICKSTART.md)** — PowerShell commands and expected outputs.
- **[Harness guide](harness/README.md)** — test implementation, profiles, simulator and measurement fields.
- **[Scientific verification checklist](harness/VERIFY.md)** — what makes a result trustworthy.
- **[Safety and RF constraints](docs/SAFETY.md)** — conditions before any Pluto transmit.
- **[Technical evidence](docs/RESEARCH_EVIDENCE.md)** — sources versus hypotheses.
- **[Lower-band experiments](docs/HELTEC_V43_LOWER_BAND_2026-10-16.md)** — controlled 200 MHz tracking and source-OFF sub-37 MHz observations.
- **[Current handoff](docs/HANDOFF.md)** — what exists, what is blocked, next engineering tasks.

## Quick no-hardware test (PowerShell, repository root)

```powershell
git pull --ff-only
python -m pip install numpy scipy matplotlib pytest
python -m pytest -q harness/tests
python -m unittest discover -s tests -v
python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot
```

Expected: automated tests pass; simulation creates a timestamped `harness/results/<run-id>_SIM/` directory containing `meta.json`, `run.log`, CSV files and classification evidence. The runner also appends **`SX1262-SDR.log` to the current working directory**. Synthetic and simulated results must not be represented as hardware findings. The root offline parser can additionally audit historical SXPROBE records:

```powershell
python tools/analyze_sweep.py examples/synthetic_sxp.csv --out results/synthetic_audit.json --origin synthetic
```

Use a different `--out` filename on repeat; offline results refuse overwrite.

## Research question

A [SAMS0N1TE SX1262 report](https://github.com/SAMS0N1TE/lr2021-sdr/blob/main/research/sx1262-range/README.md) describes an *individual LilyGO board* that reportedly locked near 37–1447 and 2624–3494 MHz, with a gap around 1448–2622 MHz. Its [actual probe code](https://github.com/SAMS0N1TE/LakeShark/blob/main/components/lakeshark/board/ls_lora_sx126x.c) measures device errors and RSSI but does **not** establish calibrated sensitivity or proven direct external-tone reception at every frequency. [Another SX1262 chirp experiment](https://github.com/ibelinp/SX1262_CHIRP) reports some lower off-band operation.

We will reproduce the edges on Heltec hardware and verify external signals with source-on/off, source frequency-shift and attenuation behavior. Heltec test TX is limited to the firmware's one-shot 902–928 MHz command.

**Acceptable result classes:** command accepted; PLL lock; RSSI observed; source-correlated response; independently tracked frequency; calibrated sensitivity (only after RF level calibration). These are NOT synonyms.

## Test system

```text
Pluto-compatible AD9361 TX OUT (disabled until preflight)
   -> user-reported 30 dB attenuator -> 1 ft SMA cable
   -> shielded/cabled Heltec V4 SX1262 RF input

Reverse direction uses Pluto RX1 and the integrated --heltec-tx capture path; receive streaming is verified, but no Heltec test packet has been transmitted.

RTL-SDR V4: independent source reference, only within validated RTL receive range
Pluto RX: integrated and streaming-tested; NOT an independently calibrated high-band reference
NewcorePC Windows: harness/run_sweep.py + serial device + persisted bench evidence
```

**No unattenuated TX-to-receiver connection. No intentional radiation of experimental out-of-band signals.**

## Repository layout

| Location | Ownership |
| --- | --- |
| `harness/run_sweep.py` | **Primary host orchestration** |
| `harness/dut_serial.py` / `harness/config/dut_profiles.json` | Console protocol / DUT |
| `harness/pluto_source.py` / `harness/rtl_reference.py` | RF source and limited-band reference |
| `harness/sim.py` / `harness/tests/` | Synthetic bench, regression |
| `harness/LOCAL_QUICKSTART.md` | Operator instructions |
| `firmware/` | ESP-IDF Heltec V4.3 bounded RX and one-shot TX adapter |
| `src/sx1262_sdr/` and `tools/analyze_sweep.py` | Offline legacy SXPROBE audit |
| `docs/` | RF safety, research evidence, REA/firmware handoff |

## Credits and limitations

The harness includes GPL-3.0-licensed components with a `harness/LICENSE` file and attribution to SAMS0N1TE's [LakeShark](https://github.com/SAMS0N1TE/LakeShark) and [lr2021-sdr](https://github.com/SAMS0N1TE/lr2021-sdr) investigations. Review licensing before extracting/reusing portions in other projects. Consult the maintained private [REA-Results](https://github.com/hardcoreerik/REA-Results) archive rather than altering generated reports manually.

**No SX1262 IQ stream, no successful 2.4 GHz unlock, no calibrated reception, and no authorized flash is implied by this repository.**
