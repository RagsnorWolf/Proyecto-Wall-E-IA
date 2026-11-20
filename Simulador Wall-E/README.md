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
  walle_env_v3.py             <- el entorno V6: observacion de 66 numeros
  tools_diag_lidar.py         <- diagnostico del sensor contra la geometria real
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

La observación tiene **66 números**: 14 de posición y velocidad, 36 del abanico
LiDAR y 16 de contexto. Los últimos ocho son los sentidos que se añadieron para
que dejara de frenar en mitad de la nada:

```
 0-13   posicion, orientacion, velocidad, rumbo al objetivo
14-49   abanico de 36 rayos, denso al frente (uno cada 3.48 grados)
50-57   claridad frontal, obstaculo mas cercano, hueco libre, contacto
58-65   costado izq, costado der, ancho del hueco, despeje del hueco,
        despeje hacia el objetivo, despeje detras, velocidad real,
        fraccion del abanico libre
```

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
| `walle_ppo_model_v6.zip` | 1.2M | El que usa el modo PPO. Observación de 66 |
| `walle_ppo_model_v5_recovery.zip` | 1.3M heredados del V4 | Observación de 58: no carga con el entorno actual |
| `walle_ppo_model_v4_lidar.zip` | 1 303 520 | La base del anterior. Navega bien |
| `walle_ppo_model_v3_explorer.zip` | — | Histórico, por si hay que comparar |

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

**No lances otro proceso PyBullet mientras entrena.** Dos procesos a la vez
matan el entrenamiento con `0xC0000005` sin traceback: el log se corta limpio y
parece que terminó bien. Ni GUI, ni diagnósticos, ni pruebas.

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
