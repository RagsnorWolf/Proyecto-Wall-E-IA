---
name: wall-e-proyecto
description: Contexto maestro del proyecto WALL-E. Usar siempre que se trabaje en Cerebro Wall-E, Simulador Wall-E o Asistente IA Wall-E: define qué va en cada carpeta, en cuál se trabaja según la tarea, y cómo se publica cada cambio en el repositorio. Cargar antes de tocar cualquier archivo del proyecto.
---

---
name: wall-e-proyecto
description: Contexto maestro del proyecto WALL-E. Usar siempre que se trabaje en Cerebro Wall-E, Simulador Wall-E o Asistente IA Wall-E: define qué va en cada carpeta, en cuál se trabaja según la tarea, y cómo se publica cada cambio en el repositorio. Cargar antes de tocar cualquier archivo del proyecto.
---

# Proyecto WALL-E — Contexto maestro

Este documento es la fuente de verdad del proyecto. Si algo acá contradice a
cualquier otra nota, manda este archivo.

---

## 1. Qué es el proyecto

Un robot WALL-E físico, construido y controlado desde una PC. El objetivo final
es que el robot se mueva solo: que perciba, decida y actúe sin que nadie le diga
qué hacer.

La inteligencia **nunca** vive en el hardware. Vive en la PC. El hardware solo
obedece.

```
   PC                        ESP32                    Arduino UNO
   ────                      ─────                    ───────────
   cerebro                    puente                   músculos
   decide todo      WiFi      sin lógica      serie    sin lógica
   ──────────────────────►    ──────────────────────►
   UDP 4210                  <id>,<op>,<a>,<b>        motores + servos
```

| Pieza | Rol | Qué hace | Qué NO hace |
|---|---|---|---|
| **PC** | Cerebro | Percibe, decide, planifica, manda órdenes | No mueve motores |
| **ESP32** | Puente | Recibe por WiFi, traduce a serie, devuelve el ACK | No decide nada |
| **UNO** | Músculos | PWM de motores, ángulos de servo, lee encoders | No decide nada |

El ACK solo es válido si lo generó el UNO después de ejecutar. El ESP32 no
inventa respuestas.

---

## 2. Las tres carpetas

Viven en el escritorio. Cada una es un proyecto cerrado que se puede abrir solo,
en otra PC, con otra IA, y entender qué es.

```
Escritorio\
  Cerebro Wall-E\        el robot físico: hardware + enlace + consola
  Simulador Wall-E\      el gemelo virtual: física, GUI, entrenamiento
  Asistente IA Wall-E\   el agente conversacional: proyecto aparte
```

### 2.1 `Cerebro Wall-E`

**Qué es:** todo lo necesario para que el robot de la vida real se mueva.

**Qué contiene:**

```
Cerebro Wall-E\
  README.md
  protocolo.md                  el contrato PC ↔ ESP32 ↔ UNO
  PARA AGUS - puesta en marcha.md
  Hablar con WALL-E.bat         consola interactiva
  arduino_uno\walle_motors\     el sketch del UNO
  esp32\walle_bridge\           el sketch del ESP32 + config.h
  cerebro\walle_link.py         cliente UDP, el protocolo del lado PC
  cerebro\test_link.py          pruebas del enlace, con --loopback
  cerebro\sim_link.py           adaptador para que el simulador maneje el robot
  cerebro\consola.py            control manual por teclado
```

**Regla:** acá entra el hardware y el enlace. No entra el modelo de IA, ni
PyBullet, ni el simulador.

**Cuando el cerebro aprenda a navegar solo**, acá va a entrar la política
entrenada (el `.zip`) y el código que la corre contra los sensores reales. Hoy no
está porque el robot físico todavía no tiene sensor de distancia — ver §7.

### 2.2 `Simulador Wall-E`

**Qué es:** el gemelo virtual del robot. Sirve para dos cosas distintas:

1. **Ver** el robot en 3D y manejarlo a mano (modo manual, chat en castellano).
2. **Entrenar** el cerebro PPO que después va a manejar el robot real.

