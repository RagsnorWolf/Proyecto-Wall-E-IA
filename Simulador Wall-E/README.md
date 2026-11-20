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
  walle_env_v3.py             <- el entorno V5: observacion de 58 numeros
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
| **Modo: PPO** | El cerebro autónomo maneja. Carga `models\walle_ppo_model_v5_recovery.zip` |
| **Robot Real** | Manda las mismas órdenes por WiFi al ESP32. Ver `WALL-E Robot Real.bat` |

## Qué hay en `models\`

| Archivo | Pasos | Estado |
|---|---|---|
| `walle_ppo_model_v5_recovery.zip` | 1.3M heredados del V4 | El que usa el modo PPO |
| `walle_ppo_model_v4_lidar.zip` | 1 303 520 | La base del anterior. Navega bien |
| `walle_ppo_model_v3_explorer.zip` | — | Histórico, por si hay que comparar |

El V5 se generó con `transplant_v4_to_v5.py`: copia los pesos del V4 y ensancha
la entrada del LSTM de 50 a 58 con las columnas nuevas en cero. Así arranca
sabiendo navegar en vez de empezar girando en el sitio.

## Entrenar

Doble clic en `WALL-E Entrenar Cerebro.bat`. **Con el simulador cerrado**: el
lanzador del simulador mata todo `train_walle*` para liberar CPU.

```bash
.venv\Scripts\python.exe train_walle_v5.py --timesteps 300000 --workers 2 --vec dummy
```

Checkpoint cada 10 000 pasos en `models\checkpoints\`. A ~90 pasos por segundo,
300 000 son unos 55 minutos.

Para reanudar desde un checkpoint:

```bash
.venv\Scripts\python.exe train_walle_v5.py --timesteps 300000 --resume models\walle_ppo_model_v5_recovery.zip
```

## Detalles que costaron encontrar

- **`p.rayTestBatch` con `parentObjectUniqueId` anula el lote entero.** En esta
  build (PyBullet 3.2.7) todas las lecturas vuelven `(-1, fracción 1.0)`, que el
  entorno lee como "libre a 6 m": el robot ve el mundo vacío y se come la pared.
  `parentLinkIndex=0` sí excluye, pero depende de que el robot tenga links. Lo
  que se usa: sacar al robot del broadphase con
  `setCollisionFilterGroupMask(robot, -1, 0, 0)`, barrer y restaurar en un
  `finally`. Determinista y sin depender de la geometría.
- **El plano de escaneo va a 6 cm del SUELO, no de la base.** `pos[2] + 0.06`
  daba 0.21 m del piso y una caja de 12 cm era invisible para el sensor aunque
  el robot chocara con ella.
- **Las distancias se miden desde el paragolpes.** Se resta el semieje del
  chasis en la dirección del rayo. Si no, `0.00` significa "a 17 cm del centro"
  y todos los umbrales quedan corridos: el robot frena lejos de todo.
- **El abanico es denso al frente.** 24 rayos en ±40° (uno cada 3.48°) y 6 por
  lado hasta ±90°. Un reparto uniforme gastaba 5° por rayo y metía una caja
  centrada y una esquina en el mismo rayo.
- **`LIDAR_THREADS = 0`.** Con hilos, el pool de PyBullet revienta con access
  violation en procesos hijos.
- **`SubprocVecEnv` no sirve en este equipo.** Dos hijos o más mueren con
  `0xC0000005` en `reset()`. Se entrena con `DummyVecEnv`.
- **`torch.set_num_threads`.** Con pocos hilos el backward del LSTM tarda 27 s
  por iteración; con demasiados, la inferencia de una sola muestra se arrastra
  por sincronización. Entrenamiento: núcleos menos dos. Inferencia: un hilo.

## Si algo no anda

| Síntoma | Causa | Arreglo |
|---|---|---|
| «No se reconoce python» | Falta Python o el `.venv` | Correr `INSTALAR.bat` |
| Ventana en damero, sin robot | Ventana huérfana de una corrida anterior | Cerrar todo y relanzar el `.bat` |
| Modo PPO no carga | Falta el `.zip` en `models\` | Ver la tabla de arriba |
| Se mueve lentísimo | Hay un entrenamiento comiendo CPU | Cerrarlo antes de simular |
| Frena lejos de los obstáculos | Umbrales en metros desde el centro | Ya están convertidos a metros desde el paragolpes |
| «Ve todo libre» y choca | El lote de rayos volvió vacío | Correr `tools_diag_lidar.py`: si el mínimo es 6.00 m con una caja delante, el barrido está roto |
