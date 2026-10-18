# Experimental architecture

Heltec V4: ESP32-S3 control MCU -> SPI + BUSY/DIO1/RESET -> SX1262 RF.
Reference: Pluto-compatible Zynq/AD9361 source -> measured fixed attenuation (+ DC isolation if appropriate) -> Heltec RF input.
Host: serial command console -> immutable raw session log -> CSV/JSON parser -> evidence report -> REA-Results inbox. The Heltec firmware exposes bounded RX probes and one armed one-shot TX packet.

The Heltec S3 Wi-Fi radio is a separate RF path; do not attribute its 2.4 GHz receptions to the SX1262. Do not flash or change Mesh firmware automatically.

Start with transparent commands: identify silicon, STDBY, RX config, SetRfFrequency, CalibrateImage, GetDeviceErrors, GetStatus and GetRssiInst. Preserve command-acknowledgment, calibration outcomes, PLL status and RSSI as separate fields. TX is restricted to one fixed test packet after runtime arming; there is no arbitrary register or payload command.

Require RF source-off/source-on paired captures, references at nominal bands, a pair of LO offsets, and independent RF-source evidence before saying a gap has been bridged. 