**Qué contiene:**

```
Simulador Wall-E\
  INSTALAR.bat                  crea .venv e instala dependencias
  WALL-E Simulador Robot.bat    abre la GUI
  WALL-E Entrenar Cerebro.bat   entrena el PPO
  WALL-E Robot Real.bat         manda las órdenes al ESP32 por WiFi
  interactive_walle.py          la GUI, el chat, el controlador
  walle_env_v3.py               el entorno V6: observación de 66 números
  train_walle_v5.py             el entrenamiento
  transplant_v4_to_v5.py        trasplante de pesos V4 → V5
  models\                       las políticas entrenadas (.zip)
  material_0.png                textura real del robot, 2048×2048
  walle_visual.obj              la malla del robot
  walle_color_parts\            las 16 piezas de color (fallback sin textura)
```

**Regla:** acá entra todo lo que corre en PyBullet. El simulador es el laboratorio
donde se entrena; el resultado del entrenamiento es un archivo `.zip`.

### 2.3 `Asistente IA Wall-E`

**Qué es:** un proyecto **aparte**. No es el cerebro motor. Es el intento de
construir un agente conversacional propio — estilo ChatGPT, Claude, Grok — que
corre local, sin cuentas ni internet.

**Qué contiene:**

```
Asistente IA Wall-E\
  Iniciar WALL-E.bat            abre la cabina en el navegador
  INSTALAR.bat                  dependencias de Python
  README.md
  Modelo AI\                    el cerebro: personalidad, memoria, voz, visión
  Pagina Web\cockpit\           el servidor y la interfaz web
```

**Regla:** este proyecto no sabe nada del PPO ni del robot físico. Se desarrolla
por separado. Hoy está **pausado**: primero el cerebro motor y el simulador.

---

## 3. En qué carpeta se trabaja

Esta es la regla de oro del proyecto. No se mezcla.

| Si la tarea es… | Se trabaja en… | Se toca… |
|---|---|---|
| Mover el robot real, protocolo, sketches, consola | `Cerebro Wall-E` | `cerebro\`, `esp32\`, `arduino_uno\` |
| Entrenar, cambiar la física, la GUI, la recompensa | `Simulador Wall-E` | `interactive_walle.py`, `walle_env_v3.py`, `train_walle_v5.py` |
| Conversación, voz, memoria, cabina web | `Asistente IA Wall-E` | `Modelo AI\`, `Pagina Web\cockpit\` |
| Publicar | repositorio | ver §5 |

**El simulador produce, el cerebro consume.** Cuando el simulador genera una
política mejor, esa política se copia al cerebro. Nunca al revés.

```
Simulador Wall-E\models\walle_ppo_model_v5_recovery.zip
        │
        │  se entrena y mejora acá
        ▼
Cerebro Wall-E\politica\walle_ppo_model_v5_recovery.zip
        │
        │  se ejecuta contra los sensores reales
        ▼
        robot físico
```

---

## 4. El porqué de esta organización

Tres razones, y las tres importan:

1. **Continuidad entre dispositivos.** Cada carpeta se abre sola en cualquier PC.
2. **Continuidad entre IAs.** Cada carpeta lleva su `00-CONTEXTO.md` y su
   `README.md`. Una IA que la abra por primera vez entiende qué es, qué hay
   dentro y qué se hace, sin preguntar.
3. **Orden de trabajo.** Se sabe en todo momento qué se está tocando y qué no.
   El simulador no ensucia el cerebro, el cerebro no ensucia el agente.

---

## 5. El repositorio

**Repositorio oficial del proyecto:**

```
https://github.com/RagsnorWolf/Proyecto-Wall-E-IA
```

**Regla permanente:** cada avance real en cualquiera de las tres carpetas se
commitea y se pushea. Sin excepción y sin que haya que pedirlo.

### 5.1 Anatomía del repo

```
Proyecto-Wall-E-IA\
  Cerebro Wall-E\
  Simulador Wall-E\
  Asistente IA Wall-E\
  README.md
