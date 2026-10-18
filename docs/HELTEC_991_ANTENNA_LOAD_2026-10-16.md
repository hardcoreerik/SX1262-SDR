# Heltec 99.1 MHz: monopole, open input and LOAD

## Result

Twelve receive-only runner invocations completed **492 real points**, all exit
0, with firmware 1.3 unchanged. No Heltec FM audio was captured or decoded.
Pluto TX remained OFF. The user confirmed these three physical input conditions:

1. Approximately 27-inch monopole on Heltec LoRa RF connector; TX cable removed.
2. Antenna and TX cable removed, RF input disconnected (not a matched load).
3. NanoVNA nominal 50-ohm LOAD on Heltec input; antenna/TX cable removed.

Each condition uses 41 tunes, 98.6..99.6 MHz in 25 kHz steps, forward then
reverse, with 58.6 and 467 kHz GFSK filters: 164 points per condition. Probe
settings remain 20 ms/eight RSSI reads, XOSC, existing FEM bypass and calibration
policy. All completed samples report valid RX/no device error. Results stay
`UNVERIFIED`; clear errors do not establish direct station reception.

| Filter | Antenna RSSI at 99.1, forward/reverse | Open input | 50-ohm LOAD | Median antenna minus LOAD |
|---|---|---|---|---:|
| 58.6 kHz | -112.5 / -114.5 | -122 / -123.5 | -123.5 / -122.5 | 9.5 dB |
| 467 kHz | -112.5 / -105.5 | -114.5 / -112.5 | -115 / -111 | 4 dB |

RSSI units are chip-reported uncalibrated dBm. The differences are not calibrated
SNR or sensitivity. Antenna connection changes received power, supporting
antenna-coupled energy; input mismatch, ambient changes, interference and board
coupling remain possible contributors. The station is not identified.

Antenna scans show substantial direction/time dependence: maximum paired
forward/reverse differences 29 dB (58.6 kHz) and 34 dB (467 kHz); median across
frequencies 2 and 17.5 dB respectively. LOAD scans are much more repeatable:
maximum 4/5 dB, median 1.5 dB for each width. Do not select a scan peak and call
it a stable station or install a tuning correction from it.

The 27-inch radiator is reasonably close in length to a free-space quarter-wave
at 99.1 MHz (~29.8 inches). Ground/counterpoise, cable and mounting still affect
match; no NanoVNA antenna measurement was made. The LOAD is useful as a nominal
matched termination, not an absolute RSSI/power calibration or a noise source.
Its actual RF return loss was not measured. OPEN/SHORT were not used here.

## Evidence and interpretation

Session folder: `harness/results/20261016-heltec991-antenna-session/`.
`commands.ps1`, `open-input-commands.ps1` and `load50-commands.ps1` preserve the
exact invocations/configs; they call the single `harness/run_sweep.py` with
`--pll-only --gfsk-probe --gfsk-bandwidth-hz 58600|467000`. This existing mode
guarantees external source OFF and records RSSI/status. Its generic
`no_external_stimulus` labels mean no controlled external source; ambient RF
may exist on the antenna. These labels were not changed into receive proof.

Raw run groups are `*_heltec-antenna991-*`, `*_heltec-openinput991-*`,
`*_heltec-load50ohm991-*`. All twelve raw manifests were verified. Derived
`three-input-analysis.json` and `three-input-hashes.json` retain every sampled
frequency and paired condition; `three-input-conditions.png` plots the results.
The earlier antenna-only/open-only derivations are preserved separately.
Root `SX1262-SDR.log` appended. No new implementation, host tests, firmware build,
flash or Linux CI in this receive-only stage. No commit/push/merge.

Independent final check: TX LO powerdown=1, gain=-89.75 dB, all TX1 DDS scales
zero; COM38 firmware 1.3 identity and successful `stop`. **Current physical
state is LOAD on Heltec, antenna disconnected, TX cable disconnected.** No RF
output may be enabled with that conducted path absent.

## Next useful step

The matched baseline does not establish a working FM decoder. Next add a bounded
on-device rapid-RSSI/audio capture with timestamps and measured sample rate,
starting with the LOAD still fitted to establish self-noise and capture timing.
Only after that baseline and valid timing should the antenna be restored for
an identical capture. Firmware must generate any claimed PCM audio; host audio
from Pluto is not Heltec decoding. Keep station identity, intelligibility,
frequency accuracy and source-correlated reception as separate acceptance gates.
