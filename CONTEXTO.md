# WALL-E — Contexto del proyecto

> Este archivo vive en el escritorio a propósito: es lo primero que hay que leer
> antes de tocar cualquier cosa. Explica qué se pidió, cómo está organizado, qué
> se hizo ya y cómo se publica cada cambio.

Última actualización: 20 de noviembre de 2026.

---

## 1. Qué es el proyecto

Un robot WALL-E físico, controlado desde una PC. El objetivo final es que se
mueva solo: que perciba, decida y actúe sin que nadie le diga qué hacer.

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
| **PC** | Cerebro | Percibe, decide, manda órdenes | No mueve motores |
| **ESP32** | Puente | Recibe por WiFi, traduce a serie, devuelve el ACK | No decide nada |
| **UNO** | Músculos | PWM de motores, ángulos de servo, encoders | No decide nada |

El ACK solo es válido si lo generó el UNO después de ejecutar. El ESP32 no
inventa respuestas.

---

## 2. Lo que se pidió

Los requisitos, tal cual, para que no se pierdan:

1. **Tres carpetas en el escritorio**, cada una con su rol, para poder trabajar
   desde otros dispositivos y con otras IAs sin perder el contexto.
2. **`Cerebro Wall-E`** contiene todo lo necesario para mover el robot físico real.
3. **`Simulador Wall-E`** sirve para ver el robot virtual **y** para entrenar el
   cerebro.
4. **El simulador produce, el cerebro consume:** cada mejora del cerebro
   entrenado se guarda y se actualiza también en `Cerebro Wall-E`.
5. **`Asistente IA Wall-E`** es un proyecto aparte — un agente estilo ChatGPT,
   Claude, Grok. Se desarrolla más adelante.
6. **Cada actualización se commitea y se pushea** al repositorio, automáticamente.
7. **Se trabaja dentro de la carpeta que corresponde.** Si es el simulador, en el
   simulador. Si es el cerebro, en el cerebro. Si es el agente, en el agente.
8. **Un `.md` con todo este contexto**, como si fuera una skill.

---

## 3. Las tres carpetas

```
Escritorio\
  Proyecto Wall-E\          ← el clon del repo, y el árbol de trabajo
    Cerebro Wall-E\         el robot físico: hardware + enlace + consola
    Simulador Wall-E\       el gemelo virtual: física, GUI, entrenamiento
    Asistente IA Wall-E\    el agente conversacional: proyecto aparte
```

**No hay dos carpetas.** El escritorio tiene una sola carpeta real,
`Proyecto Wall-E`, y adentro las tres. Los accesos directos (`WALL-E Simulador
Robot`, `WALL-E Asistente IA`, `WALL-E Cerebro Robot`) son atajos, no carpetas.

### 3.1 `Cerebro Wall-E`

Todo lo necesario para mover el robot real. **No** entra el modelo de IA, ni
PyBullet, ni el simulador.

```
README.md
00-CONTEXTO.md                  el contexto maestro, para otra IA
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

### 3.2 `Simulador Wall-E`

El gemelo virtual. Dos usos: ver el robot en 3D y manejarlo a mano, y entrenar
el cerebro PPO.

```
INSTALAR.bat                  crea .venv e instala dependencias
WALL-E Simulador Robot.bat    abre la GUI
WALL-E Entrenar Cerebro.bat   entrena el PPO
WALL-E Robot Real.bat         manda las órdenes al ESP32 por WiFi
interactive_walle.py          GUI, chat y controlador
walle_env_v3.py               entorno V6, observación de 66 números
train_walle_v5.py             entrenamiento
transplant_v4_to_v5.py        trasplante de pesos V4 → V5
models\                       las políticas entrenadas
material_0.png                textura del robot, 2048×2048
walle_visual.obj              la malla
```

### 3.3 `Asistente IA Wall-E`

Proyecto aparte. Hoy **pausado**: primero el cerebro motor.

```
Iniciar WALL-E.bat            abre la cabina en el navegador
INSTALAR.bat                  dependencias de Python
Modelo AI\                    personalidad, memoria, voz, visión
Pagina Web\cockpit\           servidor e interfaz web
```

---

## 4. En qué carpeta se trabaja

La regla de oro. No se mezcla.

| Si la tarea es… | Se trabaja en… | Se toca… |
|---|---|---|
| Mover el robot real, protocolo, sketches, consola | `Cerebro Wall-E` | `cerebro\`, `esp32\`, `arduino_uno\` |
| Entrenar, física, GUI, recompensa | `Simulador Wall-E` | `interactive_walle.py`, `walle_env_v3.py`, `train_walle_v5.py` |
| Conversación, voz, memoria, cabina web | `Asistente IA Wall-E` | `Modelo AI\`, `Pagina Web\cockpit\` |
| Publicar | repositorio | ver §5 |

Y el flujo entre las dos primeras:

```
Simulador Wall-E\models\walle_ppo_model_v5_recovery.zip
        │  se entrena y mejora acá
        ▼
