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
| `arduino_uno/walle_motors/walle_motors.ino` | Sketch del UNO: L298N, 4 servos, HC-SR04, parser de línea, ACK, watchdog. |
| `esp32/walle_bridge/walle_bridge.ino` | Sketch del ESP32: WiFi + UDP + Serial2, reenvía y espera el ACK del UNO. |
| `esp32/walle_bridge/config.h` | SSID, contraseña, IP, puerto, pines. **Lo único que hay que tocar.** |
| `cerebro/walle_link.py` | Cliente Python: abre el enlace, manda órdenes, espera ACK, lee telemetría y distancia. |
| `cerebro/consola.py` | **Modo manual**: consola en castellano, `avanza 2 metros`, `gira 90 grados`, `detente`. |
| `cerebro/autonomo.py` | **Modo autónomo**: esquiva obstáculos solo con el sonar. |
| `cerebro/test_link.py` | Prueba sin hardware (`--loopback`) o contra el robot real (`--host`). |
| `cerebro/test_autonomo.py` | Prueba el cerebro autónomo con un enlace falso, sin robot. |
| `cerebro/sim_link.py` | Adaptador para que el simulador PyBullet mande sus acciones por WiFi. |
| `WALL-E Cerebro Robot.bat` | **El lanzador.** Menú: manual, autónomo, pruebas, estado, IP. |
| `Hablar con WALL-E.bat` | Atajo directo al modo manual, sin pasar por el menú. |
| `protocolo.md` | Gramática exacta de los dos enlaces, incluida la trama de distancia. |

## Los dos modos

Todo arranca con doble clic en `WALL-E Cerebro Robot.bat` (o en el acceso
directo `WALL-E Cerebro Robot` del escritorio).

```
  [1] Modo manual      -> consola.py    le hablás y obedece
  [2] Modo autonomo    -> autonomo.py   se mueve solo, esquiva
  [3] Probar enlace    -> test_link.py  sin robot, sin WiFi
  [4] Estado           -> ping + telemetría + distancia
  [5] Cambiar la IP     escribe ip_robot.txt
```

### Modo manual

Le hablás en castellano y traduce cada orden a PWM de oruga. No tiene encoders:
"avanza 2 metros" es "mueve las orugas este tiempo". Los dos números de
calibración (`VMAX_MS`, `TURN_DEG_S`) están arriba de `consola.py` y se ajustan
midiendo con cinta métrica.

### Modo autónomo

Reactivo, no aprendido. Lee el sonar, y según lo que ve:

| Distancia al frente | Qué hace |
|---|---|
| más de 120 cm | avanza a crucero |
| entre 65 y 120 cm | interpola la velocidad |
| entre 22 y 65 cm | avanza despacio, sin frenar en seco |
| 22 cm o menos | frena, barre con el servo, escapa por el lado libre |
| sin lectura por más de 1,2 s | se queda quieto |

El sonar va montado en el **servo 0**. Barre a ±55° para elegir el lado de
escape. Si el sonar va fijo, `SONAR_SERVO = -1` en `autonomo.py` y el robot
elige el lado alternando.

**No usa el PPO del simulador.** La política entrenada come 36 rayos LiDAR que
el robot físico no tiene. Correrla con un solo sonar sería inventar 35 números.
Cuando haya un LiDAR giratorio, `autonomo.py` es el archivo que se reemplaza por
el cargador del modelo.

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

### Arduino UNO ↔ HC-SR04

| UNO | HC-SR04 | Nota |
|---|---|---|
| A0 | TRIG | Analógico usado como digital: los pines digitales están tomados |
| A1 | ECHO | Ídem. El HC-SR04 emite 5 V, el UNO los lee bien |
| 5V | VCC | El módulo consume ~15 mA en picos, el regulador del UNO lo aguanta |
| GND | GND | Masa común |

Montado sobre el servo 0 para poder barrer. Si va fijo, apuntarlo al frente y
poner `SONAR_SERVO = -1` en `autonomo.py`.

El `pulseIn` bloquea hasta 10 ms por lectura, y en ese tiempo el buffer de 64
bytes de `SoftwareSerial` se puede desbordar. Por eso el UNO muestrea cada
150 ms: el ACK perdido se reintenta, la distancia vieja no se recupera.

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
  [OK]   distancia del sonar recibida  (71 cm)
  [OK]   la distancia se refresca, no se congela  (71 -> 73 cm)
== 2. el UNO rechaza: op desconocida ==
  [OK]   op invalida devuelve ER  (codigo=2)
== 3. perdida del 40%: el reintento salva la orden ==
  [OK]   8 de 10 ordenes sobreviven al 40% de perdida  (10/10  descartadas=6)
== 4. enlace muerto: timeout limpio, sin colgarse ==
  [OK]   timeout se dispara  (172 ms)

resultado: 10 OK, 0 fallos
```

Ese falso puente valida **igual que el sketch del UNO**: si aceptara algo que el
UNO rechaza, la prueba mentiría. Por eso el caso 2 usa una op que no existe y
espera `ER 2`.

Y el cerebro autónomo se prueba sin robot, con distancias inventadas:

```
python cerebro/test_autonomo.py

== 1. pista libre: avanza ==
  [OK]   avanza con 200 cm al frente
  [OK]   no frena de golpe
== 2. obstaculo cerca: frena, barre y escapa ==
  [OK]   frena antes de tocar
  [OK]   barre a los dos lados
  [OK]   escapa hacia la izquierda libre
  [OK]   no gira hacia el lado tapado
== 3. sin sonar: quieto, nunca a ciegas ==
  [OK]   no avanza sin lecturas
  [OK]   frena por seguridad
== 4. obstaculo a la derecha: escapa a la derecha ==
  [OK]   escapa hacia la derecha libre
== 5. zona lenta: avanza despacio, no se detiene ==
  [OK]   avanza en la zona lenta
  [OK]   no acelera en la zona lenta

resultado: 11 OK, 0 fallos
```

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


