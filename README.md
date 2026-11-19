# Proyecto WALL-E

Tres piezas que funcionan juntas y también por separado:

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

## Requisitos

- Python 3.10 o superior. Nada más obligatorio.
- `pygame` solo si querés ver la ventana del simulador.
- `pyserial` solo si vas a conectar una placa real.
- `opencv-python` solo si vas a usar la cámara del Agente.

No hay numpy ni torch: el PPO está escrito en Python puro, con gradiente
verificado por diferencias finitas. Eso lo hace lento comparado con una GPU,
pero corre en cualquier instalación de Python sin compilar nada.

## Inicio rápido

```powershell
# 1. mirar el mundo
cd "Simulador Wall-E"
pip install pygame
python main.py

# 2. entrenar el cerebro (unos minutos en CPU)
cd "..\Cerebro Wall-E (Actividad Fisica + PPO) .py"
python entrenar_ppo.py --pasos 60000
python evaluar.py --ventana

# 3. darle una cabeza al robot
cd "..\Agente de IA Wall-E"
$env:WALLE_API_KEY="tu-clave-del-proveedor"
copy config.ejemplo.json config.json
python main.py --probar
python main.py --demo
```

## Pruebas

Cada carpeta trae su suite, sin dependencias y sin red:

```powershell
cd "Cerebro Wall-E (Actividad Fisica + PPO) .py"; python -m unittest -v pruebas
cd "..\Agente de IA Wall-E";                     python -m unittest -v pruebas_agente
```

La prueba importante del Cerebro es la del gradiente: compara el gradiente
analítico del PPO con diferencias finitas. Si alguien toca una fórmula y el
signo se va, truena antes de entrenar media hora para nada.

## Cómo se comparte

El repositorio es público y no contiene claves. Para usarlo:

```powershell
git clone https://github.com/RagsnorWolf/Proyecto-Wall-E-IA.git
cd Proyecto-Wall-E-IA
```

Cada quien pone su propia clave en `WALLE_API_KEY` (variable de entorno) o en
`config.json`. Ese archivo está en `.gitignore`: nunca se sube.

## Estructura

```
Proyecto-Wall-E-IA/
├── Simulador Wall-E/                     física, escenarios, visor pygame
├── Cerebro Wall-E (Actividad Fisica + PPO) .py/
│   ├── cerebro/                          red, PPO, recompensa, entorno
│   ├── entrenar_ppo.py                   entrenamiento + CSV de la curva
│   └── evaluar.py                        mirar la política jugando
├── Agente de IA Wall-E/                  modelo de lenguaje + herramientas
└── .github/workflows/pruebas.yml         CI: compila y corre las suites
```

## Licencia

MIT. Usalo, cambialo, compartilo.
