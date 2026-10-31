# SX1262-SDR — AGENTS.md

This is the authoritative engineering contract for AI agents working on [hardcoreerik/SX1262-SDR](https://github.com/hardcoreerik/SX1262-SDR).

## Objective and actual hardware

Discover the **true receive and synthesizer limits of the Semtech SX1262 in the Heltec WiFi LoRa 32 V4 (ESP32-S3)**. Replicate or disprove published out-of-spec tuning windows and the reported PLL unlock gap around 1448–2622 MHz using error/status evidence and independently controlled conducted RF. The current bench scope also includes bounded bidirectional conducted checks: Pluto TX to Heltec RX and Heltec TX to Pluto RX.

User-provided instruments: a **Pluto-compatible Zynq-7020/AD9361 clone** as low-power cabled source and possible high-band reference RX, plus an RTL-SDR V4 where its own tuning range permits. Discover ports and device identification afresh; values in previous reports, such as COM17, COM39, ip:192.168.2.1, are HISTORICAL, not authoritative for the current session.

**Read `docs/LOCAL_SESSION_GPT_LUNA.md` and `harness/LOCAL_QUICKSTART.md` first when operating locally.**

## One fluid test harness — no competing frameworks

1. **`harness/run_sweep.py` is the single orchestration program** for simulated and eventually real RF bench runs.
2. `harness/pluto_source.py`: cabled source controller, normally TX OFF.
3. `harness/rtl_reference.py`: limited-band independent source validation. Outside verified RTL capability, status is UNVERIFIED unless a new independently tested reference adapter exists.
4. `harness/dut_serial.py` and `harness/config/dut_profiles.json`: hardware-specific serial protocol. The placeholder `sx1262_sdr_tbd` deliberately **refuses live operation**. Do not disable this protection just to run a sweep.
5. `harness/sim.py`, `harness/tests/`: simulator and regression testing; NEVER publish simulated values as hardware results.
6. `tools/analyze_sweep.py` / `src/sx1262_sdr/analysis.py`: **offline import and auditing only**, not another live harness.
7. `firmware/`: board-specific ESP-IDF adapter with bounded RX probing and one-shot test TX. Hardware behavior remains unverified until the identified board is flashed and checked.

Preserve Grok's good harness architecture, no rewrite, no second runner, no desktop UI until requested. Extend shared data schemas rather than creating competing output formats.

## What is proven versus conjecture

- External experiments on a **different LilyGO board** reported PLL lock bands near 37–1447 and 2624–3494 MHz. These are not verified on the user's Heltec.
- **PLL register acceptance != PLL lock != non-null RSSI != source-correlated reception != calibrated sensitivity.**
- SX1262 is an RSSI/packet modem, not currently a demonstrated raw I/Q source; do not import LR2021 IQ semantics.
- An RSSI scan walks **absolute RF frequencies**; moving a nominal centre without independent physical LO evidence does not validate a real receiver retune. Require TX source shift, attenuation trend, source-OFF control, valid PLL status, and independent reference verification.
- A Pluto clone's reported tuning range does NOT mean calibrated power, spectral purity, or independent reference evidence across it.

## Authorization and RF safety — non-negotiable

- Local session MAY inspect checked-out source, inventory USB/serial, query device properties, run simulations, build firmware and analyze logs **without changing equipment**.
- Local session MUST ask the user for explicit approval **before first flashing or erasing the named, positively identified Heltec board**. Protect Meshtastic/NVS/partitions; back up what is recoverable, provide rollback and recognize when no safe backup is possible.
- The user has explicitly authorized Pluto and Heltec TX/RX for the reported conducted path (Pluto -> 30 dB, 10 W, 3 GHz attenuator -> 1 ft SMA cable -> Heltec V4.3). Verify installed port orientation, attenuator rating/tolerance, and per-direction input levels before enabling an RF test. Authorization does not certify measured power or source purity.
- Heltec TX is limited to one fixed LoRa test packet at a time, with runtime arming, fixed low SX1262 output setting, and 902–928 MHz test band. Pluto TX remains under `--arm-rf`, attenuation/gain limits and source shutdown. No CW, repeated/unbounded TX, off-band radiation, undocumented PA/fuse writes, or destructive eFuse operations.
- No live bypass of `--arm-rf`, the typed interlock, mandatory attenuation, known board revision/FEM, or firmware identity checks. `--yes` is simulation-only.
- Do not assume that an attenuator's declared dB value certifies safe input; measure/verify the clone's output and every FEM's maximum allowable level as actually installed. On communications failure, stop and independently confirm RF output is OFF.

## Tests, provenance, data integrity

From repository root:

```powershell
python -m pip install numpy scipy matplotlib pytest
python -m pytest -q harness/tests
python -m unittest discover -s tests -v
python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot
```

Run data goes to `harness/results/<run-id>/`, not Git by default. **Append `SX1262-SDR.log` in the process current working directory** for each runner/analysis operation. Preserve raw serial logs and source commands. Do not silently overwrite measured artifacts. Results must include board revision/FEM mode, firmware commit, Pluto build, timestamp, source on/off, signal-path insertion loss, calibration basis, threshold and negative controls. Add SHA-256 hashes for copied evidence artifacts.

Evidence labels: `SIMULATED`, `UNVERIFIED`, `COMMAND_ACCEPTED`, `PLL_LOCKED`, `RSSI_OBSERVED`, `EXTERNAL_TONE_CORRELATED`, `FREQUENCY_TRACKED`, `CALIBRATED`. Never collapse these.

Require Linux CI green and local Windows tests passing before code is considered test-ready. Build and validate exact firmware target before proposing flash. Every milestone must state commands executed, return codes, test counts, evidence, and limitations.

## Collaborative development

- Work on a single cohesive `ai/<topic>` branch from `main`. Never make routine commits to main.
- When user approves a merge, merge after CI succeeds, then verify remote main and update the handoff.
- Prefer a coherent PR for the milestone over PRs for each small change.
- Preserve license/attribution for GPL-3.0 harness components and any copied upstream code; audit licensing before reuse. Do not commit credentials, device identifiers, secrets, massive raw captures or proprietary vendor firmware blobs.

## REA / RSA handoff

Consult private `hardcoreerik/REA-Results`, especially its `AGENTS.md` and `INDEX.md`. The RSA-Sandbox is **local-only**; do not push it. New findings belong in a dated `REA-Results/inbox/` note with source commits, raw evidence paths, hashes and limitations. Do **not** manually edit generated `targets/`, `comparisons/`, `index.json` or `graph.json` in REA-Results; local RSA publisher owns these.

## Hard stop / escalation conditions

Unidentified serial port; ambiguous Heltec revision/pin mapping; unverified TCXO or RF switch voltage; inability to preserve operational firmware before flash; missing RF filter or input-level budget; evidence of emitted RF without authorization; inconsistent PLL status; source-on/off uncorrelated; simulator falsely labeled as real; missing log file; CI regression. Stop the affected stage, protect hardware, document blocker, then seek the specific missing confirmation.

This file controls all local-session engineering decisions. See `docs/LOCAL_SESSION_GPT_LUNA.md` for execution order.
