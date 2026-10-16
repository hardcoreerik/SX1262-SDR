# Canonical local execution prompt

For the unified Grok + ChatGPT harness, the authoritative **complete local-session engineering prompt is [LOCAL_SESSION_GPT_LUNA.md](LOCAL_SESSION_GPT_LUNA.md)**.

The earlier one-harness integration supersedes the original stand-alone test-scaffold brief. Do not create a second orchestrator, assume firmware exists or rely on a named COM port from a historical note.

Minimum required order:
1. Read AGENTS.md, README.md, docs/LOCAL_SESSION_GPT_LUNA.md and harness/LOCAL_QUICKSTART.md.
2. Safely fetch main and create an ai/<topic> development branch, preserving local changes.
3. Run Python harness/unit regression and simulation, verify current-directory SX1262-SDR.log.
4. Inventory the Heltec exact hardware revision and Pluto clone read-only; verify safe RX hardware interface.
5. Implement/compile a receive-only Heltec SX1262 firmware adapter, verified serial protocol, simulator fixture and host profile.
6. Obtain explicit flashing authorization before touching the identified Heltec firmware.
7. Obtain separate physical conducted-RF confirmation and TX authorization before enabling the Pluto source.
8. Persist real source-off/on bench evidence and uncertainty. Above RTL reference coverage, UNVERIFIED until independent high-band source verification exists.
9. Update docs/HANDOFF.md and preserve evidence for REA-Results inbox. Never confuse simulations, lock, RSSI and true RF reception.
