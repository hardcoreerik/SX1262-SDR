# VERIFY.md: testing checklist for SX1262-SDR

Use this checklist when ChatGPT (or anyone else) pushes the first SX1262-SDR code.

- Tick an item only with evidence: a file:line in the new repo, or a measurement.
- "SDR:" means [SAMS0N1TE/lr2021-sdr](https://github.com/SAMS0N1TE/lr2021-sdr) @ 9706241b and "LS:" means [SAMS0N1TE/LakeShark](https://github.com/SAMS0N1TE/LakeShark) @ 8586c6de.
- The background for each item is in [`TESTING-NOTES.md`](TESTING-NOTES.md).

Merging anything into `main` needs Erik's explicit OK. Review on a branch or a
draft PR first.

## 1. License and credit

- [ ] **License compatibility.** lr2021-sdr is GPL-3.0 (SDR:`README.md:7`)
      and LakeShark is GPL-3.0. If the new repo copies or adapts *any* code from them, the new repo must be GPL-3.0
      (or later-compatible) and keep their copyright notices. That includes the 0x0290 sequence, sxprobe/lrprobe
      logic, register tables and parsers. Check that a `LICENSE` file is present and correct.
- [ ] **Credit.** Credit SAMS0N1TE for lr2021-sdr and LakeShark in the README. Upstream itself credits LakeShark:
      "Original LR2021 capture and hardware integration developed for LakeShark" (SDR:`README.md:141`).
- [ ] **Provenance of the research.** Any reused facts from `research/sx1262-range/README.md` must be cited to it:
      the lock windows 37-1447 and 2624-3494 MHz (lines 23-25), the image behaviour (lines 92-103) and the gain
      register 0x08AC (lines 135-138). Do not present them as new measurements.
- [ ] **No vendor material.** No copied Semtech datasheet text, figures or binary blobs. ROM patches are Semtech
      binaries: check their license before redistributing.
- [ ] **No secrets.** No Wi-Fi credentials, tokens or personal data in configs or logs. Upstream left BLE logs out
      for exactly this reason (SDR:`research/rx-range-and-gain/README.md`, "Advertising logs are not included").

## 2. Test methodology (the gaps found in sx1262-range)

The README must state, and the data must show, each of these:

- [ ] **More than one board.** Upstream used one board and one antenna (sx1262-range README:15-17, 209-215). Ask
      for at least 2 boards, or state "single board" in every result table.
- [ ] **A real, cabled signal source** (Pluto through a filter and fixed attenuator), not board leakage. Upstream's
      only signal was the board's own 40 MHz harmonics at unknown level (lines 66-71).
- [ ] **A numeric pass threshold.** Upstream counted 1-9 dB over the floor as "weak reception" (lines 28, 85). The
      harness default is SNR >= 10 dB and all four checks.
- [ ] **Architecture-appropriate checks reported for every frequency:** on SX1262 RSSI sweeps require source shift, 10 dB attenuation, paired source-OFF and RTL reference where it can actually tune. Retune-offset does not count as independent evidence for a sweep of absolute frequencies; for IQ receivers retain a real LO-retune check.
      "Stays put when the tune moves" (lines 69-71) does not rule out an image or a different comb line.
- [ ] **Repeatability.** At least 5 reps in randomised order, with the seed recorded and mean and spread reported.
      Upstream quotes lock edges to 1 MHz from one pass (lines 41-42, 44-52).
- [ ] **Temperature** recorded at start and end, and lock edges re-checked warm and cold. Upstream says the edges
      "may move a few MHz on other parts" (lines 214-215).
- [ ] **Levels in dBm only with a calibration path.** That means a power meter on the Pluto and losses entered.
      Otherwise label levels as relative. Upstream quotes dBm far outside the matched band (lines 120-138) and says
      it is unknown whether a gain change was real (lines 136-138).
- [ ] **Image rejection measured the same way on both chips** before comparing. The upstream comparison is 30 dB
      (SX1262) against 41 dB (LR2021), measured by different methods (sx1262-range README:189).
- [ ] **The below-340 MHz offset theory** (lines 92-103) tested with a real tone, not leakage. Upstream says it
      "has not been tried on a real transmission" (lines 102-103).
- [ ] **High-window accuracy.** Frequency accuracy tested with a known tone. Upstream can only pin it to about
      25 kHz (lines 110-111).
- [ ] **Raw data and scripts committed.** Upstream's folder holds only `README.md`, whose "Reproduce" section points
      at a LakeShark dev build (lines 192-205). Expect `results/<run>/` CSV + `meta.json` (board ID, chip, ROM,
      firmware commit, temperature, losses, seed).
- [ ] **Controls present:** a terminated-input spur map, a shielded or boxed run, and the source verified on the RTL
      (harmonics checked against the dongle's own: `rtl_reference.py` linearity test).

## 3. Firmware behaviours the tests depend on (known pitfalls in lr2021-sdr / LakeShark)

- [ ] **ROM dependence (LR2021 parts).** The raw I/Q trick (undocumented 0x0290 command) is verified on LR2021
      ROM 1.24 only (SDR:`README.md:56`). The code refuses to run when Semtech's patch marker is present
      (SDR:`src/lr2021_iq.c:15-18`, LS:`ls_lora_lr20xx.c:3862-3869`). The new repo must read and log the ROM version
      and refuse unknown versions. This does not apply to a pure SX1262 design. If 0x0290-like tricks are claimed
      for the SX1262, demand evidence.
- [ ] **Wedge recovery.** A ROM routine can spin with no timeout (SDR:`docs/capture-engine.md:66-69`). On the LilyGO
      board, NRESET goes through an I2C expander (SDR:`firmware/esp32p4/main/radio.c:119-122`), so a failed I2C
      means a failed reset. Require:
      - a direct-GPIO reset (or a documented fallback)
      - BUSY timeouts on every wait
      - recovery that re-applies the full configuration
      - a test that kills a capture midway and checks the radio comes back.
- [ ] **DMA from stack buffers.** The standalone driver builds its 258-byte SPI frames on the stack
      (SDR:`radio.c:67`, `:75`, `:211`) and hands them to `spi_device_polling_transmit` (`radio.c:43-49`) on a bus
      opened with `SPI_DMA_CH_AUTO` (`radio.c:257`). LakeShark deliberately avoids DMA for these transfers
      (LS:`ls_lora_spi_cpu.h:4-7`). The new code should either use DMA-capable, cache-aligned heap buffers
      (`heap_caps_malloc(MALLOC_CAP_DMA)`) or CPU transfers.
- [ ] **Mutex race.** In the standalone firmware, `tune` and `info` (SDR:`main.c:99`, `:104`) call
      `radio_configure` / `radio_info` (`radio.c:148`, `:225`) without the radio lock that the capture path takes.
      In the new code, every console command that touches SPI must hold the same lock as streaming.
- [ ] **Unchecked return values.** Some radio calls ignore errors (SDR:`radio.c:189`, `:199`, `:254`). Grep the new
      repo for ignored `esp_err_t` and SPI results.
- [ ] **Gain control.** If gain is left to the chip's AGC (no fixed-gain command, as in the standalone LR2021
      firmware), linearity tests such as check 3 are meaningless. Require a fixed-gain mode.
- [ ] **Throughput claims.** Any sample rate above what the SPI clock carries is impossible. For the LR2021 path,
      16 MHz SPI gives at most 2 MB/s, under 500 k IQ16 pairs/s before overhead (SDR:`radio.c:258`). Ask for
      overflow counters and continuity checks (generation/first_pair, as SDR:`src/lr2021_iq.c:90-174`) in every
      streaming result.
- [ ] **Shared-bus capture.** A capture holding the whole SPI bus (SDR:`radio.c:194-205`) blocks other devices.
      Check the board design for a dedicated bus.
- [ ] **RF switch and TCXO configuration.** Pins and voltages must come from the board's schematic, not be copied
      from the LilyGO variant (LS:`variants/t_display_p4.h:153-215`).
- [ ] **Receive-only by default.** Probe and test commands must never transmit. Upstream states this for
      sxprobe/lrprobe (LS:`ls_lora_sx126x.c:1008-1015`, `ls_lora_lr20xx.c:3791-3794`). Any TX feature needs a
      clear legal note.

## 4. Heltec WiFi LoRa 32 V4 specifics

- [ ] **Revision and FEM.** Record the board revision and the FEM part (GC1109 on V4.2, KCT8103L on V4.3, per third-party sources). Set and log the FEM's RX mode (LNA or bypass) explicitly at boot. Do not leave it to defaults.
- [ ] **Input limits.** Use the FEM datasheet's maximum input, not the SX1262's, for the bench attenuation budget.
- [ ] **RF switch.** Check DIO2-as-RF-switch, the TCXO voltage, and that nothing drives the PA control pin twice (a known Heltec V4 pitfall in Meshtastic, PR #9029).
- [ ] **Not a LakeShark board.** `lora sxprobe` and the published tuning windows come from LakeShark on another board. Re-measure them on the V4 rather than quoting them.

## 5. Harness integration

- [ ] The new firmware's console commands are added as a profile in `config/dut_profiles.json`, with
      template, done_regex, parser and file:line sources, and `sx1262_sdr_tbd` is replaced.
- [ ] `python -m pytest -q harness/tests` (from the repo root) passes, with a parser test that uses the new firmware's literal output.
- [ ] One real bench run is committed with its `meta.json`, and the README's claims match `summary.csv`.
