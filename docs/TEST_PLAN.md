# SX1262 Heltec V4 RF capability test plan

**Single orchestration harness:** `harness/run_sweep.py`. The earlier `tools/analyze_sweep.py` is only a static log parser. Begin with `harness/LOCAL_QUICKSTART.md`. Heltec V4.3 firmware 1.2 has been flashed and checked; the generic placeholder profile remains simulation-only. See `HELTEC_V43_BENCH_2026-10-16.md` for exact measured results.

## Gates and milestones
### 0. Freeze scope
Bounded receive tests plus one-shot conducted SX1262 TX. No firmware flash without explicit approval. Preserve Meshtastic image/config. Document exact Heltec revision and Pluto clone's actual supported RF connectors/controls.

### 1. Desktop host parser
Run: python -m unittest discover -s tests -v
Run: python tools/analyze_sweep.py examples/synthetic_sxp.csv --out results/synthetic.json --origin synthetic
Expected: six passing unit tests; JSON reports 9 rows; 5 RX PLL errors; rf_reception_proven=false. File SX1262-SDR.log appears in invocation folder. Delete or name a NEW JSON on repeat; scripts refuse overwrite.

### 2. Firmware preflight
V4.3 pin/FEM controls and firmware protocol are implemented for ESP32-S3. The user explicitly accepted no old-image backup and approved flashing COM38 and custom firmware development. Both LoRa and GFSK probes and stop have responded successfully. New devices still require their own approval.

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
- Signed-off safety checklist and evidence of the bounded one-shot TX control.
- Current-directory persistent log and handoff reproducibility commands.
