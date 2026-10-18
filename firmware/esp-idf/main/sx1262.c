#include "sx1262.h"

#include <string.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_err.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

/* HTIT-WB32LAF V4.3 official board wiring. PA_CPS is driven by SX1262 DIO2. */
#define PIN_NSS GPIO_NUM_8
#define PIN_SCK GPIO_NUM_9
#define PIN_MOSI GPIO_NUM_10
#define PIN_MISO GPIO_NUM_11
#define PIN_RESET GPIO_NUM_12
#define PIN_BUSY GPIO_NUM_13
#define PIN_DIO1 GPIO_NUM_14
#define PIN_PA_CSD GPIO_NUM_2
#define PIN_PA_CTX GPIO_NUM_5
#define PIN_FEM_POWER GPIO_NUM_7

#define SPI_HOST SPI2_HOST
#define SPI_HZ 4000000
#define BUSY_TIMEOUT_MS 100
#define RX_MIN_HZ 1000000u
#define RX_MAX_HZ 3500000000u
#define TX_MIN_HZ 902000000u
#define TX_MAX_HZ 928000000u
#define TX_POWER_DBM (-9)
#define IRQ_TX_DONE 0x0001u

enum {
    CMD_SET_STANDBY = 0x80,
    CMD_SET_TX = 0x83,
    CMD_SET_RX = 0x82,
    CMD_SET_RF_FREQUENCY = 0x86,
    CMD_CALIBRATE = 0x89,
    CMD_SET_PACKET_TYPE = 0x8A,
    CMD_SET_MODULATION_PARAMS = 0x8B,
    CMD_SET_PACKET_PARAMS = 0x8C,
    CMD_SET_TX_PARAMS = 0x8E,
    CMD_SET_BUFFER_BASE = 0x8F,
    CMD_SET_PA_CONFIG = 0x95,
    CMD_SET_REGULATOR_MODE = 0x96,
    CMD_SET_TCXO = 0x97,
    CMD_CALIBRATE_IMAGE = 0x98,
    CMD_SET_DIO2_RF_SWITCH = 0x9D,
    CMD_GET_STATUS = 0xC0,
    CMD_GET_IRQ_STATUS = 0x12,
    CMD_CLEAR_IRQ_STATUS = 0x02,
    CMD_GET_RSSI_INST = 0x15,
    CMD_GET_DEVICE_ERRORS = 0x17,
    CMD_CLEAR_DEVICE_ERRORS = 0x07,
    CMD_WRITE_BUFFER = 0x0E,
    CMD_SET_DIO_IRQ_PARAMS = 0x08,
};

static spi_device_handle_t radio_spi;
static SemaphoreHandle_t radio_mutex;
static bool initialized;

static int wait_busy(uint32_t timeout_ms)
{
    const TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);
    while (gpio_get_level(PIN_BUSY) != 0) {
        if ((int32_t)(deadline - xTaskGetTickCount()) <= 0) return ESP_ERR_TIMEOUT;
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    return ESP_OK;
}

static int transfer(const uint8_t *tx, uint8_t *rx, size_t len)
{
    spi_transaction_t t = {0};
    t.length = len * 8;
    t.tx_buffer = tx;
    t.rx_buffer = rx;
    return spi_device_transmit(radio_spi, &t);
}

static int write_command(uint8_t opcode, const uint8_t *args, size_t len)
{
    if (len > 32) return ESP_ERR_INVALID_SIZE;
    uint8_t tx[33] = {0};
    tx[0] = opcode;
    if (len) memcpy(&tx[1], args, len);
    int rc = wait_busy(BUSY_TIMEOUT_MS);
    if (rc != ESP_OK) return rc;
    rc = transfer(tx, NULL, len + 1);
    if (rc != ESP_OK) return rc;
    return wait_busy(BUSY_TIMEOUT_MS);
}

static int read_command(uint8_t opcode, uint8_t *out, size_t len)
{
    if (len > 32) return ESP_ERR_INVALID_SIZE;
    uint8_t tx[34] = {0}, rx[34] = {0};
    tx[0] = opcode;
    int rc = wait_busy(BUSY_TIMEOUT_MS);
    if (rc != ESP_OK) return rc;
    rc = transfer(tx, rx, len + 2);
    if (rc != ESP_OK) return rc;
    rc = wait_busy(BUSY_TIMEOUT_MS);
    if (rc == ESP_OK && len) memcpy(out, &rx[2], len);
    return rc;
}

