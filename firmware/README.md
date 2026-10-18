# Heltec V4.3 conducted RF test firmware

Target: Heltec WiFi LoRa 32 **HTIT-WB32LAF V4.3**, ESP32-S3 + SX1262 + KCT8103L FEM.
This is a bounded bench adapter for both receive and transmit experiments. It does not
replace the repository's single `harness/run_sweep.py` measurement harness.
The ESP-IDF partition table matches the connected board's reported 16 MB two-slot OTA map;
the operator accepted proceeding without a full old-image backup and approved flashing COM38. The writes left the NVS partition outside the erased ranges; the bootloader, partition table, OTA selection and app0 were replaced.

## Commands

Current device continuation: firmware **1.3** adds `gfsk58` (58.6 kHz) and
`gfsk467` (467 kHz) probe modes; `gfsk` remains 4.8 kHz. Actual filter width is
reported. No audio decoder or I/Q output is implemented. Version 1.3 is flashed
on COM38, 207,392 bytes, SHA-256
`805bb48b716ff7a14d6e0b5bb657eb99c2a0e594125e91fc6f2e55bacf9e6151`.
See `docs/HELTEC_DIRECT_991_2026-10-16.md`; the 1.2 build record below is historical.

- `info`, `status`, `stop`
- `probe <frequency_hz> <dwell_ms> [lora|gfsk]`: bounded RX attempts (1..5000 ms; 1 MHz..3.5 GHz). The command range is not a guaranteed lock/reception range. LoRa uses 125 kHz bandwidth and one RSSI read. GFSK uses 4.8 kHz, XOSC standby and eight RSSI reads. Mode, bandwidth, calibration errors and read count are reported; invalid RX status is rejected as a valid sample.
- `armtx`: arm exactly one low-power LoRa test packet for 30 seconds.
- `tx <frequency_hz>`: send the fixed test payload once, only in 902..928 MHz, after
  `armtx`; requested SX1262 power is capped at -9 dBm. TX completion has a 2 s timeout.

TX is a conducted bench operation. The firmware cannot verify cabling, the attenuator's
frequency/power rating, or the power arriving at the Pluto. It does not transmit CW,
repeat packets, accept arbitrary payloads or permit TX outside the bounded band. The
operator must verify the coax and attenuator before arming. Heltec's KCT8103L FEM adds
gain, so the chip's -9 dBm setting is not a calibrated SMA-port level.

## Build

From PowerShell, with ESP-IDF 6.0.2 installed:

```powershell
Push-Location C:\Espressif\frameworks\esp-idf-v6.0.2
. .\export.ps1
Pop-Location
idf.py -C .\firmware\esp-idf set-target esp32s3
idf.py -C .\firmware\esp-idf build
```

Current flashed firmware: **1.2**, 207,152 bytes; SHA-256 `71b283f50a2fde36df7558ce1fe7ad39ed319069f31c96b02aa915efb42954c9`. Version 1.2 lowers only the RX attempt floor from 37 MHz to 1 MHz, with a new identity; TX bounds remain 902-928 MHz. Firmware 1.1 and its source were archived before this change. USB Serial/JTAG is the primary console; the command loop survives a closed/disconnected host port. The operator approved custom firmware development and flashing this board without an old-image backup. See `docs/HELTEC_V43_LOWER_BAND_2026-10-16.md` for the latest evidence. A different device still requires its own identification and flash approval.


### Firmware1.4 rapid RSSI experiment (2026-10-17)

COM38 HeltecV4.3 now runs1.4. `capture <58600|467000> <1000|2000|4000|8000>` captures up to one second at99.1MHz and returns standby before dumping timestamp/RSSI/experimental envelope PCM records with CRC32. This is not an FM decoder or raw I/Q source. Invoke through `harness/run_sweep.py --heltec-audio`; the mode keeps PlutoTXoff. See `docs/HELTEC_RAPID_RSSI_LOAD_2026-10-17.md` for exact evidence and limitations.


### Firmware1.5 (2026-10-17)

COM38 now runs1.5: capture syntax is `capture <99100000|250001000> <58600|467000> <1000|2000|4000|8000>`. The conducted AM response test is prepared in the existing runner as `--heltec-modulation --arm-rf`; RF test remains pending physical recabling and typed interlock. See `docs/HELTEC_AM_RESPONSE_2026-10-17.md`.


### Firmware 1.6 (2026-10-17)

COM38 now runs1.6. The bounded rapid `capture` command accepts88–108MHz as well as250.001MHz. Each burst remains at most one second; no TX limits changed. Use `run_sweep.py --heltec-audio --offair-fm` with <=30 FM-band candidate frequencies and bounded repetitions; this mode keeps PlutoTXOFF. See `docs/HELTEC_OFFAIR_FM_2026-10-17.md`; station reception remains unverified.
