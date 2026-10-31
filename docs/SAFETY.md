# Safety and RF compliance

The current bench work includes receive/synthesizer characterization plus bounded, conducted bidirectional checks: Pluto TX -> Heltec RX and Heltec TX -> Pluto RX. Heltec test TX is limited to one fixed packet per runtime arm at a conservative chip output setting in 902–928 MHz. Do not add CW, repeated/unbounded TX, off-band radiation, deauthentication, or undocumented PA/eFuse writes.

For Pluto-based source verification, use only a physically isolated conducted path, never radiated out-of-band RF:
- TX disabled until cable/power budget is documented and a safe attenuation chain is verified;
- the user reports a 30 dB, 10 W attenuator rated through 3 GHz followed by a 1 ft SMA cable between Pluto and Heltec V4.3; its exact model, tolerance, connectors and installed orientation still need direct bench verification;
- the KCT8103L FEM is specified for 860–930 MHz; don't infer its receive bypass behavior or power handling outside that band from SX1262-only limits;
- use appropriate 50-ohm attenuators, proper connector adaptors and DC block where needed;
- be aware clone Pluto TX output and Heltec RF input maxima vary with board hardware and settings; do not invent dBm figures;
- verify no attached over-the-air antenna or incorrect TX/RX port;
- use lowest available output, conservative attenuation and independent power verification where possible;
- signal generator should default to OFF and require an explicit operator action to enable;
- recheck source-off control before every new frequency group, and disable TX on completion or abnormal state.

It is never acceptable to call a device-state value calibrated sensitivity. If Pluto output power cannot be trusted at a frequency, document RELATIVE detection only. Keep all controlled-tone work authorized, conducted and low-level.