```

Los nombres de las tres carpetas del repo son **exactamente** los nombres de las
carpetas del escritorio. Así la copia es directa.

### 5.2 Qué se commitea y qué no

| Se commitea | No se commitea |
|---|---|
| Código fuente (`.py`, `.ino`, `.js`, `.jsx`) | `.venv\` (887 MB, no portable) |
| Lanzadores (`.bat`) | `__pycache__\` |
| Documentación (`.md`) | `node_modules\` |
| Modelos entrenados (`.zip`, `.onnx`) | `checkpoints\` (historial de entrenamiento) |
| Texturas y mallas (`.png`, `.obj`, `.glb`) | `*.log`, `*.db`, temporales |
| Configuración de ejemplo | `config.json` con datos personales |

Un modelo entrenado **sí** se commitea: es el producto del proyecto. Un
checkpoint intermedio no: es basura regenerable.

### 5.3 El mensaje de commit

Formato: `tipo(carpeta): qué cambió`

```
feat(simulador): recompensa de holgura en el entorno V6
fix(cerebro): timeout del ACK del UNO
docs(agente): puesta en marcha con Ollama
```

---

## 6. Arquitectura técnica

### 6.1 Protocolo PC ↔ ESP32 ↔ UNO

**PC → ESP32 (UDP 4210, ASCII):**

```
WALLE/1 <id> <op> <a> <b>
```

| op | Significado | a | b |
|---|---|---|---|
| `M` | Mover orugas | izquierda −1000..1000 | derecha −1000..1000 |
| `V` | Velocidad de crucero | mm/s | — |
| `X` | Parar | — | — |
| `P` | Ping | — | — |

**ESP32 → PC:**

```
WALLE/1 <id> OK <v1> <v2> <rtt_ms>
WALLE/1 <id> ER <codigo> <rtt_ms>
```

| Código | Significado |
|---|---|
| 1 | El UNO no respondió a tiempo |
| 2 | Línea inválida |
| 3 | Cola llena |
| 4 | El UNO no está inicializado |

**ESP32 ↔ UNO (serie 57600 8N1):**

```
→  <id>,<op>,<a>,<b>\n
←  <id>,OK,<v1>,<v2>\n
←  <id>,ER,<codigo>,<detalle>\n
```

**Timeouts, en cascada:**

```
PC espera ACK      400 ms
  ESP32 espera UNO 120 ms
    UNO link timeout 500 ms
ESP32 espera PC   1000 ms
```

Decrecientes a propósito: el `ER 1` del ESP32 tiene que llegar antes de que la PC
se rinda, si no el error se reporta como timeout de red y se pierde la causa.

**Hardware del enlace:**

```
UNO D13 (TX) ──[1 kΩ]──┬── ESP32 GPIO16 (RX2)
                       │
                     [2 kΩ]
                       │
                      GND
```

Divisor de tensión obligatorio: el UNO transmite a 5 V y el ESP32 tolera 3,3 V.
ESP32 → UNO (GPIO17 → D12) va directo.

### 6.2 El entorno del simulador (V5)

```
Observación: 66 números
  ├── 14  base (posición, orientación, velocidad, contacto)  ← V2 original
  ├── 36  abanico LiDAR frontal de 36 rayos                  ← V4
  └──  8  resolución de atascos                              ← V5
Acción: 2 continuas (oruga izquierda, oruga derecha)
```

Los primeros 50 números son exactamente los del V4, en el mismo orden. Por eso el
trasplante de pesos funciona sin reentrenar de cero.

**Cómo mira el LiDAR (corregido en esta tanda):**

```
Plano de escaneo     SENSOR_FOOT_Z = 0.06 m sobre el suelo LOCAL del robot
                     (antes: 0.06 m sobre la base = 0.21 m del piso,
                      y un obstáculo de 12 cm era invisible)

