# Testing notes: lessons from the original SX1262 range test

Source reviewed: `research/sx1262-range/README.md` in [SAMS0N1TE/lr2021-sdr](https://github.com/SAMS0N1TE/lr2021-sdr)
@ 9706241b (GPL-3.0). Line numbers below refer to that file. The review was part of REA Bot's deep dive for Erik
Elfstrom on 2026-10-16.

## In plain language

The original study is good exploratory work and was honest about its limits (lines 207-217). As evidence, though,
it is weak:
- One board.
- No external signal: the only "signal" was the board's own 40 MHz clock leaking.
- A chip RSSI reading with no pass threshold.
- No controls.

So it shows *where the synthesizer locks* on that one board. It does not show *how well the receiver works* at
those frequencies.

This harness exists to fix that. It uses a real cabled tone, four independent checks per frequency, repeats in
random order, and records everything needed to repeat the run.

## What went wrong, and what the harness does instead

| # | Gap in the original test | Evidence | What to do (harness feature) |
|---|---|---|---|
| 1 | One board, one antenna, one place, no repeats or spread. Lock edges quoted to 1 MHz from one part. | lines 15-17, 23-25, 41-52, 209-215 | At least 5 reps in randomised order from a recorded seed; mean and SD in `summary.csv`; `board_id` in `meta.json`. Test at least 2 boards before quoting edges. |
| 2 | No external source. Every receive result uses the board's 40 MHz harmonics, at unknown level. | lines 66-71 | Pluto → filter → fixed attenuator → step attenuator → DUT, cabled. The antenna is out of the measurement. |
| 3 | "Works" has no threshold: 1-9 dB over the floor counted as "weak reception". | lines 28, 85 | Pass rule in config: SNR ≥ 10 dB **and** all four checks pass **and** no spur conflict, in ≥ 80% of reps. |
| 4 | Lock judged only by the `PLL_LOCK` flag. "Locks at most points" is not quantified. | lines 38-40, 50 | A lock flag is recorded but never counts as reception. Only a tone that passes the checks does. |
| 5 | **Biggest confound.** "Stays put when the tune moves" rules out spurs that follow the tune, but not a *different* comb line heard through mixing or an image. The 10 ppm argument fits every comb line equally. | lines 69-77, 105-113 | Four checks: the source moves → the response moves the same way; the receiver retunes → the response moves the opposite way; 10 dB less in → 10 dB less out; the RTL-SDR confirms the source is clean at alias and image frequencies. |
| 6 | The theory for responses below 340 MHz (the IF/image explanation) was never tried with a real transmission. | lines 92-103 | The retune check exposes image responses directly: they move the wrong way. |
| 7 | Image rejection (~30 dB) was measured differently from the LR2021's 41 dB, then compared. | line 189 | Same method for both chips: a tone at F+Δ, compared with the response at F-Δ (I/Q profiles). For RSSI-only chips this is N/A until the IF is known. |
| 8 | dBm quoted far outside the band where the RSSI is calibrated. A gain register effect could not be told apart from a shifted reading. | lines 120-138 | dBm only when the Pluto output is measured (`pluto.ref_dbm_at_0db_gain`) and the losses are entered; otherwise relative dB only. |
| 9 | Internal 868/915 antenna used from 37 to 3494 MHz. | lines 209-211 | Conducted test only. |
| 10 | Temperature not recorded, although the edges "may move a few MHz". | lines 214-215 | Temperature asked at start and end. Repeat the edge frequencies cold and warm. |
| 11 | No controls: no terminated input, no shielded run, no second board, no random order. | (absent) | A terminated-input spur map before every sweep; spur-on-tone conflicts fail the point. |
| 12 | RSSI comes in 0.5 dB steps and floors at -127.5 dBm. | lines 216-217 | Weak SNRs read short. The MDS search stops at the threshold; it does not extrapolate. |
| 13 | No raw data or scripts in the study folder. The "Reproduce" section points at a LakeShark dev build. | lines 192-205 | `results/<run>/` holds `measurements.csv`, `summary.csv`, `spur_map.csv`, `source_check.csv`, `meta.json` and `run.log`. Commit them. |
| 14 | No version info (silicon revision, firmware commit). | (absent) | `meta.json` records the chip, ROM/revision, firmware commit, harness commit and config. |

## Extra lessons that matter for this repo

- **Different board.** The original numbers come from LakeShark's SX1262 board. The Heltec WiFi LoRa 32 V4 adds an
  external FEM (LNA or bypass in receive; the part varies by revision, per third-party docs). Re-measure everything,
  and record the FEM mode.
- **The SX1262 has no I/Q stream.** It offers only RSSI and its own demodulators (line 188). On the SX1262, "SDR"
  means RSSI sweeps and demodulator tests. Any I/Q claim needs proof.
- **Trust the source before the DUT.** A Pluto image or harmonic sitting where the DUT listens makes a deaf receiver
  look alive. That is why `rtl_clean` is a required check, and why points the RTL cannot see are reported as
  **UNVERIFIED**, not PASS.
- **Fixed gain for linearity.** AGC (chip or host) hides the 10 dB step. Use a fixed gain step for the attenuation
  check.
- **Safety.** Always have 30-40 dB of fixed attenuation at the Pluto, and stay below the receiver's input limits:
  SX1262 +10 dBm absolute maximum and 0 dBm operating (DS_SX1261-2 V1.1, Tables 3-2 and 3-3). The FEM limits on
  the V4 still need checking. Bench testing is cabled only, with minimum TX power.
