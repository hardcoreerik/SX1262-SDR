# Heltec V4.3 SX1262 bench record — 2026-10-16

The priority is SX1262 receive/synthesizer limits. These are real hardware observations,
kept separate from simulation, direct-frequency proof and calibrated sensitivity.

## Setup and authorization

- Heltec HTIT-WB32LAF V4.3 / ESP32-S3 / SX1262 / KCT8103L, user-identified COM38.
- Pluto-compatible FISH Ball Z7020/AD9361 clone discovered at `fishball.local`,
  currently `192.168.1.228`; the old `192.168.2.1` address did not respond.
- User confirmed the established SSTV arrangement: TX1 -> 30 dB, 10 W, 3 GHz pad
  -> 1 ft SMA cable -> Heltec. The cable was briefly on RX1 for receive-stream work
  and was confirmed back on TX1 before the conducted source tests.
- Historical `F:\Ai\OrcSDR\docs\sstv\WEAK_SIGNAL.md` records tinySA measurements
  at 145.5 MHz with that arrangement. Those numbers are not calibration at the
  frequencies tested here. Pad tolerance and frequency-dependent path loss are unknown.
- User accepted proceeding without an old firmware backup, approved flashing COM38
  and authorized further firmware specific to this board.
- User explicitly waived the added-filter requirement for the nominal 915 MHz check,
  then for the listed bounded conducted receive checks. Full source-verified sweeps
  retain their existing filter/reference requirements. No source testing exceeded
  the pad's reported 3 GHz limit. The higher synthesizer tests were source-OFF only.

## Firmware and source study

Firmware 1.0 used LoRa/125 kHz and RC standby. Its console initially selected UART0;
this was corrected to USB Serial/JTAG, and the input loop now survives host disconnects.
The working 1.0 image was 206,560 bytes, SHA-256
`2FDD164F6F020AC6135A796C1E617CDC912BE7CF47D3DFE5A1252CCF2495C2C2`.

Firmware **1.1** adds a selectable GFSK/4.8 kHz/XOSC probe with eight RSSI reads,
separate calibration error reporting and invalid-RX rejection. LoRa mode remains
available. The flashed 207,136-byte image has SHA-256
`42E2F2CE63D095FD7B204635EDFDDAB401D40F7E9E437C7642BDCE2E65170855`.
Esptool verified the write. Both modes returned valid 915 MHz probes and `stop`.
The image, source hashes and local dirty-build provenance are preserved in
`harness/results/20261016-heltec-v43-session/`.

Reviewed primary sources before the GFSK change:

