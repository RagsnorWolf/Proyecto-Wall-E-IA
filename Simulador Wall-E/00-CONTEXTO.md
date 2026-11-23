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
  walle_env_v3.py               el entorno V7: observación de 74 números
  walle_pybullet.py             vista de PyBullet atada a una conexión concreta
  train_walle_v5.py             el entrenamiento
  walle_look.py                 la paleta y los materiales: una sola fuente de color
  walle_piezas.py               parte la malla en 24 piezas de color solido
  tools_vista_previa.py         capturas headless a capturas\ para revisar el aspecto
  transplant_v4_to_v5.py        trasplante de pesos V4 → V5
  transplant_v6_to_v7.py        trasplante de pesos V6 -> V7 (620k pasos conservados)
  tools_soak_entorno.py         banco de fatiga del entorno (RSS, pasos/s)
  probe_clientes.py             prueba de que cada entorno tiene su mundo
  models\                       las políticas entrenadas (.zip)
  material_0.png                textura real del robot, 2048×2048
  walle_visual.obj              la malla del robot
  walle_color_parts\            las 24 piezas de color (fallback sin textura)
  capturas\                     PNGs de verificacion del aspecto
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

### 6.2 El entorno del simulador (V7)

```
Observación: 74 números
  ├── 14  base (posición, orientación, velocidad, contacto)  ← V2 original
  ├── 36  abanico LiDAR frontal de 36 rayos                  ← V4
  ├──  8  resolución de atascos                              ← V5
  ├──  8  contexto del entorno                               ← V6
  │       ├── despeje del costado izquierdo
  │       ├── despeje del costado derecho
  │       ├── ancho del hueco más ancho (radianes/π)
  │       ├── despeje en el centro de ese hueco
  │       ├── despeje en el rumbo al objetivo (±20°)
  │       ├── despeje detrás del robot
  │       ├── velocidad real sobre el eje del chasis
  │       └── fracción del abanico que está despejada
  └──  8  comprensión del entorno                            ← V7
          ├── derrape: velocidad lateral sobre el eje del chasis
          ├── tiempo hasta el impacto, normalizado a 2 s
          ├── despeje del plano alto al frente
          ├── despeje del plano alto a la izquierda
          ├── despeje del plano alto a la derecha
          ├── fracción del frente con obstáculo trepable
          ├── fracción del frente con obstáculo que bloquea
          └── costado más libre (−1 izquierda, +1 derecha)
Acción: 2 continuas (oruga izquierda, oruga derecha)
```

Cada versión es un prefijo de la siguiente: los 50 del V4 siguen siendo los
primeros 50, los 58 del V5 los primeros 58 y los 66 del V6 los primeros 66. Las
columnas nuevas van siempre al final, así que el trasplante de pesos sigue
funcionando y nada de lo que ya funcionaba se movió. El precio es que un modelo
de 66 columnas no carga en un entorno de 74: `train_walle_v5.py` mira la forma
del `.zip` antes de reanudar y descarta los checkpoints de otra observación en
vez de morir con un `ValueError` a mitad de la corrida.

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

**Los dos planos de escaneo (V7):**

```
Plano bajo     SENSOR_FOOT_Z   = 0.06 m   → qué hay delante
Plano alto     HEADROOM_FOOT_Z = 0.34 m   → qué llega a la altura del chasis

                  plano bajo    plano alto    lectura
libre                  no            no       nada
caja baja              sí            no       se trepa o se pasa por encima
pared                  sí            sí       no se pasa
voladizo               no            sí       se pasa por debajo
```

Con un solo plano una pared de 2 m y una caja de 12 cm se leían igual: las dos
eran "obstáculo a 1.4 m". La política no tenía con qué decidir entre rodear y
trepar, así que trataba todo como pared.

El plano alto **no** se lanza entero. Se lanza solo en las direcciones donde el
plano bajo chocó algo: sin impacto abajo no hay nada que comparar, porque o no
hay obstáculo o hay un voladizo que el robot pasa por debajo de todos modos. En
una arena despejada el segundo barrido no se hace. Medido: lanzar los 36 rayos
altos siempre costaba 1.3 ms por paso (3.35 ms de barrido) y la GUI perdía el
presupuesto de 16.6 ms por tick, cayendo de 58 a 25-56 FPS; bajo demanda el
barrido baja a 2.19 ms y la GUI vuelve a 49-56 FPS sostenidos.

