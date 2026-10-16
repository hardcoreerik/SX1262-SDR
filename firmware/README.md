# Planned receive-only Heltec V4 firmware

Not flashable yet. This directory intentionally contains **no firmware binary or flashing scripts** until exact revision, electrical pin mapping, TCXO and RF front-end configuration are verified.

Requirements: compile under ESP-IDF for ESP32-S3; conservative radio ownership; no TX opcodes; RESTORE config; log all RX, image calibration and PLL states; commands to query device revision/status and sweep <= bounded point count.

The implementation must preserve operating firmware until explicit flash permission and record a recovery procedure. It must never assume Heltec board resources or pins from LilyGO LakeShark without reading the Heltec schematic. A PC simulator for the command protocol should be written first.
