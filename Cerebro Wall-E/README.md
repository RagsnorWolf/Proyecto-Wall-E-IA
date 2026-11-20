# WALL-E — Cerebro, puente inalámbrico y músculos

Arquitectura pedida en el audio: **el cerebro es la computadora**. El modelo de IA
no entra en ningún microcontrolador. El ESP32 es el puente inalámbrico y el que
confirma que el comando llegó; el Arduino UNO sólo mueve motores y servos.

```
 ┌────────────────────────┐        UDP/WiFi         ┌──────────────┐      UART       ┌──────────────┐
 │  PC — Cerebro          │   WALLE/1 <id> <op> …   │    ESP32     │  57600 8N1      │ Arduino UNO  │
 │  modelo / PID / GUI    │ ──────────────────────► │  puente WiFi │ ──────────────► │  motores     │
 │  walle_link.py         │ ◄────────────────────── │              │ ◄────────────── │  servos      │
 └────────────────────────┘   WALLE/1 <id> OK …     └──────────────┘  <id>,OK,enc,enc└──────────────┘
                              + telemetría 10 Hz
```

El ida y vuelta es obligatorio: el PC no da una orden por buena hasta que el
**UNO** contesta. Si el ESP32 está vivo pero el UNO no, se ve en el ACK.

## Por qué no va el modelo adentro

- ATmega328P: 32 KB de flash, 2 KB de RAM. No entra ni el cargador del modelo.
- ESP32: 4 MB de flash típicos, WiFi, pero sigue sin ser un lugar sano para
  correr una política de RL a 60 Hz con LiDAR de 72 rayos.
- La PC ya tiene el cerebro entrenado (`walle_env_v3.py` + PPO) y sobra CPU.

## Qué hay en cada carpeta

| Ruta | Qué es |
|---|---|
| `arduino_uno/walle_motors/walle_motors.ino` | Sketch del UNO: L298N, 4 servos, parser de línea, ACK, watchdog. |
| `esp32/walle_bridge/walle_bridge.ino` | Sketch del ESP32: WiFi + UDP + Serial2, reenvía y espera el ACK del UNO. |
| `esp32/walle_bridge/config.h` | SSID, contraseña, IP, puerto, pines. **Lo único que hay que tocar.** |
| `cerebro/walle_link.py` | Cliente Python: abre el enlace, manda órdenes, espera ACK, lee telemetría. |
| `cerebro/consola.py` | Consola en castellano: `avanza 2 metros`, `gira 90 grados`, `detente`. |
| `cerebro/test_link.py` | Prueba sin hardware (`--loopback`) o contra el robot real (`--host`). |
| `cerebro/sim_link.py` | Adaptador para que el simulador PyBullet mande sus acciones por WiFi. |
| `protocolo.md` | Gramática exacta de los dos enlaces. |

## Cableado

### ESP32 ↔ Arduino UNO (UART 57600 8N1)

| ESP32 | UNO | Nota |
|---|---|---|
| GPIO17 (TX2) | D12 (RX SoftwareSerial) | **Directo**. 3,3 V supera el umbral del UNO (3,0 V) |
| GPIO16 (RX2) | D13 (TX SoftwareSerial) | **Divisor 1k/2k**: el UNO emite 5 V y el ESP32 no es tolerante |
| GND | GND | Obligatorio, masa común |

El divisor va en la línea que **sale del UNO**: 1 kΩ en serie desde D13 y 2 kΩ
de esa unión a GND. El pin del ESP32 ve 5 × 2/(1+2) = 3,33 V. Al revés no
hace falta nada: 3,3 V ya está por encima del umbral de 3,0 V del ATmega.
Poner el divisor en el sentido contrario deja el pin del ESP32 recibiendo 5 V
directos y se degrada con las semanas.

### Arduino UNO ↔ L298N

| UNO | L298N | Nota |
|---|---|---|
| D11 (PWM) | ENA | Velocidad oruga izquierda |
| D7 | IN1 | Sentido izquierda |
| D8 | IN2 | Sentido izquierda |
| D3 (PWM) | ENB | Velocidad oruga derecha |
| D4 | IN3 | Sentido derecha |
| D2 | IN4 | Sentido derecha |
| GND | GND | Masa común con la batería |

Los pines 3 y 11 son Timer2: el PWM no choca con `Servo.h` (Timer1) ni con
`millis()` (Timer0). Quitar los jumpers de 5 V del L298N si la lógica va a 5 V
del propio UNO.

### Arduino UNO ↔ servos

| UNO | Servo |
|---|---|
| D5 | Servo 0 (cuello) |
| D6 | Servo 1 (brazo izq.) |
| D9 | Servo 2 (brazo der.) |
| D10 | Servo 3 (libre) |

Alimentar los servos con fuente aparte y unir la masa. Cuatro servos colgados
del regulador del UNO lo reinician en el primer movimiento.

## Puesta en marcha

1. Editar `esp32/walle_bridge/config.h` con tu SSID, contraseña y la IP fija que
   le vas a dar al ESP32.
2. Flashear el UNO con `arduino_uno/walle_motors`.
3. Flashear el ESP32 con `esp32/walle_bridge` (placa «ESP32 Dev Module»).
4. Abrir el monitor serie del ESP32 a 115200: imprime la IP que tomó.
5. Probar sin robot, sólo el protocolo:

