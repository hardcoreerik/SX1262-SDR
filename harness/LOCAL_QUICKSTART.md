# Local Quickstart — ONE SX1262-SDR harness

The operator's detailed task description is at [../docs/LOCAL_SESSION_GPT_LUNA.md](../docs/LOCAL_SESSION_GPT_LUNA.md). **This repo is host-simulation-ready, not yet live-Heltec-ready.** The placeholder `sx1262_sdr_tbd` refuses to operate real radios by design.

## 0. Update safely on NewcorePC (PowerShell)

```powershell
# If the repository already exists on this PC, use its actual directory instead:
cd <YOUR_SX1262-SDR_REPO_DIRECTORY>
git status --short
git branch --show-current
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse --short HEAD
```

**Do not literally run the placeholder `cd <...>` line.** If there is no checkout yet, run `git clone https://github.com/hardcoreerik/SX1262-SDR.git`, then `cd SX1262-SDR`. If there are preexisting local changes, do not discard them; create a separate worktree/branch after review. The local AI should work in an `ai/<topic>` branch, not main.

## 1. Host-only dependencies and tests — safe, no physical RF

```powershell
python --version
python -m pip install numpy matplotlib pytest
python -m pytest -q harness/tests
python -m unittest discover -s tests -v
python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot
```

The `--sim` run should generate `harness/results/<timestamp>_*_SIM/` with `meta.json`, `run.log`, `summary.csv`, `measurements.csv`, `spur_map.csv`, and `source_check.csv`. **`SX1262-SDR.log` MUST be saved in the directory the command is run from**; check `Test-Path .\SX1262-SDR.log`. `meta.simulated=true` is mandatory. You may omit `--no-plot` to render charts.

**Do not treat the checked-in `harness/sample_output/` images as current test results:** those were produced by Grok's initial simulator before the unification changes.

## 2. Read-only local inventory — no flash, no RF output

```powershell
python harness/dut_serial.py --list
python harness/pluto_source.py --detect --uri ip:192.168.2.1
```

The second command opens a radio backend and requests TX OFF; it is **read-only/disable-intended**, not an RF source test. Verify the correct network/USB device and physical RF state. Historic Grok discoveries (FISH Ball PlutoSDR Rev.A Z7020/AD9361, COM17/COM39, TX 46.875 MHz–6 GHz, RX 70 MHz–6 GHz) must be rediscovered. Do not assume COM17 is Heltec: another project uses it.

Inventory Windows ESP-IDF toolchain, Python, serial VID/PID, specific Heltec board revision, its SX1262 pin connections and FEM (GC1109/KCT8103L or another verified part). Do not overwrite installed versions indiscriminately.

## 3. Firmware engineering, NO FLASH until permission

Implement a modular **RX-only ESP-IDF** receiver for the actual Heltec revision and board pins. First support `info`, `probe` and `status` with bounded sweep arguments, explicit SPI/BUSY timeouts, PLL and image-cal errors, state restoration, and honest machine-readable results. Match or explicitly version the existing `sxprobe` format; add a verified profile replacing the TODO in `harness/config/dut_profiles.json` only after matching actual firmware. Compile and run host fixture tests. Save current firmware and partition/NVS metadata if supported. Then ask for **specific user authorization for flashing the identified port**.

## 4. Conducted Pluto testing, SECOND separate permission

The user must inspect a physically isolated and terminated **Pluto RF output -> proper filter -> fixed attenuator(s) -> Heltec SX1262 RF input** path; measure/verify output limits, board FEM input limits, filter losses and cables. A software-interlock minimum of 30 dB fixed attenuation and -20 dB max hardware gain is not, by itself, a certified RF safety budget.

Do not enable Pluto TX or call `harness/run_sweep.py` in hardware mode without the separate explicit authorization, a completed input budget, and operator hand-on verification. Hardware mode requires `--arm-rf` and an exact manual typed confirmation; `--yes` is simulation-only. All experimental off-band work stays **conducted/receive-only** at the Heltec.

Example **for a future validated system only**:

```powershell
python harness/run_sweep.py --config .\my_verified_bench.json --profile VERIFIED_HELTEC_RX_PROFILE --port COMxx --arm-rf
```

Never copy/paste that command with the placeholder profile or unidentified COM port.

## 5. Interpret measurements cautiously

A high-frequency source can't be verified by an RTL-SDR V4 beyond its validated coverage. Report **UNVERIFIED**, not PASS, until a separately proven higher-frequency source reference exists. A PLL lock, an RSSI number, or a simulated PASS does not demonstrate on-channel RF reception. Use source-OFF, source-shift, 10 dB attenuation, at least five randomized repetitions and multiple power/temperature conditions. Record current-directory log and immutable raw session evidence. If equipment identification, filter input-power limit, or source purity cannot be verified, stop after simulation/preflight.

## 6. Handoff

Publish a concise evidence-led `docs/HANDOFF.md` with the actual commands/results and outstanding blockers. Put reusable REA findings in a properly attributed inbox document, leaving RSA's generated archives alone. Work in an `ai/heltec-v4-rx-firmware` or similarly named branch; request review before merging code.

Current hardware status: **zero physical experiments yet in this repository.**