static int set_frequency(uint32_t hz, uint8_t standby)
{
    /* SX126x frequency word uses a 32 MHz reference and 25 fractional bits. */
    const uint32_t word = (uint32_t)(((uint64_t)hz << 25) / 32000000ull);
    uint8_t a[] = {(uint8_t)(word >> 24), (uint8_t)(word >> 16),
                   (uint8_t)(word >> 8), (uint8_t)word};
    int rc = write_command(CMD_SET_STANDBY, &standby, 1);
    if (rc == ESP_OK) rc = write_command(CMD_SET_RF_FREQUENCY, a, sizeof(a));
    return rc;
}

static int calibrate_915(void)
{
    /* Datasheet image-calibration range covering 902-928 MHz. */
    const uint8_t range[] = {0xE1, 0xE9};
    return write_command(CMD_CALIBRATE_IMAGE, range, sizeof(range));
}

static int configure_lora(void)
{
    const uint8_t packet_type[] = {0x01};       /* LoRa */
    const uint8_t modulation[] = {0x07, 0x04, 0x01, 0x00}; /* SF7, 125 kHz, CR 4/5 */
    const uint8_t packet[] = {0x00, 0x08, 0x00, 0x12, 0x01, 0x00};
    const uint8_t buffer_base[] = {0x00, 0x00};
    const uint8_t irq[] = {0x00, 0x03, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00};
    int rc = write_command(CMD_SET_PACKET_TYPE, packet_type, sizeof(packet_type));
    if (rc == ESP_OK) rc = write_command(CMD_SET_MODULATION_PARAMS, modulation, sizeof(modulation));
    if (rc == ESP_OK) rc = write_command(CMD_SET_PACKET_PARAMS, packet, sizeof(packet));
    if (rc == ESP_OK) rc = write_command(CMD_SET_BUFFER_BASE, buffer_base, sizeof(buffer_base));
    if (rc == ESP_OK) rc = write_command(CMD_SET_DIO_IRQ_PARAMS, irq, sizeof(irq));
    return rc;
}

static int configure_gfsk(uint32_t bandwidth_hz)
{
    uint8_t bw;
    switch (bandwidth_hz) {
        case 4800: bw = 0x1F; break;
        case 58600: bw = 0x0C; break;
        case 467000: bw = 0x09; break;
        default: return ESP_ERR_INVALID_ARG;
    }
    /* Documented GFSK fields: 1200 bps, no shaping, 4.8 kHz RX BW, 600 Hz deviation.
       Research comparison: LakeShark sxprobe at 8586c6d, GPL-3.0; see docs/RESEARCH_EVIDENCE.md. */
    const uint32_t bitrate = (1024000000u + 600u) / 1200u;
    const uint32_t deviation = (uint32_t)(((uint64_t)600u << 25) / 32000000ull);
    const uint8_t type[] = {0x00};
    const uint8_t modulation[] = {(uint8_t)(bitrate >> 16), (uint8_t)(bitrate >> 8),
                                  (uint8_t)bitrate, 0x00, bw,
                                  (uint8_t)(deviation >> 16), (uint8_t)(deviation >> 8),
                                  (uint8_t)deviation};
    const uint8_t packet[] = {0x00, 0x20, 0x04, 0x20, 0x00, 0x00, 0x10, 0x01, 0x00};
    int rc = write_command(CMD_SET_PACKET_TYPE, type, sizeof(type));
    if (rc == ESP_OK) rc = write_command(CMD_SET_MODULATION_PARAMS, modulation, sizeof(modulation));
    if (rc == ESP_OK) rc = write_command(CMD_SET_PACKET_PARAMS, packet, sizeof(packet));
    return rc;
}

static int read_status(uint8_t *status)
{
    uint8_t tx[] = {CMD_GET_STATUS, 0x00};
    uint8_t rx[sizeof(tx)] = {0};
    int rc = wait_busy(BUSY_TIMEOUT_MS);
    if (rc == ESP_OK) rc = transfer(tx, rx, sizeof(tx));
    if (rc == ESP_OK) rc = wait_busy(BUSY_TIMEOUT_MS);
    if (rc == ESP_OK) *status = rx[1];
    return rc;
}

