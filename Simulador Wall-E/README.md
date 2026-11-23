# Simulador Wall-E

El gemelo virtual del robot: física con PyBullet, la cabina 3D con chat, y el
cerebro PPO que aprende a moverse.

```
Simulador Wall-E\
  INSTALAR.bat                <- una sola vez: crea .venv e instala todo
  WALL-E Simulador Robot.bat  <- doble clic para abrir el simulador
  WALL-E Entrenar Cerebro.bat <- entrenar el cerebro PPO
  WALL-E Robot Real.bat       <- manejar el robot fisico desde el simulador
  interactive_walle.py        <- la GUI y el controlador
  walle_env_v3.py             <- el entorno V7: observacion de 74 numeros
  walle_pybullet.py           <- ata cada entorno a su propio cliente PyBullet
  tools_diag_lidar.py         <- diagnostico del sensor contra la geometria real
  tools_soak_entorno.py       <- banco de fatiga: pasos, memoria, cuerpos vivos
  evaluar_v6.py               <- banco de pruebas: mide si el modelo aprendio
  test_v4_smoke.py            <- prueba rapida de que el entorno no miente
  models\                     <- las politicas entrenadas (.zip)
  material_0.png              <- textura real del modelo, 2048x2048
  walle_visual.obj            <- malla del robot
```

## Puesta en marcha

**1. Python.** Si no está, `winget install Python.Python.3.12`.

**2. Instalar.** Doble clic en `INSTALAR.bat`. Crea `.venv` e instala PyBullet,
PyTorch, Stable-Baselines3 y sb3-contrib. Tarda unos minutos.

**3. Abrir.** Doble clic en `WALL-E Simulador Robot.bat`.

Si PyBullet no arranca, casi siempre falta el Visual C++ Redistributable:
https://aka.ms/vs/17/release/vc_redist.x64.exe

## Los tres modos

| Botón | Qué hace |
|---|---|
| **Modo: Manual** | Le escribís en castellano: «avanza 2 metros», «gira 90 grados» |
| **Modo: PPO** | El cerebro autónomo maneja. Carga el modelo que encaje con la observación |
| **Robot Real** | Manda las mismas órdenes por WiFi al ESP32. Ver `WALL-E Robot Real.bat` |

## Qué ve el robot

La observación tiene **74 números**: 14 de posición y velocidad, 36 del abanico
LiDAR y 24 de contexto. Los últimos dieciséis son los sentidos que se añadieron
para que dejara de frenar en mitad de la nada y para que entienda qué tiene
delante, no solo a qué distancia:

```
 0-13   posicion, orientacion, velocidad, rumbo al objetivo
14-49   abanico de 36 rayos, denso al frente (uno cada 3.48 grados)
50-57   claridad frontal, obstaculo mas cercano, hueco libre, contacto
58-65   costado izq, costado der, ancho del hueco, despeje del hueco,
        despeje hacia el objetivo, despeje detras, velocidad real,
        fraccion del abanico libre
66-73   derrape lateral, tiempo hasta el impacto, despeje del plano alto
        (frente/izq/der), fraccion del frente trepable, fraccion del
        frente que bloquea, costado mas libre
```

**Los dos planos de escaneo.** El abanico de 36 se lanza dos veces: a 6 cm del
suelo y a 34 cm, la altura del chasis. Un rayo que toca abajo y no arriba es un
obstáculo bajo — una caja de 12 cm, un escalón — y se puede trepar. Un rayo que
toca en los dos planos es una pared y no se pasa. Con un solo plano las dos
cosas se leían igual y la política no tenía con qué decidir.

Todo lo que el robot siente se puede leer en la ventana, debajo del título:

```
Sentidos · frente 0.42 m · izq 2.10 · der 2.08 m · hueco 148° a 3.40 m ·
objetivo +12°/1.90 m · vel +0.84 m/s · libre 61%
```

