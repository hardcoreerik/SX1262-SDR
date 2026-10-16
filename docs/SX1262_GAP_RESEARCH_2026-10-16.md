# SX1262 frequency-gap investigation — research note (2026-10-16)

Goal: determine if the apparent 1448–2622 MHz SX1262 PLL failure can be reproduced and whether alternate documented/undocumented receive-only initialization provides a path around it.

## What is published
See docs/RESEARCH_EVIDENCE.md for permanent URLs. A LilyGO SX1262 receiver successfully acknowledged SetRfFrequency in many places but reported PLL_LOCK in the gap. Clock-harmonic response was reported in separated lower and upper windows. The author tested CalibrateImage, gain register 0x08AC, bandwidth codes, and RSSI sweep speed. The report does not establish an RF synthesizer topology or silicon ability to operate continuously across the gap.

## Read the code, not just README
LakeShark probe sets up LoRa first (board TCXO/regulator/calibration), changes to GFSK, writes modulation parameters, reads gain register, and scans SetRfFrequency/SetRx/GetDeviceErrors/GetRssiInst. Per-step calibration may be none/once/each; calibration band above ~1020 MHz is clamped because the command takes two 4 MHz units as bytes. It clears errors before the RX attempt, so an independent PLL_LOCK result cannot be dismissed as a stale image-cal flag.

## Key unanswered questions
1. Is the apparent gap deterministic on multiple chips, temperatures and board layouts?
2. Does a standby RC vs XOSC sequence change RF lock at gap boundaries?
3. Do cold-start vs sequential tune histories change the lock window?
4. Does the result depend on preceding LoRa/GFSK mode, TCXO timing or DCDC/LDO power regime?
5. Can known external RF be observed at upper window across external attenuator/connector independent of internal harmonics?
6. Are there undocumented divider/VCO control registers? If so, collect reproducible evidence before use.
7. Do IF image offsets explain any observed responses; can source+delta/LO-delta tests reject spurs?

## Limits
No silicon-level PHY netlist, no calibrated sensitivity survey, no independent upper window RF replication and no demonstrated SX1262 IQ. Do not imply 2.4 GHz has been unlocked or is only a software validation issue. This file is a hypothesis/test document, not a success report.
