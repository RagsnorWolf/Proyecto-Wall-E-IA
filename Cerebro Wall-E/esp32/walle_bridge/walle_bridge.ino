/*
 * WALL-E — ESP32: puente inalambrico PC <-> Arduino UNO.
 *
 * No piensa. Recibe ordenes por UDP, las reenvia por Serial2 al UNO y espera
 * el ACK del UNO antes de contestarle a la PC. Ese ida y vuelta es lo que
 * confirma que el ESP32 esta realmente funcionando y no solo encendido.
 *
 *   PC --UDP--> ESP32 --UART--> UNO
 *   PC <--UDP-- ESP32 <--UART-- UNO
 *
 * Si la PC deja de hablar 1 s, manda X al UNO. El UNO ademas se frena solo a
 * los 500 ms sin lineas del ESP32.
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include "config.h"

// --------------------------------------------------------------------------
// Estado
// --------------------------------------------------------------------------
WiFiUDP udp;

static IPAddress pcAddr;
static uint16_t pcPort = 0;
static bool pcKnown = false;
static uint32_t lastPcMs = 0;

struct Pending {
  bool used;
  int32_t id;
  char op;
  int32_t a;
  int32_t b;
  uint32_t sentMs;
  uint8_t retries;
  IPAddress addr;
  uint16_t port;
};

static Pending pending[PENDING_MAX];
static int32_t lastAnsweredId = 0;
static bool unoOk = false;
static uint8_t queueLen = 0;

static char unoBuf[64];
static uint8_t unoLen = 0;
static bool unoOverflow = false;

static char udpBuf[96];

// --------------------------------------------------------------------------
// Utilidades
// --------------------------------------------------------------------------
static void sendToUno(int32_t id, char op, int32_t a, int32_t b) {
  Serial2.print(id);
  Serial2.print(',');
  Serial2.print(op);
  Serial2.print(',');
  Serial2.print(a);
  Serial2.print(',');
  Serial2.print(b);
  Serial2.print('\n');
}

static void sendRawToUno(const char *line) {
  Serial2.print(line);
  Serial2.print('\n');
}

static Pending *findPending(int32_t id) {
  for (int i = 0; i < PENDING_MAX; ++i) {
    if (pending[i].used && pending[i].id == id) return &pending[i];
  }
  return NULL;
}

static Pending *freeSlot() {
  for (int i = 0; i < PENDING_MAX; ++i) {
    if (!pending[i].used) return &pending[i];
  }
  return NULL;
}

static void countQueue() {
  uint8_t n = 0;
  for (int i = 0; i < PENDING_MAX; ++i) {
    if (pending[i].used) ++n;
  }
  queueLen = n;
}

static void replyTo(const IPAddress &addr, uint16_t port, int32_t id,
                    bool ok, int32_t v1, int32_t v2, uint32_t rtt) {
  char out[80];
  if (ok) {
    snprintf(out, sizeof(out), "WALLE/1 %ld OK %ld %ld %lu",
             (long)id, (long)v1, (long)v2, (unsigned long)rtt);
  } else {
    snprintf(out, sizeof(out), "WALLE/1 %ld ER %ld %lu",
             (long)id, (long)v1, (unsigned long)rtt);
  }
  udp.beginPacket(addr, port);
  udp.write((const uint8_t *)out, strlen(out));
  udp.endPacket();
}

// --------------------------------------------------------------------------
// WiFi
// --------------------------------------------------------------------------
static void startFallbackAp() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP(FALLBACK_AP_SSID, FALLBACK_AP_PASS);
  Serial.print(F("[WiFi] Sin red. AP de emergencia: "));
  Serial.print(FALLBACK_AP_SSID);
  Serial.print(F("  IP: "));
  Serial.println(WiFi.softAPIP());
}

static void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);              // el ahorro de energia mete 100 ms de lag
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print(F("[WiFi] Conectando"));
  for (int i = 0; i < WIFI_RETRIES; ++i) {
    if (WiFi.status() == WL_CONNECTED) break;
    delay(WIFI_RETRY_MS);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(F("[WiFi] IP del ESP32: "));
    Serial.println(WiFi.localIP());
    Serial.print(F("[WiFi] RSSI: "));
    Serial.print(WiFi.RSSI());
    Serial.println(F(" dBm"));
  } else {
    startFallbackAp();
  }
}

// --------------------------------------------------------------------------
// Recepcion del UNO
// --------------------------------------------------------------------------
static void handleUnoLine(char *line) {
  // <id>,OK,<v1>,<v2>   |   <id>,ER,<codigo>,<detalle>   |   <id>,D,<cm>,<0>
  char *comma1 = strchr(line, ',');
  if (comma1 == NULL) return;
  *comma1 = '\0';

  int32_t id = atol(line);
  if (id <= 0) return;

  char *status = comma1 + 1;
  char *comma2 = strchr(status, ',');
  if (comma2 == NULL) return;
  *comma2 = '\0';

  char *v1s = comma2 + 1;
  char *comma3 = strchr(v1s, ',');
  int32_t v1 = 0;
  int32_t v2 = 0;
  if (comma3 != NULL) {
    *comma3 = '\0';
    v2 = atol(comma3 + 1);
  }
  v1 = atol(v1s);

  // Telemetria del sensor: no es la respuesta de una orden, no tiene ranura.
  // Se reenvia al PC tal cual y se sigue.
  if (status[0] == 'D' && status[1] == '\0') {
    if (!pcKnown) return;
    char out[40];
    snprintf(out, sizeof(out), "WALLE/1 D %ld", (long)v1);
    udp.beginPacket(pcAddr, pcPort);
    udp.write((const uint8_t *)out, strlen(out));
    udp.endPacket();
    return;
  }

  Pending *slot = findPending(id);
  if (slot == NULL) return;   // ACK de algo que ya se contesto: se ignora

  uint32_t rtt = (uint32_t)(millis() - slot->sentMs);
  bool ok = (status[0] == 'O' && status[1] == 'K');

  unoOk = ok;
  lastAnsweredId = id;
  replyTo(slot->addr, slot->port, id, ok, v1, v2, rtt);
  slot->used = false;
  countQueue();
}

static void pollUno() {
  while (Serial2.available() > 0) {
    char c = (char)Serial2.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!unoOverflow && unoLen > 0) {
        unoBuf[unoLen] = '\0';
        handleUnoLine(unoBuf);
      }
      unoLen = 0;
      unoOverflow = false;
      continue;
    }
    if (unoLen < sizeof(unoBuf) - 1) {
      unoBuf[unoLen++] = c;
    } else {
      unoOverflow = true;
    }
  }
}

// --------------------------------------------------------------------------
// Recepcion de la PC
// --------------------------------------------------------------------------
static void handlePcPacket(char *line, const IPAddress &addr, uint16_t port) {
  // WALLE/1 <id> <op> <a> <b>
  int32_t id = 0;
  int32_t a = 0;
  int32_t b = 0;
  char op = 0;

  if (strncmp(line, "WALLE/1 ", 8) != 0) return;   // basura: no se contesta

  int parsed = sscanf(line + 8, "%ld %c %ld %ld", (long *)&id, &op,
                      (long *)&a, (long *)&b);
  if (parsed < 2 || id <= 0) return;

  pcAddr = addr;
  pcPort = port;
  pcKnown = true;
  lastPcMs = millis();

  if (parsed < 4) {
    // P y X pueden venir sin argumentos: se normalizan a 0.
    if (op == 'P' || op == 'X') {
      a = 0;
      b = 0;
    } else {
      replyTo(addr, port, id, false, 1, 0, 0);   // linea invalida
      return;
    }
  }

  // Reintento del PC con el mismo id: se reenvia al UNO sobre la ranura que ya
  // existe. Abrir otra dejaria dos ACK para el mismo id y una de las dos
  // ranuras terminaria en ER por timeout, ensuciando la telemetria.
  Pending *dup = findPending(id);
  if (dup != NULL) {
    dup->sentMs = millis();
    dup->retries = 0;
    dup->addr = addr;
    dup->port = port;
    sendToUno(id, op, a, b);
    return;
  }

  Pending *slot = freeSlot();
  if (slot == NULL) {
    replyTo(addr, port, id, false, 3, 0, 0);     // cola llena
    return;
  }

  slot->used = true;
  slot->id = id;
  slot->op = op;
  slot->a = a;
  slot->b = b;
  slot->sentMs = millis();
  slot->retries = 0;
  slot->addr = addr;
  slot->port = port;
  countQueue();

  sendToUno(id, op, a, b);
}

static void pollPc() {
  int size = udp.parsePacket();
  if (size <= 0) return;
  if (size >= (int)sizeof(udpBuf)) {
    while (udp.available()) udp.read();
    return;
  }
  int len = udp.read(udpBuf, sizeof(udpBuf) - 1);
  if (len <= 0) return;
  udpBuf[len] = '\0';

  char *nl = strpbrk(udpBuf, "\r\n");
  if (nl != NULL) *nl = '\0';

  handlePcPacket(udpBuf, udp.remoteIP(), udp.remotePort());
}

// --------------------------------------------------------------------------
// Mantenimiento
// --------------------------------------------------------------------------
static void expirePending() {
  uint32_t now = millis();
  for (int i = 0; i < PENDING_MAX; ++i) {
    Pending &p = pending[i];
    if (!p.used) continue;
    if ((uint32_t)(now - p.sentMs) < UNO_ACK_TIMEOUT_MS) continue;

    if (p.retries < UNO_RETRIES) {
      p.retries++;
      p.sentMs = now;
      sendToUno(p.id, p.op, p.a, p.b);
      continue;
    }
    unoOk = false;
    replyTo(p.addr, p.port, p.id, false, 1, 0,
            (uint32_t)(now - p.sentMs));
    p.used = false;
  }
  countQueue();
}

static void deadMan() {
  static bool latched = false;
  // El UNO descarta cualquier linea con id <= 0. Una parada de emergencia
  // necesita id valido o no se ejecuta: se usa un contador fuera del rango
  // que reparte el PC.
  static int32_t stopId = 2000000000;
  if (!pcKnown) return;
  bool stale = (uint32_t)(millis() - lastPcMs) > PC_LINK_TIMEOUT_MS;
  if (stale && !latched) {
    for (int i = 0; i < 2; ++i) {          // dos lineas: una se puede perder
      char line[24];
      snprintf(line, sizeof(line), "%ld,X,0,0", (long)stopId++);
      sendRawToUno(line);
    }
    latched = true;
    Serial.println(F("[dead-man] PC en silencio: motores frenados."));
  } else if (!stale) {
    latched = false;
  }
}

static void telemetry() {
  static uint32_t lastMs = 0;
  uint32_t now = millis();
  if ((uint32_t)(now - lastMs) < TELEMETRY_MS) return;
  lastMs = now;
  if (!pcKnown) return;

  char out[80];
  snprintf(out, sizeof(out), "WALLE/1 T %lu %d %d %ld %u",
           (unsigned long)now, (int)WiFi.RSSI(), unoOk ? 1 : 0,
           (long)lastAnsweredId, (unsigned)queueLen);
  udp.beginPacket(pcAddr, pcPort);
  udp.write((const uint8_t *)out, strlen(out));
  udp.endPacket();
}

// --------------------------------------------------------------------------
// Setup / loop
// --------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println(F("=== WALL-E bridge ESP32 ==="));

  Serial2.begin(UNO_BAUD, SERIAL_8N1, UNO_RX_PIN, UNO_TX_PIN);

  connectWifi();

  udp.begin(UDP_PORT);
  Serial.print(F("[UDP] escuchando en el puerto "));
  Serial.println(UDP_PORT);

  for (int i = 0; i < PENDING_MAX; ++i) pending[i].used = false;
  lastPcMs = millis();
}

void loop() {
  pollPc();
  pollUno();
  expirePending();
  deadMan();
  telemetry();
}