Por rayo del abanico salen tres banderas que no van a la observación pero que la
GUI usa para pintar el cono:

```
fan_low_hit     el rayo bajo tocó algo
fan_high_hit    el rayo alto tocó algo
fan_climbable   tocó abajo y no arriba   → obstáculo bajo
fan_blocking    tocó en los dos planos   → pared
```

**Los 8 valores V7 (columnas 66-73):**

```
66  derrape           velocidad lateral sobre el eje del chasis, −1 a +1
67  tiempo_impacto    segundos hasta tocar / 2 s; 1.0 = sin riesgo
68  techo_frente      despeje del plano alto en el cono de decisión
69  techo_izq         despeje del plano alto de +40° a +90°
70  techo_der         despeje del plano alto de −90° a −40°
71  ratio_trepable    fracción del frente con obstáculo bajo
72  ratio_bloqueante  fracción del frente con obstáculo que bloquea
73  costado_libre     −1 = conviene ir a la izquierda, +1 a la derecha
```

`tiempo_impacto` es el que cambia el comportamiento de frenado: con la distancia
sola, a 0.4 m y a 2 m/s el robot tiene 0.2 s y no hay nada que hacer; a 0.4 m y
0.2 m/s tiene 2 s y sobra. El número que importa es el cociente, no la distancia,
y ahora está en la observación. `costado_libre` es la resta de los dos despejes
laterales normalizada: una columna en vez de dos, con el signo ya resuelto.

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
| `LIDAR_THREADS = 0` con más de un entorno en el proceso | `rayTestBatch` **no vuelve nunca**: el proceso se queda colgado sin error. Medido en aislado: con `nt=0` el primer barrido no retorna ni en 15 s; con `nt=1` tarda 2 ms | `LIDAR_THREADS = 1`. PyBullet comparte un pool global de hilos de rayos entre clientes; con 0 no lo levanta y el barrido espera para siempre |
| Llamadas `p.*` sin `physicsClientId` (198 en `walle_env*.py`) | El segundo entorno del proceso construye su mundo en el cliente 0, o sea **encima del primero**: `probe_clientes.py` lo midió con `cuerpos en A: 60 / en B: 0`, y el entrenamiento moría con `0xC0000005` a los pocos miles de pasos | `walle_pybullet.Cliente(client_id)`: cada entorno tiene su `self.p` y cada llamada lleva su `physicsClientId`. Las funciones puras se detectan por reintento ante `TypeError` (los builtins de PyBullet no exponen `__signature__`). `train_walle_v5.py` aborta si dos entornos comparten cliente |
| Plano de escaneo a altura fija sobre la base | `pos[2] + 0.06` = 0.21 m del piso: una caja de 12 cm, una rampa baja o el borde de un escalón pasan por debajo del sensor | `pos[2] - BASE_Z + SENSOR_FOOT_Z` (altura sobre el suelo local) |
| Distancia medida desde el centro del robot | Todos los umbrales (`NEAR_OBSTACLE_M`, `SAFE_GO_M`, `SAFE_SLOW_M`) quedaban 17,5 cm corridos y el robot frenaba lejos de todo | Restar `_body_radius(theta)` en cada rayo: 0 = tocando |
| `SubprocVecEnv` con 2+ hijos | `0xC0000005` en `reset()`; y en esta build el **segundo hijo ni siquiera levanta** (se cuelga en el `connect`, probado con `probe_subproc.py`) | Usar `DummyVecEnv`; `train_walle_v5.py` rechaza `--vec subproc` con el motivo escrito |
| `psapi.GetProcessMemoryInfo` en Windows moderno | Devuelve 0 sin error: el banco de fatiga marcaba `RSS 0.0 MB` y su veredicto "estable" no medía nada | `kernel32.K32GetProcessMemoryInfo`, con `GetCurrentProcess.restype = c_void_p` y `argtypes`; sin ellos ctypes trunca el pseudo-handle |
| `rich` con stdout redirigido | Se bloquea | `progress_bar=False` |
| `torch.set_num_threads` alto en inferencia | 1,5 s por paso | 1 hilo en inferencia, núcleos−2 en entrenamiento |
| El LSTM de esta build de torch con rollout largo | `0xC0000005` dentro de `torch.nn.modules.rnn.forward` y en el `backward` de `ppo_recurrent.py`, sin traceback de Python. Medido: cae con 6 hilos y con 2, con 4 entornos y con 2. Una iteración de 2048 pasos sí completa (55-80 s); la segunda ya no. Con `mkldnn` apagado no crashea pero se cuelga | No pelear: el cerebro que va al robot es el reactivo. El PPO queda para cuando se cambie de máquina o de build de torch |
| `COV_ENABLE_RGB_AXES` en PyBullet 3.2.7 | No existe, tira excepción | `getattr(p, "COV_ENABLE_RGB_AXES", None)` |
| Un proceso GUI colgado | Deja ventana huérfana y bloquea el siguiente arranque | El `.bat` limpia antes de lanzar |
| `PYTHONUTF8` sin definir | Un acento en un `print` mata el proceso | Siempre `PYTHONUTF8=1` |
| Un `0xC0000005` sin `faulthandler` | El log se corta limpio y parece que terminó bien: no hay traceback porque el fallo es de C, no de Python | `faulthandler.enable()` al principio de `train_walle_v5.py`; imprime la pila del hilo que murió |
| Checkpoint de otra observación al reanudar | `RecurrentPPO.load` levanta `ValueError` por la forma de la capa de entrada y el proceso muere a mitad de la corrida, perdiendo las horas ya invertidas | `_obs_dim_del_zip()` lee `observation_space.shape` del `data` del `.zip` **antes** de cargar. `auto_resume` filtra los incompatibles y `--resume` explícito cae a cero con un aviso. Al cambiar `OBS_EXTRAS` hay que subir el prefijo de `MODEL_NAME` y de `CheckpointCallback` para no mezclar versiones |
| `OBS_EXTRAS` cambiado sin tocar `extras_low` | El `Box` de observación se arma con `[1.0] * OBS_EXTRAS` para el máximo y una lista literal para el mínimo: si la lista no crece, el `__init__` aborta con `observation_space mal dimensionado`. Es a propósito — falla ruidoso antes de entrenar | Mantener `extras_low` con un valor por columna, en el mismo orden que `_problem_obs()` |

