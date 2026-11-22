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
  train_walle_v5.py             el entrenamiento
  walle_look.py                 la paleta y los materiales: una sola fuente de color
  walle_piezas.py               parte la malla en 24 piezas de color solido
  tools_vista_previa.py         capturas headless a capturas\ para revisar el aspecto
  transplant_v4_to_v5.py        trasplante de pesos V4 → V5
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

### 6.2 El entorno del simulador (V5)

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

Los primeros 58 números son exactamente los del V5, y los 66 primeros los del V6,
en el mismo orden. Las columnas nuevas van siempre al final, así que nada de lo
que ya funcionaba se movió: cada versión se puede leer como un prefijo de la
siguiente. El precio es que un modelo entrenado con 66 columnas no carga en un
entorno de 74 — por eso `train_walle_v5.py` mira la forma del `.zip` antes de
reanudar y descarta los checkpoints de otra observación en vez de morir.

**Por qué hacían falta los ocho nuevos:** con la observación vieja la política
sabía *dónde* estaba el obstáculo más cercano y *hacia dónde* estaba el hueco,
pero no **cuánto medía el hueco** ni **qué había a los costados**. Un pasillo de
40 cm y una puerta de 2 m se veían igual: dos rayos libres. Ahora el ancho del
hueco en radianes, el despeje de cada costado y la fracción del abanico libre
distinguen "paso" de "no paso".

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

**Recompensas V6 (calibradas contra el avance):**

```
Avance libre          +4/s    (0.0036 m/paso × 20 × 60 pasos/s)
CONTACT_PENALTY      −0.25    por paso tocando algo
ESCAPE_BONUS         +3.00    por soltarse retrocediendo
CLEARANCE_REWARD     +2.00    por ganar distancia libre estando pegado
CLOSE_OBSTACLE_M      0.80    desde acá empieza a descontar
CLOSE_OBSTACLE_PENALTY −0.12  por paso pegado, escalado por cercanía
APPROACH_PENALTY     −0.05    por acercarse teniendo el frente libre
NEAR_OBSTACLE_M       0.40    umbral de "pegado"
FREE_RAY_M            1.20    rayo que cuenta como libre
STUCK_SPEED           0.03    por debajo de esto, está trabado
STUCK_STEPS           45      pasos trabado antes de considerarlo atasco
```

La relación importa más que los números sueltos. Antes el castigo por
proximidad era un escalón de **−1.0 por paso = −60/s**, contra **+4/s** por
avanzar: quince veces más caro acercarse que el premio por moverse. La política
aprendía exactamente una cosa — quedarse quieta lejos de todo — y eso es el
"frena en seco en mitad de la nada" que se reportó. Ahora la proximidad
descuenta de forma gradual y su techo (−7/s a 0.1 m) sigue siendo menor que
tocar (−15/s).

Chocar **no** termina el episodio (`collision_terminates = False`). El robot
aprende a recuperarse en vez de aprender a evitar el episodio.

### 6.3 Trampas del entorno que ya costaron caro

Estas están resueltas. Si alguien las vuelve a tocar, se rompe.

