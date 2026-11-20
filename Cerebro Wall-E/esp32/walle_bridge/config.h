/*
 * WALL-E — configuracion del puente ESP32.
 *
 * Este es el UNICO archivo que hay que editar para poner el robot en tu red.
 */

#ifndef WALLE_CONFIG_H
#define WALLE_CONFIG_H

// --------------------------------------------------------------------------
// WiFi
// --------------------------------------------------------------------------
#define WIFI_SSID       "TU_SSID"
#define WIFI_PASSWORD   "TU_PASSWORD"

// Cuantas veces reintenta conectar antes de levantar un AP de emergencia.
#define WIFI_RETRIES    40
#define WIFI_RETRY_MS   500

// AP de emergencia: si no engancha la red, el robot queda accesible para
// corregir la configuracion sin desarmarlo.
#define FALLBACK_AP_SSID  "WALL-E-BRIDGE"
#define FALLBACK_AP_PASS  "walle1234"

// --------------------------------------------------------------------------
// Red
// --------------------------------------------------------------------------
#define UDP_PORT        4210

// --------------------------------------------------------------------------
// UART hacia el Arduino UNO (57600 8N1, ver README para el divisor)
// --------------------------------------------------------------------------
#define UNO_BAUD        57600
#define UNO_RX_PIN      16      // GPIO16 <- TX del UNO (D13), CON divisor 1k/2k
#define UNO_TX_PIN      17      // GPIO17 -> RX del UNO (D12), directo

// --------------------------------------------------------------------------
// Tiempos
// --------------------------------------------------------------------------
#define UNO_ACK_TIMEOUT_MS   120    // espera del ACK del UNO
#define UNO_RETRIES          1      // reenvios al UNO antes de dar ER
#define PC_LINK_TIMEOUT_MS   1000   // sin PC -> manda X al UNO
#define TELEMETRY_MS         100    // 10 Hz

// --------------------------------------------------------------------------
// Cola de ordenes pendientes
// --------------------------------------------------------------------------
#define PENDING_MAX      8

#endif  // WALLE_CONFIG_H
