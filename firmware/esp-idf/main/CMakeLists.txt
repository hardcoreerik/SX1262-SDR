idf_component_register(SRCS "main.c" "sx1262.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_driver_gpio esp_driver_spi esp_timer)
