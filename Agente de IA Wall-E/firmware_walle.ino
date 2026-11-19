/*
 * firmware_walle.ino — placa del cuerpo de WALL-E.
 *
 * Habla el protocolo de linea que espera `agente/actuadores.py`:
 *
 *   PC   -> placa : AVANZAR 3\n   GIRAR IZQ 2\n   RECOGER\n   ESPERAR 1\n   ESTADO\n
 *   placa -> PC   : OK {"bateria": 88.2, "basura": 3}\n
 *                   ERR bateria baja\n
 *
 * Placa: Arduino UNO/Nano o ESP32. Puente H L298N en los pines de motor,
 * servo de brazo en SERVO_PIN, divisor resistivo en PIN_BATERIA.
 *
 * Ajustar los cuatro numeros de calibracion antes de mover: sin ellos el
 * robot gira distinto a cada lado y el agente nunca llega al objetivo.
 */

#include <Servo.h>

// --- pines ---------------------------------------------------------------
const uint8_t PIN_IZQ_ADELANTE = 5;
const uint8_t PIN_IZQ_ATRAS     = 6;
const uint8_t PIN_DER_ADELANTE  = 9;
const uint8_t PIN_DER_ATRAS     = 10;
const uint8_t SERVO_PIN         = 3;
const uint8_t PIN_BATERIA       = A0;
const uint8_t PIN_IR_CUBO       = 7;   // sensor de presencia del cubo

// --- calibracion ---------------------------------------------------------
const uint16_t MS_POR_PASO       = 100;  // igual que DT del simulador
const uint8_t  VELOCIDAD_AVANCE  = 150;  // 0-255
const uint8_t  VELOCIDAD_GIRO    = 130;
const uint8_t  ANGULO_RECOGER    = 20;   // brazo abajo
const uint8_t  ANGULO_REPOSO     = 110;  // brazo arriba
const float    VOLTIOS_REFERENCIA = 5.0;
const float    DIVISOR            = 3.0; // R1=10k, R2=5k -> factor 3
const float    BATERIA_MINIMA     = 11.0; // por debajo, se rechaza avanzar

Servo brazo;
char buffer[64];
uint8_t usados = 0;
unsigned long cubos_recogidos = 0;

void setup() {
  pinMode(PIN_IZQ_ADELANTE, OUTPUT);
  pinMode(PIN_IZQ_ATRAS, OUTPUT);
  pinMode(PIN_DER_ADELANTE, OUTPUT);
  pinMode(PIN_DER_ATRAS, OUTPUT);
  pinMode(PIN_IR_CUBO, INPUT_PULLUP);
  brazo.attach(SERVO_PIN);
  brazo.write(ANGULO_REPOSO);
  Serial.begin(115200);
  parar();
}

void parar() {
  digitalWrite(PIN_IZQ_ADELANTE, LOW);
  digitalWrite(PIN_IZQ_ATRAS, LOW);
  digitalWrite(PIN_DER_ADELANTE, LOW);
  digitalWrite(PIN_DER_ATRAS, LOW);
}

void avanzar(uint16_t pasos) {
  for (uint16_t i = 0; i < pasos; i++) {
    digitalWrite(PIN_IZQ_ADELANTE, HIGH);
    digitalWrite(PIN_DER_ADELANTE, HIGH);
    delay(MS_POR_PASO);
  }
  parar();
}

void girar(bool izquierda, uint16_t pasos) {
  for (uint16_t i = 0; i < pasos; i++) {
    if (izquierda) {
      digitalWrite(PIN_IZQ_ATRAS, HIGH);
      digitalWrite(PIN_DER_ADELANTE, HIGH);
    } else {
      digitalWrite(PIN_IZQ_ADELANTE, HIGH);
      digitalWrite(PIN_DER_ATRAS, HIGH);
    }
    delay(MS_POR_PASO);
  }
  parar();
}

float leerBateria() {
  long suma = 0;
  for (uint8_t i = 0; i < 8; i++) {
    suma += analogRead(PIN_BATERIA);
    delay(2);
  }
  float voltios = (suma / 8.0) * (VOLTIOS_REFERENCIA / 1023.0) * DIVISOR;
  // Escala a 0-100 % entre 10.5 V (vacía) y 12.6 V (llena).
  float porcentaje = (voltios - 10.5) / (12.6 - 10.5) * 100.0;
  if (porcentaje < 0.0) porcentaje = 0.0;
  if (porcentaje > 100.0) porcentaje = 100.0;
  return porcentaje;
}

bool hayCubo() {
  return digitalRead(PIN_IR_CUBO) == LOW;
}

void responder(const char *cuerpo) {
  Serial.print(F("OK "));
  Serial.println(cuerpo);
}

void estado() {
  char salida[96];
  snprintf(salida, sizeof(salida),
           "{\"bateria\":%.1f,\"cubo\":%s,\"recogidos\":%lu}",
           leerBateria(), hayCubo() ? "true" : "false", cubos_recogidos);
  responder(salida);
}

void error(const __FlashStringHelper *motivo) {
  Serial.print(F("ERR "));
  Serial.println(motivo);
}

void atender(char *linea) {
  char *orden = strtok(linea, " ");
  if (orden == NULL) return;

  if (!strcmp(orden, "ESTADO")) {
    estado();
    return;
  }

  if (!strcmp(orden, "RECOGER")) {
    if (!hayCubo()) {
      error(F("no hay cubo al alcance"));
      return;
    }
    brazo.write(ANGULO_RECOGER);
    delay(400);
    brazo.write(ANGULO_REPOSO);
    delay(400);
    cubos_recogidos++;
    estado();
    return;
  }

  if (leerBateria() < BATERIA_MINIMA) {
    error(F("bateria baja"));
    return;
  }

  char *arg = strtok(NULL, " ");
  uint16_t repeticiones = arg ? (uint16_t)atoi(arg) : 1;
  if (repeticiones == 0) repeticiones = 1;
  if (repeticiones > 40) repeticiones = 40;

  if (!strcmp(orden, "AVANZAR")) {
    avanzar(repeticiones);
    estado();
  } else if (!strcmp(orden, "GIRAR")) {
    char *lado = strtok(NULL, " ");
    bool izquierda = lado && (!strcmp(lado, "IZQ") || !strcmp(lado, "IZQUIERDA"));
    girar(izquierda, repeticiones);
    estado();
  } else if (!strcmp(orden, "ESPERAR")) {
    delay(MS_POR_PASO * repeticiones);
    estado();
  } else {
    error(F("orden desconocida"));
  }
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      buffer[usados] = '\0';
      if (usados > 0) atender(buffer);
      usados = 0;
    } else if (usados < sizeof(buffer) - 1) {
      buffer[usados++] = c;
    } else {
      usados = 0;
      error(F("linea demasiado larga"));
    }
  }
}
