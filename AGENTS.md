# Agent operating contract — SX1262-SDR

The experiment's owner is Erik; do not assume blanket permission to flash a connected board. This repo is private research, not a validated production device.

## Scope
- Primary device: Heltec WiFi LoRa 32 V4, exact revision to be verified, SX1262 and ESP32-S3.
- Reference: Pluto-compatible Zynq-7020 + AD9361; capabilities, calibration and actual firmware must be verified.
- First work: receiver-only commands, RSSI sweeps, reproducible conducted reference-tone tests and capture analysis.
- No transmissions from SX1262, no unknown-band radiated TX, no destructive eFuse changes, and no PCB modification without explicit user permission.

## Git and integration
- Develop on chatgpt/sx1262-rx-probe or another ai/topic branch, never directly on main.
- Use draft PRs for integration; changes can be batched rather than one PR per micro-change.
- Separate measured facts from hypotheses and simulated/fixture outcomes.
- Never copy GPL sources without deliberately reviewing license obligations and providing attribution.

## Repeatable test evidence
- Save one log file named SX1262-SDR.log in the **process current working directory**, regardless of script location.
- Store raw session logs with timestamp, firmware commit, silicon identity, board revision, TCXO and antenna path, calibration mode, frequency, errors/status, RSSI, ambient/test setup, and source-on/off.
- Never overwrite evidence. Use atomic writes where possible; hash received artifacts.
- A valid receiver-range result requires controlled source-on/off and known RF tone/frequency tracking, not merely a tuning register or RSSI.
- Differentiate synthesizer lock, RX ADC availability (if any), RSSI-only observation, packet decode, external signal confirmation.
- Reproduce each threshold measurement at least twice before promotion to an evidenced result.

## Build gates
- Run host unit tests before committing.
- Build ESP-IDF only if it is installed; declare what could not run.
- Verify target pins and crystal/TCXO before a flash.
- Test the Heltec without changing operational Meshtastic images until user approves.
- Tests must run offline using only Python standard library unless new dependencies have a compelling reason.

## REA-Results
- Read private repo hardcoreerik/REA-Results/AGENTS.md and relevant indexed findings.
- Do not hand-edit generated targets, comparisons or indexes.
- New externally generated research belongs under inbox/YYYY-MM-DD_sx1262_gap.md with source links and caveats, then feeds the local RSA publisher.

## Operational safety
- RF source must remain disabled until a physically reviewed conducted path with appropriate fixed attenuators, DC block (if required), and verified source power is present.
- Never assume a clone of the Pluto has the same output specs or calibration as the branded unit.
- Do not suggest radiating test carriers in unauthorized bands.
