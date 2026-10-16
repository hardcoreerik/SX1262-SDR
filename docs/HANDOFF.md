# Current handoff

## Complete
- Created isolated project structure in hardcoreerik/SX1262-SDR.
- Evidence summary and receive-only test plan.
- Offline SXPROBE parser, example fixture, six unit tests and execution-folder log helper.
- Proposed Pluto conducted oracle and negative-control procedure.

## Not completed
- No verified Heltec V4 hardware revision/pin mapping.
- No compiled ESP-IDF firmware.
- No SX1262 radio commands executed.
- No Pluto or Heltec connected; no data collected on actual hardware.
- No direct 2.4 GHz SX1262 reception demonstrated or claimed.

## How to run/test
Open a terminal at repository root. Execute python -m unittest discover -s tests -v.
For the sample file run: python tools/analyze_sweep.py examples/synthetic_sxp.csv --out results/synthetic.json --origin synthetic.
Expect 9 synthetic rows with 5 RX PLL lock errors; classification includes rssi_observed_unverified, never real RF proof. Verify SX1262-SDR.log exists in the folder you ran the command from. On repeat use a different output filename; generated files are protected from overwrites.

## Next owner
Start in docs/CHATGPT_START_PROMPT.md. Preserve RX-only boundary and staged hardware approval. Add a modular ESP-IDF SX1262 service rather than pinning LilyGO GPIO assumptions.
