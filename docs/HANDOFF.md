# SX1262-SDR — local bench handoff (2026-10-16)

## Current objective

Latest receive-only comparison: [monopole/open/LOAD](HELTEC_991_ANTENNA_LOAD_2026-10-16.md).
492 points across twelve exits0, 98.6..99.6 MHz, 58.6/467 kHz filters, both scan
directions. User reports27-inch monopole; NanoVNA nominal50ohmLOAD gives matched
baseline. At programmed99.1, median antenna aboveLOAD9.5dB/4dB, but antenna
scans vary markedly; station/FM audio remains unverified. Firmware1.3 unchanged.
Current physicalstate: LOAD on Heltec, antenna and TX cable disconnected.
Independent Pluto TX-off and Heltec standby checks passed. No host tests needed
for this no-code stage; no build/flash. Raw/derived evidence and hashes:
`harness/results/20261016-heltec991-antenna-session/`.

Latest direct-reception attempt: [99.1 MHz record](HELTEC_DIRECT_991_2026-10-16.md).
74 conducted points with 4.8/58.6/467 kHz filters found at most 0.5/1.5/0.5 dB
ON-OFF rises at 99.1 MHz, versus 26.5/23/17 dB at 250 MHz controls. No direct
99.1 reception or Heltec audio established. Custom firmware **1.3** built,
flashed/hash-verified on COM38 and identity/mode checked; TX limits unchanged.
30 targeted tests passed, no full suites/Linux CI. Source independently OFF,
Heltec standby. Antenna transfer to Heltec requested for receive-only check.
Evidence `harness/results/20261016-direct991-session/`. Inherited wider-run
metadata has old image hash; use actual flash/provenance sidecar as documented.

Latest bench: [99.1 MHz RX1 -> 250 MHz TX1 relay](PLUTO_FM_RELAY_2026-10-16.md).
User confirmed RX1 monopole and existing TX1 pad/cable. One ten-second live
host-buffer relay completed after two preserved TX-timeout aborts; decoupling
serial probes from DMA resolved the observed stall in the bounded check.
Heltec RSSI -116 off / -108..-109 on / -116 after at 250 MHz, status/errors valid.
Saved audio comes from Pluto RX1, not Heltec. Firmware remains 1.2. Independent
TX-off and Heltec standby checks passed; 29 targeted host tests passed.
Evidence: `harness/results/20261016-211747-028280_heltec-v43-fm991-relay-decoupled/`.

Discover SX1262 receive/synthesizer limits on the user's Heltec V4.3. The user
reaffirmed that other frequency ranges are the main goal. Bidirectional packet
checks are secondary. Use the single `harness/run_sweep.py` runner.

### Latest frequency-offset investigation

Units clarification: 156 Hz is the source-frequency adjustment around 250/315
MHz carriers, not reception at 156 Hz. The follow-up report now includes a
planned 96-point lower-band bandwidth/image survey (169.4/185/200 MHz plus
250 MHz control), with a bounded firmware bandwidth option required first.
That next survey is not run. Preserve the existing session hashes; the original
report snapshot is saved separately before this documentation amendment.

Follow-up: [fixed RX / adjusted source record](HELTEC_V43_FIXED_RX_2026-10-16.md).
Previous findings committed as 841daf7 (three docs/evidence files). Twelve new
live runs then completed 228 points, five paired repeats at 250 MHz and one at
315 MHz. Median source-axis center shift -164 Hz at 250 MHz versus -156 Hz
prediction; median pairwise model-axis difference -7 Hz (interpolated, not
absolute accuracy). Fixed frequency programming, not continuously held PLL.
New `--fixed-rx-mhz` mode remains inside the existing runner and safety guards.
Targeted tests: 24 passed, exit 0. Final independent shutdown/standby passed.
Evidence: `harness/results/20261016-fixed-rx-source-session/`. New runtime changes
and this follow-up report remain uncommitted; no push/merge/flash.