static int read_errors(uint16_t *errors)
{
    uint8_t b[2];
    int rc = read_command(CMD_GET_DEVICE_ERRORS, b, sizeof(b));
    if (rc == ESP_OK) *errors = (uint16_t)((b[0] << 8) | b[1]);
    return rc;
}

static int set_frontend_rx(uint32_t frequency_hz)
{
    int rc = gpio_set_level(PIN_PA_CSD, 1);
    /* KCT8103L is specified for 860-930 MHz; use its documented bypass state elsewhere. */
    const int bypass = frequency_hz < 860000000u || frequency_hz > 930000000u;
    if (rc == ESP_OK) rc = gpio_set_level(PIN_PA_CTX, bypass ? 1 : 0);
    return rc;
}

static int set_frontend_tx(void)
{
    int rc = gpio_set_level(PIN_PA_CSD, 1);
    if (rc == ESP_OK) rc = gpio_set_level(PIN_PA_CTX, 1);
    return rc;
}

int sx1262_init(void)
{
    esp_err_t rc;
    const gpio_config_t out = {.pin_bit_mask = (1ull << PIN_NSS) | (1ull << PIN_RESET) |
                                                (1ull << PIN_PA_CSD) | (1ull << PIN_PA_CTX),
                               .mode = GPIO_MODE_OUTPUT, .pull_up_en = GPIO_PULLUP_DISABLE,
                               .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_DISABLE};
    const gpio_config_t in = {.pin_bit_mask = (1ull << PIN_BUSY) | (1ull << PIN_DIO1),
                              .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_DISABLE,
                              .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_DISABLE};
    if ((rc = gpio_config(&out)) != ESP_OK || (rc = gpio_config(&in)) != ESP_OK) return rc;
    gpio_set_level(PIN_NSS, 1);
    gpio_set_level(PIN_RESET, 1);
    gpio_set_level(PIN_PA_CSD, 1);
    gpio_set_level(PIN_PA_CTX, 0);
    /* V4.3 VFEM regulator enable: official LORA_PA_POWER GPIO7. */
    const gpio_config_t power = {.pin_bit_mask = 1ull << PIN_FEM_POWER,
                                 .mode = GPIO_MODE_INPUT_OUTPUT,
                                 .pull_up_en = GPIO_PULLUP_DISABLE,
                                 .pull_down_en = GPIO_PULLDOWN_DISABLE,
                                 .intr_type = GPIO_INTR_DISABLE};
    if ((rc = gpio_config(&power)) != ESP_OK) return rc;
    if ((rc = gpio_set_level(PIN_FEM_POWER, 1)) != ESP_OK) return rc;
    vTaskDelay(pdMS_TO_TICKS(2));

    spi_bus_config_t bus = {.mosi_io_num = PIN_MOSI, .miso_io_num = PIN_MISO, .sclk_io_num = PIN_SCK,
                            .quadwp_io_num = -1, .quadhd_io_num = -1, .max_transfer_sz = 64};
    rc = spi_bus_initialize(SPI_HOST, &bus, SPI_DMA_DISABLED);
    if (rc != ESP_OK && rc != ESP_ERR_INVALID_STATE) return rc;
    spi_device_interface_config_t dev = {.clock_speed_hz = SPI_HZ, .mode = 0,
                                         .spics_io_num = PIN_NSS, .queue_size = 1,
                                         .cs_ena_pretrans = 2, .cs_ena_posttrans = 2};
    if ((rc = spi_bus_add_device(SPI_HOST, &dev, &radio_spi)) != ESP_OK) return rc;
    radio_mutex = xSemaphoreCreateMutex();
    if (!radio_mutex) return ESP_ERR_NO_MEM;

    gpio_set_level(PIN_RESET, 0);
    vTaskDelay(pdMS_TO_TICKS(2));
    gpio_set_level(PIN_RESET, 1);
    vTaskDelay(pdMS_TO_TICKS(10));

    const uint8_t standby[] = {0x00};
    const uint8_t tcxo[] = {0x02, 0x00, 0x01, 0x40}; /* DIO3 1.8 V, 5 ms */
    const uint8_t calibrate[] = {0x7F};
    const uint8_t dio2[] = {0x01};
    const uint8_t regulator[] = {0x01}; /* DC-DC */
    if ((rc = write_command(CMD_SET_STANDBY, standby, sizeof(standby))) != ESP_OK ||
        (rc = write_command(CMD_SET_REGULATOR_MODE, regulator, sizeof(regulator))) != ESP_OK ||
        (rc = write_command(CMD_SET_TCXO, tcxo, sizeof(tcxo))) != ESP_OK ||
        (rc = write_command(CMD_CALIBRATE, calibrate, sizeof(calibrate))) != ESP_OK ||
        (rc = write_command(CMD_SET_DIO2_RF_SWITCH, dio2, sizeof(dio2))) != ESP_OK) return rc;
    initialized = true;
    return ESP_OK;
}

