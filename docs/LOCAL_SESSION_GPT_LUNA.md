# GPT Luna — Local SX1262-SDR engineering session

**Task:** On NewcorePC, bring up the single merged SX1262 receive-test harness, build a Heltec WiFi LoRa 32 V4 RX-only firmware adapter, and prepare an actual controlled measurement program using the existing Pluto-compatible AD9361 SDR, without overstating success or bypassing physical permissions.

**Repo:** `https://github.com/hardcoreerik/SX1262-SDR` — start from latest `main`, work on a new `ai/heltec-v4-rx-bringup` branch, and preserve any working trees or other sessions. Your current model/session may be called GPT Luna; prioritize correct reproducible engineering over speed. Use your local tools to do the work; do not merely write a plan when a safe action can be completed.

## 0 — First-person working rules (MANDATORY)

You are the on-machine engineering agent. Work systematically, read actual files, run real commands, save evidence, and report exact outcomes. Do not say hardware was verified when you only simulated or reviewed source.

Before any action:
- Read root `AGENTS.md`, `README.md`, this prompt, `harness/LOCAL_QUICKSTART.md`, `harness/README.md`, `harness/VERIFY.md`, `docs/SAFETY.md`, `docs/PLUTO_PROCEDURE.md`, `docs/RESEARCH_EVIDENCE.md`, `docs/HANDOFF.md`, and `harness/config/dut_profiles.json`.
- Treat this folder's `harness/run_sweep.py` as **the one master runner**. Grok's harness already contains the Pluto source, RTL reference, serial profile layer, simulator, test cases and plots. Extend it; DO NOT clone a new runner, make multiple conflicting scripts, create an unrequested GUI, or rewrite working logic gratuitously.
- `tools/analyze_sweep.py` is a historical **offline** parser only. `firmware/` has no complete flashable Heltec receiver program yet.
- The original reported SX1262 bands (~37–1447 and 2624–3494 MHz) and the 1448–2622 MHz gap are **LilyGO-board reports**, not a calibrated Heltec result. No proof of direct SX1262 reception at 2.4 GHz exists here.
- Never call RSSI readouts raw I/Q; the SX1262 is a packet/RSSI modem, not the LR2021 IQ interface.
- Physical work permission is staged: you CAN inventory/read/configure development workspace, run simulations and builds; **you must ask before flashing the positively identified Heltec**; ask separately and require a physically confirmed RF setup before enabling the Pluto's transmitter. No SX1262 TX routines, no radiated off-band tests, no unknown register writes to PA/high-voltage/fuse sections.

## 1 — Establish the exact local project state

In PowerShell, locate or clone the actual working checkout. Do not presume a path. Verify other AI sessions or branches before changing files.

```powershell
git clone https://github.com/hardcoreerik/SX1262-SDR.git
cd SX1262-SDR
git status --short
git fetch origin
git switch main
git pull --ff-only origin main
git log -5 --oneline
git switch -c ai/heltec-v4-rx-bringup
```

**If the repository already exists**, do not clone again; `cd` to its real location. If there are uncommitted changes, don't overwrite/reset them; resolve them explicitly or use a new git worktree. If the requested branch name exists, inspect it before using a different branch suffix. Confirm the merged `main` contains `harness/LOCAL_QUICKSTART.md`, `docs/LOCAL_SESSION_GPT_LUNA.md`, and current `AGENTS.md`.

Record repo SHA and Python/PowerShell/platform versions. Establish a local, untracked `bench-notes/` or timestamped evidence location. Don't store RF results or secrets in Git by default.

## 2 — Baseline: full offline suite (NO hardware RF)

Identify the working Windows Python interpreter and available packages; avoid changing global/other-project environments unnecessarily.

```powershell
python --version
python -m pip install numpy matplotlib pytest
python -m pytest -q harness/tests
python -m unittest discover -s tests -v
python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot
Test-Path .\SX1262-SDR.log
```

Optionally create `.venv` first if dependencies conflict. Ensure the `harness/tests/` tests and root legacy parser tests pass; if not, fix the real cause in a focused commit with a regression test.

