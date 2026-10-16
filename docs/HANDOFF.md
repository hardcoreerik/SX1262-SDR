# SX1262-SDR — Engineering handoff (2026-10-16)

## Canonical next step

Use **`docs/LOCAL_SESSION_GPT_LUNA.md`** and **`harness/LOCAL_QUICKSTART.md`** from `main` after approved integration. They are the source of truth for the first NewcorePC session.

The authoritative runner is `harness/run_sweep.py`, consolidated from Grok's `harness/`; `tools/analyze_sweep.py` is a legacy OFFLINE log-audit reader. Never create a second harness.

## Completed (software only)

- GitHub repository, source documentation, research provenance, safety plan and legacy parser.
- Grok's Pluto source controller, RTL source reference, board command profiles, simulator, plots, simulated output and verification checklist.
- Integration improvements: reject partial/PLL-failed scans, source-OFF check per repetition, no false independent retune validation on RSSI, RF arming interlock, CWD log, nonoverwriting output dirs, filter loss accounting.
- Extended CI and regression tests, including live TODO profile blocked before touching Pluto. Check recent GitHub Actions status and run tests again on local Windows.

## Explicitly NOT completed

- Correct Heltec V4 physical revision and pinout verification.
- Heltec ESP-IDF receive-only firmware and real serial protocol/profile.
- Flashing, instrument hookups, RF emissions, SX1262 receive data, calibrated power-level measurements.
- Real 1448–2622 MHz PLL gap replication on Heltec, gap closure, 2.4 GHz direct RX, evidence for high-band source beyond RTL coverage.

## Local phase gates

1. **Read-only and safe:** discover checkout, install non-hardware Python dependencies if appropriate, run simulator/unit tests, inventory actual USB hardware and Pluto properties with transmitter disabled.
2. **Code and build:** write small, testable ESP-IDF SX1262 RX-only firmware based on verified Heltec revision; implement profile, simulator fixture and error-propagation tests; compile.
3. **Permission gate 1:** user explicitly approves flashing this identified device, with backup and recovery plan.
4. **Receive-only no-source measurements:** record PLL error/status, RSSI, modes and edge behavior; no Pluto emission.
5. **Permission gate 2:** user verifies attenuated cabled RF chain and explicitly approves Pluto RF; record power/uncertainty.
6. **Conducted benchmark:** nominal bands first, then transition/gap points, TX-source OFF controls and independent source/reference evidence; stop on ambiguous RF response.
7. **Preserve:** output `SX1262-SDR.log` in current working directory, timestamped run folders, SHA-256 of any promoted artifacts, updated HANDOFF and REA inbox note.

## Offline How to run/test — PowerShell

```powershell
git pull --ff-only
python -m pip install numpy matplotlib pytest
python -m pytest -q harness/tests
python -m unittest discover -s tests -v
python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot
Test-Path .\SX1262-SDR.log
```

Expected `True` for the final line, all tests passing, and synthetic `meta.json` marked `simulated: true`. When full plots are desired, rerun without `--no-plot`.

## Source context

- https://github.com/SAMS0N1TE/lr2021-sdr/blob/main/research/sx1262-range/README.md
- https://github.com/SAMS0N1TE/LakeShark/blob/main/components/lakeshark/board/ls_lora_sx126x.c
- https://github.com/ibelinp/SX1262_CHIRP
- private REA-Results: https://github.com/hardcoreerik/REA-Results

The next local agent must not report simulation-derived frequency windows as actual Heltec observations.