static int probe(uint32_t frequency_hz, uint32_t dwell_ms, sx1262_sample_t *sample, uint32_t gfsk_bw)
{
    const bool gfsk = gfsk_bw != 0;
    if (!initialized || !sample || frequency_hz < RX_MIN_HZ || frequency_hz > RX_MAX_HZ ||
        dwell_ms < 1 || dwell_ms > 5000) return ESP_ERR_INVALID_ARG;
    if (xSemaphoreTake(radio_mutex, pdMS_TO_TICKS(100)) != pdTRUE) return ESP_ERR_TIMEOUT;
    memset(sample, 0, sizeof(*sample));
    int rc = set_frontend_rx(frequency_hz);
    const uint8_t clear_errors[] = {0x00, 0x00};
    if (rc == ESP_OK) rc = write_command(CMD_CLEAR_DEVICE_ERRORS, clear_errors, sizeof(clear_errors));
    if (rc == ESP_OK) rc = set_frequency(frequency_hz, gfsk ? 0x01 : 0x00);
    if (rc == ESP_OK && frequency_hz >= 902000000u && frequency_hz <= 928000000u) rc = calibrate_915();
    if (rc == ESP_OK) rc = read_errors(&sample->cal_errors);
    if (rc == ESP_OK) rc = gfsk ? configure_gfsk(gfsk_bw) : configure_lora();
    const uint8_t rx_timeout[] = {0xFF, 0xFF, 0xFF};
    if (rc == ESP_OK) rc = write_command(CMD_SET_RX, rx_timeout, sizeof(rx_timeout));
    if (rc == ESP_OK) vTaskDelay(pdMS_TO_TICKS(dwell_ms));
    if (rc == ESP_OK) rc = read_status(&sample->status);
    if (rc == ESP_OK) rc = read_errors(&sample->errors);
    const unsigned command_status = (sample->status >> 1) & 7;
    const bool rx_valid = ((sample->status >> 4) & 7) == 5 && command_status != 7 &&
                          !(command_status >= 3 && command_status <= 5) && sample->errors == 0;
    unsigned sum = 0;
    for (unsigned i = 0; rc == ESP_OK && rx_valid && i < (gfsk ? 8u : 1u); ++i) {
        uint8_t rssi = 0;
        rc = read_command(CMD_GET_RSSI_INST, &rssi, 1);
        if (rc == ESP_OK) { sum += rssi; sample->reads++; }
        esp_rom_delay_us(200);
    }
    const int stop_rc = write_command(CMD_SET_STANDBY, (uint8_t[]){0x00}, 1);
    sample->rssi_dbm_x2 = sample->reads ? -(int16_t)((sum + sample->reads / 2u) / sample->reads) : 0;
    sample->valid = rc == ESP_OK && stop_rc == ESP_OK && rx_valid && sample->reads > 0;
    if (rc == ESP_OK) rc = stop_rc;
    xSemaphoreGive(radio_mutex);
    return rc;
}

int sx1262_probe(uint32_t frequency_hz, uint32_t dwell_ms, sx1262_sample_t *sample)
{
    return probe(frequency_hz, dwell_ms, sample, false);
}

int sx1262_probe_gfsk(uint32_t frequency_hz, uint32_t dwell_ms, sx1262_sample_t *sample)
{
    return probe(frequency_hz, dwell_ms, sample, 4800);
}

