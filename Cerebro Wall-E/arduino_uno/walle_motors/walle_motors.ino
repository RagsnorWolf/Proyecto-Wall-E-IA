/*
 * WALL-E — Arduino UNO: motores y servos.
 *
 * Este sketch NO piensa. Recibe lineas por SoftwareSerial desde el ESP32,
 * las ejecuta y contesta siempre. Toda la inteligencia vive en la PC.
 *
 * Protocolo (ver ../protocolo.md):
 *   entrada:  <id>,<op>,<a>,<b>\n      op = M | V | X | P
 *   salida:   <id>,OK,<v1>,<v2>\n
 *             <id>,ER,<codigo>,<detalle>\n
 *
 * Mapa de pines y por que:
 *   Timer0 -> millis()      : no se toca (pines 5 y 6 quedan para servos)
 *   Timer1 -> Servo.h       : pines 9 y 10 para servos, no PWM de motor
 *   Timer2 -> PWM de motor  : pines 3 (ENB) y 11 (ENA)
 *   SoftwareSerial          : 12 (RX) y 13 (TX), libres de todo lo anterior
 */

#include <SoftwareSerial.h>
#include <Servo.h>

// --------------------------------------------------------------------------
// Configuracion
// --------------------------------------------------------------------------
#define USE_ENCODERS 0        // 1 para contar pulsos en A2/A3

static const uint8_t PIN_SS_RX = 12;   // <- TX del ESP32 (GPIO17), directo
static const uint8_t PIN_SS_TX = 13;   // -> RX del ESP32 (GPIO16), con divisor 1k/2k

static const uint8_t PIN_ENA = 11;     // Timer2A
static const uint8_t PIN_IN1 = 7;
static const uint8_t PIN_IN2 = 8;
static const uint8_t PIN_ENB = 3;      // Timer2B
static const uint8_t PIN_IN3 = 4;
static const uint8_t PIN_IN4 = 2;

static const uint8_t PIN_SERVO[4] = {5, 6, 9, 10};

static const uint32_t BAUD_LINK = 57600;
static const uint32_t LINK_TIMEOUT_MS = 500;   // sin linea valida -> parada
static const uint16_t LINE_MAX = 48;
static const int16_t  MOTOR_DEADBAND = 60;     // por debajo de 6% el motor no arranca
static const int16_t  SERVO_MIN_DEG = 0;
static const int16_t  SERVO_MAX_DEG = 180;

// --------------------------------------------------------------------------
// Estado
// --------------------------------------------------------------------------
SoftwareSerial link(PIN_SS_RX, PIN_SS_TX);
Servo servos[4];

static char lineBuf[LINE_MAX + 1];
static uint8_t lineLen = 0;
static bool lineOverflow = false;
static uint32_t lastLineMs = 0;

static int16_t motorLeft = 0;
static int16_t motorRight = 0;
static uint8_t servoDeg[4] = {90, 90, 90, 90};
static bool servoAttached[4] = {false, false, false, false};

#if USE_ENCODERS
volatile int32_t encCount[2] = {0, 0};
#endif

// --------------------------------------------------------------------------
// Utilidades
// --------------------------------------------------------------------------
static int16_t clampInt(int32_t v, int16_t lo, int16_t hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return (int16_t)v;
}

/* Parsea un entero con signo. Devuelve false si no hay ningun digito. */
static bool parseLong(const char *s, int32_t *out) {
  if (s == NULL || *s == '\0') return false;
  bool neg = false;
  if (*s == '+' || *s == '-') {
    neg = (*s == '-');
    ++s;
  }
  if (*s < '0' || *s > '9') return false;
  int32_t acc = 0;
  while (*s >= '0' && *s <= '9') {
    int32_t digit = *s - '0';
    if (acc > 214748364L) return false;   // overflow
    acc = acc * 10L + digit;
    ++s;
  }
  if (*s != '\0') return false;           // basura despues del numero
  *out = neg ? -acc : acc;
  return true;
}

/* Corta el buffer en campos por coma, in situ. */
static uint8_t splitFields(char *buf, char **fields, uint8_t maxFields) {
  uint8_t n = 0;
  fields[n++] = buf;
  for (char *p = buf; *p != '\0'; ++p) {
    if (*p == ',') {
      *p = '\0';
      if (n < maxFields) fields[n++] = p + 1;
    }
  }
  return n;
}

// --------------------------------------------------------------------------
// Motores
// --------------------------------------------------------------------------
static void applyMotor(uint8_t side, int16_t value) {
  value = clampInt(value, -1000, 1000);
  bool forward = value >= 0;
  int32_t magnitude = forward ? value : -value;
  if (magnitude > 0 && magnitude < MOTOR_DEADBAND) magnitude = MOTOR_DEADBAND;
  uint8_t pwm = (uint8_t)((magnitude * 255L) / 1000L);

  if (side == 0) {
    digitalWrite(PIN_IN1, forward ? HIGH : LOW);
    digitalWrite(PIN_IN2, forward ? LOW : HIGH);
    analogWrite(PIN_ENA, pwm);
  } else {
    digitalWrite(PIN_IN3, forward ? HIGH : LOW);
    digitalWrite(PIN_IN4, forward ? LOW : HIGH);
    analogWrite(PIN_ENB, pwm);
  }
}

