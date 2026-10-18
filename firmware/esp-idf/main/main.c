#include "sx1262.h"

#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_err.h"
#include "esp_rom_crc.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define ARM_WINDOW_MS 30000u
static bool tx_armed;
static TickType_t arm_deadline;

static bool parse_u32(const char *s, uint32_t *value)
{
    char *end = NULL;
    unsigned long long v = strtoull(s, &end, 10);
    if (!s[0] || !end || *end || v > UINT32_MAX) return false;
    *value = (uint32_t)v;
    return true;
}

static void print_status(void)
{
    sx1262_sample_t s = {0};
    int rc = sx1262_probe(915000000u, 1, &s);
    printf("SXSTATUS1 ok=%u status=0x%02X errors=0x%04X rssi_dbm=%.1f code=%s\n",
           rc == ESP_OK, s.status, s.errors, s.rssi_dbm_x2 / 2.0, esp_err_to_name(rc));
}

static void command(char *line)
{
    char *save = NULL;
    char *op = strtok_r(line, " \t\r\n", &save);
    if (!op) return;
    if (!strcmp(op, "info")) {
        printf("SX1262-SDR fw=1.6 board=HTIT-WB32LAF-V4.3 fem=KCT8103L rx_min_hz=1000000 rx_modes=lora,gfsk,gfsk58,gfsk467 tx=one-shot-armed-test-packet\n");
    } else if (!strcmp(op, "status")) {
        print_status();
    } else if (!strcmp(op, "stop")) {
        tx_armed = false;
        int rc = sx1262_stop();
        printf("SXSTOP1 ok=%u code=%s\n", rc == ESP_OK, esp_err_to_name(rc));
    } else if (!strcmp(op, "probe")) {
        char *f = strtok_r(NULL, " \t\r\n", &save), *d = strtok_r(NULL, " \t\r\n", &save);
        char *mode = strtok_r(NULL, " \t\r\n", &save);
        uint32_t hz, dwell;
        char *extra = strtok_r(NULL, " \t\r\n", &save);
        if (!f || !d || extra || !parse_u32(f, &hz) || !parse_u32(d, &dwell) ||
            (mode && strcmp(mode, "lora") && strcmp(mode, "gfsk") && strcmp(mode, "gfsk58") && strcmp(mode, "gfsk467"))) {
            puts("SXERR usage=probe_hz_dwell_ms_lora_or_gfsk"); return;
        }
        sx1262_sample_t s = {0};
        const bool gfsk = mode && strncmp(mode, "gfsk", 4) == 0;
        const uint32_t bw = !gfsk ? 125000 : !strcmp(mode, "gfsk58") ? 58600 : !strcmp(mode, "gfsk467") ? 467000 : 4800;
        int rc = gfsk ? sx1262_probe_gfsk_bw(hz, dwell, bw, &s) : sx1262_probe(hz, dwell, &s);
        printf("SXPROBE1 f_hz=%" PRIu32 " dwell_ms=%" PRIu32 " ok=%u rssi_dbm=%.1f status=0x%02X errors=0x%04X code=%s mode=%s bw_hz=%" PRIu32 " reads=%u cal_errors=0x%04X\n",
               hz, dwell, rc == ESP_OK && s.valid, s.rssi_dbm_x2 / 2.0, s.status, s.errors,
               esp_err_to_name(rc), gfsk ? "gfsk" : "lora", bw, s.reads, s.cal_errors);
    } else if (!strcmp(op, "capture")) {
        tx_armed = false;
        char *f = strtok_r(NULL, " \t\r\n", &save);
        char *b = strtok_r(NULL, " \t\r\n", &save);
        char *r = strtok_r(NULL, " \t\r\n", &save);
        uint32_t hz, bw, rate;
        if (!f || !b || !r || strtok_r(NULL, " \t\r\n", &save) ||
            !parse_u32(f, &hz) || !parse_u32(b, &bw) || !parse_u32(r, &rate) ||
            ((hz < 88000000u || hz > 108000000u) && hz != 250001000u) ||
            (bw != 58600 && bw != 467000) ||
            (rate != 1000 && rate != 2000 && rate != 4000 && rate != 8000)) {
            puts("SXERR usage=capture_hz_bw_rate"); return;
        }
        uint8_t *data = malloc(rate * 7);
        if (!data) { puts("SXERR capture=no_memory"); return; }
        uint32_t n = 0;
        bool stopped = false;
        sx1262_sample_t s = {0};
        int rc = sx1262_capture(hz, bw, rate, data, &n, &s, &stopped);
        /* All serial output follows standby; serial bandwidth cannot pace sampling. */
        printf("SXCAP1 ok=%u f_hz=%" PRIu32 " bw_hz=%" PRIu32 " rate_hz=%" PRIu32
               " n=%" PRIu32 " status=0x%02X errors=0x%04X cal_errors=0x%04X code=%s\n",
               rc == ESP_OK && s.valid, hz, bw, rate, n, s.status, s.errors, s.cal_errors, esp_err_to_name(rc));
        for (uint32_t off = 0; off < n * 7; off += 56) {
            printf("SXDATA1 offset=%" PRIu32 " hex=", off);
            for (uint32_t j = off; j < n * 7 && j < off + 56; ++j) printf("%02X", data[j]);
            putchar('\n');
        }
        printf("SXCAPEND1 bytes=%" PRIu32 " crc32=%08" PRIX32 " stop=%u\n",
               n * 7, esp_rom_crc32_le(0, data, n * 7), stopped);
        free(data);
    } else if (!strcmp(op, "armtx")) {
        if (strtok_r(NULL, " \t\r\n", &save)) { puts("SXERR usage=armtx"); return; }
        tx_armed = true;
        arm_deadline = xTaskGetTickCount() + pdMS_TO_TICKS(ARM_WINDOW_MS);
        puts("SXTXARM1 packets=1 power_dbm=-9 expires_ms=30000");
    } else if (!strcmp(op, "tx")) {
        char *f = strtok_r(NULL, " \t\r\n", &save);
        char *extra = strtok_r(NULL, " \t\r\n", &save);
        uint32_t hz;
        if (!tx_armed || (int32_t)(arm_deadline - xTaskGetTickCount()) <= 0) {
            tx_armed = false; puts("SXTX1 ok=0 reason=not_armed"); return;
        }
        tx_armed = false; /* one shot, even on error */
        if (!f || extra || !parse_u32(f, &hz) || hz < 902000000u || hz > 928000000u) {
            puts("SXTX1 ok=0 reason=frequency_out_of_test_band"); return;
        }
        uint8_t irq = 0;
        int rc = sx1262_send_test_packet(hz, &irq);
        printf("SXTX1 f_hz=%" PRIu32 " ok=%u power_dbm=-9 packets=1 irq=0x%02X code=%s\n",
               hz, rc == ESP_OK, irq, esp_err_to_name(rc));
    } else {
        printf("SXERR command=unknown\n");
    }
}

void app_main(void)
{
    int rc = sx1262_init();
    if (rc != ESP_OK) {
        printf("SX1262-SDR fw=1.6 init=FAIL code=%s\n", esp_err_to_name(rc));
        return;
    }
    printf("SX1262-SDR fw=1.6 board=HTIT-WB32LAF-V4.3 fem=KCT8103L init=OK\n");
    puts("SXREADY1 commands=info,status,probe,capture,armtx,tx,stop");
    char line[128];
    for (;;) {
        /* USB console reads can fail while the host port is closed. Keep serving after reconnect. */
        if (!fgets(line, sizeof(line), stdin)) {
            clearerr(stdin);
            clearerr(stdout);
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        if (!strchr(line, '\n')) {
            int c;
            while ((c = getchar()) != '\n' && c != EOF) { }
            puts("SXERR command=too_long");
            continue;
        }
        command(line);
    }
}