Origen de los rayos  centro del chasis (LIDAR_ORIGIN_OFFSET = 0.0)
                     el robot se saca del broadphase durante el barrido

Distancias           desde el PARAGOLPES: se resta el semieje del chasis
                     en la dirección del rayo (BODY_HALF_X/Y)
                     0.00 m = tocando, no "a 17 cm del centro"

Anillo               72 rayos, 360°, cada 5°   → distancia mínima, huecos, rumbo
Abanico              36 rayos, −90° a +90°     → los 36 números de la observación
   ├── 24 rayos de −40° a +40°, uno cada 3.48°  ← donde el robot decide
   └──  6 + 6 de ±48° a ±90°, uno cada 8.4°     ← cobertura lateral
Cono frontal         FRONT_CONE_DEG = 35°  → 18 rayos (antes 13 con reparto uniforme)
```

Un reparto uniforme de 36 rayos en 180° gasta 5° por rayo y deja el cono de
decisión con muy poca resolución: la diferencia entre una caja centrada y una
esquina entraba en el mismo rayo. El reparto denso-al-frente arregla eso sin
gastar dimensiones de observación.

**Recompensas V5:**

```
CONTACT_PENALTY    −0.25    tocó algo
ESCAPE_BONUS       +3.00    salió de un atasco
CLEARANCE_REWARD   +2.00    avanza con espacio libre
APPROACH_PENALTY   −0.30    se acerca demasiado a un obstáculo
NEAR_OBSTACLE_M     0.40    umbral de "demasiado cerca"
FREE_RAY_M          1.20    rayo que cuenta como libre
STUCK_SPEED         0.03    por debajo de esto, está trabado
STUCK_STEPS         45      pasos trabado antes de considerarlo atasco
```

Chocar **no** termina el episodio (`collision_terminates = False`). El robot
aprende a recuperarse en vez de aprender a evitar el episodio.

### 6.3 Trampas del entorno que ya costaron caro

Estas están resueltas. Si alguien las vuelve a tocar, se rompe.

| Trampa | Consecuencia | Estado |
|---|---|---|
| `p.rayTestBatch(..., parentObjectUniqueId=robot, parentLinkIndex=-1)` | En PyBullet 3.2.7 **anula el lote entero**: todas las lecturas vuelven `(-1, frac 1.0)`, que el entorno interpreta como "libre a 6 m". WALL-E ve el mundo vacío y se come la pared | **Sacar al robot del broadphase**: `setCollisionFilterGroupMask(robot, -1, 0, 0)` → barrido → restaurar a `(1, 0xFFFF)` en un `finally` |
| `parentLinkIndex=0` como alternativa | Excluye de verdad, pero depende de que el robot tenga al menos un link. Un robot sin links vuelve al fallo de arriba | No usar: el filtro de colisión no depende de la geometría |
| `LIDAR_THREADS > 0` | Access violation en procesos hijos | `LIDAR_THREADS = 0` |
| Plano de escaneo a altura fija sobre la base | `pos[2] + 0.06` = 0.21 m del piso: una caja de 12 cm, una rampa baja o el borde de un escalón pasan por debajo del sensor | `pos[2] - BASE_Z + SENSOR_FOOT_Z` (altura sobre el suelo local) |
| Distancia medida desde el centro del robot | Todos los umbrales (`NEAR_OBSTACLE_M`, `SAFE_GO_M`, `SAFE_SLOW_M`) quedaban 17,5 cm corridos y el robot frenaba lejos de todo | Restar `_body_radius(theta)` en cada rayo: 0 = tocando |
| `SubprocVecEnv` con 2+ hijos | `0xC0000005` en `reset()` | Usar `DummyVecEnv` |
| `rich` con stdout redirigido | Se bloquea | `progress_bar=False` |
| `torch.set_num_threads` alto en inferencia | 1,5 s por paso | 1 hilo en inferencia, núcleos−2 en entrenamiento |
| `COV_ENABLE_RGB_AXES` en PyBullet 3.2.7 | No existe, tira excepción | `getattr(p, "COV_ENABLE_RGB_AXES", None)` |
| Un proceso GUI colgado | Deja ventana huérfana y bloquea el siguiente arranque | El `.bat` limpia antes de lanzar |
| `PYTHONUTF8` sin definir | Un acento en un `print` mata el proceso | Siempre `PYTHONUTF8=1` |

### 6.4 Cómo se comprueba que el sensor no miente

`tools_diag_lidar.py` mide contra la geometría real, no contra lo que uno cree:

```
1. Distancia desde el paragolpes   caja a 2.00 / 1.20 / 0.80 / 0.50 / 0.47 m
                                   error < 1 mm en los cinco casos