See [the offset-map record](HELTEC_V43_OFFSET_MAP_2026-10-16.md): 494 new
conducted points, five fine repeat sweeps and source/LO controls. Source DDS
quantization explains much of the small apparent offset. Changing LO/DDS split
moved strong response centers about 299/333 Hz against a 312.5 Hz prediction.
Do not apply the earlier -1 kHz estimate or the descriptive fitted ppm as a
receiver calibration. Candidate table, hashes and plots are in
`harness/results/20261016-offset-map-session/`; automatic application is off.
Raw probe metadata now preserves IIO LO/DDS readbacks. Targeted regressions:
23 passed, exit 0; full suites/Linux CI not repeated. Firmware remains 1.2;
final source shutdown and Heltec standby were checked.

### Latest lower-band continuation

See [the lower-band record](HELTEC_V43_LOWER_BAND_2026-10-16.md). Five further
hardware runs completed 117 points without changing firmware 1.1. A measurable
response appeared at 200 MHz; at fixed -60 dB source drive, rises were 9 dB at
200, 20.5 dB at 225 and 29 dB at 250 MHz. In a paired fixed-absolute-grid test,
a +5 kHz source shift moved the sampled RX peak +5 kHz. Source purity/direct
fundamental RX remain unverified. 100/169.4 MHz did not respond at the tested
nominal and displaced settings. Do not call the weak 175-200 MHz transition a
hard chip limit.

Added bounded `--rx-offsets-khz` to the existing receive-check path; no new
runner or flash. Targeted host regressions returned 21 passed for the offset extension, then 22 passed after the firmware identity/range extension, all exit 0.
Final shutdown was independently checked again. Next priority is controlled
calibration/filter comparison and independent source verification, then known
payload recovery. Preserve all raw lower-band results and the analysis plot.

Firmware 1.2 subsequently expanded only the RX command floor from 37 MHz to 1 MHz. Two source-OFF surveys completed 32 requests. 36.3 MHz returned RX/no-error once, but 36.4 failed and 36.5-36.9 cleared. No stable lower limit or sub-37 MHz reception is proven. Firmware 1.1 binary/source are archived; current final shutdown evidence is in `harness/results/20261016-lower-synth-v12-session/`.

## Authorization and current hardware

- User identified HTIT-WB32LAF V4.3 / KCT8103L on COM38, accepted no old-image
  backup, approved its flash, and authorized continued device-specific firmware.
  Do not restart the waived backup gate for this board/session.
- Same SSTV TX1 -> 30 dB, 10 W, 3 GHz pad -> 1 ft SMA -> Heltec arrangement.
  User confirmed TX1 after briefly moving to RX1. The cable is last known on TX1.
- User explicitly authorized bounded unfiltered receive checks at the listed
  frequencies through 3 GHz. Full source-verified sweeps still require their filter.
- Pluto discovered at `fishball.local` / `192.168.1.228`; old `192.168.2.1` failed.
- Final readback: Pluto TX LO powerdown=1, gain=-89.75 dB, all four DDS scales=0.
  Heltec passed a 915 MHz LoRa probe and confirmed standby with `stop`.

## Implemented and exercised

- Firmware **1.2** flashed/verified on COM38: 207,152 bytes, SHA-256
  `71b283f50a2fde36df7558ce1fe7ad39ed319069f31c96b02aa915efb42954c9`.
- USB Serial/JTAG primary console and reconnect-tolerant command loop.
- Bounded LoRa/125 kHz probe plus selectable GFSK/4.8 kHz/XOSC/eight-read probe.
  Invalid RX status/errors no longer produce a valid RSSI sample; mode, bandwidth,
  read count and calibration errors are reported. Host profile requires fw 1.2.
- `--pll-only` runs with source OFF. `--nominal-check` is fixed to 915 MHz.
  `--receive-check` permits <=20 frequencies within source range and <=3 GHz,
  drive -80/-70/-60 dB, paired source-OFF controls, no source enable on bad preflight,
  shutdown on failures, raw logs and hashed evidence. Typed RF interlocks remain.
