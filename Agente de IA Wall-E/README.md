# Agente de IA Wall-E

La cabeza del robot: un modelo de lenguaje decide qué hacer, un catálogo cerrado
de herramientas lo ejecuta, y la política PPO del Cerebro conduce las ruedas
cuando hay que recorrer distancia.

## Configurar

```powershell
copy config.ejemplo.json config.json
$env:WALLE_API_KEY="tu-clave"
python main.py --probar
```

`config.json` no se sube al repositorio (está en `.gitignore`). La clave tampoco:
se lee de la variable de entorno que diga `variable_clave` (por defecto
`WALLE_API_KEY`).

Cualquier proveedor que hable el dialecto de OpenAI sirve, cambiando `base_url`
y `modelo`:

| Proveedor | base_url | modelo de ejemplo |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-3.5-sonnet` |
| Ollama local | `http://localhost:11434/v1` | `llama3.1` |

Con Ollama no hace falta clave: poné `"proveedor": "ollama"` y la variable puede
estar vacía.

## Usar

```powershell
python main.py                        # consola interactiva
python main.py --demo                 # una orden de ejemplo y sale
python main.py --cuerpo consola       # sin simulador: solo registra órdenes
python main.py --sin-llm --reflejo 200  # solo la política PPO conduciendo
python main.py --instruccion "recogé un cubo y llevalo al contenedor"
```

En consola escribís la orden; el agente mira, decide, actúa y responde. Todo
queda en `datos/memoria.db`.

## Cuerpos

| `cuerpo` | Qué hace | Cuándo |
|---|---|---|
| `simulado` | Mueve el WALL-E del Simulador | Desarrollo y pruebas (por defecto) |
| `serial` | Habla con una placa por USB | Robot real |
| `consola` | Solo registra las órdenes | Probar el bucle sin mover nada |

### Protocolo serial

Pensado para un Arduino o ESP32. Una orden por línea, una respuesta por línea:

```
PC   -> placa : AVANZAR 3\n
placa -> PC   : OK {"bateria": 88.2, "basura": 3}\n
```

Órdenes: `AVANZAR <n>`, `GIRAR IZQ|DER <n>`, `RECOGER`, `ESPERAR <n>`, `ESTADO`.
Respuestas: `OK <json opcional>` o `ERR <motivo>`. `ESTADO` debe devolver un
objeto JSON en una sola línea. Con eso, cualquier firmware de veinte líneas
conecta.

## Herramientas del agente

El modelo solo puede llamar a estas ocho. El catálogo es cerrado: si pide otra
cosa, recibe un error explícito con la lista válida.

| Herramienta | Para qué |
|---|---|
| `mirar` | Estado del mundo + descripción de la percepción |
| `mover` | `avanzar`, `izquierda`, `derecha`, `esperar` (máx. 40) |
| `recoger` | Agarrar un cubo o depositar en el contenedor |
| `reflejo` | Delegar N pasos a la política PPO entrenada |
| `recordar` / `consultar_memoria` | Memoria de largo plazo (SQLite) |
| `hablar` | Decirle algo al operador |
| `terminar` | Cerrar la tarea con un resumen |

El reparto es a propósito: **pensar con el modelo, moverse con la política.**
Recorrer 3 metros no debería costar ocho llamadas a la API.

## Percepción

| Modo | Necesita | Qué entrega |
|---|---|---|
| `simulado` | nada | Estado exacto del mundo |
| `manual` | nada | Una línea que escribe el operador |
| `camara` | `opencv-python` | Fotograma listo para un modelo de visión |

`--percepcion auto` elige `simulado` si el cuerpo es el simulador y `manual` si
es hardware. Nada simula una cámara que no existe.

## Pruebas

```powershell
python -m unittest -v pruebas_agente
```

Levantan un servidor OpenAI falso en `127.0.0.1`, con tool calling real, y
verifican el bucle completo: formato de mensajes, despacho de herramientas,
memoria y cierre. Sin red, sin claves, sin costo.

## Estructura

```
main.py                 CLI: consola, demo, probar credenciales, solo reflejo
agente/config.py        JSON + variables de entorno, validado
agente/llm.py           cliente HTTP compatible con OpenAI, con reintentos
agente/herramientas.py  esquemas + despacho, errores como valores
agente/bucle.py         el ciclo instrucción → modelo → herramientas
agente/memoria.py       SQLite: eventos + hechos con búsqueda por palabra
agente/actuadores.py    simulado / serial / consola
agente/percepcion.py    simulado / manual / cámara
agente/cerebro.py       la política PPO como reflejo
```
