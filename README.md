# SX1262-SDR

**How far can an SX1262 really receive?** SX1262-SDR is an open, evidence-first RF research project built around the **Heltec WiFi LoRa 32 V4.3** (ESP32-S3 + Semtech SX1262 + KCT8103L RF front end). We use controlled signals, receiver status, RSSI and repeatable bench experiments to investigate the radio's practical limits—including behavior outside its nominal 150–960 MHz tuning range.

> **Current status — October 2026:** Real V4.3 hardware is running custom ESP-IDF bench firmware **1.8**. Conducted tests show repeatable signal-correlated RSSI responses at selected frequencies, including 200, 250, 915, 1300 and 1400 MHz; experimental AM and FM-to-envelope tone responses have also been measured. **This is not a wideband IQ SDR, and the results do not establish a continuous extended receive range or a 2.4 GHz unlock.**

**[What's new](CHANGELOG.md)** · **[RF test evidence](docs/HELTEC_V43_BENCH_2026-10-16.md)** · **[Engineering handoff](docs/HANDOFF.md)** · **[Local quickstart](harness/LOCAL_QUICKSTART.md)** · **[Safety rules](docs/SAFETY.md)**

## Project highlights

| Area | What we've built or measured | Important limitation |
| --- | --- | --- |
| **Heltec V4.3 firmware** | ESP-IDF SX1262 control, bounded LoRa/GFSK probes, status/error reporting, rapid RSSI capture, GPIO7 front-end power enable and selectable KCT8103L LNA modes | Bench firmware, **not** a production receiver or a raw-I/Q interface |
| **Extended-range RF investigation** | Conducted source-on/off and offset testing, including source-correlated RSSI at 200, 1300 and 1400 MHz | Source purity and fundamental-frequency reception remain unverified |
| **Frequency / PLL mapping** | Repeated edge, calibration, tuning-history and source-offset tests; documented negative results at selected high-band points | PLL/status acceptance is **not** proof of usable reception |
| **AM envelope experiments** | Known 300, 1000 and 2500 Hz AM-envelope responses at a programmed 250.001 MHz receiver setting | Not arbitrary AM broadcast decoding or calibrated RF sensitivity |
| **FM slope experiments** | Known 1 and 2.5 kHz modulation recovered as RSSI-envelope changes with an offset carrier | Not a general FM demodulator; physical FM purity not independently verified |
| **Pluto + RTL reference workflow** | Pluto-compatible AD9361 source/receiver, limited-band RTL-SDR V4 reference and automated host evidence collection | References must be validated for the specific frequencies used |

## What the hardware experiments actually showed

Measurements below are **repository-recorded test observations** from October 16–17, 2026, not fresh independent replications. RSSI differences are uncalibrated readings, **not** SNR or certified RF sensitivity.

| Test | Observed result | Evidence |
| --- | --- | --- |
| 200–250 MHz conducted receive checks | Source-correlated RSSI; a controlled +5 kHz source change moved a sampled peak by +5 kHz at a lower-band test point | [Lower-band experiments](docs/HELTEC_V43_LOWER_BAND_2026-10-16.md) |
| 915 MHz nominal-band control | Conducted positive receive response | [V4.3 RF bench](docs/HELTEC_V43_BENCH_2026-10-16.md) |
| 1300 / 1400 MHz | Source-dependent RSSI rises, reported at up to 40.5 / 35.5 dB in GFSK at the strongest tested source setting | [V4.3 RF bench](docs/HELTEC_V43_BENCH_2026-10-16.md) |
| 2400 / 2450 / 2624 / 2700 / 3000 MHz | No consistent, convincing source-dependent receive response in the recorded setup | [V4.3 RF bench](docs/HELTEC_V43_BENCH_2026-10-16.md) |
| Known AM modulation at 250.001 MHz | All five rounds met the specified screens for 300, 1000 and 2500 Hz | [AM report](docs/HELTEC_AM_RESPONSE_2026-10-17.md) |
| Known FM slope modulation near 250 MHz | 1 and 2.5 kHz tones met screens in all five selected-slope confirmations | [FM slope report](docs/HELTEC_FM_SLOPE_2026-10-17.md) |
| Broadcast-FM antenna experiments | RF energy observed, **no verified station audio** | [Off-air FM report](docs/HELTEC_OFFAIR_FM_2026-10-17.md) |
| KCT8103L LNA comparison | 21.5–23.5 dB increase in reported total RSSI across selected FM-band tests | [LNA / GPIO7 report](docs/HELTEC_LNA_COMPARISON_2026-10-17.md) |

**Important provenance correction:** Firmware through 1.6 did not explicitly enable/read back the board's GPIO7 front-end power rail. Firmware 1.7 added that control; firmware 1.8 added bounded LNA selection. The earlier results remain useful but **do not establish a known FEM power state**. See the [LNA report](docs/HELTEC_LNA_COMPARISON_2026-10-17.md).

## Hardware and architecture

- **Device under test:** Heltec WiFi LoRa 32 **V4.3 / HTIT-WB32LAF**, with **ESP32-S3**, **SX1262**, and **KCT8103L** front-end module. Board revisions are electrically distinct: do not assume V4.2 GPIO or FEM settings apply to V4.3.
- **Controlled stimulus:** Pluto-compatible AD9361 SDR with a physically checked conducted RF path, attenuators, and safety interlocks. The measured path and source purity are experiment-specific.
- **Reference receiver:** RTL-SDR Blog V4 only where its frequency coverage has been independently validated; Pluto RX can record I/Q but is not automatically a calibrated high-band oracle.
- **Host software:** One canonical test runner, `harness/run_sweep.py`, on Windows or Linux, with simulator, CSV/JSON records, logs and regression tests.
- **Restricted transmit capability:** Heltec firmware includes separately armed, bounded single-packet **902–928 MHz conducted TX** for future checks. This does not imply permission to radiate or automatic RF activation. The project's primary focus remains **RX measurement**.

## Run the no-hardware tests

From a clean checkout in the repository root:

```powershell
python -m pip install numpy scipy matplotlib pytest
python -m pytest -q harness/tests
python -m unittest discover -s tests -v
python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot
Test-Path .\SX1262-SDR.log
```

Expected: passing host tests, a timestamped `harness/results/<run-id>_SIM/` folder with clearly marked simulated metadata, and **`SX1262-SDR.log` in the directory where you launched the commands. Simulated results **never** count as physical RF findings. For hardware and ESP-IDF steps, use the [local quickstart](harness/LOCAL_QUICKSTART.md) and [engineering handoff](docs/HANDOFF.md); don't assume old COM ports, Pluto addresses or cabling still apply.

## Documentation and research trail

| Start here | Purpose |
| --- | --- |
| [CHANGELOG.md](CHANGELOG.md) | Dated development history, firmware milestones and important corrections |
| [harness/README.md](harness/README.md) | Unified sweep runner, modes, profiles, evidence fields and controls |
| [harness/LOCAL_QUICKSTART.md](harness/LOCAL_QUICKSTART.md) | Windows/PowerShell setup, simulator, hardware preflight and handoff |
| [docs/HANDOFF.md](docs/HANDOFF.md) | Bench chronology, actual results and outstanding gates |
| [docs/TEST_PLAN.md](docs/TEST_PLAN.md) | Falsifiable research plan and acceptance criteria |
| [docs/RESEARCH_EVIDENCE.md](docs/RESEARCH_EVIDENCE.md) | Published LakeShark/SX1262 work versus our own observations |
| [docs/HELTEC_V43_BENCH_2026-10-16.md](docs/HELTEC_V43_BENCH_2026-10-16.md) | Conducted V4.3 RF measurements and failed tests |
| [docs/HELTEC_AM_RESPONSE_2026-10-17.md](docs/HELTEC_AM_RESPONSE_2026-10-17.md) | Measured AM envelope response |
| [docs/HELTEC_FM_SLOPE_2026-10-17.md](docs/HELTEC_FM_SLOPE_2026-10-17.md) | Experimental FM-to-envelope response |
| [docs/HELTEC_LNA_COMPARISON_2026-10-17.md](docs/HELTEC_LNA_COMPARISON_2026-10-17.md) | Firmware 1.7/1.8 front-end power and LNA qualification |
| [docs/SAFETY.md](docs/SAFETY.md) | Conducted RF constraints, separate approval and shutdown checks |

## What this project does *not* claim

**No raw SX1262 I/Q stream. No validated continuous wideband receiver. No demonstrated direct 2.4 GHz reception or closure of the reported PLL gap. No calibrated RF sensitivity survey. No verified broadcast FM audio.** Accepted frequency commands, PLL status, RSSI changes, source-correlated responses, frequency tracking and calibrated reception are separate evidence levels.

Published research from [SAMS0N1TE / lr2021-sdr](https://github.com/SAMS0N1TE/lr2021-sdr/blob/main/research/sx1262-range/README.md), the [LakeShark SX126x implementation](https://github.com/SAMS0N1TE/LakeShark/blob/main/components/lakeshark/board/ls_lora_sx126x.c) and [SX1262_CHIRP](https://github.com/ibelinp/SX1262_CHIRP) informs our test plan, but their board-level claims are **not** automatically Heltec V4.3 findings.

### Next research milestones

1. Reproduce the 200, 1300 and 1400 MHz responses with confirmed FEM state and independently checked source spectral purity.
2. Map PLL boundaries across cold starts, reference clocks, receive modes and calibration sequences; retain failures.
3. Determine the actual audio-envelope bandwidth and quantify antenna/filter effects without calling RSSI audio a general FM decoder.
4. Promote repeatable findings with original logs, hashes, known setup details and explicit uncertainty.

## Credits, licensing and support

The harness contains GPL-3.0-licensed work documented in [harness/LICENSE](harness/LICENSE) and acknowledges upstream work by [SAMS0N1TE](https://github.com/SAMS0N1TE). Review the relevant source licensing before redistributing combined firmware/software. Some raw bench evidence and private RSA/REA records remain off-repository; linked notes describe their provenance and limitations.

Development support helps fund electronics, receiver compatibility and controlled bench tests:

[GitHub Sponsors](https://github.com/sponsors/hardcoreerik) · [Ko-fi](https://ko-fi.com/hardcoreerik) · [PayPal](https://paypal.me/hardcoreerik)