Inspect a newly produced `harness/results/<run_id>_SIM/`: `meta.json`, `run.log`, `measurements.csv`, `summary.csv`, `source_check.csv`, `spur_map.csv`. Confirm `simulated=true`, the recorded RNG seed, profile, software revisions and that no synthetic result is labeled actual hardware reception. Verify `SX1262-SDR.log` was written **to the directory you executed the script from**, not only next to `run_sweep.py`.

Check fail-safe tests specifically:
- A missing/unimplemented `sx1262_sdr_tbd` LIVE profile refuses BEFORE opening Pluto.
- SXPROBE incomplete rows, failed restore, or PLL error on any step must reject the measurement rather than silently discard rows without RSSI.
- Source-OFF remains required per repetition; RSSI's fictitious "nominal retune" result is not counted as a separate check.
- `--yes` never skips physical safety prompts in live mode; live `--arm-rf` and typed operator confirmation are mandatory.
- A missing RTL reference at 2.4 or 3.0 GHz results in UNVERIFIED, not PASS.
- Abrupt exception/interrupt requests TX disable, closes devices and logs the aborted state.
- Results paths never silently overwrite measured runs. Randomized sweeps persist seed and scan ordering.
- No record is called "calibrated dBm" when reference output/filter/cable/path losses remain unknown.

Do NOT proceed to hardware flash if offline tests aren't green.

## 3 — Read-only connected-hardware discovery

Inventory by actual USB VID/PID, board silkscreen/revision and observable connections; do not assume past device letters or IPs are still correct.

```powershell
python harness/dut_serial.py --list
python harness/pluto_source.py --detect --uri ip:192.168.2.1
```

Those commands are examples to use **after** confirming the device is actually connected. A prior Grok snapshot recorded a FISH Ball PlutoSDR Rev.A Z7020/AD9361 with `ip:192.168.2.1` (USB) and `192.168.1.228` (LAN), and USB serial devices on COM17/COM39, but these are **historical observations**. COM17 may be an OrcSDR Tab5; never flash it assuming it is a Heltec.

Inspect:
1. Heltec WiFi LoRa 32 V4 hardware: exact PCB revision, ESP32-S3 variant, Semtech chip marking, SX1262 SPI CLK/MOSI/MISO/CS, RESET, BUSY, DIO1, oscillator/TCXO supply and reset timing, FEM part, RF switch/LNA/bypass GPIO and antenna connector. Corroborate with revision-specific Heltec official schematic and board source, not LilyGO pins.
2. Any installed Meshtastic/other firmware and how to preserve recoverable flash, partition table, NVS and calibration; a backup or rollback that cannot actually be performed must be called out. Verify USB port at the moment of flash.
3. Pluto clone: real libiio IIO context, `ad9361-phy` channels, `cf-ad9361-dds-core-lpc`, firmware, TX/RX port labels, `frequency_available`, `hardwaregain_available`, RF powerdown status, actual external RF power limit, driver setup. Read-only discovery must not generate a test tone.
4. RTL-SDR V4 reference: current USB presence and `rtl_test` status. Grok previously saw a `pyrtlsdr`/librtlsdr DLL mismatch and `rtl_power` fallback; repair if necessary without breaking OrcSDR's working Windows setup. Do not assume it validates 2.4 GHz merely because its driver runs.
5. Available fixed attenuators, measured filter passbands/insertion losses, SMA/u.FL adapters, RF DC block, 50-ohm terminators, isolation/couplers, RF level measurement device. Draw the actual cabled layout, with estimated and known uncertainties. No TX until accepted.

Provide a short preflight summary with **confirmed vs assumed vs missing** facts before code uses hardware GPIO or radio ports.

## 4 — Build the missing Heltec RX-only firmware (first useful engineering deliverable)

Use the installed ESP-IDF version for a maintained ESP32-S3 project under `firmware/`. Read the real Heltec board header and schematic. Construct a **minimal, modular, bounded receive-only** firmware. Do not modify OrcSDR, OrcXM or production Meshtastic code. Avoid dragging in an entire LakeShark application.

