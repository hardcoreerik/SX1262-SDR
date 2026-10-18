# Pluto RX1 99.1 MHz -> TX1 250 MHz conducted relay

## Setup and authorization

The user requested RX1 reception with a monopole and forwarding over the existing
TX1 pad/cable, then confirmed both connections. Existing conducted authorization
and unfiltered bench exception apply; no radiated TX experiment was requested.
Heltec HTIT-WB32LAF V4.3 / KCT8103L on COM38, firmware 1.2 unchanged.

```text
Monopole -> Pluto RX1 at 99.1 MHz
         -> host I/Q filter and forwarding
         -> Pluto TX1 at 250 MHz, hardwaregain -60 dB
         -> 30 dB, 10 W, 3 GHz pad -> cable -> Heltec RX
```

This is live host-buffer forwarding, not passive RF pass-through. The Heltec
receives a translated signal at 250 MHz, not directly at 99.1 MHz.

## Successful bounded run

`harness/results/20261016-211747-028280_heltec-v43-fm991-relay-decoupled/`:

- Runner exit 0. Forwarded 25,165,824 complex samples at reported 2.5 MS/s:
  10.066 sample-seconds during 10.010 loop wall-seconds. Buffered start/end data
  explain why sample duration need not equal wall duration. No sample-perfect
  continuity claim; hardware underruns/overruns were not independently counted.
- RX1 fixed manual gain 40 dB, analog bandwidth 300 kHz. Saved pre-relay capture:
  5,242,880 complex samples (2.097 seconds), no ADC clipping. Six-pole digital
  low-pass at 110 kHz selects the station channel before forwarding.
- TX sample normalization is fixed from an initial block; components limited to
  +/-12000 in 16-bit DMA storage. Maximum numeric component clipping fraction 0.
  Neither numeric scaling nor gain is calibrated SMA output power.
- Heltec 250 MHz LoRa-mode/125 kHz RSSI: before -116, during -108/-108/-108/-109,
  after -116 dBm (chip-reported, uncalibrated). Every probe had RX status 0x52,
  device errors 0. This is source-correlated RF response, not recovered FM audio.
- The saved mono WAV is decoded from **Pluto RX1**, not the Heltec. It uses FM
  phase discrimination, 48 kHz audio, 15 kHz low-pass and 75 us de-emphasis.
  Audio is peak-normalized; no station identity or human-listening acceptance
  is claimed. No stereo/RDS decoder was added.
- Independent fresh IIO context confirmed TX LO powerdown=1, gain=-89.75 dB,
  all four TX1 DDS scales zero. Heltec `stop` succeeded.

In this DMA experiment DDS tones are disabled. The recorded DDS frequency
attributes are inactive; the historical `lo_plus_dds_i_hz` field in
`source_before_tx` does **not** describe this transmitted signal. The translated
channel is centered on the TX LO near 250 MHz. Subsequent code marks this
distinction explicitly. Absolute RF frequency and source purity remain unverified.

## Failure investigation preserved

Two earlier runs aborted and requested safe shutdown:

- `20261016-211617-881523_heltec-v43-fm991-live-relay`: exit 1, IIO error 110.
- `20261016-211715-884710_heltec-v43-fm991-relay-diagnostic`: exit 1, error localized
  to TX push. Partial timings show steady streaming until a serial probe pauses
  the DMA loop roughly 370 ms, then TX push times out. The leading explanation
  was TX starvation. Moving serial probes to a separate monitoring thread was
  followed by the successful bounded run; hardware underrun registers were not
  measured, so the mechanism is not independently certified.

RX captures, decoded WAVs, serial logs, errors and diagnostic tracebacks remain
in their original folders. No aborted run is presented as complete. All three
have closed-run `final-sha256.txt` manifests. Initial relay manifests may include
a still-open log; use the final manifests for closed artifacts.

## Implementation and verification

The one master runner now supports `--pluto-relay`. It retains `--arm-rf`, fitted
>=30 dB attenuation, named board/FEM identity and typed `ARM FM RELAY` interlock.
The adapter fixes RX at 99.1 MHz, TX at 250 MHz, -60 dB drive, ten-second loop;
no arbitrary relay frequencies, unbounded loop or Heltec TX were added.
`PlutoReceiver` gained optional gain/bandwidth/buffer-size arguments; existing
defaults are unchanged. `harness/pluto_relay.py` is a helper, not another runner.

Live command (each label differs for its corresponding evidence folder):

```powershell
'ARM FM RELAY' | python -u harness/run_sweep.py --pluto-relay --arm-rf --config harness/results/20261016-lower-synth-v12-session/bench.json --port COM38 --uri ip:fishball.local --label heltec-v43-fm991-relay-decoupled --no-plot
```

The command was issued only after the user's physical connection confirmation.

Targeted host command:
`python -m pytest -q harness/tests/test_pluto_relay.py harness/tests/test_pluto_receiver.py harness/tests/test_unified_guardrails.py`
returned **29 passed**, exit 0. Tests cover numeric scaling, synthetic 1 kHz FM
recovery, RX/TX failures, short writes and RF/attenuation/typed interlocks.
`git diff --check` exit 0, line-ending warnings only. Full suites/Linux CI not run.

The successful folder contains raw pre-relay IQ, Pluto RX audio, an RX spectrum,
relay metadata, timing, independent shutdown, host-test record, source hashes
and final artifact hashes. Root `SX1262-SDR.log` appended. No firmware flash,
commit, push or merge in this stage.

The earlier idea of dropping to 625 kS/s was rejected after read-only discovery
showed the current non-FIR sample-rate minimum is 2,083,333 S/s. No FIR configuration
was changed. ADI's [IIO streaming example](https://github.com/analogdevicesinc/libiio/blob/v0.25/examples/ad9361-iiostream.c)
was consulted for API/sample alignment; no example source was copied into this helper.
