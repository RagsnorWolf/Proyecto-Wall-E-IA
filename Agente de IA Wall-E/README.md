# Agente de IA WALL-E — Centro de Comando

La cabina del robot: una interfaz web local en `http://127.0.0.1:8765/` con
WALL-E en 3D, chat con voz, telemetría, control de orugas, cámara, memoria de
largo plazo y agenda. Detrás hay un cerebro que piensa con un modelo local
(Ollama) y ejecuta herramientas de verdad.

Es la misma aplicación que abrís con el acceso directo **WALL-E Asistente IA**
del escritorio.

## Instalar (Windows, sin saber nada de Python)

1. Instalá Python 3.10 o superior desde <https://www.python.org/downloads/> y
   marcá la casilla **"Add python.exe to PATH"**.
2. Doble clic en **`instalar.bat`**. Crea el entorno, instala lo opcional,
   corre las 10 pruebas y deja `config.json` listo.
3. Doble clic en **`WALL-E Asistente IA.bat`**. Abre el navegador solo.

Para dejarlo en el escritorio con el icono de WALL-E:

```
crear_acceso_directo.bat
```

## Instalar (Linux o macOS)

```bash
chmod +x instalar.sh
./instalar.sh
.venv/bin/python server.py
```

## El modelo de lenguaje (Ollama)

Sin Ollama la cabina abre igual —el chat responde con una frase de cortesía—
pero para conversar de verdad:

```powershell
# 1. Instalar Ollama: https://ollama.com/download
ollama pull qwen2.5:3b

# 2. Crear el modelo con la personalidad de WALL-E
.\.venv\Scripts\python.exe build_model.py --create

# 3. Arrancar la cabina
iniciar.bat
```

`build_model.py` arma el `Modelfile` leyendo `prompts/system.md`, así que la
personalidad se edita en un solo lugar. Detalles de qué modelo conviene según
la máquina: `MODELOS.md`.

Para probar el cerebro sin interfaz: `python cli.py --model walle`.

## Qué hace cada panel

| Panel | Qué muestra |
|---|---|
| Chat | Conversación con voz; el modelo decide y llama herramientas |
| WALL-E 3D | El robot animado en tres.js, con expresión y sonidos |
| Telemetría | CPU, RAM, batería y estado del proceso |
| Orugas | Manejo manual y conexión con el robot real por USB |
| Cámara | Foto, detección de color y seguimiento automático |
| Memoria | Lo que WALL-E recuerda, con búsqueda y borrado |
| Agenda | Eventos locales (Google Calendar si hay credenciales) |
| Ajustes | Modelo, puerto serial, índice de cámara |

## Qué necesita y qué no

Nada es obligatorio. Cada cosa que falte se reporta en `/api/state` y la cabina
sigue funcionando con el resto:

| Falta | Consecuencia |
|---|---|
| Ollama | El chat contesta con una frase fija, sin pensar |
| `pyserial` | No hay control del robot real; queda el modo simulación |
| `opencv-python` | El panel de cámara queda apagado |
| `psutil` | Telemetría del sistema en blanco |
| Piper + modelo `.onnx` | Sin voz; `/api/tts` responde 503 |

## API

Todo lo que hace la interfaz se puede llamar a mano:

```
GET  /api/health          GET  /api/state        GET  /api/companion
GET  /api/events          GET  /api/ports        GET  /api/diagnostics
POST /api/chat            POST /api/robot/move   POST /api/robot/drive
POST /api/robot/stop      POST /api/robot/connect /disconnect
POST /api/emotion         GET  /api/camera/frame POST /api/vision/track
GET  /api/memory?q=       POST /api/memory       DELETE /api/memory/<id>
GET  /api/agenda          POST /api/agenda       DELETE /api/agenda?index=0
GET  /api/settings        POST /api/settings     POST /api/shutdown
```

## Pruebas

```powershell
python -m unittest -v pruebas_agente
```

Diez pruebas, sin red, sin cámara y sin Ollama: importan el cerebro, escriben y
buscan en la memoria SQLite, levantan `server.py` en un puerto libre y hablan
con la API como lo haría el navegador —incluido el caso de que falte todo— y
verifican que la interfaz se sirve.

## Estructura

```
server.py                 servidor HTTP + todas las rutas /api
launcher.py               arranca el servidor y abre el navegador
tts.py                    voz local con Piper (opcional)
build_model.py            crea el modelo de Ollama desde prompts/system.md
cli.py                    chat por terminal, sin interfaz
brain/                    agent, llm (Ollama), tools, memory, emotions, computer
hardware/esp32_link.py    puente serial con el robot
vision/reflex.py          cámara y detección de color (opcional)
prompts/system.md         personalidad — fuente de verdad del modelo
static/                   interfaz ya compilada (no necesita Node)
ui/                       fuentes React por si querés recompilarla
datos/                    memoria, emociones y agenda (no se sube al repo)
tools/                    generador de sonidos de WALL-E
```

La carpeta funciona sola: no importa nada de las otras dos del repositorio.