static void stopAll() {
  motorLeft = 0;
  motorRight = 0;
  analogWrite(PIN_ENA, 0);
  analogWrite(PIN_ENB, 0);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, LOW);
  digitalWrite(PIN_IN4, LOW);
}

static void setServo(uint8_t channel, int16_t deg) {
  if (channel > 3) return;
  deg = clampInt(deg, SERVO_MIN_DEG, SERVO_MAX_DEG);
  if (!servoAttached[channel]) {
    servos[channel].attach(PIN_SERVO[channel]);
    servoAttached[channel] = true;
  }
  servos[channel].write(deg);
  servoDeg[channel] = (uint8_t)deg;
}

// --------------------------------------------------------------------------
// Respuesta
// --------------------------------------------------------------------------
static void replyOk(int32_t id, int16_t v1, int16_t v2) {
  link.print(id);
  link.print(F(",OK,"));
  link.print(v1);
  link.print(',');
  link.println(v2);
}

static void replyErr(int32_t id, uint8_t code, int16_t detail) {
  link.print(id);
  link.print(F(",ER,"));
  link.print(code);
  link.print(',');
  link.println(detail);
}

// --------------------------------------------------------------------------
// Ejecucion de una linea completa
// --------------------------------------------------------------------------
static void executeLine(char *line) {
  char *fields[4];
  uint8_t n = splitFields(line, fields, 4);
  if (n < 2) return;                      // sin id u op: se ignora en silencio

  int32_t id = 0;
  if (!parseLong(fields[0], &id) || id <= 0) return;

  char op = fields[1][0];
  if (fields[1][1] != '\0') {
    replyErr(id, 2, 0);
    return;
  }

  int32_t a = 0;
  int32_t b = 0;
  bool haveA = (n >= 3) && parseLong(fields[2], &a);
  bool haveB = (n >= 4) && parseLong(fields[3], &b);

  switch (op) {
    case 'M':
      if (!haveA || !haveB) {
        replyErr(id, 1, 0);
        return;
      }
      if (a < -1000 || a > 1000 || b < -1000 || b > 1000) {
        replyErr(id, 3, 0);
        return;
      }
      motorLeft = (int16_t)a;
      motorRight = (int16_t)b;
      applyMotor(0, motorLeft);
      applyMotor(1, motorRight);
      replyOk(id, motorLeft, motorRight);
      return;

    case 'V':
      if (!haveA || !haveB) {
        replyErr(id, 1, 0);
        return;
      }
      if (a < 0 || a > 3 || b < SERVO_MIN_DEG || b > SERVO_MAX_DEG) {
        replyErr(id, 3, 0);
        return;
      }
      setServo((uint8_t)a, (int16_t)b);
      replyOk(id, (int16_t)a, (int16_t)b);
      return;

    case 'X':
      stopAll();
      replyOk(id, 0, 0);
      return;

    case 'P':
      // uptime en segundos, saturado a 9 h: el campo es int16 y envolveria
      // en falso cada 32 s.
      replyOk(id, (int16_t)min((uint32_t)32767, millis() / 1000L),
              (int16_t)(RAMEND - SP));
      return;

    default:
      replyErr(id, 2, 0);
      return;
  }
}

// --------------------------------------------------------------------------
// Recepcion
// --------------------------------------------------------------------------
static void pollLink() {
  while (link.available() > 0) {
    char c = (char)link.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!lineOverflow && lineLen > 0) {
        lineBuf[lineLen] = '\0';
        lastLineMs = millis();
        executeLine(lineBuf);
      }
      lineLen = 0;
      lineOverflow = false;
      continue;
    }
    if (lineLen < LINE_MAX) {
      lineBuf[lineLen++] = c;
    } else {
      lineOverflow = true;   // se descarta la linea entera, no se parte
    }
  }
}

// --------------------------------------------------------------------------
// Encoders opcionales (un canal por oruga, PCINT en el puerto C)
// --------------------------------------------------------------------------
#if USE_ENCODERS
ISR(PCINT1_vect) {
  // A2 = PC2 (oruga izquierda), A3 = PC3 (oruga derecha)
  static uint8_t prev = 0;
  uint8_t now = PINC;
  uint8_t rising = (uint8_t)(~prev) & now;
  if (rising & _BV(PC2)) encCount[0]++;
  if (rising & _BV(PC3)) encCount[1]++;
  prev = now;
}
#endif

// --------------------------------------------------------------------------
// Setup / loop
// --------------------------------------------------------------------------
void setup() {
  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_ENB, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  stopAll();

  link.begin(BAUD_LINK);
  link.setTimeout(20);

#if USE_ENCODERS
  pinMode(A2, INPUT_PULLUP);
  pinMode(A3, INPUT_PULLUP);
  PCMSK1 |= _BV(PCINT10) | _BV(PCINT11);
  PCICR |= _BV(PCIE1);
#endif

  lastLineMs = millis();
}

void loop() {
  pollLink();

  // Dead-man: si el ESP32 deja de hablar, se frena solo. El ESP32 hace lo
  // mismo un segundo despues si la PC desaparece.
  if (motorLeft != 0 || motorRight != 0) {
    if ((uint32_t)(millis() - lastLineMs) > LINK_TIMEOUT_MS) {
      stopAll();
    }
  }
}
