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

- **`p.rayTestBatch` exige argumentos por nombre.** Por posición ignora
  `parentObjectUniqueId` y cada rayo impacta el propio chasis a fracción 0:
  medio anillo de ceros y el robot frenando en la nada.
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
| Frena lejos de los obstáculos | LiDAR mal configurado | Ver `rayTestBatch` arriba |