Required architecture:
- Dedicated SX1262 SPI hardware abstraction with bounded BUSY wait, correct protocol framing, checked ESP errors, fixed and validated target GPIOs, SPI ownership/mutex, watchdog-friendly loops, and robust reset/recovery.
- Verify TCXO voltage and settle delay, actual FEM LNA/bypass states and antenna switch before accessing RF. Never toggle unknown PA pins or send TX opcodes.
- Support only safe receive operations: status/part-read, `SetStandby`, `SetRfFrequency`, documented safe `CalibrateImage`, `SetRx`, `GetStatus`, `GetDeviceErrors`, `ClearDeviceErrors`, `GetRssiInst`, and required RX-only modulation setup.
- Serial commands with explicit versioning, at minimum `info`, `status`, `probe`, `stop`/restore. Favor the existing LakeShark SXPROBE CSV response shape plus a unique firmware/version header, so `harness/dut_serial.py` needs only a new verified profile.
- Print every sweep row even on invalid RSSI/PLL failure; raw error fields separate from calibrated values. Limit frequency/count, reject malformed input, time out on BUSY; never lock up forever in a scan.
- For receive-only frequency sweeps preserve exactly what frequency word was requested and whether firmware command succeeded, PLL lock error was reported, RSSI valid and complete, receiver recovery succeeded.
- Restore safe RF/TCXO state after interrupts/scan errors. No TX commands or generic register-write CLI.

In `harness/config/dut_profiles.json`, replace **TODO only after actual protocol implementation exists**, using a fresh `heltec_v4_sx1262_rx` profile with literal firmware-source evidence. Do not replace profiles for LR2021 or LakeShark. Add unit tests for real firmware output strings, incomplete replies, timeouts, bad CRC/framing if used, boundary errors, and scan restore. Keep simulator physics honest. Limit integration changes to what the protocol requires.

Build firmware locally with esp-idf and report exact `idf.py` command, ESP-IDF version, target, binary path/size, and whether compilation passed. If firmware cannot compile, do not ask the user to flash.

## 5 — FLASH AUTHORIZATION STOP

Once firmware compiles and test fixtures are green, give the user a succinct targeted request:

- Exact Heltec device name, silkscreen revision, confirmed serial port AND USB identifiers.
- What existing firmware/config will be preserved, backup path, recovery behavior and what cannot be preserved.
- Built ELF/BIN and branch/commit SHA, what the new firmware does and that it includes **no SX1262 TX**.
- What observable serial output is expected after flash.

Ask: **"May I flash this identified Heltec V4 on COMxx with the RX-only test firmware?"** Wait for an affirmative answer; do not infer permission from the wider project's previous Tab5 flashing authorization.

After explicit approval, flash only the identified device. Capture serial output and verify receiver identification, status, frequency errors and restoration at a nominal band. Run **PLL-only** edge sweeps with the Pluto TX OFF/disconnected; save logs. Take note of actual reset/boot behavior. Verify no other COM port was changed.

## 6 — PLUTO RF AUTHORIZATION STOP (independent of flash approval)

A working flash does **not** authorize RF output. Before emitting ANY controlled RF tone, the user must confirm the physically installed RF chain:

```text
Pluto-compatible AD9361 TX port (RF OFF)
  -> verified suitable band filter
  -> verified adequate FIXED attenuator(s), fitted directly at source
  -> optional step attenuator/splitter and verified loss
  -> physically verified Heltec SX1262 receive RF connector
```

No unattenuated transmitter-to-receiver connection, no open-antenna/radiated path, no port swaps while output is enabled. Ensure connector compatibility and DC isolation as appropriate. Verify the receiver's FEM maximum input (not only the SX1262 die maximum). Confirm output/filter losses and safe maximum level; a 30 dB software floor and Pluto -20 dB gain cap are NOT a substitute for a real physical safety budget. The source must start OFF, and every abort must request OFF and independent physical verification.

**Do not enable RF until the user explicitly authorizes this specific cabled configuration after visual inspection.** Use `--arm-rf` and type the real operator phrase yourself only after the user confirms. Never use `--yes` to evade verification or alter code to bypass interlocks. If the power meter or filter is missing, restrict conclusions to safe read-only experiments; mark levels uncalibrated and withhold conducted TX if safe input cannot be established.

## 7 — Real bench experiments: acceptance criteria

### A. Nominal-band anchor
With proper permission and confirmed cabled setup, start in the manufacturer's supported frequencies and the **actually matched Heltec FEM path** (e.g. a verified 915 MHz board). Establish a source-OFF baseline, then a weak known CW tone within the receiver's GFSK filter, then TX frequency shift and 10 dB attenuation response. Use randomized repetitions (at least 5), track cold and warm behavior, and record controls before touching extended bands.

