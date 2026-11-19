# Simulador Wall-E

Mundo 2D con física de chasis diferencial: ruedas, inercia de batería, colisiones
contra muros y cubos de basura que hay que llevar al contenedor. Es la base sobre
la que entrena el Cerebro y donde el Agente practica sin romper nada.

## Instalar (Windows, sin saber nada de Python)

1. Instalá Python 3.10 o superior desde <https://www.python.org/downloads/> y
   marcá la casilla **"Add python.exe to PATH"** durante la instalación.
2. Doble clic en **`instalar.bat`**. Crea el entorno, instala pygame y hace una
   prueba de humo.
3. Doble clic en **`iniciar.bat`** para jugar.

## Instalar (Linux o macOS)

```bash
chmod +x instalar.sh
./instalar.sh
.venv/bin/python main.py
```

## Instalar a mano

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Esta carpeta funciona sola

No necesita nada del resto del repositorio: la física, los escenarios y el visor
están acá adentro. Si descargaste únicamente `Simulador Wall-E/`, alcanza.

## Jugar

```powershell
pip install pygame
python main.py
python main.py --escenario pasillo
python main.py --sin-ventana --pasos 500   # prueba headless, sin pygame
```

| Tecla | Acción |
|---|---|
| Flecha arriba | Avanzar |
| Flecha izquierda / derecha | Girar |
| Espacio | Recoger cubo o depositar en el contenedor |
| 1 / 2 / 3 | Cambiar de escenario |
| R | Reiniciar el episodio |
| ESC | Salir |

## Escenarios

- **chatarreria** — mapa abierto, 9 cubos, muros sueltos.
- **pasillo** — corredor con puertas, obliga a girar y planificar.
- **patio** — columnas en rejilla, 12 cubos alrededor.

Cada escenario acepta `--semilla N` para que la partida sea reproducible.

## Física

Unidades del Sistema Internacional. Nada está inventado:

| Constante | Valor | Por qué |
|---|---|---|
| Radio del chasis | 0.16 m | Tamaño de WALL-E comprimido |
| Velocidad lineal | 0.24 m/s | Paso de oruga lento y controlable |
| Velocidad angular | 1.9 rad/s | Giro sobre el sitio |
| Paso de simulación | 0.1 s | 10 Hz, suficiente para control discreto |
| Alcance de recogida | 0.26 m | Brazo corto |
| Batería | 1.2 %/m + 0.005 %/paso | Autonomía de unos 100 m |
| Calorías | `m·g·μ·d / 4184` | Trabajo de rodadura real, no un número de adorno |

La energía se calcula con `m = 20 kg`, `g = 9.81`, `μ = 0.05`: trabajo mecánico
de rodar sobre chatarra compactada, convertido a kcal.

## Estructura

```
main.py                 bucle de teclado y prueba headless
simulador/fisica.py     geometría, colisiones, batería, energía, 8 rayos
simulador/escenarios.py mapas con colocación de basura por rechazo
simulador/entorno.py    Escena: episodio + vector de observación (17 valores)
simulador/render.py     visor pygame
```

## Observación que entrega

17 flotantes acotados, pensados para una red pequeña:

```
[cos θ, sin θ, batería, carga, cubos restantes,
 dx, dy, distancia a la basura más cercana,
 distancia al contenedor,
 8 distancias de rayo normalizadas]
```

## Prueba rápida

```powershell
python main.py --sin-ventana --escenario patio --pasos 300
```

Devuelve batería, posición y choques. Sirve para comprobar que una modificación
en la física no rompió nada, sin abrir ventana.