int sx1262_probe_gfsk_bw(uint32_t frequency_hz, uint32_t dwell_ms, uint32_t bandwidth_hz, sx1262_sample_t *sample)
{
    if (bandwidth_hz != 4800 && bandwidth_hz != 58600 && bandwidth_hz != 467000)
        return ESP_ERR_INVALID_ARG;
    return probe(frequency_hz, dwell_ms, sample, bandwidth_hz);
}

int sx1262_capture(uint32_t frequency_hz, uint32_t bandwidth_hz, uint32_t rate_hz, bool force_lna, uint8_t *records,
                   uint32_t *count, sx1262_sample_t *sample, bool *stopped)
{
    if (!initialized || !records || !count || !sample || !stopped ||
        (force_lna && (frequency_hz < 88000000u || frequency_hz > 108000000u)) ||
        ((frequency_hz < 88000000u || frequency_hz > 108000000u) && frequency_hz != 250001000u) ||
        (rate_hz != 1000 && rate_hz != 2000 && rate_hz != 4000 && rate_hz != 8000) ||
        (bandwidth_hz != 58600 && bandwidth_hz != 467000)) return ESP_ERR_INVALID_ARG;
    *count = 0;
    *stopped = false;
    memset(sample, 0, sizeof(*sample));
    if (xSemaphoreTake(radio_mutex, pdMS_TO_TICKS(100)) != pdTRUE) return ESP_ERR_TIMEOUT;
    int rc = set_frontend_rx(frequency_hz);
    /* Documented RX LNA state; gain at FM frequencies is unverified. */
    if (rc == ESP_OK && force_lna) rc = gpio_set_level(PIN_PA_CTX, 0);
    const uint8_t clear[] = {0, 0};
    if (rc == ESP_OK) rc = write_command(CMD_CLEAR_DEVICE_ERRORS, clear, sizeof(clear));
    if (rc == ESP_OK) rc = set_frequency(frequency_hz, 1);
    if (rc == ESP_OK) rc = read_errors(&sample->cal_errors);
    if (rc == ESP_OK) rc = configure_gfsk(bandwidth_hz);
    const uint8_t timeout[] = {0xFF, 0xFF, 0xFF};
    if (rc == ESP_OK) rc = write_command(CMD_SET_RX, timeout, sizeof(timeout));
    if (rc == ESP_OK) vTaskDelay(pdMS_TO_TICKS(20));
    if (rc == ESP_OK) rc = read_status(&sample->status);
    if (rc == ESP_OK) rc = read_errors(&sample->errors);
    unsigned cs = (sample->status >> 1) & 7;
    if (rc == ESP_OK && (((sample->status >> 4) & 7) != 5 || cs == 7 ||
        (cs >= 3 && cs <= 5) || sample->errors || sample->cal_errors)) rc = ESP_ERR_INVALID_STATE;
    const int64_t start = esp_timer_get_time();
    const uint32_t period = 1000000u / rate_hz;
    int32_t dc = 0;
    for (uint32_t i = 0; rc == ESP_OK && i < rate_hz; ++i) {
        int64_t now = esp_timer_get_time(), due = start + (int64_t)i * period;
        if (due > now) esp_rom_delay_us((uint32_t)(due - now));
        if (esp_timer_get_time() - start >= 1000000) break;
        uint8_t rssi;
        rc = read_command(CMD_GET_RSSI_INST, &rssi, 1);
        uint32_t stamp = (uint32_t)(esp_timer_get_time() - start);
        if (rc != ESP_OK) break;
        /* Experimental RSSI envelope only: fixed gain, no FM discriminator or I/Q. */
        int32_t x = -(int32_t)rssi * 128;
        if (i == 0) dc = x;
        dc += (x - dc) / 64;
        int16_t pcm = (int16_t)(x - dc);
        uint8_t *p = records + i * 7;
        memcpy(p, &stamp, 4);
        p[4] = rssi;
        memcpy(p + 5, &pcm, 2);
        ++*count;
    }
    if (rc == ESP_OK) rc = read_status(&sample->status);
    if (rc == ESP_OK) rc = read_errors(&sample->errors);
    int stop_rc = write_command(CMD_SET_STANDBY, (uint8_t[]){0}, 1);
    *stopped = stop_rc == ESP_OK;
    if (rc == ESP_OK) rc = stop_rc;
    cs = (sample->status >> 1) & 7;
    sample->valid = rc == ESP_OK && *count > 1 && !sample->errors && !sample->cal_errors &&
        ((sample->status >> 4) & 7) == 5 && cs != 7 && !(cs >= 3 && cs <= 5);
    xSemaphoreGive(radio_mutex);
    return rc;
}

