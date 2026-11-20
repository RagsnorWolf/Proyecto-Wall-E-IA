# Asistente IA Wall-E

La cabina web con la que se conversa con WALL-E. Corre entera en esta PC: no
necesita internet ni ninguna cuenta.

```
Asistente IA Wall-E\
  Iniciar WALL-E.bat          <- doble clic para abrir la cabina
  INSTALAR.bat                <- una sola vez, antes de lo anterior
  Modelo AI\                  <- el cerebro: personalidad, memoria, voz, visión
  Pagina Web\cockpit\         <- el servidor y la interfaz que se ve en el navegador
```

## Puesta en marcha

**1. Python.** Si no está, `winget install Python.Python.3.12`.

**2. Dependencias.** Doble clic en `INSTALAR.bat`. Instala `pyserial`,
`opencv-python`, `numpy` y `pyttsx3`.

**3. Ollama.** Es el motor que hace hablar al modelo. No se instala con pip:

- Descargar de https://ollama.com
- Después, en una consola:

```bash
ollama pull qwen2.5:3b
```

**4. Abrir.** Doble clic en `Iniciar WALL-E.bat`. Se abre el navegador en
`http://127.0.0.1:8765/`.

Si el navegador no se abre solo, entrar a mano a esa dirección.

## Qué modelo usar

| Modelo | RAM | Velocidad | Cuándo |
|---|---|---|---|
| `qwen2.5:3b` | ~2 GB | 8–12 tok/s | El default. Sirve para conversar |
| `qwen2.5:1.5b` | ~1 GB | 18–25 tok/s | Si la voz se siente lenta |
| `qwen2.5:7b` | ~4.7 GB | 3–5 tok/s | Solo con GPU de 8 GB o más |

El detalle medido en esta máquina está en `Modelo AI\MODELOS.md`.

## Qué hay dentro de `Modelo AI\`

| Archivo | Qué hace |
|---|---|
| `brain\agent.py` | El bucle: recibe texto, decide, responde, recuerda |
| `brain\llm.py` | Cliente de Ollama. Sin dependencias, stdlib pura |
| `brain\emotions.py` | Estado de ánimo que tiñe las respuestas |
| `brain\memory.py` | Memoria en SQLite entre sesiones |
| `brain\tools.py` | Acciones que puede ejecutar |
| `brain\computer.py` | Control de la PC, con lista blanca |
| `vision\reflex.py` | Reacciones a lo que ve la cámara |
| `hardware\esp32_link.py` | Enlace serie con el robot, si está conectado |
| `prompts\system.md` | La personalidad de WALL-E |
| `voices\` | Voz TTS en español (60 MB, modelo Piper) |

## Problemas comunes

| Síntoma | Causa | Arreglo |
|---|---|---|
| «No puedo hablar con Ollama» | Ollama no está corriendo | Abrir Ollama, o `ollama serve` |
| Responde pero no habla | Falta `pyttsx3` | Correr `INSTALAR.bat` |
| Página en blanco | Falta el build del frontend | Está en `cockpit\static\`; no borrarlo |
| Va lentísimo | Modelo muy grande para la RAM | `ollama pull qwen2.5:1.5b` |

## Nota sobre el frontend

`cockpit\static\` trae el build ya hecho: es lo que sirve el servidor y no hay
que compilar nada. `cockpit\ui\` es el código fuente de esa interfaz, por si
alguna vez hay que cambiarla — para eso hace falta Node y `npm install`, que
no vienen incluidos.