- [LakeShark `sxprobe`, commit 8586c6d](https://github.com/SAMS0N1TE/LakeShark/blob/8586c6de0c40fd019b3e21eb2c05a48b35e099d3/components/lakeshark/board/ls_lora_sx126x.c):
  GFSK setup, XOSC standby, optional image calibration, separate calibration/RX
  errors, validated RSSI reads and restoration. Our mode uses fixed documented
  command fields; it does not expose their arbitrary register/gain controls or
  reproduce every calibration option. LakeShark's root license is GPL-3.0.
- [ESP-SDR receive controls, commit e2b35dc](https://github.com/ESPARGOS/esp-sdr/blob/e2b35dc593a378e4c5eb69cb8db59313117c9838/docs/rx-controls.md)
  and its S3 receiver: the extended-LO mechanism controls the ESP32's internal
  Wi-Fi RF path. It does not operate the external SX1262. Its calibration can
  emit RF, so no Wi-Fi PHY capture or divider manipulation was added here.
  Upstream declares GPL-3.0-or-later. No ESP-SDR code was copied into this adapter.

Pinned downloaded source/license hashes are in
`harness/results/upstream-research-20261016/manifest.json`.

## Conducted receive observations

At each frequency the source used hardwaregain -80, -70 and -60 dB, with an
OFF/ON/OFF RX probe per level. LoRa tone offset was +20 kHz; GFSK was +1 kHz.
At 3000 MHz the source was clamped to exactly 3000 MHz to respect the pad rating.
The reported RSSI is an uncalibrated chip value, not SMA-port input power.

| DUT frequency | LoRa RSSI rise at -60 dB drive | GFSK RSSI rise at -60 dB drive |
|---|---:|---:|
| 50 / 100 / 169.4 MHz | -1 / +1 / +1 dB | not tested with source |
| 315 MHz | +14 dB | not tested with source |
| 433.92 MHz | +23 dB | +31.5 dB |
| 600 MHz | +34 dB | not tested with source |
| 868 MHz | +54 dB | not tested with source |
| 915 MHz | +51 dB | +64.5 dB |
| 1000 MHz | +43 dB | not tested with source |
| 1300 MHz | +30 dB | +40.5 dB |
| 1400 MHz | +25 dB | +35.5 dB |
| 2400 MHz | 0 dB | -1 dB |
| 2450 MHz | +1 dB | 0 dB |
| 2624 MHz | +1 dB | -1 dB |
| 2700 MHz | +1 dB | 0 dB |
| 3000 MHz | 0 dB | -1.5 dB |

At 1300/1400 MHz, increasing source drive in 10 dB steps produced roughly 10 dB
RSSI steps and turning the source off returned readings to the background. At
the upper tested points, fluctuations did not grow consistently with drive.
Some GFSK background readings hit the RSSI-code floor of -127.5 dBm; these
differences are not calibrated SNR or sensitivity measurements.

The LoRa run stopped at 1447 MHz when an ON probe returned status `0x3A` and
PLL error `0x0040` after a clear preflight probe. Shutdown was independently
confirmed. The partial log was retained; 33 completed measurements were
recovered into a new JSON artifact without editing the original log. The upper
frequencies were tested in a separate run away from that unstable edge.

All exploratory RF verdicts remain **UNVERIFIED** for source purity. These
observations do not establish fundamental-frequency reception, exclude images,
prove a contiguous receive band, or establish packet decoding.

## Synthesizer observations with Pluto OFF

The 40-point LoRa survey returned clear flags at 37 MHz and at many points through
1448 MHz; 1449, 1450, 1500 and 2000 MHz reported PLL errors. At 2400/2450 MHz and
several higher points, flags cleared and status was RX despite the absent
conducted response. At the upper edge, 3493 failed while 3494 cleared once.

The 28-point GFSK/XOSC comparison had different edge outcomes: 1446 failed,
1447 cleared, 1448/1449 failed, and 1450 cleared. 1500/2000 failed while
2200/2300 and the tested 2400–3400 MHz points cleared; 3490 failed.
These are individual status/error observations. **No stable lock window or
closure of the published PLL gap is established.** Mode, tune history,
temperature and power conditions were not held across independent cold starts.

## Evidence and exact operations

All commands ran from `F:\Ai\SX1262-SDR`. Complete-run folders include
`run.log`, raw serial output, CSV/JSON and `sha256.txt`; the runner also appended
`SX1262-SDR.log` in the launch directory. Paths below are relative to repository root.

| Operation | Evidence under `harness/results/` | Result |
|---|---|---|
| 915 MHz LoRa baseline | `20261016-194408-654565_heltec-v4-sx1262` | exit 0, 3 drive levels |
| LoRa source-OFF boundary survey | `20261016-194455-113356_heltec-v43-pll-boundaries` | exit 0, 40 frequencies |
| LoRa conducted lower/mid frequencies | `20261016-194740-958773_heltec-v43-conducted-ranges` | exit 1 at intermittent 1447 MHz PLL failure; `recovered_partial.json` preserves 33 completed points |
| LoRa conducted upper frequencies | `20261016-195017-673073_heltec-v43-conducted-upper` | exit 0, 15 points |
| GFSK source-OFF comparison | `20261016-195426-796731_heltec-v43-gfsk-pll-comparison` | exit 0, 28 frequencies |
| GFSK conducted comparison | `20261016-195502-446730_heltec-v43-gfsk-conducted` | exit 0, 27 points |
| Pluto RX stream without transmission | `20261016-194217_pluto-rx-preflight` | exit 0, 260 blocks / 2,129,920 I/Q pairs at 2.5 MS/s; RX state restored |
| Current firmware and final shutdown | `20261016-heltec-v43-session` | fw 1.1; valid 915 MHz LoRa probe; Heltec standby; Pluto TX LO powerdown=1, DDS scales all zero |

Main command forms, with actual interlocks entered only after the user's
authorization and connector confirmation:

```powershell
python harness/run_sweep.py --nominal-check --arm-rf --port COM38 --uri ip:192.168.1.228 --no-plot
python harness/run_sweep.py --pll-only --freqs 37,1447,1448,1449,1500,2000,2400,2450,2624,3494 --no-plot
python harness/run_sweep.py --receive-check --arm-rf --freqs 2400,2450,2624,2700,3000 --no-plot
python harness/run_sweep.py --pll-only --gfsk-probe --freqs 37,915,1300,1400,1500,2000,2200,2400,2450,2624,2700,3000 --no-plot
python harness/run_sweep.py --receive-check --gfsk-probe --arm-rf --freqs 433.92,915,1300,1400,2400,2450,2624,2700,3000 --no-plot
```

These compact forms explain the options; exact frequency lists, selected probe
mode and configuration for each actual run are preserved in that run's metadata
(or the immutable serial log for the aborted LoRa run).

Firmware was built with ESP-IDF 6.0.2 via `idf.py -C firmware/esp-idf build`
(exit 0). Esptool 5.3.1 on COM38 wrote/verified the images; the last write was
only app0 at `0x10000`, not a full flash erase. Local harness checks are recorded
in HANDOFF. No Linux CI, commit, push, PR or merge was performed in this session.

## Remaining experiments

Prioritize source-frequency shift and independent receiver checks at the positive
out-of-band points, especially 1300/1400 MHz. Explore repeatable reset/calibration
and tune-history controls before classifying unstable edges. Negative upper-band
results remain bounded by FEM/matching, source purity, narrow-filter frequency
alignment and the current calibration policy (915 MHz image calibration only).
RF tests above 3 GHz require a suitably verified path. Heltec-to-Pluto packet TX
remains untested and secondary to the receive-range objective.
