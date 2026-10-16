# Safety and RF compliance

Research is receive-only on the SX1262. Do not add SX1262 TX or deauthentication functionality.

For Pluto-based source verification, use only a physically isolated conducted path, never radiated out-of-band RF:
- TX disabled until cable/power budget is documented and a safe attenuation chain is verified;
- use appropriate 50-ohm attenuators, proper connector adaptors and DC block where needed;
- be aware clone Pluto TX output and Heltec RF input maxima vary with board hardware and settings; do not invent dBm figures;
- verify no attached over-the-air antenna or incorrect TX/RX port;
- use lowest available output, conservative attenuation and independent power verification where possible;
- signal generator should default to OFF and require an explicit operator action to enable;
- recheck source-off control before every new frequency group, and disable TX on completion or abnormal state.

It is never acceptable to call a device-state value calibrated sensitivity. If Pluto output power cannot be trusted at a frequency, document RELATIVE detection only. Keep all controlled-tone work authorized, conducted and low-level.