- `--gfsk-probe` selects the comparison mode. Firmware modes are not equivalent data.
- Pluto RX helper and `--heltec-tx --arm-heltec-tx` integrated in the master runner.
  Actual RX streaming captured 2,129,920 I/Q pairs and restored RX settings.
  No Heltec test packet has been transmitted.
- Custom firmware remains a bounded RSSI/packet modem adapter; no SX1262 raw I/Q claim.

## Actual findings and evidence

See **[the dated bench record](HELTEC_V43_BENCH_2026-10-16.md)** for tables,
commands, pinned upstream sources, raw artifact locations, hashes and limitations.

- Source-dependent RSSI steps at discrete points including 1300 and 1400 MHz in
  both LoRa and GFSK. At strongest tested drive, GFSK rises were 40.5 and 35.5 dB.
- No consistent drive-dependent response at 2400, 2450, 2624, 2700 or 3000 MHz
  through this setup, despite clear error flags on several of those tunes.
- PLL error/status behavior was unstable near the edges and changed with probe
  mode/history. No stable lock windows, gap closure or direct high-band RX proven.
- LoRa RF run stopped at intermittent 1447 MHz PLL error. Its immutable log and
  recovered partial data preserve 33 completed points; the stop was not a PASS.
- Old-image backup remains incomplete by accepted operator decision. Never claim
  original Meshtastic rollback was preserved.

## Validation and remaining gates

- `python -m pytest -q harness/tests`: **33 passed**, exit 0.
- `python -m unittest discover -s tests -v`: **6 passed**, exit 0.
- `python harness/run_sweep.py --sim --config harness/config/sim_example.json --no-plot`:
  simulator only; fresh successful output is recorded in preflight logs.
- `idf.py -C firmware/esp-idf build`: exit 0 with ESP-IDF 6.0.2.
- Esptool app writes: exit 0, hash verified. Actual fw 1.1 identity, both nominal
  probe modes, stop and final source shutdown checked.
- Linux CI is not run for these uncommitted changes. No push, PR or merge performed.

Next: source-shift and independent reference checks at positive out-of-band
points; controlled calibration/reset/history comparison before declaring edges.
No calibrated RF input levels or source purity have been established at these
frequencies. Above-3-GHz RF work needs a suitable verified path. Preserve local
results, copied firmware and raw logs; do not commit binaries/device identifiers.


## 2026-10-17 rapid RSSI LOAD test

Custom firmware1.4 is flashed on identified COM38 HeltecV4.3. Eight receive-only 99.1MHz bursts collected30000 records, matching CRCs, and checked device envelope PCM. See [rapid RSSI report](HELTEC_RAPID_RSSI_LOAD_2026-10-17.md). All timestamp intervals within+/-10%; strict >=8000/s voice gate remained false at measured7999.968/s. No FM audio or internal RSSI update bandwidth proven. Final Heltec standby; Pluto powerdown1 and DDS scaleszero. User reconfirmed50ohm LOAD remains fitted; antenna/TX cable disconnected. Next useful step: known conducted modulation to test temporal response, requiring physical recabling before TX. Local targeted tests34passed; no LinuxCI/fullsuite.


## 2026-10-17 AM response preparation

Firmware1.5 is now flashed and identity-checked onCOM38, extending rapid capture to fixed99.1/250.001MHz. Source-OFF250.001MHzprobe valid/status0x52/errors0; Heltecstandby and Plutopowerdown1. AM test has NOT run: awaiting operator recabling fromLOAD to TX1->30dBpad->cable->Heltec, no antennas, and typed ARM MODULATION CHECK. See [prepared protocol](HELTEC_AM_RESPONSE_2026-10-17.md).38targeted tests passed; no LinuxCI/fullsuite.


## 2026-10-17 AM response completed

