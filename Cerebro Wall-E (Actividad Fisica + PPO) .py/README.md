# Cerebro Wall-E — Actividad Física + PPO

Aprendizaje por refuerzo para que WALL-E se mueva de verdad: recorra el mapa,
junte cubos y los entregue. Todo el PPO está escrito a mano en Python puro —sin
numpy, sin torch— con retropropagación verificada por diferencias finitas.

## Instalar (Windows, sin saber nada de Python)

1. Instalá Python 3.10 o superior desde <https://www.python.org/downloads/> y
   marcá la casilla **"Add python.exe to PATH"**.
2. Doble clic en **`instalar.bat`**. Crea el entorno, corre las pruebas
   (incluida la del gradiente) y entrena 2048 pasos como humo.
3. Doble clic en **`entrenar.bat`** para entrenar en serio (60.000 pasos).
4. Doble clic en **`iniciar.bat`** para ver la política jugando.

## Instalar (Linux o macOS)

```bash
chmod +x instalar.sh
./instalar.sh
.venv/bin/python entrenar_ppo.py --pasos 60000
```

## Esta carpeta funciona sola

No depende de la carpeta hermana: lleva una copia vendorizada del simulador en
`vendor/simulador/`, generada desde la fuente de verdad por `sincronizar.py`
(está en la raíz del repo). Por eso podés descargar únicamente
`Cerebro Wall-E (Actividad Fisica + PPO) .py/` y entrenar igual.

La copia se regenera con `python sincronizar.py`; la CI falla si queda vieja.

## Ya viene entrenada

`modelo/politica.json` está en la carpeta: después de `instalar.bat`, `iniciar.bat`
abre la ventana y la política juega sin entrenar nada. Si querés tu propia
política, `entrenar.bat` la reemplaza.

Si falta pygame, `iniciar.bat` avisa y sigue sin ventana; `evaluar.py` también
cae a modo texto en vez de romperse.

## Entrenar

```powershell
python entrenar_ppo.py --pasos 60000
python entrenar_ppo.py --pasos 60000 --escenario patio --semilla 3 --lr 5e-4
python entrenar_ppo.py --pasos 20000 --reanudar      # sigue desde el checkpoint
```

Salidas:

- `modelo/politica.json` — pesos + configuración de la red.
- `modelo/entrenamiento.csv` — una fila por actualización (para graficar la curva).

## Mirar la política jugando

```powershell
pip install pygame
python evaluar.py --ventana --episodios 5
python evaluar.py --escenario pasillo --episodios 10
```

## Qué está aprendiendo (la recompensa)

El premio central es la **cobertura**: se paga por entrar en celdas de 0.5 × 0.5 m
que no se habían visitado. Girar en el sitio no descubre nada y por lo tanto no
paga. Esto evita la política degenerada clásica de premiar distancia recorrida,
que termina en un robot dando vueltas para siempre.

| Señal | Valor | Motivo |
|---|---|---|
| Celda nueva | +0.35 | Actividad física real, medida en área |
| Por metro | +0.02 | Forma suave mientras explora |
| Recoger cubo | +2.5 | Progreso parcial hacia el objetivo |
| Entregar cubo | +12.0 | Objetivo cumplido |
| Limpiar el mapa | +6.0 | Bonus de episodio terminado |
| Paso | −0.02 | Presión de tiempo |
| Colisión | −0.35 | Castiga chocar |
| Batería < 10 % | −0.05/paso | No dejar que se apague |
| Batería agotada | −6.0 | Episodio fallido |

Están en `cerebro/recompensa.py`, en un solo dataclass `PesosRecompensa`.
Cambiar el comportamiento del robot es cambiar esos números.

## Cómo está armado

```
cerebro/red.py          dos capas tanh + cabezas de política y valor, Adam
cerebro/ppo.py          muestreo, GAE(λ), recorte, entropía, minilotes
cerebro/recompensa.py   los pesos de arriba, sin estado
cerebro/entorno.py      el Simulador envuelto con API reset/step
cerebro/politica.py     checkpoint cargado para inferencia (lo usa el Agente)
entrenar_ppo.py         bucle de entrenamiento + CSV
evaluar.py              episodios deterministas, con ventana opcional
pruebas.py              gradiente finito + contrato del entorno
```

Hiperparámetros por defecto: red 32-32, `γ = 0.99`, `λ = 0.95`, `lr = 3e-4`,
rollout 1024, 4 épocas, minilote 256, recorte 0.2, entropía 0.01.

## La prueba que importa

```powershell
python -m unittest -v pruebas
```

`test_gradiente_coincide_con_diferencias_finitas` calcula el gradiente analítico
del PPO y lo compara con el numérico en cada peso y sesgo de la red. Tolerancia:
1e-4. Si se toca una fórmula y el signo se va, esto truena antes de entrenar.

## Terminar rápido duele

En CPU, `--pasos 60000` tarda unos 5 minutos y la política ya recorre el mapa
(unas 8 m² de cobertura). Las primeras entregas aparecen cerca de los 120.000
pasos; para que juegue fino hacen falta entre 150.000 y 250.000 (20-30 minutos).
El CSV guarda la curva: si `recompensa_media` deja de subir, mirá `entropia`
(si está cerca de 0, la política dejó de explorar) y `aprox_kl` (si se dispara,
bajá `--lr`).

La `politica.json` incluida viene de 300.000 pasos: explora bien, entrega poco y
arranca mal en algunos episodios (choca al salir). Es un punto de partida, no el
techo: `entrenar.bat` con `--reanudar` la sigue mejorando desde ahí.