int sx1262_send_test_packet(uint32_t frequency_hz, uint8_t *irq_status)
{
    if (!initialized || !irq_status || frequency_hz < TX_MIN_HZ || frequency_hz > TX_MAX_HZ)
        return ESP_ERR_INVALID_ARG;
    if (xSemaphoreTake(radio_mutex, pdMS_TO_TICKS(100)) != pdTRUE) return ESP_ERR_TIMEOUT;
    int rc = set_frontend_tx();
    const uint8_t clear_errors[] = {0x00, 0x00};
    if (rc == ESP_OK) rc = write_command(CMD_CLEAR_DEVICE_ERRORS, clear_errors, sizeof(clear_errors));
    if (rc == ESP_OK) rc = set_frequency(frequency_hz, 0x00);
    if (rc == ESP_OK) rc = calibrate_915();
    if (rc == ESP_OK) rc = configure_lora();
    const uint8_t pa[] = {0x04, 0x07, 0x00, 0x01}; /* SX1262 high-power path; output capped below */
    const uint8_t tx_params[] = {(uint8_t)TX_POWER_DBM, 0x04}; /* -9 dBm, 200 us ramp */
    const uint8_t payload[] = {'S','X','1','2','6','2','-','S','D','R','-','T','E','S','T','-','V','1'};
    if (rc == ESP_OK) rc = write_command(CMD_SET_PA_CONFIG, pa, sizeof(pa));
    if (rc == ESP_OK) rc = write_command(CMD_SET_TX_PARAMS, tx_params, sizeof(tx_params));
    if (rc == ESP_OK) {
        uint8_t b[sizeof(payload) + 2] = {CMD_WRITE_BUFFER, 0x00};
        memcpy(&b[2], payload, sizeof(payload));
        rc = wait_busy(BUSY_TIMEOUT_MS);
        if (rc == ESP_OK) rc = transfer(b, NULL, sizeof(b));
        if (rc == ESP_OK) rc = wait_busy(BUSY_TIMEOUT_MS);
    }
    const uint8_t tx_timeout[] = {0x02, 0x00, 0x00}; /* 2 seconds at 64 kHz */
    if (rc == ESP_OK) rc = write_command(CMD_SET_TX, tx_timeout, sizeof(tx_timeout));
    uint16_t irq = 0;
    for (unsigned i = 0; rc == ESP_OK && i < 200; ++i) {
        uint8_t b[2] = {0};
        rc = read_command(CMD_GET_IRQ_STATUS, b, sizeof(b));
        irq = (uint16_t)((b[0] << 8) | b[1]);
        if (irq & IRQ_TX_DONE) break;
        vTaskDelay(pdMS_TO_TICKS(10));
        if (i == 199) rc = ESP_ERR_TIMEOUT;
    }
    *irq_status = (uint8_t)(irq & 0xFF);
    const uint8_t clear_irq[] = {(uint8_t)(irq >> 8), (uint8_t)irq};
    const int clear_rc = write_command(CMD_CLEAR_IRQ_STATUS, clear_irq, sizeof(clear_irq));
    const int standby_rc = write_command(CMD_SET_STANDBY, (uint8_t[]){0x00}, 1);
    set_frontend_rx(frequency_hz);
    if (rc == ESP_OK) rc = clear_rc;
    if (rc == ESP_OK) rc = standby_rc;
    xSemaphoreGive(radio_mutex);
    return rc;
}

int sx1262_stop(void)
{
    if (!initialized) return ESP_OK;
    int rc = write_command(CMD_SET_STANDBY, (uint8_t[]){0x00}, 1);
    set_frontend_rx(915000000u);
    return rc;
}

bool sx1262_frontend_power_enabled(void)
{
    return initialized && gpio_get_level(PIN_FEM_POWER) == 1;
}
