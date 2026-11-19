# Proyecto WALL-E

Tres piezas que funcionan juntas y también **por separado**. Cada carpeta se
descarga, se instala y se ejecuta sola:

| Carpeta | Qué es | Qué resuelve |
|---|---|---|
| `Simulador Wall-E/` | Motor 2D con física realista | El mundo donde se prueba todo, sin hardware |
| `Cerebro Wall-E (Actividad Fisica + PPO) .py/` | Aprendizaje por refuerzo (PPO escrito a mano) | La política que conduce: explora, recoge, entrega |
| `Agente de IA Wall-E/` | Agente con modelo de lenguaje y herramientas | La cabeza que decide qué hacer y por qué |

La cadena es simple: **el Simulador presta la física, el Cerebro aprende a moverse
dentro de ella, y el Agente usa ese reflejo entrenado como músculo mientras piensa
con un modelo de lenguaje.**

```
Simulador Wall-E  ──física──▶  Cerebro PPO  ──política──▶  Agente de IA
   (mundo)                     (entrena)                    (decide + actúa)
```

## Instalación por carpeta

Cada carpeta trae su propio `instalar.bat` (Windows) e `instalar.sh` (Linux/macOS).
Nada más que hacer: doble clic y el instalador crea el entorno, instala lo que
falta y hace una prueba de humo.

| Si querés… | Bajá solo | Después |
|---|---|---|
| Jugar con el simulador | `Simulador Wall-E/` | `instalar.bat` → `iniciar.bat` |
| Entrenar el cerebro | `Cerebro Wall-E (Actividad Fisica + PPO) .py/` | `instalar.bat` → `entrenar.bat` → `iniciar.bat` |
| Usar el agente | `Agente de IA Wall-E/` | `instalar.bat` → poner `WALLE_API_KEY` → `iniciar.bat` |

Requisito único: **Python 3.10 o superior**, con la casilla *"Add python.exe to
PATH"* marcada al instalar.

### Por qué funcionan solas

El Cerebro y el Agente dependen del simulador (y el Agente de la política), así
que cada uno lleva una copia vendorizada en `vendor/`:

```
Cerebro/vendor/simulador    copia de Simulador Wall-E/simulador
Agente/vendor/simulador     la misma copia
Agente/vendor/cerebro       copia de Cerebro/cerebro (red, ppo, politica)
```

La fuente de verdad es siempre la carpeta original. Las copias se regeneran con
un solo comando y la CI verifica que no queden viejas:

```powershell
python sincronizar.py              # actualiza las copias
python sincronizar.py --verificar  # solo compara (lo que corre la CI)
```

## Requisitos reales

- Python 3.10+. Nada más obligatorio.
- `pygame` solo para ver la ventana del simulador (lo instala `instalar.bat`).
- `pyserial` solo para un robot real por USB.
- `opencv-python` solo para la percepción por cámara.

No hay numpy ni torch: el PPO está escrito en Python puro, con gradiente
verificado por diferencias finitas. Corre en cualquier Python sin compilar nada.

## Pruebas

Cada carpeta trae su suite, sin dependencias externas ni red:

```powershell
cd "Cerebro Wall-E (Actividad Fisica + PPO) .py"; python -m unittest -v pruebas
cd "..\Agente de IA Wall-E";                     python -m unittest -v pruebas_agente
cd "..\Simulador Wall-E";                        python main.py --sin-ventana --pasos 200
```

La prueba importante del Cerebro compara el gradiente analítico del PPO con
diferencias finitas: si una fórmula pierde el signo, truena antes de entrenar
media hora para nada.

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
│   ├── instalar.bat / iniciar.bat / instalar.sh
│   ├── agente/                           LLM, herramientas, memoria, actuadores
│   ├── firmware_walle.ino                cuerpo real por USB
│   └── vendor/                           copias generadas (simulador + cerebro)
└── .github/workflows/pruebas.yml         CI: suites, carpeta suelta y vendor
```

## Cómo se comparte

El repositorio es público y no contiene claves. Cada quien pone la suya:

```powershell
git clone https://github.com/RagsnorWolf/Proyecto-Wall-E-IA.git
```

`config.json`, `datos/` y los CSV de entrenamiento están en `.gitignore`.

## Licencia

MIT. Usalo, cambialo, compartilo.
