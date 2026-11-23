"""Paleta y materiales del simulador WALL-E.

Un solo lugar para el aspecto visual. Lo leen `interactive_walle.py` (la GUI)
y `tools_vista_previa.py` (las capturas de verificacion), asi el robot y la
escena se ven exactamente igual en los dos lados.

Por que existe este modulo
--------------------------
La textura original (`material_0.png`) trae los naranjas apagados por el
horneado de luz: al muestrearla por UV y pintar cada pieza con su color medio,
WALL-E sale marron. Aca se conserva el orden de la textura (que pieza es mas
clara que cual, que zona es goma y que zona es acero) y se empuja el conjunto
a la paleta del personaje.

El renderer OpenGL2 de esta PC ignora la textura del MTL, asi que las piezas
de color solido son la unica via para que WALL-E se vea como WALL-E.
"""

from __future__ import annotations

import colorsys

# --------------------------------------------------------------------------- #
# WALL-E: colores del personaje
# --------------------------------------------------------------------------- #
# Cuerpo: amarillo mostaza al sol, no naranja puro. Las sombras van calidas,
# nunca negras, porque el chasis tiene rebote de suelo.
WALLE_BODY_LIGHT = (0.95, 0.75, 0.33)
WALLE_BODY = (0.89, 0.63, 0.20)
WALLE_BODY_DARK = (0.71, 0.45, 0.13)
# Oxido: marron rojizo de los bordes gastados.
WALLE_RUST = (0.36, 0.20, 0.08)
# Visor y optica: casi negro, para que el brillo de los ojos se lea.
WALLE_VISOR = (0.055, 0.055, 0.065)
# Orugas: goma, no plastico.
WALLE_RUBBER = (0.105, 0.105, 0.115)
# Brazos, bisagras y tornillos.
WALLE_STEEL = (0.66, 0.67, 0.69)
WALLE_STEEL_DARK = (0.28, 0.29, 0.31)

# Matiz ancla de la familia mostaza (grados/360). 0.098 = 35 grados.
_HUE_ANCHOR = 0.098
# Cuanto se lleva cada pieza hacia ese matiz. 1.0 = todo el mismo amarillo y
# se pierde el detalle de la textura; 0.0 = se queda en el naranja apagado.
_HUE_PULL = 0.78


def _to_hsv(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(
        float(rgb[0]), float(rgb[1]), float(rgb[2])
    )


def _clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def _steel_color(value: float) -> tuple[float, float, float]:
    """Gris con el mismo brillo relativo, del acero oscuro al claro."""
    t = _clamp01((value - 0.18) / 0.72)
    return (
        WALLE_STEEL_DARK[0] + (WALLE_STEEL[0] - WALLE_STEEL_DARK[0]) * t,
        WALLE_STEEL_DARK[1] + (WALLE_STEEL[1] - WALLE_STEEL_DARK[1]) * t,
        WALLE_STEEL_DARK[2] + (WALLE_STEEL[2] - WALLE_STEEL_DARK[2]) * t,
    )


def walle_body_color(
    rgb: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Lleva un color muestreado de la textura a la familia de WALL-E.

    Tres familias, decididas por el color de origen:

    - Muy oscuro (`value < 0.18`): visor y optica. Se deja casi negro.
    - Sin saturacion (`saturation < 0.16`): metal. Se reescala el brillo sobre
      la rampa de acero para que no quede gris lavado.
    - El resto: cuerpo. Se gira el matiz hacia mostaza, se sube la saturacion
      y se levantan las sombras para que no se lea como barro.

    El orden entre piezas se conserva: si una pieza era mas clara que otra en
    la textura, sigue siendolo despues.
    """
    hue, saturation, value = _to_hsv(rgb)

    if value < 0.18:
        return WALLE_VISOR
    if saturation < 0.16:
        return _steel_color(value)

    hue = hue + ( _HUE_ANCHOR - hue) * _HUE_PULL
    # La textura trae saturacion de carton pintado. Se baja un poco para que
    # lea como chapa pintada al sol y no como plastico.
    saturation = _clamp01(0.46 + 0.42 * saturation)
    value = _clamp01(0.56 + 0.42 * value)
    out = colorsys.hsv_to_rgb(hue, saturation, value)
    return (float(out[0]), float(out[1]), float(out[2]))


def body_palette(
    sampled: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    """Aplica `walle_body_color` a la lista completa de clusters."""
    return [walle_body_color(color) for color in sampled]


# --------------------------------------------------------------------------- #
# Escena: materiales del estudio
# --------------------------------------------------------------------------- #
# Estetica Isaac Sim: fondo casi negro, suelo grafito y geometria neutra.
# El contraste lo dan los materiales, no los colores fuertes.
#
# El fondo tiene que quedar POR DEBAJO del suelo o el horizonte desaparece y
# el viewport se lee como una mancha. Con el suelo en 0.20 y el fondo en 0.085
# la linea donde termina la arena se ve sin necesidad de paredes claras.
SKY_RGB = (0.085, 0.088, 0.100)
GROUND_RGBA = (0.200, 0.204, 0.222, 1.0)
# Un especular algo mas alto que el difuso hace que el piso devuelva un brillo
# tenue y las patas del robot se apoyen: sin el, el suelo es una lamina plana.
GROUND_SPECULAR = (0.085, 0.085, 0.100)
# La cuadricula va un escalon por encima del suelo, no dos: si brilla mas que
# los solidos, el piso se come la escena.
GRID_MINOR_RGB = (0.268, 0.272, 0.295)
GRID_MAJOR_RGB = (0.370, 0.376, 0.405)
WALL_RGBA = (0.150, 0.153, 0.170, 1.0)
WALL_SPECULAR = (0.070, 0.070, 0.082)
# Borde de la arena: una franja mas clara que separa el piso de la nada.
BORDER_RGBA = (0.395, 0.400, 0.430, 1.0)

# Solidos de la escena. Familia calida-neutra para que el ambar del LiDAR
# siga siendo el color mas caliente del viewport.
#
# Los tres primeros tonos son la escala de grises de un almacen: yeso, piedra
# y hormigon. El cuarto es el unico calido y esta reservado para que un solido
# se distinga de otro de un vistazo. El ultimo, grafito, se usa cuando el
# cuerpo esta lejos del robot y conviene que se hunda en el fondo.
SOLID_PALETTE = (
    (0.690, 0.676, 0.645, 1.0),   # yeso
    (0.545, 0.532, 0.510, 1.0),   # piedra
    (0.395, 0.388, 0.378, 1.0),   # hormigon
    (0.735, 0.505, 0.235, 1.0),   # oxido, el unico calido
    (0.255, 0.252, 0.258, 1.0),   # grafito
    (0.470, 0.505, 0.545, 1.0),   # acero azulado, para romper la escala calida
)
SOLID_SPECULAR = (0.110, 0.105, 0.095)


def solid_color(index: int) -> tuple[float, float, float, float]:
    """Color estable por indice de cuerpo: el mismo solido no cambia de tono."""
    return SOLID_PALETTE[index % len(SOLID_PALETTE)]


def solid_specular(index: int) -> tuple[float, float, float]:
    """El oxido claro es mas mate que el yeso: menos brillo especular."""
    if SOLID_PALETTE[index % len(SOLID_PALETTE)][0] > 0.75:
        return (0.060, 0.055, 0.045)
    return SOLID_SPECULAR