Cerebro Wall-E\  (cuando el robot tenga sensor)
        │  se ejecuta contra los sensores reales
        ▼
   robot físico
```

---

## 5. El repositorio

```
https://github.com/RagsnorWolf/Proyecto-Wall-E-IA
```

**Regla permanente:** cada avance real se commitea y se pushea. Sin que haya que
pedirlo.

### Cómo está conectado

El clon del repo **es** la carpeta de trabajo. No hay copias.

```
Escritorio\Proyecto Wall-E\   ← esto es el clon, y es donde se trabaja
```

Trabajar, commitear y pushear pasan sobre el mismo árbol. Cero
desincronización.

### Ramas

| Rama | Contenido |
|---|---|
| `main` | el proyecto real, las tres carpetas actuales |
| `legacy` | la versión vieja del repo, guardada por si hace falta |

### Qué se versiona

| Sí | No |
|---|---|
| Código (`.py`, `.ino`, `.js`, `.jsx`) | `.venv\` (887 MB, no portable) |
| Lanzadores (`.bat`) | `models\checkpoints\` (historial) |
| Documentación (`.md`) | `__pycache__\`, `node_modules\` |
| Políticas finales (`models\*.zip`) | `*.log`, `*.db`, `reports\` |
| Texturas y mallas (`.png`, `.obj`, `.glb`) | `config.json` con datos personales |

Un modelo entrenado **sí** se versiona: es el producto del proyecto. Un
checkpoint intermedio no: es basura regenerable.

### El mensaje de commit

```
tipo(carpeta): qué cambió