| Trampa | Consecuencia | Estado |
|---|---|---|
| `p.rayTestBatch(..., parentObjectUniqueId=robot, parentLinkIndex=-1)` | En PyBullet 3.2.7 **anula el lote entero**: todas las lecturas vuelven `(-1, frac 1.0)`, que el entorno interpreta como "libre a 6 m". WALL-E ve el mundo vacío y se come la pared | **Sacar al robot del broadphase**: `setCollisionFilterGroupMask(robot, -1, 0, 0)` → barrido → restaurar a `(1, 0xFFFF)` en un `finally` |
| `parentLinkIndex=0` como alternativa | Excluye de verdad, pero depende de que el robot tenga al menos un link. Un robot sin links vuelve al fallo de arriba | No usar: el filtro de colisión no depende de la geometría |
| `LIDAR_THREADS = 0` con más de un entorno en el proceso | `rayTestBatch` **no vuelve nunca**: el proceso se queda colgado sin error. Medido en aislado: con `nt=0` el primer barrido no retorna ni en 15 s; con `nt=1` tarda 2 ms | `LIDAR_THREADS = 1`. PyBullet toma el tamaño del pool del procesador de comandos y lo levanta en el primer barrido; dentro de un proceso con dos clientes eso se queda esperando para siempre. Si se vuelve a subir a 4, se cuelga igual |
| Llamadas `p.*` sin `physicsClientId` (198 en `walle_env*.py`) | El segundo entorno del proceso construye su mundo en el cliente 0, o sea **encima del primero**: `probe_clientes.py` lo midió con `cuerpos en A: 60 / en B: 0`, y el entrenamiento moría con `0xC0000005` a los pocos miles de pasos | `walle_pybullet.Cliente(client_id)`: cada entorno tiene su `self.p` y cada llamada lleva su `physicsClientId`. Las funciones puras se detectan por reintento ante `TypeError` (los builtins de PyBullet no exponen `__signature__`). `train_walle_v5.py` aborta si dos entornos comparten cliente |
| Plano de escaneo a altura fija sobre la base | `pos[2] + 0.06` = 0.21 m del piso: una caja de 12 cm, una rampa baja o el borde de un escalón pasan por debajo del sensor | `pos[2] - BASE_Z + SENSOR_FOOT_Z` (altura sobre el suelo local) |
| Distancia medida desde el centro del robot | Todos los umbrales (`NEAR_OBSTACLE_M`, `SAFE_GO_M`, `SAFE_SLOW_M`) quedaban 17,5 cm corridos y el robot frenaba lejos de todo | Restar `_body_radius(theta)` en cada rayo: 0 = tocando |
| `SubprocVecEnv` con 2+ hijos | El segundo hijo nunca arranca: `probe_subproc.py` imprime solo `[HIJO w0]` y se queda ahí para siempre | Usar `DummyVecEnv`. `train_walle_v5.py` rechaza `--vec subproc` con el motivo escrito |
| `psapi.GetProcessMemoryInfo` en Windows moderno | Devuelve 0 sin error: el banco de fatiga marcaba `RSS 0.0 MB` y su veredicto "estable" no medía nada | `kernel32.K32GetProcessMemoryInfo`, con `GetCurrentProcess.restype = c_void_p` y `argtypes`; sin ellos ctypes trunca el pseudo-handle |
| Dos procesos PyBullet en paralelo | El entrenamiento muere con `0xC0000005` sin traceback (el log se corta limpio). Pasó a los 6144 pasos con un `probe` corriendo al lado | Un solo proceso PyBullet a la vez: no lanzar diagnóstico ni GUI mientras entrena |
| `Monitor` ausente en el `env_fns` | SB3 nunca recibe `info["episode"]`: no hay `rollout/ep_rew_mean` y no se puede saber si mejora | `return Monitor(env)` en la factory |
| Checkpoint de otra observación al reanudar | `RecurrentPPO.load` levanta `ValueError` por la forma de la capa de entrada y el proceso muere a mitad de la corrida, perdiendo las horas ya invertidas | `_obs_dim_del_zip()` lee `observation_space.shape` del `data` del `.zip` **antes** de cargar. `auto_resume` filtra los incompatibles y `--resume` explícito cae a cero con un aviso. Al cambiar `OBS_EXTRAS` hay que subir el prefijo de `MODEL_NAME` y de `CheckpointCallback` para no mezclar versiones |
| `OBS_EXTRAS` cambiado sin tocar `extras_low` | El `Box` de observación se arma con `[1.0] * OBS_EXTRAS` para el máximo y una lista literal para el mínimo: si la lista no crece, el `__init__` aborta con `observation_space mal dimensionado`. Es a propósito — falla ruidoso antes de entrenar | Mantener `extras_low` con un valor por columna, en el mismo orden que `_problem_obs()` |
| Recompensa sin normalizar | Retorno ±200 contra una cabeza de valor que no lo sigue (`value_loss` entre 5 y 130, oscilando) | `VecNormalize(env, norm_obs=False, norm_reward=True, clip_reward=10.0)` |
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
5. Observación                     (74,) y el espacio de Gymnasium igual
```

`test_v4_smoke.py` lo repite como aserción: si alguien vuelve a romper el barrido,
falla con el número exacto en vez de entrenar un robot ciego durante horas.

**Lo que se ve en pantalla.** La GUI pinta dos capas de rayos y un panel de
sentidos, para no tener que abrir el código cuando el robot hace algo raro:

```
Anillo 72     azul acero, arco frontal completo   cobertura de 360°
Cono 36       ámbar, más grueso, encima            los que deciden
Panel         frente · izq · der · hueco · objetivo · vel · libre%
```

El panel se lee como una frase: *frente 0.42 m · izq 2.10 · der 2.08 m ·
hueco 148° a 3.40 m · objetivo +12°/1.90 m · vel +0.84 m/s · libre 61%*. Si el
robot frena sin motivo aparente, ese renglón dice por qué.

### 6.5 Cómo se mide si el cerebro aprendió

Entrenar no es aprender. `evaluar_v6.py` corre N episodios con **semillas
fijas** y saca una tabla que se compara entre versiones sin adivinar:

```
modelo                 dist. neta         camino  contactos  t. contacto ...
v6                          8.42±1.10      14.20±2.30      1.20±0.60       3.1% ...
```

| Métrica | Qué mide | Por qué importa |
|---|---|---|
| distancia neta | cuánto se alejó del punto de partida | es el objetivo del robot: explorar |
| camino | suma de desplazamientos | distingue explorar de dar vueltas |
| contactos | eventos de choque | una vez por evento, no por paso |
| t. contacto | % de pasos pegados a algo | si es alto, el robot empuja en vez de rodear |
| atascos | veces que se quedó sin moverse 0.75 s | el fallo más común en pasillos |
| chunks | celdas de 1 m descubiertas | cobertura real del terreno |
| vel. media | m/s sobre el eje del chasis | detecta el "avanza pero no avanza" |
| recompensa | retorno del episodio | comparable con el entrenamiento |

`--compare v6 v5 v4` usa las mismas semillas para todos: la diferencia es del
modelo, no del escenario. Sin esto, comparar dos `.zip` es mirar la recompensa
de entrenamiento, que miente cuando cambia el entorno.

---

## 7. Estado actual

### Lo que funciona y está verificado

| Pieza | Estado | Cómo se verificó |
|---|---|---|
| `Cerebro Wall-E` completo | ✅ | `test_link.py --loopback`: 8 OK, 0 fallos |
| Consola de control | ✅ | 97 órdenes, 97 ACK, 0 reintentos, 0 timeouts |
| Cadena simulador → UDP → puente | ✅ | 0 errores, parada limpia al cerrar |
| Modo manual del simulador | ✅ | Avanzó 0,95 m de 1,00 · giró 43° de 45° |
| Modo PPO del simulador | ⚠️ avisa y sigue en manual | Los tres `.zip` del repo son de 58 números y la observación actual es de 74: el cargador los prueba todos, ninguno encaja y lo dice |
| Entrenamiento | ✅ | 8192 pasos con 2 entornos (`Conexiones PyBullet: [0, 1]`) y 20 000 pasos de banco de fatiga con el RSS plano en 271 MB |
| GUI | ✅ | 59 FPS estables, textura aplicada, sin ejes |

### Lo que está pendiente

| Pendiente | Por qué | Desbloquea |
|---|---|---|
| **La corrida larga de 1,2 M** | El entorno ya soporta dos clientes y no fuga memoria; falta dejarla correr las horas que pide (~23 fps con LSTM en CPU) | Un `walle_ppo_model_v7.zip` real, y con él el modo PPO deja de caer a manual |
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