### 6.4 Cómo se comprueba que el sensor no miente

`tools_diag_lidar.py` mide contra la geometría real, no contra lo que uno cree:

```
1. Distancia desde el paragolpes   caja a 2.00 / 1.20 / 0.80 / 0.50 / 0.47 m
                                   error < 1 mm en los cinco casos
2. Objetos bajos                   cajas de 8, 12, 20 y 40 cm de alto
                                   las cuatro se ven; antes solo la de 40
3. Reparto del abanico             36 rayos, 3.48° al frente, 8.4° al costado
4. El anillo sigue completo        (72,) y coincide con el centro del abanico
5. Observación                     (74,) y el espacio de Gymnasium igual
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
| Modo PPO del simulador | ✅ carga y decide | `walle_ppo_model_v7.zip`: 620 000 pasos trasplantados del V6 a la observación de 74, recargado desde el `.zip` y el `.pkl` como lo hace `train_walle_v5`; 111 de 120 pasos avanza |
| Entrenamiento | ⚠️ arranca y avanza, pero torch lo tumba | Reanuda desde 620 000 y completa una iteración de 2048 pasos en 55-80 s; en la siguiente muere con `0xC0000005` en el LSTM. Ver la trampa en 6.3 |
| GUI | ✅ | 59 FPS estables, textura aplicada, sin ejes |

### Lo que está pendiente

| Pendiente | Por qué | Desbloquea |
|---|---|---|
| **Terminar los 580 000 pasos que faltan** | El entorno y el trasplante ya están: lo que falta es que torch aguante. Cae con `access violation` en el LSTM cuando el rollout se alarga | Un v7 entrenado de verdad, no solo trasplantado |
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