feat(simulador): recompensa de holgura en el entorno V6
fix(cerebro): timeout del ACK del UNO
docs(agente): puesta en marcha con Ollama
```

---

## 6. Qué se hizo ya

### Organización y repositorio

| Hecho | Detalle |
|---|---|
| Las tres carpetas, pobladas | Cerebro 12 archivos · Simulador 69 · Agente 126 |
| Clon del repo en el escritorio | `Proyecto Wall-E\`, es el árbol de trabajo |
| Contenido viejo del repo salvado | rama `legacy` (simulador Pygame, PPO propio) |
| `.gitignore` reescrito | se versiona código y modelos, no artefactos |
| CI reescrito y verde | 15 de 15 jobs, Windows y Linux |
| `tools\verificar.py` | chequeos portables: `.bat`, `OBS_DIM`, contexto, agente |
| Accesos directos repuntados | los tres apuntan a la carpeta nueva |
| Este archivo y `PROYECTO.md` | contexto maestro en el repo y en cada carpeta |

### Cerebro

| Hecho | Verificación |
|---|---|
| Enlace completo ESP32 + UNO + consola | `test_link.py --loopback`: 8 OK, 0 fallos |
| Consola end-to-end | 97 órdenes, 97 ACK, 0 reintentos, 0 timeouts |
| Protocolo ida y vuelta con ACK real | el ACK lo genera el UNO, no el ESP32 |
| Runbook para Agus | 8 pasos, sin programar nada |

### Simulador

| Hecho | Verificación |
|---|---|
| Modo manual | avanzó 0,95 m de 1,00 · giró 43° de 45° |
| Modo PPO | carga `RecurrentPPO (LSTM)`, obs 66D, decide y mueve |
| Entrenamiento | 1,2 M pasos, ~100 fps, modelo en `models\walle_ppo_model_v6.zip` |
| GUI | 59 FPS, textura aplicada, sin ejes ni panel gris |
| Trasplante V4 → V5 | 0,000000 de diferencia en 60 pasos |
| Sensor LiDAR | error < 1 mm desde el paragolpes en 5 posiciones |
| Objetos bajos | cajas de 8, 12, 20 y 40 cm, las cuatro visibles |
| Sentidos nuevos | 8 columnas: costados, hueco, objetivo, detrás, velocidad |

### Bugs reales encontrados y corregidos

| Bug | Consecuencia | Estado |
|---|---|---|
| `p.rayTestBatch` con `parentObjectUniqueId` | Anula el lote entero en PyBullet 3.2.7: todo vuelve "libre a 6 m" y el robot se come la pared | Corregido: el robot se saca del broadphase durante el barrido |
| Plano de escaneo a 0,21 m del piso | Una caja de 12 cm pasaba por debajo del sensor aunque el robot chocara con ella | Corregido: escanea a 6 cm sobre el suelo local |
| Distancias medidas desde el centro | Todos los umbrales quedaban 17,5 cm corridos y el robot frenaba lejos de todo | Corregido: se mide desde el paragolpes, 0 = tocando |
| Castigo por proximidad de −1,0 por paso | Quince veces el premio por avanzar: la política aprendía a quedarse quieta lejos de todo | Corregido: descuento gradual con techo menor que tocar |
| `LIDAR_THREADS > 0` | Access violation en procesos hijos | `LIDAR_THREADS = 0` |
| `SubprocVecEnv` con 2+ hijos | `0xC0000005` en `reset()` | Se entrena con `DummyVecEnv` |
| Dos procesos PyBullet a la vez | El entrenamiento muere con `0xC0000005` sin traceback | Un solo proceso: ni GUI ni diagnósticos mientras entrena |
| Faltaba `Monitor` en la factory | Sin `ep_rew_mean` no se sabía si el entrenamiento mejoraba | `return Monitor(env)` |
| Faltaba `sb3-contrib` en `requirements.txt` | Una instalación limpia no podía cargar el modo PPO | Corregido |
| `--direct` creaba siempre el entorno V1 (13D) | El PPO de 58D nunca cargaba y caía a manual en silencio | Corregido: respeta `--env v3` |
| `WALL-E Asistente IA.bat` con `E:\` clavado | El lanzador solo funcionaba en esta máquina | Corregido: `%~dp0` |
| CI usaba heredoc de bash | Fallaba en el runner de Windows | Reescrito en `tools/verificar.py` |
| Control inteligente de aplicaciones | Bloqueaba todos los DLL de Python; mató el entrenamiento | Desactivado (§8) |

---

## 7. Estado actual

### Funciona

- Enlace PC ↔ ESP32 ↔ UNO, verificado sin hardware.
- Consola de control del robot.
- Simulador: modo manual, modo PPO, entrenamiento, GUI.
- Cada carpeta se descarga sola y funciona (lo verifica el CI).

### Pendiente

| Pendiente | Por qué | Desbloquea |
|---|---|---|
| **Sensor de distancia real** | La política usa 36 rayos LiDAR que el robot físico no tiene | La autonomía real |
| Compilar los `.ino` | No hay `arduino-cli` en la máquina | Lo hace quien los cargue |
| Entrenamiento largo | Murió con `0xC0000005` a los 20 000 pasos | Navegación fina |
| Bajar a 38400 baudios si falla | `SoftwareSerial` + `Servo` a 57600 puede quedar justo | Enlace estable |

**Sobre el sensor:** es la decisión técnica más importante que queda. Solo un
LiDAR giratorio permite reusar la política sin reentrenar, porque da el mismo
abanico de rayos que el simulador. Un HC-SR04 da un solo haz y obliga a
reentrenar con otra observación. Va al ESP32 por un UART libre, como trama
nueva: `WALLE/1 L <n> <d0>…`.

**Sobre el entrenamiento:** el access violation es el mismo problema de PyBullet
con múltiples instancias en el mismo proceso. Se salvaron los checkpoints hasta
1 403 520 pasos. Falta una corrida que aguante.

---

## 8. Nota sobre Windows

**Control inteligente de aplicaciones está desactivado** en esta máquina
(`VerifiedAndReputablePolicyState = 0`). Estaba bloqueando todos los binarios de
Python sin firma:

```
ImportError: DLL load failed while importing pybullet:
Una directiva de Control de aplicaciones bloqueó este archivo.
```

Eso mató un entrenamiento y habría hecho fallar el simulador aunque estuviera
todo bien instalado.

**No se puede volver a activar sin reinstalar Windows.** Es unidireccional, así
lo diseñó Microsoft.

Si en el futuro algo deja de cargar con ese mismo mensaje, no es el código: es
esta política.

---

## 9. Reglas de trabajo

1. **Una carpeta a la vez.** Si se trabaja en el simulador, se trabaja en el
   simulador. No se toca el cerebro "de paso".
2. **Cada avance se commitea y se pushea.** Sin que haya que pedirlo.
3. **Se verifica antes de decir que funciona.** Correr el comando, no asumir.
4. **El `.bat` es la interfaz.** Todo arranca con doble clic. Rutas relativas con
   `%~dp0`, nunca absolutas.
5. **Los `.bat` son ASCII puro y sin BOM.** Un acento o un BOM rompe `cmd`.
6. **El hardware obedece, no decide.** Si aparece lógica en el ESP32 o en el UNO,
   está mal puesta.
7. **Documentar la trampa, no solo la solución.** La tabla de §6 existe para que
   nadie vuelva a perder una noche en lo mismo.

---

## 10. Para una IA que abra esto

Si estás leyendo esto sin contexto previo:

- El proyecto está en `Escritorio\Proyecto Wall-E\`, que es un clon de
  `github.com/RagsnorWolf/Proyecto-Wall-E-IA`.
- Hay **tres carpetas** con roles distintos. Leé §4 antes de tocar nada.
- El documento técnico completo está en `PROYECTO.md`, en la raíz del repo, y
  copiado como `00-CONTEXTO.md` dentro de cada carpeta.
- El estado real de cada pieza está en §7. No asumas que algo funciona porque el
  código existe: la tabla dice qué se verificó y cómo.
- Antes de commitear, correr `python tools\verificar.py todo`.