Operator confirmed conductedTX1path and armed the test. Five repetitions completed30captures240000records at programmed250.001MHz; all300/1000/2500HzAM responses passed predeclared screen thresholds, carrier delta12.5–17dB, source-OFF recovered. AllrecordCRCs and122originalmanifestentries verified, every devicePCM value independently matched. DevicePCM tone demo saved. This is repeatable AM/RSSI envelope response, notFM decoding, independent RF-frequency proof, or99.1MHz reception. See [AM report](HELTEC_AM_RESPONSE_2026-10-17.md). Finalfirmware1.5/COM38, Heltecstandby; Plutopowerdown1/all8DDSscaleszero. ConductedTX1->30dBpad->cable->Heltec remains connected, antennas disconnected. Next: bounded FM/slope experiment at this same responsive band before returning99.1MHz. NoFMtest run yet.


## 2026-10-17 controlled FM slope test completed

Firmware 1.5 unchanged. Same conducted connection, RX fixed at 250.001 MHz, 58.6 kHz GFSK filter. Source generated constant-envelope FM, +/-5 kHz deviation; offset scan selected source -30 kHz (nominal 249.971 MHz). Centered 1 kHz FM fit 0.023 dB; selected slope 5.87 dB. Five confirmations passed both 1 kHz and 2.5 kHz tones with source-OFF and steady-carrier controls. 43 captures / 344000 records, all CRCs and device PCM checked; 174 original artifact hashes verified. See [FM slope report](HELTEC_FM_SLOPE_2026-10-17.md). This supports FM-to-envelope conversion in the setup, not independently pure RF FM, broadcast FM bandwidth, or direct 99.1 MHz reception. Final COM38 fw1.5 stop acknowledged; Pluto powerdown1 and all eight DDS scales zero. Conducted TX1->30 dB pad->cable->Heltec remains connected; no antenna. Next: controlled 99.1 MHz carrier/slope checks, noting prior direct checks were negative. 41 targeted tests passed; no flash/build, Linux CI, commit/push/merge this step.


## 2026-10-17 direct antenna FM attempt

User removed conducted Heltec cable and attached ~27inch monopole; ZIP97477. PlutoTXOFF for entire attempt.400RSSI survey points and30one-secondcaptures/240000records; no verified station audio. Strong98MHzregion energy remains unclassified. Firmware1.6 flashed,44targeted tests pass; capture now bounded88–108MHz plus250.001MHz anchor. See [off-air report](HELTEC_OFFAIR_FM_2026-10-17.md). Local speech screen found no reliable transcript; no broadcast success claimed. A fine98.0–98.2MHz capture is prepared; awaiting operator reply to move board/antenna away fromPC/USBhubs or state cable limits before logging new placement. FinalCOM38fw1.6stopacknowledged, Plutopowerdown1/all8DDSscaleszero. Current last confirmed Heltec connection is antenna, NOT conductedTXcable.


## 2026-10-17 approved LNA comparison completed

Firmware1.8 flashed and identified onCOM38; GPIO7powerenable readback1. Approved12captures completed,96000records,49originalhashes and all devicePCM verified. Bypass versus onboardLNA increased reported RSSI21.5–23.5dB across89.7/98.1/99.1MHz and58.6/467kHz filters; no verified broadcast audio. See [LNA comparison](HELTEC_LNA_COMPARISON_2026-10-17.md). This is total-level change, not calibrated wanted-signal gain.46targeted tests pass; noLinuxCI/fullsuite/commit/push/merge. Important prior-provenance qualification: firmware<=1.6 did not explicitly drive front-end regulatorGPIO7; actual earlierrail state unknown, not necessarilyOFF. Firmware1.7 corrected that;1.8 adds bounded FM-band forcedRX LNA. FinalHeltecstandby; Plutopowerdown1/all8DDSscaleszero. Relocated vertical monopole remains onHeltec, conducted cable disconnected. Next useful diagnostic: known conducted98MHz stimulus with corrected power/LNA states; requires physicalrecabling beforeTX and has notrun.
