# Local Quickstart — ONE SX1262-SDR harness

The operator's detailed task description is at [../docs/LOCAL_SESSION_GPT_LUNA.md](../docs/LOCAL_SESSION_GPT_LUNA.md). The repo now has a compiled Heltec V4.3 firmware adapter and identity-checked serial profile. **Firmware 1.2 is flashed; discrete conducted LoRa receive checks and source-OFF LoRa/GFSK surveys have run.** The generic `sx1262_sdr_tbd` placeholder still refuses real hardware.

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

The ESP-IDF firmware and `heltec_v4_3_sx1262` profile are implemented. The firmware supports bounded RSSI/status probing and a one-shot armed LoRa packet at -9 dBm chip setting in 902–928 MHz. For the current COM38 device, the user accepted proceeding without the old-image backup and explicitly approved custom firmware and flashing. Firmware 1.2 uses native USB Serial/JTAG and supports optional `probe ... gfsk` with a fixed 4.8 kHz filter.

## 4. Conducted Pluto testing

The user authorized both radios to TX/RX on the reported conducted setup: **Pluto -> 30 dB, 10 W, 3 GHz attenuator -> 1 ft SMA cable -> Heltec V4.3**. The user confirmed the same TX1/30 dB pad/cable arrangement used for SSTV and explicitly authorized bounded unfiltered receive checks at the listed frequencies. Absolute levels and source purity remain unverified at the new frequencies. Pluto RX capture is integrated and streaming-tested; it is not a calibrated reference.

Full sweeps retain the source filter and source-verification requirements. `--nominal-check` is fixed to 915 MHz; `--receive-check` permits at most 20 operator-authorized frequencies within the source range and <=3 GHz, at gains -80/-70/-60 dB. Both require `--arm-rf` and the typed interlock. Failed preflight RX/PLL probes never enable the source. `--yes` is simulation-only. `--heltec-tx --arm-heltec-tx` is one 915 MHz packet and requires moving the attenuator to RX1.

Example **for a future validated system only**:

```powershell
python harness/run_sweep.py --config .\my_verified_bench.json --profile VERIFIED_HELTEC_RX_PROFILE --port COMxx --arm-rf
```

Never copy/paste that command with the placeholder profile or unidentified COM port.

## 5. Interpret measurements cautiously

A high-frequency source can't be verified by an RTL-SDR V4 beyond its validated coverage. Report **UNVERIFIED**, not PASS, until a separately proven higher-frequency source reference exists. A PLL lock, an RSSI number, or a simulated PASS does not demonstrate on-channel RF reception. Use source-OFF, source-shift, 10 dB attenuation, at least five randomized repetitions and multiple power/temperature conditions. Record current-directory log and immutable raw session evidence. If equipment identification, filter input-power limit, or source purity cannot be verified, stop after simulation/preflight.

## 6. Handoff

Publish a concise evidence-led `docs/HANDOFF.md` with the actual commands/results and outstanding blockers. Put reusable REA findings in a properly attributed inbox document, leaving RSA's generated archives alone. Work in an `ai/heltec-v4-rx-firmware` or similarly named branch; request review before merging code.

Current hardware status and evidence: **see [the dated bench record](../docs/HELTEC_V43_BENCH_2026-10-16.md)**. The cable was last confirmed on TX1; Pluto TX is shut down between probes and on every exit.

Source-OFF survey (no RF arming):

```powershell
python harness/run_sweep.py --pll-only --gfsk-probe --port COM38 --uri ip:fishball.local --freqs 37,433.92,915,1300,1400,1500,2000,2400,2450,2624,2700,3000 --no-plot
```

`--gfsk-probe` selects the narrow GFSK/XOSC companion mode; omit it for LoRa/125 kHz/RC. These are different receiver configurations and must not be pooled as equivalent measurements. Source-OFF survey results do not demonstrate external reception.

Lower-band offset experiments are recorded in
[the lower-band bench note](../docs/HELTEC_V43_LOWER_BAND_2026-10-16.md).
`--receive-check --gfsk-probe --rx-offsets-khz=-5,0,135,225` varies the RX tune
while keeping the source fixed per selected frequency. This path is limited
to three sources <=340 MHz, nineteen offsets within +/-400 kHz and fixed
-60 dB source drive; the existing RF arming and typed interlock still apply.

For the complementary source-axis experiment, use
`--receive-check --gfsk-probe --fixed-rx-mhz 250.001 --freqs 249.99975,250,250.00025`.
The source tone is each listed base frequency +1 kHz; every Heltec probe uses
the fixed RX frequency. This mode permits <=20 nearby sources within 400 kHz
of RX, both source and RX <=340 MHz, at fixed -60 dB source gain. It cannot be
combined with `--rx-offsets-khz`. RF arming, typed confirmation, pad and identity
checks remain mandatory. Firmware re-enters RX for each reading; fixed frequency
does not mean a continuously held PLL. Treat DDS-model frequency as a prediction,
not independently calibrated RF.
