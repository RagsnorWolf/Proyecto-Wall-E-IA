"""Mapas del simulador: obstaculos, basura inicial y punto de aparicion.

Cada escenario se genera con semilla para que dos partidas con la misma
semilla sean identicas (reproducibilidad del entrenamiento).
"""
from __future__ import annotations

import random
from typing import NamedTuple

from .fisica import RADIO_BASURA, RADIO_ROBOT, Rect, colision_circulo_rect

ANCHO = 10.0
ALTO = 7.0


class Escenario(NamedTuple):
    nombre: str
    ancho: float
    alto: float
    obstaculos: list[Rect]
    basuras: list[tuple[float, float]]
    contenedor: tuple[float, float]
    inicio: tuple[float, float, float]


_DEFINICIONES: dict[str, dict] = {
    # Chatarreria abierta: pocos muros, basura repartida.
    "chatarreria": {
        "obstaculos": [
            (2.2, 1.4, 1.6, 0.35),
            (5.6, 0.8, 0.35, 2.2),
            (2.2, 4.4, 0.35, 1.8),
            (6.4, 4.2, 2.0, 0.35),
            (8.4, 1.2, 0.9, 1.0),
        ],
        "basuras": 9,
        "contenedor": (8.9, 6.2),
        "inicio": (0.9, 0.9, 0.0),
    },
    # Pasillo: pasillo central con puertas, obliga a girar.
    "pasillo": {
        "obstaculos": [
            (0.0, 2.2, 3.4, 0.4),
            (3.8, 2.2, 2.6, 0.4),
            (0.0, 4.4, 2.2, 0.4),
            (2.8, 4.4, 3.6, 0.4),
            (7.0, 2.2, 0.4, 1.6),
            (6.4, 4.4, 3.6, 0.4),
            (8.8, 5.6, 1.2, 0.4),
        ],
        "basuras": 10,
        "contenedor": (9.2, 0.9),
        "inicio": (0.9, 6.2, 0.0),
    },
    # Patio: columnas en rejilla, basura alrededor de cada una.
    "patio": {
        "obstaculos": [
            (1.8, 1.6, 0.6, 0.6),
            (4.4, 1.6, 0.6, 0.6),
            (7.0, 1.6, 0.6, 0.6),
            (1.8, 3.8, 0.6, 0.6),
            (4.4, 3.8, 0.6, 0.6),
            (7.0, 3.8, 0.6, 0.6),
            (1.8, 5.8, 0.6, 0.6),
            (4.4, 5.8, 0.6, 0.6),
            (7.0, 5.8, 0.6, 0.6),
        ],
        "basuras": 12,
        "contenedor": (9.3, 3.5),
        "inicio": (0.8, 3.5, 0.0),
    },
}

ESCENARIOS = tuple(_DEFINICIONES)


def _coloca_basura(
    rng: random.Random,
    obstaculos: list[Rect],
    contenedor: tuple[float, float],
    inicio: tuple[float, float, float],
    ya_puestas: list[tuple[float, float]],
    ancho: float,
    alto: float,
) -> tuple[float, float] | None:
    """Busca un hueco libre con margen; None si no encuentra en 200 intentos."""
    for _ in range(200):
        x = rng.uniform(0.5, ancho - 0.5)
        y = rng.uniform(0.5, alto - 0.5)
        if x < 0.9 and y < 0.9:
            continue
        if any(colision_circulo_rect(x, y, RADIO_BASURA + 0.08, r) for r in obstaculos):
            continue
        if (x - contenedor[0]) ** 2 + (y - contenedor[1]) ** 2 < 0.8**2:
            continue
        if (x - inicio[0]) ** 2 + (y - inicio[1]) ** 2 < RADIO_ROBOT + 0.4:
            continue
        if any((x - px) ** 2 + (y - py) ** 2 < 0.45**2 for px, py in ya_puestas):
            continue
        return x, y
    return None


def crear(nombre: str = "chatarreria", semilla: int | None = None) -> Escenario:
    """Construye un escenario con basura colocada por muestreo con rechazo."""
    if nombre not in _DEFINICIONES:
        raise ValueError(f"escenario desconocido: {nombre!r} (usa {ESCENARIOS})")
    definicion = _DEFINICIONES[nombre]
    rng = random.Random(semilla)
    obstaculos = [tuple(map(float, o)) for o in definicion["obstaculos"]]
    contenedor = tuple(map(float, definicion["contenedor"]))
    inicio = tuple(map(float, definicion["inicio"]))

    basuras: list[tuple[float, float]] = []
    for _ in range(definicion["basuras"]):
        posicion = _coloca_basura(rng, obstaculos, contenedor, inicio, basuras, ANCHO, ALTO)
        if posicion is not None:
            basuras.append(posicion)

    return Escenario(
        nombre=nombre,
        ancho=ANCHO,
        alto=ALTO,
        obstaculos=obstaculos,
        basuras=basuras,
        contenedor=contenedor,
        inicio=inicio,
    )
