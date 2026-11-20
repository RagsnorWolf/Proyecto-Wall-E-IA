# Protocolo WALL-E — PC ⇄ ESP32 ⇄ UNO

Dos enlaces, dos gramáticas. Ambas en ASCII, una línea por mensaje, `\n` al
final. Sin binario, sin JSON: se lee en el monitor serie y se depura a ojo.

---

## 1. PC ⇄ ESP32 (UDP, puerto 4210)

Texto plano en un datagrama. Un datagrama = una línea = un mensaje.

### 1.1 PC → ESP32 (orden)

```
WALLE/1 <id> <op> <a> <b>
```

| Campo | Tipo | Rango | Qué es |
|---|---|---|---|
| `WALLE/1` | literal | — | Versión del protocolo. Cualquier otra cosa se descarta. |
| `id` | entero | 1 … 2 000 000 000 | Identificador de la orden. El ACK repite el mismo. |
| `op` | char | `M` `V` `X` `P` | Motor, servo, parada, ping. |
| `a` | entero | ver op | Primer argumento. |
| `b` | entero | ver op | Segundo argumento. |

Operaciones:

| op | a | b | Significado |
|---|---|---|---|
| `M` | −1000 … 1000 | −1000 … 1000 | Oruga izquierda / derecha. Negativo = atrás. |
| `V` | 0 … 3 | 0 … 180 | Servo `a` al ángulo `b` en grados. |
| `X` | 0 | 0 | Parada inmediata de motores (servos quedan). |
| `P` | 0 | 0 | Ping: no toca nada, sólo mide ida y vuelta. |

Ejemplo: `WALLE/1 421 M 620 -620` → girar sobre el sitio hacia la izquierda.

### 1.2 ESP32 → PC (respuesta)

```
WALLE/1 <id> OK <v1> <v2> <rtt_ms>
WALLE/1 <id> ER <codigo> <rtt_ms>
```

| Campo | Qué es |
|---|---|
| `v1`, `v2` | Eco de lo aplicado por el UNO (misma semántica que `a`, `b`). |
| `rtt_ms` | Milisegundos desde que el ESP32 recibió la orden hasta el ACK del UNO. |
| `codigo` | `1` = timeout del UNO · `2` = línea inválida · `3` = cola llena · `4` = UNO sin init |

`OK` significa: el ESP32 recibió, el UNO ejecutó y contestó. No significa que el
robot se haya movido.

### 1.3 ESP32 → PC (telemetría, 10 Hz, sin pedirla)

```
WALLE/1 T <uptime_ms> <rssi> <uno_ok> <ultimo_id> <cola>
```

| Campo | Qué es |
|---|---|
| `uptime_ms` | Milisegundos desde el arranque del ESP32. |
| `rssi` | dBm de la WiFi. −50 pegado al router, −85 al borde. |
| `uno_ok` | `1` si el último ACK del UNO llegó a tiempo, `0` si no. |
| `ultimo_id` | Último id contestado. Sirve para detectar datagramas perdidos. |
| `cola` | Órdenes esperando ACK en este momento (0 … 8). |

La telemetría va a la última IP que mandó una orden. Si no hay ninguna, no se
emite.

---

## 2. ESP32 ⇄ UNO (UART 57600 8N1)

### 2.1 ESP32 → UNO

```
<id>,<op>,<a>,<b>\n
```

| op | a | b |
|---|---|---|
| `M` | −1000 … 1000 | −1000 … 1000 |
| `V` | 0 … 3 | 0 … 180 |
| `X` | 0 | 0 |
| `P` | 0 | 0 |

Ejemplo: `421,M,620,-620`

### 2.2 UNO → ESP32

```
<id>,OK,<v1>,<v2>\n
<id>,ER,<codigo>,<detalle>\n
```

Códigos de error del UNO:

| Código | Qué pasó |
|---|---|
| `1` | Línea mal formada (campos de menos, letra donde va un número). |
| `2` | `op` desconocida. |
| `3` | Argumento fuera de rango. |

El UNO contesta **siempre**, incluso cuando rechaza. Un `ER` es prueba de vida
igual que un `OK`.

---

## 3. Reglas de temporización

| Constante | Valor | Dónde | Para qué |
|---|---|---|---|
| `PC_ACK_TIMEOUT_MS` | 400 | PC | Espera del ACK antes de reintentar. |
| `PC_RETRIES` | 3 | PC | Reintentos por orden. |
| `ESP_UNO_TIMEOUT_MS` | 120 | ESP32 | Espera del ACK del UNO. |
| `ESP_PC_TIMEOUT_MS` | 1000 | ESP32 | Sin paquetes del PC → `X` al UNO. |
| `UNO_LINK_TIMEOUT_MS` | 500 | UNO | Sin líneas del ESP32 → `stopAll()`. |
| `TELEMETRY_HZ` | 10 | ESP32 | Ritmo de telemetría. |

Los tres timeouts son decrecientes a propósito: el más chico perdona primero al
más grande. Si el PC se cuelga, el ESP32 lo nota en 1 s y el UNO ya se frenó
solo 0,5 s antes.

El presupuesto del ACK tiene una restricción aparte: el PC espera 400 ms, y el
ESP32 tarda como mucho 120 × (1 + 1 reintento) = 240 ms en rendirse y contestar
`ER 1`. Así el PC recibe el error del puente antes de darse por vencido él
mismo, y el diagnóstico dice «el UNO no contestó» en vez de un timeout mudo.

---

## 4. Casos que el protocolo cubre

**El WiFi se corta a mitad de marcha.** El ESP32 deja de recibir, a los 1000 ms
manda `X`. El UNO además se frena solo a los 500 ms si el ESP32 también se cayó.

**Se pierde un datagrama.** El PC reintenta con el mismo `id` hasta 3 veces. El
UNO es idempotente: repetir `M,600,600` deja el mismo PWM.

**El UNO se resetea.** El ESP32 recibe silencio, marca `uno_ok=0` en la
telemetría y empieza a contestar `ER 1`. El PC lo ve y puede avisar.

**Dos órdenes seguidas.** La cola del ESP32 es de 8. Con más, contesta `ER 3`
enseguida en vez de acumular latencia.

**Llega basura al puerto UDP.** Se descarta si no empieza con `WALLE/1` o si
algún campo no parsea. Nunca se contesta a basura: evita bucles de rebote.
