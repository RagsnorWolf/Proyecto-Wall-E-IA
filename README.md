# Proyecto WALL-E

Un robot WALL-E físico controlado desde una PC. La inteligencia vive en la PC;
el hardware solo obedece.

Este repositorio contiene las tres carpetas del proyecto. Cada una se puede
descargar sola y funciona.

```
Cerebro Wall-E\          el robot físico: ESP32 + Arduino UNO + enlace + consola
Simulador Wall-E\        el gemelo virtual: PyBullet, GUI y entrenamiento PPO
Asistente IA Wall-E\     el agente conversacional: proyecto aparte
```

---

## La arquitectura

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
| **PC** | Cerebro | Percibe, decide, manda órdenes | No mueve motores |
| **ESP32** | Puente | Recibe por WiFi, traduce a serie, devuelve el ACK | No decide |
| **UNO** | Músculos | PWM de motores, ángulos de servo | No decide |

El ACK solo es válido si lo generó el UNO después de ejecutar. El ESP32 no
inventa respuestas.

---

## Cerebro Wall-E

Todo lo necesario para mover el robot real.

```
README.md
protocolo.md                    el contrato PC ↔ ESP32 ↔ UNO
PARA AGUS - puesta en marcha.md runbook de 8 pasos
Hablar con WALL-E.bat           consola interactiva
arduino_uno\walle_motors\       sketch del UNO
esp32\walle_bridge\             sketch del ESP32 + config.h
cerebro\walle_link.py           cliente UDP
cerebro\test_link.py            pruebas, con --loopback
cerebro\consola.py              control manual por teclado
cerebro\sim_link.py             adaptador para el simulador
```

Verificado con `test_link.py --loopback`: 8 OK, 0 fallos. Y con la consola
end-to-end: 97 órdenes, 97 ACK, 0 reintentos, 0 timeouts.

---

## Simulador Wall-E

El gemelo virtual. Sirve para ver el robot y para entrenar el cerebro.

```
INSTALAR.bat                  crea .venv e instala dependencias
WALL-E Simulador Robot.bat    abre la GUI
WALL-E Entrenar Cerebro.bat   entrena el PPO
WALL-E Robot Real.bat         manda las órdenes al ESP32
interactive_walle.py          GUI, chat y controlador
walle_env_v3.py               entorno V7, observación de 74 números
train_walle_v5.py             entrenamiento
transplant_v4_to_v5.py        trasplante de pesos V4 → V5
transplant_v6_to_v7.py        trasplante de pesos V6 -> V7 (620k pasos conservados)
models\                       las políticas entrenadas
material_0.png                textura del robot, 2048×2048
walle_visual.obj              la malla
```

**Los tres modos:** manual (chat en castellano), PPO (autónomo) y robot real
(por WiFi al ESP32).

La observación de 74 números son 14 base + 36 rayos del abanico + 24 de
contexto. El abanico se lanza en dos planos, bajo (6 cm) y alto (34 cm): un rayo
que toca abajo y no arriba es una caja que se trepa; uno que toca en los dos es
pared. Los primeros 66 son los del V6 y los primeros 58 los del V5, por eso el
trasplante de pesos funciona sin reentrenar de cero.

### Trampas del entorno que ya costaron caro

| Trampa | Consecuencia |
|---|---|
| `p.rayTestBatch` con argumentos por posición | Ignora `parentObjectUniqueId`; cada rayo pega contra el propio chasis y el robot frena en la nada. **Usar argumentos por nombre** |
| `LIDAR_THREADS > 0` | Access violation en procesos hijos |
| `SubprocVecEnv` con 2+ hijos | `0xC0000005` en `reset()` |
| `rich` con stdout redirigido | Se bloquea |
| `torch.set_num_threads` alto en inferencia | 1,5 s por paso |
| `COV_ENABLE_RGB_AXES` en PyBullet 3.2.7 | No existe |

---

## Asistente IA Wall-E

Proyecto aparte: un agente conversacional local, sin cuentas ni internet.

```
Iniciar WALL-E.bat     abre la cabina en el navegador
INSTALAR.bat           dependencias de Python
Modelo AI\             personalidad, memoria, voz, visión
Pagina Web\cockpit\    servidor e interfaz
```

Necesita [Ollama](https://ollama.com) y `ollama pull qwen2.5:3b`. Hoy está
pausado: primero el cerebro motor.

---

## Qué se versiona

El código y los modelos entrenados **sí**. Los artefactos regenerables **no**:

| Sí | No |
|---|---|
| `.py`, `.ino`, `.js`, `.jsx`, `.md`, `.bat` | `.venv\` (887 MB, no portable) |
| `models\*.zip` (políticas finales) | `models\checkpoints\` (historial) |
| Texturas y mallas (`.png`, `.obj`, `.glb`) | `__pycache__\`, `node_modules\` |
| El build servido (`cockpit\static\`) | `*.log`, `*.db`, `reports\` |

---

## Puesta en marcha

Cada carpeta tiene su `INSTALAR.bat` y su `README.md`. No hace falta leer nada
de las otras dos.

| Quiero… | Carpeta | Archivo |
|---|---|---|
| Mover el robot real | `Cerebro Wall-E` | `Hablar con WALL-E.bat` |
| Ver el robot en 3D | `Simulador Wall-E` | `WALL-E Simulador Robot.bat` |
| Entrenar el cerebro | `Simulador Wall-E` | `WALL-E Entrenar Cerebro.bat` |
| Conversar con WALL-E | `Asistente IA Wall-E` | `Iniciar WALL-E.bat` |

Cada una lleva además un `00-CONTEXTO.md` con el contexto completo del proyecto,
para que quien la abra entienda dónde está parado.

---

## Estado

| Pieza | Estado |
|---|---|
| Enlace PC ↔ ESP32 ↔ UNO | ✅ verificado con loopback |
| Consola de control | ✅ 97 órdenes, 0 fallos |
| Simulador, modo manual | ✅ 0,95 m de 1,00 · 43° de 45° |
| Simulador, modo PPO | OK carga y decide (obs 74D, 620k trasplantados) |
| Entrenamiento | AVISO reanuda y avanza, pero torch cae con access violation |
| GUI | ✅ 59 FPS, textura aplicada |
| Robot autónomo real | ⏳ falta el sensor de distancia |

**El bloqueo actual:** la política usa 36 rayos LiDAR que el robot físico no
tiene. Solo un LiDAR giratorio permite reusar el modelo sin reentrenar; un
HC-SR04 da un haz y obliga a reentrenar con otra observación.

---

## Licencia

Ver `LICENSE`.