Si frena sin motivo aparente, ese renglón dice por qué. En la escena, el anillo
de 72 rayos se pinta azul y el abanico de 36 que decide se pinta ámbar encima.

## Qué hay en `models\`

| Archivo | Pasos | Estado |
|---|---|---|
| `walle_ppo_model_v7.zip` | 620 000 | **El que usa la GUI.** Trasplantado del V6 a la observación de 74: las 8 columnas nuevas entran en cero y la política se comporta como el V6 |
| `walle_ppo_model_v5_recovery.zip` | 1.3M heredados del V4 | Observación de 58: no carga con el entorno actual |
| `walle_ppo_model_v4_lidar.zip` | 1 303 520 | La base del anterior. Navega bien |
| `walle_ppo_model_v3_explorer.zip` | - | Histórico, por si hay que comparar |

El v7 no se entrenó desde cero: `transplant_v6_to_v7.py` copia los 19
tensores que encajan del `walle_v6_620000_steps.zip` y ensancha las dos
entradas del LSTM de `(1024, 66)` a `(1024, 74)`. Se pierde el
entrenamiento de las 8 columnas nuevas, no las horas anteriores. Viene
con su `_vecnormalize.pkl` al lado, o el crítico recibe un salto de
escala.

El cargador no tiene dimensiones escritas a mano: prueba los modelos de
`models\` y de `models\checkpoints\`, y se queda con el primero cuya
observación coincida con la del entorno. Si ninguno encaja, lo dice y sigue en
modo manual.

## Entrenar

Doble clic en `WALL-E Entrenar Cerebro.bat`. **Con el simulador cerrado**: el
lanzador del simulador mata todo `train_walle*` para liberar CPU.

```bash
.venv\Scripts\python.exe train_walle_v5.py --timesteps 1200000 --workers 2 --vec dummy
```

Checkpoint cada 10 000 pasos en `models\checkpoints\`. A ~100 pasos por segundo,
1.2M son unas 3 horas y media.

`--timesteps` es el **total** del modelo, no "pasos que faltan". Si el `.zip`
más reciente ya tiene 400 000, el mismo comando entrena los 800 000 que quedan.
Así el guardián puede relanzar con el mismo número cada vez sin inflar el
presupuesto. `--auto_resume` elige el checkpoint más nuevo, y si no hay ninguno
empieza de cero.

**No lances otro proceso PyBullet mientras entrena.** Dos procesos a la vez
matan el entrenamiento con `0xC0000005` sin traceback: el log se corta limpio y
parece que terminó bien. Ni GUI, ni diagnósticos, ni pruebas.

### Si se corta

El entrenamiento son horas. Un reinicio, un cierre de sesión o abrir el
simulador lo matan, y no avisa. Para eso está `continuar_entrenamiento.ps1` y la
tarea programada **`WALL-E Entrenamiento`**, que lo llama cada 10 minutos:

```powershell
Get-ScheduledTask -TaskName "WALL-E Entrenamiento" | Select-Object TaskName,State
Start-ScheduledTask  -TaskName "WALL-E Entrenamiento"   # relanzar ya
Disable-ScheduledTask -TaskName "WALL-E Entrenamiento"  # parar de relanzar
```

El guardián solo hace algo si se cumplen tres cosas: no existe
`models\ENTRENAMIENTO_COMPLETO.txt`, no hay ya un `train_walle*` corriendo y hay
un checkpoint que reanudar (o no hay modelo final todavía). Si el entrenamiento
terminó de verdad, no toca nada; para volver a entrenar hay que borrar la marca.

Hay una cuarta: si hay un `train_walle*` vivo pero el log lleva **30 minutos sin
escribir**, se considera colgado y lo reanuda igual. Un cuelgue del barrido de
rayos deja el proceso ahí, sin CPU y sin errores, y sin esta comprobación el
guardián lo daría por bueno durante horas.

Los checkpoints se guardan con sus estadísticas de `VecNormalize`
(`walle_v7_NNNNNN_steps_vecnormalize.pkl`). Si el `.pkl` no está —los anteriores
a esta versión no lo tienen— el log avisa y el crítico arranca con la escala
cruda: se ve en `ep_rew_mean` dando un salto los primeros miles de pasos.

## Dos entornos en el mismo proceso

El entrenamiento usa `--workers 2`: dos WALL-E dentro del mismo proceso. Eso
tiene dos trampas propias, y las dos ya están resueltas en el código. Si alguna
vuelve, el síntoma es raro y no dice el motivo.

| Trampa | Síntoma | Arreglo |
|---|---|---|
| Llamar `p.*` sin `physicsClientId` | El segundo robot construye su mundo **encima del primero**. El log se corta limpio con `0xC0000005` a los miles de pasos | Todo el entorno pasa por `walle_pybullet.Cliente`, que ata cada llamada a su cliente |
| `LIDAR_THREADS = 0` | El primer barrido de rayos no vuelve nunca. El proceso queda colgado, sin error | `LIDAR_THREADS = 1` |

Para comprobar que los dos mundos están de verdad separados:

```bash
.venv\Scripts\python.exe probe_clientes.py    # pone una pared solo en A y mide desde B
.venv\Scripts\python.exe probe_subproc.py     # muestra por qué no se usa SubprocVecEnv
```

`probe_clientes.py` clava una pared en el entorno A a 0.58 m y mide el LiDAR del
entorno B: si B la ve a 2.09 m, cada uno tiene su mundo. Si compartieran cliente,
B vería la pared encima.

Para medir si el proceso aguanta pasos sin fugas (RSS, cuerpos vivos,
pasos/s) está el banco de fatiga:

```bash
.venv\Scripts\python.exe tools_soak_entorno.py --envs 2 --steps 20000
```

Imprime una línea cada 1000 pasos y termina con la pendiente de memoria. Si el
RSS sube de forma sostenida, hay fuga; si se aplana, el problema está arriba,
en PPO. Medido con 2 entornos y 20 000 pasos: 129 pasos/s, 16 episodios, 30
cuerpos vivos y RSS clavado en 271 MB de punta a punta (pendiente −0,003 MB por
1000 pasos).

## Comprobar que el sensor no miente

```bash
.venv\Scripts\python.exe tools_diag_lidar.py     # mide contra la geometria real
.venv\Scripts\python.exe test_v4_smoke.py        # aserciones del entorno
```

El diagnóstico imprime cinco secciones: distancia desde el paragolpes (error
< 1 mm), objetos de 8 a 40 cm, reparto del abanico, el anillo completo y la
forma de la observación. Si algo vuelve a romperse, falla con el número exacto
en vez de entrenar un robot ciego durante horas.

## Medir si el cerebro aprendió

Entrenar no es aprender. `evaluar_v6.py` corre varios episodios con semillas
fijas y saca una tabla comparable entre versiones:

```bash
.venv\Scripts\python.exe evaluar_v6.py --episodes 10 --obstacles 8
.venv\Scripts\python.exe evaluar_v6.py --compare v6 v5 v4
```

```
modelo                 dist. neta         camino  contactos  t. contacto ...
v6                          8.42±1.10      14.20±2.30      1.20±0.60       3.1% ...
```

| Columna | Qué dice |
|---|---|
| distancia neta | cuánto se alejó del punto de partida |
| camino | suma de desplazamientos, aunque vuelva sobre sus pasos |
| contactos | eventos de choque, no pasos |
| t. contacto | % de pasos pegados a algo |
| atascos | veces que se quedó sin moverse 0.75 s |
| chunks | celdas de 1 m descubiertas |
| vel. media | m/s reales sobre el eje del chasis |
| recompensa | retorno del episodio, comparable con el entrenamiento |

Con `--compare` usa **las mismas semillas** para todos los modelos: la
diferencia que se ve es del modelo, no del escenario.
