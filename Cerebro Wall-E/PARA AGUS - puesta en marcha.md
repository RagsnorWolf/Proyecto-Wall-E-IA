# Para Agus — puesta en marcha

Esta carpeta ya tiene todo escrito. No hay que programar nada: hay que cargar
dos sketches, cablear tres placas y correr un comando. Abajo está el orden y
cómo saber que cada paso salió bien antes de pasar al siguiente.

## Lo que hace falta

| Cosa | Detalle |
|---|---|
| Arduino IDE | Con la placa **ESP32** instalada (Boards Manager → «esp32 by Espressif») |
| Python 3 | En la computadora. Windows: `winget install Python.Python.3.12` |
| Arduino UNO | Con cable USB |
| ESP32 | Dev Module, cualquier variante con WiFi |
| L298N | Puente H para las dos orugas |
| 4 servos | Con fuente aparte, no del regulador del UNO |
| 2 resistencias | 1 kΩ y 2 kΩ (el divisor del puerto serie) |
| Batería | 7,4 V o 9 V para los motores |

---

## Paso 1 — Cargar el Arduino UNO

1. Abrir `arduino_uno/walle_motors/walle_motors.ino`.
2. Herramientas → Placa → **Arduino Uno**. Elegir el puerto COM.
3. Subir.

**Cómo saber que salió bien:** el LED de la placa hace un parpadeo y el IDE
dice «Subido». Nada más. El UNO no imprime por USB, su puerto serie está
ocupado por el ESP32.

---

## Paso 2 — Configurar el WiFi

Abrir `esp32/walle_bridge/config.h` y cambiar sólo estas dos líneas:

```c
#define WIFI_SSID       "el nombre de tu wifi"
#define WIFI_PASSWORD   "la contraseña"
```

Todo lo demás se deja como está.

---

## Paso 3 — Cargar el ESP32

1. Abrir `esp32/walle_bridge/walle_bridge.ino` (el `config.h` se abre solo al lado).
2. Herramientas → Placa → **ESP32 Dev Module**. Puerto COM del ESP32.
3. Subir.
4. Abrir el **Monitor Serie** a **115200**.

**Cómo saber que salió bien:** tiene que imprimir algo así:

```
=== WALL-E bridge ESP32 ===
[WiFi] Conectando....
[WiFi] IP del ESP32: 192.168.1.50
[WiFi] RSSI: -54 dBm
[UDP] escuchando en el puerto 4210
```

**Anotá esa IP.** Es la que va a usar la computadora.

Si en vez de eso dice `AP de emergencia: WALL-E-BRIDGE`, no enganchó el WiFi:
revisar SSID y contraseña, o que la red sea de 2,4 GHz (el ESP32 no ve 5 GHz).

---

## Paso 4 — Cablear

### ESP32 ↔ UNO

| ESP32 | UNO | Cómo |
|---|---|---|
| GPIO17 | D12 | Cable directo |
| GPIO16 | D13 | **Con divisor**: 1 kΩ en serie y 2 kΩ a GND |
| GND | GND | Cable directo, obligatorio |

El divisor va del lado del UNO, porque el UNO habla en 5 V y el ESP32 aguanta
3,3 V. Al revés no hace falta nada.

### UNO ↔ L298N

| UNO | L298N |
|---|---|
| D11 | ENA |
| D7 | IN1 |
| D8 | IN2 |
| D3 | ENB |
| D4 | IN3 |
| D2 | IN4 |
| GND | GND (masa común con la batería) |

### UNO ↔ servos

| UNO | Servo |
|---|---|
| D5 | Cuello |
| D6 | Brazo izquierdo |
| D9 | Brazo derecho |
| D10 | Libre |

Los servos van con **fuente propia** y la masa unida a la del UNO. Cuatro
servos colgados del regulador del UNO lo reinician en el primer movimiento.

---

## Paso 5 — Probar sin el robot

En la computadora, con el ESP32 encendido y en la misma red:

```bash
cd "Cerebro Wall-E\cerebro"
python test_link.py --host 192.168.1.50
```

Si `python` no se reconoce, probar con `py test_link.py --host ...`.

(poner la IP del paso 3)

**Cómo saber que salió bien:**