### B. External reference
Use the RTL-SDR V4 only where its actual tuner/backend verifies the intended fundamental and relevant spurs. Where the RTL cannot tune (especially around 2.4–3.5 GHz), treat the result as **UNVERIFIED** until a suitable independent high-band source/reference check is implemented. An AD9361 clone's RX path might work; build/verify that path separately and validate isolation and its own images/spurs, never reuse TX-as-RX assumptions.

### C. Gap mapping
On the Heltec, repeat tests near 1400–1500 and 2600–2680 MHz first, logging every PLL lock/error; then cautious gap points 1600, 1800, 2100, 2400/2450 MHz. Evaluate requested frequency, chip error bits and actual external tone separately. Randomize frequencies/repetitions with known seed. Include image calibration none/once/each, standby RC vs XOSC, TCXO warmup, cold vs hot start, fixed RX gain and revision-appropriate FEM bypass vs LNA when safely verified. Do not modify undocumented PA/VCO registers based on guesses.

### D. A result is not a result unless falsifiable
Keep these categories distinct:
- `COMMAND_ACCEPTED`: SPI transaction accepted.
- `PLL_LOCKED`: no receiver-side lock fault reported in a complete scan (does not imply sensitivity).
- `RSSI_OBSERVED`: non-null receiver reading; might be a local spur.
- `EXTERNAL_TONE_CORRELATED`: source OFF removes response, source ON restores it, attenuation causes proper response and reference is trusted.
- `FREQUENCY_TRACKED`: changing controlled TX frequency shifts detection predictably and independently of the search-window definition.
- `CALIBRATED`: proper power meter/filter/cable/FEM budget supports power-referred quantities with uncertainty.

The first four may be strong evidence on SX1262, but not an IQ waterfall. Raw no-lock samples, missing RSSI, source-not-verified and spur conflicts must **never** quietly become PASS.

### E. Stopping criteria
Abort on unexpected RF output, ambiguous antenna/cable state, excessive input, unknown board/FEM voltages, serial timeout not recovered by documented process, inconsistent reference spur behavior, source that fails to shut off, or overwrite of previous measurement data.

## 8 — Required deliverables

1. A verified checkout on an `ai/<topic>` branch, exact commit recorded, no unrelated changes.
2. Host test output and **`SX1262-SDR.log` in the folder you execute from**, plus per-run logs inside `harness/results/`.
3. A buildable Heltec ESP-IDF RX-only firmware module with repeatable IDF version and instructions; flash ONLY if separately approved.
4. An updated DUT serial profile tied to actual firmware strings, timeouts and tests; do not create a second test harness.
5. A clean hardware map and Pluto/RTL detection inventory from THIS session, not historical guesses.
6. If user authorizes conducted RF, raw paired OFF/ON runs and verification data, source-level uncertainty, measured filter/cable losses and both nominal/edge/gap experiment summaries.
7. Capability matrix: datasheet supported / independent upstream report / our Heltec PLL verified / independently RF verified / calibrated sensitivity.
8. A refreshed `docs/HANDOFF.md` explaining exactly what was run, what passed or failed, what needs physical input, recovery instructions and the next phase.
9. An attributed `REA-Results/inbox/YYYY-MM-DD_sx1262_heltec_findings.md` handoff document with source links and evidence hashes; **never write directly into RSA-generated targets/indexes**, and never push the local RSA-Sandbox.
10. Push a coherent branch and offer one reviewable PR when the milestone is complete. Do not merge into main without user approval.

## Output style and session behavior

Act like a careful embedded/RF engineer running real experiments with me at the bench, not a generic project planner. Before each phase give a one-paragraph status, what hardware will be touched and the expected artifact. Execute safe checks autonomously; only pause where you actually need my physical information or approval. Cite exact file paths and commits rather than speculative statements. Keep failure reports explicit and preserve all raw evidence. Offer recovery steps and **verbose Windows PowerShell how-to-run/how-to-test** commands. Avoid making changes to working OrcSDR Tab5s or other projects. When an experiment fails, distinguish a scientific negative from a test-fixture failure, and continue safe analyses without claiming success.

**Begin now with phases 1–3: repository synchronization, offline regression/simulation and read-only hardware inventory. Only after those are complete, develop and compile phase 4 firmware.**
