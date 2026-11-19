"""Escena jugable: une un escenario con un Mundo y maneja el fin de episodio.

Aqui no hay recompensa. El Cerebro (PPO) define la suya y el visor manual
solo dibuja. Una sola fuente de verdad para la fisica: `Mundo`.
"""
from __future__ import annotations

from . import escenarios
from .fisica import (
    ACCIONES,
    BATERIA_MAX,
    N_ACCIONES,
    N_RAYOS,
    PASOS_MAX,
    Mundo,
)


class Escena:
    """Episodio de WALL-E: recoger basura, llevarla al contenedor, no morir."""

    def __init__(self, escenario: str = "chatarreria", semilla: int | None = None) -> None:
        definicion = escenarios.crear(escenario, semilla)
        self.nombre = definicion.nombre
        self.mundo = Mundo(
            ancho=definicion.ancho,
            alto=definicion.alto,
            obstaculos=definicion.obstaculos,
            basuras=definicion.basuras,
            contenedor=definicion.contenedor,
            inicio=definicion.inicio,
            semilla=semilla,
        )
        self.semilla = semilla

    def reiniciar(self) -> None:
        self.mundo.reiniciar()

    def paso(self, accion: int) -> tuple[dict, bool, bool]:
        """Devuelve (eventos, terminado, truncado)."""
        eventos = self.mundo.paso(accion)
        terminado = eventos["sin_bateria"] or not self.mundo.basuras
        truncado = self.mundo.pasos >= PASOS_MAX
        return eventos, terminado, truncado

    def observacion(self) -> list[float]:
        """Vector plano, acotado y estable en forma — 17 valores.

        [cos, sin, bateria, llevando, basuras_restantes, dx, dy, dist,
         contenedor_dist, 8 rayos]
        """
        mundo = self.mundo
        cercana = mundo.basura_mas_cercana()
        if cercana is None:
            dx, dy, dist = 0.0, 0.0, 1.0
        else:
            dx, dy, dist = cercana
            norm = max(dist, 1e-3)
            dx, dy = dx / norm, dy / norm
        import math

        return [
            math.cos(mundo.theta),
            math.sin(mundo.theta),
            mundo.bateria / BATERIA_MAX,
            mundo.llevando / 2.0,
            len(mundo.basuras) / 12.0,
            dx,
            dy,
            min(dist / 10.0, 1.0),
            min(mundo.distancia_contenedor() / 10.0, 1.0),
            *[d / 1.2 for d in mundo.rayos()],
        ]


TAM_OBSERVACION = 9 + N_RAYOS

__all__ = ["Escena", "ACCIONES", "N_ACCIONES", "TAM_OBSERVACION"]