```
== enlace real contra 192.168.1.50:4210 ==
  [OK]   ping  (rtt=12 ms)
  telemetria: rssi=-54 dBm  uno_ok=True  cola=0
  [OK]   UNO responde detras del ESP32

resultado: 2 OK, 0 fallos
```

`uno_ok=True` es la prueba de que el ESP32 **y** el UNO están vivos y
conversando. Si el ping anda pero `uno_ok` es `False`, el problema está en el
cable ESP32↔UNO o en el divisor.

---

## Paso 6 — Probar con el robot

Con el robot levantado en el aire, ruedas al aire:

```bash
python test_link.py --host 192.168.1.50 --demo
```

Hace ping, avanza 1,2 s, barre los cuatro servos y gira sobre el sitio. Si las
orugas giran y los servos se mueven, está listo.

---

## Paso 7 — Hablarle al robot en castellano

Esta es la forma más simple. **Doble clic en `Hablar con WALL-E.bat`** (está en
la carpeta `Cerebro Wall-E`). Pide la IP la primera vez, la guarda en
`ip_robot.txt`, y a partir de ahí abre directo el prompt.

O a mano:

```bash
cd "Cerebro Wall-E\cerebro"
python consola.py --host 192.168.1.50
```

Se abre un prompt en la PC:

```
Conectado a 192.168.1.50  (rtt 12 ms)
  rssi=-54 dBm  uno_ok=True

> avanza 2 metros
  avanzar 2.00 m: 7.41 s a (600, 600)
  listo (ultimo rtt 11 ms)
> gira 90 grados
  girar +90 grados: 0.88 s a (-600, 600)
  listo (ultimo rtt 12 ms)
> detente
  motores frenados
> salir
```

Órdenes que entiende: `avanza 2 metros`, `avanza 50 cm`, `retrocede 1 m`,
`gira 90 grados` (negativo gira a la derecha), `detente`, `izquierda`,
`derecha`, `servo 0 45`, `estado`, `salir`.

**Ojo con las distancias.** El robot no tiene encoders: «avanza 2 metros» es en
realidad «mueve las orugas este tiempo a esta velocidad». Si las ruedas patinan
o la batería está baja, avanza menos. Los dos números de calibración están al
principio de `consola.py`:

```python
VMAX_MS = 0.45       # metros por segundo a PWM 1000
TURN_DEG_S = 170.0   # grados por segundo girando sobre el sitio a PWM 1000
```

Para calibrar: pedir `avanza 2 metros`, medir con cinta, y corregir
`VMAX_MS * (metros_reales / 2.0)`. Lo mismo con `gira 180 grados`.

---

## Paso 8 — Manejar el robot desde el simulador

En la carpeta del simulador, doble clic en `WALL-E Robot Real.bat`. La primera
vez pide la IP, la guarda, y a partir de ahí arranca solo.

El simulador abre igual que siempre, y ahora las velocidades que calcula el
controlador también salen por WiFi al robot.

---

## Si algo no anda

| Síntoma | Causa más probable |
|---|---|
| `ping` sin respuesta | IP equivocada, ESP32 en otra red, o firewall de Windows bloqueando UDP 4210 |
| `ping` anda, `uno_ok=False` | Cable ESP32↔UNO, divisor mal puesto, o el UNO sin cargar |
| El UNO contesta `ER 2` | Versión de protocolo distinta: revisar que los dos sketches sean los de esta carpeta |
| Los motores giran al revés | Invertir los dos cables del motor en el L298N, no en el código |
| Los servos tiemblan o el UNO se reinicia | Los servos están colgados del regulador del UNO: hace falta fuente aparte |
| Se mueve a tirones | Bajar `UNO_BAUD` a 38400 en `config.h` y en el sketch del UNO |
| El robot se frena solo a los 2 segundos | Es el dead-man: la computadora dejó de mandar. Revisar el WiFi |

---

## Lo que hay que saber antes de enchufar

- **El robot se frena solo** si la computadora deja de hablarle (1 segundo) o
  si el ESP32 se calla (medio segundo). No se va a escapar caminando.
- **Sin encoders no hay odometría.** El robot confirma que recibió y ejecutó la
  orden, no cuánto avanzó. Para eso hacen falta encoders (el sketch tiene el
  hueco marcado con `USE_ENCODERS`).
- **El modelo de IA no está adentro de ninguna placa.** Vive en la computadora.
  Las placas sólo obedecen.