```bash
python cerebro/test_link.py --loopback
```

6. Probar contra el robot real:

```bash
python cerebro/test_link.py --host 192.168.1.50 --demo
```

## Seguridad de enlace (dead-man en tres capas)

| Capa | Si deja de llegar | Qué hace |
|---|---|---|
| PC | — | manda `X` al cerrar |
| ESP32 | 1000 ms sin paquete del PC | manda `X` al UNO y deja de reenviar |
| UNO | 500 ms sin línea válida del ESP32 | `stopAll()` y servos quietos |

Perder el WiFi no deja al robot caminando solo.

## Límites reales

- El UNO no tiene encoders: el ACK devuelve la orden aplicada, no la posición
  medida. Para odometría real hay que sumar encoders (el sketch deja el punto
  marcado con `USE_ENCODERS`).
- UDP no garantiza entrega: el PC reintenta 3 veces con 250 ms de espera. Si
  querés entrega garantizada, cambiar a TCP es un cambio de dos líneas en el
  ESP32 y en `walle_link.py`.
- 57600 baudios alcanzan para ~5700 líneas por segundo; a 60 Hz sobran.

## Verificación hecha

`python cerebro/test_link.py --loopback` levanta un ESP32+UNO falsos en
`127.0.0.1` y corre el protocolo entero. Resultado en esta máquina:

```
== 1. camino feliz: ping, motores, servo, parada ==
  [OK]   ping con ACK  (rtt=8 ms)
  [OK]   giro sobre el sitio aplicado  (puente=(620, -620))
  [OK]   servo 1 a 35 grados  (servos=[90, 35, 90, 90])
  [OK]   parada aplicada  (puente=(0, 0))
  [OK]   telemetria recibida  (rssi=-53 dBm)
== 2. el UNO rechaza: op desconocida ==
  [OK]   op invalida devuelve ER  (codigo=2)
== 3. perdida del 40%: el reintento salva la orden ==
  [OK]   8 de 10 ordenes sobreviven al 40% de perdida  (9/10  descartadas=8)
== 4. enlace muerto: timeout limpio, sin colgarse ==
  [OK]   timeout se dispara  (187 ms)

resultado: 8 OK, 0 fallos
```

Ese falso puente valida **igual que el sketch del UNO**: si aceptara algo que el
UNO rechaza, la prueba mentiría. Por eso el caso 2 usa una op que no existe y
espera `ER 2`.

## Cómo lo usa el simulador

`sim_link.py` traduce los rad/s de rueda de `walle_env_v2` (tope 5.0) a
−1000…1000 y mantiene el enlace con vida:

| Situación | Qué hace el adaptador |
|---|---|
| `drive()` llamado | manda la consigna ya, sin bloquear el tick de la GUI |
| consigna quieta | la repite a 4 Hz (el dead-man del ESP32 es de 1 s) |
| consigna cambiando a 60 Hz | techo de 20 Hz de tráfico: el PID no inunda el UDP |
| 1.5 s sin `drive()` | manda `X`, no repite la última orden |
| `close()` | parada síncrona y cierre del socket |

```python
from sim_link import open_wheel_link

wheels = open_wheel_link("192.168.1.50")   # o open_wheel_link(dry_run=True)
try:
    wheels.drive(left_rad_s, right_rad_s)  # cada tick del controlador
finally:
    wheels.close()
```

`open_wheel_link(dry_run=True)` devuelve el mismo objeto sin hardware y guarda
el historial en `.history`: el simulador se puede correr con el robot apagado.

## Nota sobre los ids

El UNO descarta cualquier línea con `id <= 0`. La parada de emergencia del
ESP32 usa un contador propio que arranca en 2 000 000 000, fuera del rango que
reparte la PC, y manda la orden dos veces para que una pérdida no deje al robot
andando.

## Desde el simulador

El simulador ya puede manejar el robot real. Tres formas:

```bash
# 1) sin hardware: el enlace guarda el historial y no abre socket
python interactive_walle.py --env v3 --robot-dry

# 2) robot real
python interactive_walle.py --env v3 --robot 192.168.1.50

# 3) otro puerto UDP
python interactive_walle.py --env v3 --robot 192.168.1.50 --robot-port 4210
```

También hay un acceso directo listo: `WALL-E Robot Real.bat`, en la carpeta
`Motor RL` del simulador. Pide la IP la primera vez, la guarda en
`robot_ip.txt` y a partir de ahí arranca solo.

Si el ESP32 no está en la red, el simulador arranca igual y avisa por consola:
el enlace nunca es requisito para simular.

La ruta a `sim_link.py` se puede mover con la variable `WALLE_CEREBRO_DIR`:

```powershell
$env:WALLE_CEREBRO_DIR = "D:\robot\cerebro"
```

## Qué manda el simulador

`walle_env_v2.step()` calcula `left_speed` y `right_speed` en rad/s (tope 5.0)
y se los pasa al adaptador antes de mover las ruedas virtuales. El adaptador
los convierte a −1000…1000 con `pwm = rad_s / 5.0 * 1000`. O sea: la misma
política que mueve a WALL-E en PyBullet mueve al robot físico, con la misma
curva y el mismo signo.


