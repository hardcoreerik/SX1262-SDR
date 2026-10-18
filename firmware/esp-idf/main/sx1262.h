#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint8_t status;
    uint16_t errors;
    uint16_t cal_errors;
    uint8_t reads;
    int16_t rssi_dbm_x2;
    bool valid;
} sx1262_sample_t;

int sx1262_init(void);
int sx1262_probe(uint32_t frequency_hz, uint32_t dwell_ms, sx1262_sample_t *sample);
int sx1262_probe_gfsk(uint32_t frequency_hz, uint32_t dwell_ms, sx1262_sample_t *sample);
int sx1262_probe_gfsk_bw(uint32_t frequency_hz, uint32_t dwell_ms, uint32_t bandwidth_hz, sx1262_sample_t *sample);
int sx1262_send_test_packet(uint32_t frequency_hz, uint8_t *irq_status);
int sx1262_stop(void);
bool sx1262_frontend_power_enabled(void);
/* Packed little-endian records: completion timestamp u32, RSSI u8, DC-blocked PCM i16. */
int sx1262_capture(uint32_t frequency_hz, uint32_t bandwidth_hz, uint32_t rate_hz, bool force_lna, uint8_t *records,
                   uint32_t *count, sx1262_sample_t *sample, bool *stopped);
