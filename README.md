# Proyecto WALL-E

Tres piezas que funcionan juntas y también **por separado**. Cada carpeta se
descarga, se instala y se ejecuta sola:

| Carpeta | Qué es | Qué resuelve |
|---|---|---|
| `Simulador Wall-E/` | Motor 2D con física realista | El mundo donde se prueba todo, sin hardware |
| `Cerebro Wall-E (Actividad Fisica + PPO) .py/` | Aprendizaje por refuerzo (PPO escrito a mano) | La política que conduce: explora, recoge, entrega |
| `Agente de IA Wall-E/` | Cabina web: WALL-E en 3D, chat con voz, memoria, cámara y control del robot | La cabeza que decide qué hacer y por qué |

La cadena es simple: **el Simulador presta la física, el Cerebro aprende a moverse
dentro de ella, y el Agente conversa, recuerda y maneja el robot.**

```
Simulador Wall-E  ──física──▶  Cerebro PPO  ──política──▶  Robot
   (mundo)                     (entrena)

Agente de IA  ──habla──▶  Ollama (modelo local)  ──herramientas──▶  robot / PC
   (cabina web)
```

## Instalación por carpeta

Cada carpeta trae su propio `instalar.bat` (Windows) e `instalar.sh` (Linux/macOS).
Nada más que hacer: doble clic y el instalador crea el entorno, instala lo que
falta y hace una prueba de humo.

| Si querés… | Bajá solo | Después |
|---|---|---|
| Jugar con el simulador | `Simulador Wall-E/` | `instalar.bat` → `iniciar.bat` |
| Entrenar el cerebro | `Cerebro Wall-E (Actividad Fisica + PPO) .py/` | `instalar.bat` → `entrenar.bat` → `iniciar.bat` |
| Usar el asistente | `Agente de IA Wall-E/` | `instalar.bat` → `WALL-E Asistente IA.bat` |

Requisito único: **Python 3.10 o superior**, con la casilla *"Add python.exe to
PATH"* marcada al instalar. Para que el asistente piense hace falta además
[Ollama](https://ollama.com/download) con el modelo creado por `build_model.py`.

### Por qué funcionan solas

Solo el Cerebro necesita algo de otra carpeta: la física del Simulador. La lleva
copiada en `vendor/`, generada desde la fuente de verdad:

```
Cerebro/vendor/simulador    copia de Simulador Wall-E/simulador
```

El Agente no copia nada: su cerebro es propio (`brain/`) y trae la interfaz ya
compilada, así que no necesita Node ni internet.

Las copias se regeneran con un comando y la CI falla si quedan viejas:

```powershell
python sincronizar.py              # actualiza las copias
python sincronizar.py --verificar  # solo compara (lo que corre la CI)
```

## Requisitos reales

- Python 3.10+. Nada más obligatorio.
- `pygame` solo para ver la ventana del simulador (lo instala `instalar.bat`).
- `pyserial` solo para el robot real por USB.
- `opencv-python` solo para la cámara y el seguimiento por color.
- Ollama solo para que el chat piense; sin él la cabina abre igual.

No hay numpy ni torch en el cerebro: el PPO está escrito en Python puro, con
gradiente verificado por diferencias finitas. Corre en cualquier Python sin
compilar nada.

## Pruebas

Cada carpeta trae su suite, sin dependencias externas ni red:

```powershell
cd "Cerebro Wall-E (Actividad Fisica + PPO) .py"; python -m unittest -v pruebas
cd "..\Agente de IA Wall-E";                     python -m unittest -v pruebas_agente
cd "..\Simulador Wall-E";                        python main.py --sin-ventana --pasos 200
```

La prueba importante del Cerebro compara el gradiente analítico del PPO con
diferencias finitas: si una fórmula pierde el signo, truena antes de entrenar
media hora para nada. La del Agente levanta el servidor real en un puerto libre
y le habla por HTTP como lo haría el navegador.

## Estructura

```
Proyecto-Wall-E-IA/
├── sincronizar.py                        mantiene al día las copias vendorizadas
├── Simulador Wall-E/                     física, escenarios, visor pygame
│   ├── instalar.bat / iniciar.bat / instalar.sh
│   └── simulador/                        fisica, escenarios, entorno, render
├── Cerebro Wall-E (Actividad Fisica + PPO) .py/
│   ├── instalar.bat / entrenar.bat / iniciar.bat / instalar.sh
│   ├── cerebro/                          red, PPO, recompensa, entorno
│   ├── vendor/simulador/                 copia generada
│   ├── entrenar_ppo.py                   entrenamiento + CSV de la curva
│   └── evaluar.py                        mirar la política jugando
├── Agente de IA Wall-E/
│   ├── instalar.bat / iniciar.bat / "WALL-E Asistente IA.bat"
│   ├── server.py                         servidor local y todas las rutas /api
│   ├── brain/                            agente, Ollama, herramientas, memoria
│   ├── hardware/ vision/                 robot por USB y cámara
│   ├── static/                           interfaz compilada (sin Node)
│   └── ui/                               fuentes React para recompilarla
└── .github/workflows/pruebas.yml         CI: suites, carpeta suelta y vendor
```

## Cómo se comparte

El repositorio es público y no contiene claves ni datos personales:

```powershell
git clone https://github.com/RagsnorWolf/Proyecto-Wall-E-IA.git
```

`config.json`, `datos/` y los CSV de entrenamiento están en `.gitignore`.

## Licencia

MIT. Usalo, cambialo, compartilo.
