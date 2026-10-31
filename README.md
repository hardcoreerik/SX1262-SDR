# SX1262-SDR

**Heltec WiFi LoRa 32 V4 / Semtech SX1262 receive research** using an existing Pluto-compatible AD9361 SDR and RTL-SDR V4 as a test-reference platform. The goal is to determine real direct reception and synthesizer behavior across and outside the SX1262's supported 150–960 MHz range.

## Current state (2026-10-16)

**Unified host harness: implemented and simulation-tested. Heltec receive-only firmware: not yet implemented. Real Heltec/Pluto RF experiment: NOT RUN.**

- Grok's `harness/` is our **single authoritative test runner**. ChatGPT's earlier `tools/analyze_sweep.py` remains a separate **offline file parser only**, never an alternative live control workflow.
- The unified runner performs Pluto tone-source control, RTL source cross-checks within its verified range, SX1262 RSSI / LR2021 IQ profile parsing, negative source-OFF controls, simulated failure injection, repetition, randomized order, and CSV/JSON evidence generation.
- The SX1262's `sx1262_sdr_tbd` profile is **intentionally simulation-only**. No live firmware can be tested until the correct Heltec revision, FEM and console protocol are established.
- Every live test requires a physical attenuated/filtered **conducted** setup. The Pluto source is not automatically authorized merely because a user asked to execute the project.

## Start here

- **[Local GPT Luna execution instructions](docs/LOCAL_SESSION_GPT_LUNA.md)** — full task prompt for a locally connected AI session, with hardware identity, permission and test milestones.
- **[Local quickstart](harness/LOCAL_QUICKSTART.md)** — PowerShell commands and expected outputs.
- **[Harness guide](harness/README.md)** — test implementation, profiles, simulator and measurement fields.
- **[Scientific verification checklist](harness/VERIFY.md)** — what makes a result trustworthy.
- **[Safety and RF constraints](docs/SAFETY.md)** — conditions before any Pluto transmit.
- **[Technical evidence](docs/RESEARCH_EVIDENCE.md)** — sources versus hypotheses.
- **[Current handoff](docs/HANDOFF.md)** — what exists, what is blocked, next engineering tasks.

## Quick no-hardware test (PowerShell, repository root)

```powershell
git pull --ff-only
python -m pip install numpy matplotlib pytest
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

We will reproduce the edges on Heltec hardware, attempt falsifiable RX-only calibration/sequence variations, and separately verify each external RF tone with controlled source-on/off, source frequency-shift and attenuation behavior.

**Acceptable result classes:** command accepted; PLL lock; RSSI observed; source-correlated response; independently tracked frequency; calibrated sensitivity (only after RF level calibration). These are NOT synonyms.

## Test system

```text
Pluto-compatible AD9361 RF OUT (disabled until authorized)
   -> verified filter -> verified fixed attenuation -> optional step attenuation
   -> shielded/cabled Heltec V4 SX1262 RF input

RTL-SDR V4: independent source reference, only within validated RTL receive range
Pluto RX: potential high-band reference, NOT yet integrated or validated
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
| `firmware/` | Future ESP-IDF board-specific RX-only code |
| `src/sx1262_sdr/` and `tools/analyze_sweep.py` | Offline legacy SXPROBE audit |
| `docs/` | RF safety, research evidence, REA/firmware handoff |

## Credits and limitations

The harness includes GPL-3.0-licensed components with a `harness/LICENSE` file and attribution to SAMS0N1TE's [LakeShark](https://github.com/SAMS0N1TE/LakeShark) and [lr2021-sdr](https://github.com/SAMS0N1TE/lr2021-sdr) investigations. Review licensing before extracting/reusing portions in other projects. Consult the maintained private [REA-Results](https://github.com/hardcoreerik/REA-Results) archive rather than altering generated reports manually.

**No SX1262 IQ stream, no successful 2.4 GHz unlock, no calibrated reception, and no authorized flash is implied by this repository.**

## Support development

If this project is useful to you, consider supporting its development. Across ORC projects, support helps fund development time, hardware testing, receiver compatibility, and decoder work.

[GitHub Sponsors](https://github.com/sponsors/hardcoreerik) · [Ko-fi](https://ko-fi.com/hardcoreerik) · [PayPal](https://paypal.me/hardcoreerik)
