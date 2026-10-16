# SX1262 Heltec V4 RF capability test plan

**Single orchestration harness:** `harness/run_sweep.py`. The earlier `tools/analyze_sweep.py` is only a static log parser. Begin with `harness/LOCAL_QUICKSTART.md`. Live hardware blocked by the placeholder profile until verified board-specific firmware is built and separately authorized.

## Gates and milestones
### 0. Freeze scope
Receive-only SX1262 tests. No firmware flash without explicit approval, no RF TX through SX1262. Preserve Meshtastic image/config. Document exact Heltec revision and Pluto clone's actual supported RF connectors/controls.

### 1. Desktop host parser
Run: python -m unittest discover -s tests -v
Run: python tools/analyze_sweep.py examples/synthetic_sxp.csv --out results/synthetic.json --origin synthetic
Expected: six passing unit tests; JSON reports 9 rows; 5 RX PLL errors; rf_reception_proven=false. File SX1262-SDR.log appears in invocation folder. Delete or name a NEW JSON on repeat; scripts refuse overwrite.

### 2. Firmware preflight
Determine SX1262 SPI/RESET/BUSY/DIO1, actual Heltec TCXO supply and RF switches from schematic. Build RX-only firmware adapter with ESP-IDF and explicit no-TX opcode guard. Compile target for ESP32-S3. Add serial commands: identify, begin_rx, sweep, status, restore, emergency_stop. Log part errors and all command returns. No hardware flash until approval.

### 3. Replicate known window
Read manufacturer-approved SX1262 nominal frequency; test 433.92/868/915 MHz consistent with RF board path and reception laws; measure status, RSSI and actual injected external RF. Then test near 1400–1500, 2600–2680 MHz using strictly controlled conducted source; compare reported lock to published LilyGO figures. Temperature and rail conditions matter.

### 4. Investigate gap
Receive-only permutations: standby RC/XOSC, cold-start vs hot retune, previous-channel history, calibration none/once/each, crystal/TCXO warmup, gain power-saving/boosted. Run repeated randomized order with controls. Preserve raw error flags and timing. If chip consistently returns PLL_LOCK, do not pretend receiver is working. Restrict register exploration to identified writable safe registers and documented rollback.

### 5. RF oracle testing
Use docs/PLUTO_PROCEDURE.md. Generate controlled known-frequency CW through verified physical attenuators. Test source-on/source-off, move TX and RX frequencies separately, check signal response width and latency. Verify source independently; no unattenuated RF port-to-port connections.

### 6. Determine practical limits
Characterize noise/response vs frequency, image rejection, RSSI linearity, gain behavior and recovery after failed tune. Use traceable test levels to calculate sensitivity; otherwise mark results relative and uncalibrated. Distinguish *PLL lock* from *usable reception* and *actual packet decoding*.

## Deliverables and exit criteria
- Versioned console tool and normalized CSV/JSON schema.
- At least two reproductions of each edge, one warm and one cold boot.
- RF-connected measurements with negative controls.
- Clear capability matrix: supported by datasheet, developer report, Heltec reproduced, external-tone confirmed, calibrated.
- Failures categorized as SPI/TCXO/config/calibration/PLL/RSSI/no-signal/filter-path.
- Signed-off safety checklist, no TX code.
- Current-directory persistent log and handoff reproducibility commands.