2. Objetos bajos                   cajas de 8, 12, 20 y 40 cm de alto
                                   las cuatro se ven; antes solo la de 40
3. Reparto del abanico             36 rayos, 3.48° al frente, 8.4° al costado
4. El anillo sigue completo        (72,) y coincide con el centro del abanico
5. Observación                     (66,) y el espacio de Gymnasium igual
```

`test_v4_smoke.py` lo repite como aserción: si alguien vuelve a romper el barrido,
falla con el número exacto en vez de entrenar un robot ciego durante horas.

---

## 7. Estado actual

### Lo que funciona y está verificado

| Pieza | Estado | Cómo se verificó |
|---|---|---|
| `Cerebro Wall-E` completo | ✅ | `test_link.py --loopback`: 8 OK, 0 fallos |
| Consola de control | ✅ | 97 órdenes, 97 ACK, 0 reintentos, 0 timeouts |
| Cadena simulador → UDP → puente | ✅ | 0 errores, parada limpia al cerrar |
| Modo manual del simulador | ✅ | Avanzó 0,95 m de 1,00 · giró 43° de 45° |
| Modo PPO del simulador | ✅ carga y decide | `RecurrentPPO (LSTM)`, obs 66D, política cargada |
| Entrenamiento | ✅ | 1,2 M pasos, ~100 fps, `models\walle_ppo_model_v6.zip` |
| GUI | ✅ | 59 FPS estables, textura aplicada, sin ejes |

### Lo que está pendiente

| Pendiente | Por qué | Desbloquea |
|---|---|---|
| **Sensor de distancia real** | La política usa 36 rayos LiDAR que el robot físico no tiene | La autonomía real |
| Compilar los `.ino` | No hay `arduino-cli` en la máquina | La primera verificación la hace quien los cargue |
| Reconciliar el repo `IA` | Tiene contenido viejo de otra versión del proyecto | Que el push sea el proyecto real |
| Bajar a 38400 baudios si falla | `SoftwareSerial` + `Servo` a 57600 puede quedar justo | El enlace estable |

**Sobre el sensor:** es la decisión técnica más importante que queda. Solo un
LiDAR giratorio permite reusar la política sin reentrenar, porque da el mismo
abanico de rayos que el simulador. Un HC-SR04 da un solo haz y obliga a
reentrenar con otra observación. Va al ESP32 por un UART libre, como trama
nueva: `WALLE/1 L <n> <d0>…`.

---

## 8. Reglas de trabajo

1. **Una carpeta a la vez.** Si se trabaja en el simulador, se trabaja en el
   simulador. No se toca el cerebro "de paso".
2. **Cada avance se commitea y se pushea.** Sin que haya que pedirlo.
3. **Se verifica antes de decir que funciona.** Correr el comando, no asumir.
4. **El `.bat` es la interfaz.** Todo arranca con doble clic. Rutas relativas con
   `%~dp0`, nunca rutas absolutas clavadas.
5. **Los `.bat` son ASCII puro y sin BOM.** Un acento o un BOM rompe `cmd`.
6. **El hardware obedece, no decide.** Si aparece lógica en el ESP32 o en el UNO,
   está mal puesta.
7. **Documentar la trampa, no solo la solución.** La tabla de §6.3 existe para
   que nadie vuelva a perder una noche en lo mismo.
