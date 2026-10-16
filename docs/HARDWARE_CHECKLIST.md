# Hardware bring-up checklist — fill in before any flash

- [ ] Photograph both sides of exact Heltec WiFi LoRa 32 V4 board. Record its full revision and manufacturer silkscreen.
- [ ] Determine whether it is V4, V4.1, V4.3 or another revision; confirm genuine SX1262 chip and RF front end.
- [ ] Confirm SX1262 SPI CLK, MOSI, MISO, NSS; BUSY; DIO1; RESET; TCXO supply/control; antenna switch and any LNA/SAW controls from board-specific schematic.
- [ ] Confirm USB serial port, boot mode, ESP32-S3 flash/PSRAM details, ESP-IDF version, serial driver.
- [ ] Save current firmware image, partition table, device identity and all recoverable settings if permitted.
- [ ] Verify receive input impedance, allowed input power, DC bias, antenna path and possible inline filters.
- [ ] Identify Pluto-compatible board RF ports **from its own documentation**, firmware, RF level limits, and supported USB/ethernet transport.
- [ ] Assemble quality fixed attenuators and couplers, approved DC isolation, proper connectors and 50-ohm termination.
- [ ] Draw and verify measured line-up loss/gain before enabling RF source.
- [ ] Determine what equipment is available to measure actual power; if not calibrated, label level sweep RELATIVE only.
- [ ] Obtain specific user approval before flashing or altering hardware.
