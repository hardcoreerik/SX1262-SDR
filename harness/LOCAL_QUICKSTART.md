# Local testing workflow — Heltec V4 SX1262 + Pluto clone

**State at 2026-10-16:** The Python hardware orchestration exists; the **Heltec's own SX1262 firmware adapter does not**. Our harness has demonstrated synthetic end-to-end execution only. The live-ready profile is intentionally marked TODO. No board has been flashed or RF sent by this project.

## One test path, two read-only parsers
- **Use `harness/run_sweep.py`** as the single master runner for source, reference, DUT, safety prompts, repeated sweeps, measurement files and plots.
- `harness/dut_serial.py` parses SXPROBE-style console output, and the old root `tools/analyze_sweep.py` can **audit previously saved logs offline**, but must not be used as an alternative orchestration pipeline.
- Existing `harness/rtl_reference.py` covers frequencies your RTL-SDR V4 can actually monitor. **Above its coverage, result stays UNVERIFIED; do not convert into PASS.**
- `harness/config/dut_profiles.json` still contains `sx1262_sdr_tbd` and **will refuse real hardware** until a new verified ESP32-S3 receive-only firmware exists.

## Phase A — local simulation (no RF, safe to run)

PowerShell (repo root):

```powershell
git pull
python -m pip install numpy matplotlib pytest
python -m pytest -q harness/tests
python -m unittest discover -s tests -v
python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot
```

Expected:
- All offline unit tests green, including new guards for partial PLL failures, source-off negative controls and impossible PASS classifications.
- A timestamped folder under `harness/results/` with `run.log`, `measurements.csv`, `summary.csv`, `source_check.csv`, `spur_map.csv`, `meta.json`.
- `SX1262-SDR.log` exists in the **terminal's current working directory**, not just the source directory.
- Metadata says `simulated: true`. No synthetic PASS is a real RF result.
- For plots, omit `--no-plot`; matplotlib generates chart output.

## Phase B — read-only hardware inventory (no TX, no flash)

With physical radios connected, confirm **the devices and exact ports**; earlier Grok notes about COM17/COM39 and Pluto `ip:192.168.2.1` are a snapshot, not a current detection:

```powershell
python harness/dut_serial.py --list
python harness/pluto_source.py --detect --uri ip:192.168.2.1
```

Before selecting COMx, read Heltec's revision/silkscreen, SX1262 SPI pins, TCXO and external FEM controls from its own schematic. Inspect the actual Pluto-clone TX ports, installed firmware, driver and radio frequency range. Never assume a device is the right board solely from a reused COM number.

## Phase C — hardware RX adapter, then conducted RF only

1. Develop the Heltec ESP-IDF RX-only firmware in `firmware/`. Do not flash operational Meshtastic firmware without explicit authorization.
2. Define its actual console command/response format; add a non-placeholder profile to `harness/config/dut_profiles.json` with literal firmware-source links and a simulator/fixture parser test.
3. Run a no-Pluto RX-status sweep first. Verify calibration and PLL bit reporting, including failed tune rows.
4. Assemble a physically inspected, shielded, correctly terminated **Pluto TX -> known RF filter -> verified fixed attenuator(s) -> DUT** path with all TX off. Verify filter insertion loss, cable loss and source power with suitable instruments. If uncalibrated, label input levels relative; do not fill a made-up dBm.
5. An explicit operator must accept RF arming. The runner refuses real TX without `--arm-rf` plus a manual typed interlock and config specifying Heltec revision, FEM, known source filter, and at least 30 dB actual fixed attenuation. **Do not use this as a substitute for a power budget; physical verification is required.**
6. Only after all preflight gates pass, use an identified port and verified configuration. Example shape **(not ready today)**:

```powershell
python harness/run_sweep.py --config .\my_verified_bench.json --profile VERIFIED_HELTEC_RX_PROFILE --port COMXX --arm-rf
```

7. The radio's RSSI scanner must test source-shift, attenuation response, source-OFF contrast, reference purity. It does not get LO-retune credit. Do not treat PLL lock alone or RSSI alone as real RF reception.
8. Repeat edge tests near 1.447 / 1.448 GHz and 2.622 / 2.624 GHz on the Heltec, then only cautiously investigate interior gap frequencies. The reported bounds come from a different LilyGO board.
9. At frequencies outside the RTL-SDR V4's normal receive range, leave results UNVERIFIED until a genuine second RF verification method (characterized Pluto RX path, analyzer, downconverter, etc.) is added and tested. Never declare 2.4 GHz unlocked because the simulator says PASS.

## Results and troubleshooting

`harness/results/` is intentionally not tracked by Git. Preserve raw output, firmware SHA, board identity, exact RF setup, time, uncertainties, source-off pairing and software versions before copying a documented evidence package into the private REA-Results inbox.

If a test fails or is aborted, verify TX OFF at the radio as well as the console; this is an experimental driver, not a safety-certified RF interlock. The script requests Pluto TX shutdown on all handled exits. If control crashes or USB disconnects, disconnect power as needed and check RF state independently.
