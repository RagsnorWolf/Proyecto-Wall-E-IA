"""Recompensa del Cerebro: actividad fisica real, no dar vueltas en el sitio.

La pieza central es la recompensa por cobertura: se paga por entrar en celdas
del mapa que no se habian visitado. Rodar en circulos no descubre nada y por
tanto no paga. Eso es lo que evita la politica degenerada clasica del PPO
cuando se premia la distancia recorrida a pelo.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PesosRecompensa:
    celda_nueva: float = 0.25      # por celda de 0.5x0.5 m descubierta
    por_metro: float = 0.02        # forma suave de avance mientras explora
    recoger: float = 2.0           # cada cubo agarrado
    entregar: float = 10.0         # cada cubo depositado en el contenedor
    limpieza_total: float = 5.0    # bonus por dejar el mapa sin basura
    paso: float = -0.01            # presiona a no perder tiempo
    colision: float = -0.15        # golpe contra muro o borde
    bateria_baja: float = -0.05    # por paso con bateria bajo el 10%
    sin_bateria: float = -5.0      # se quedo tirado


class CalculadoraRecompensa:
    """Convierte eventos del mundo en una senal escalar. Sin estado global."""

    def __init__(self, pesos: PesosRecompensa | None = None) -> None:
        self.pesos = pesos or PesosRecompensa()

    def reiniciar(self) -> None:
        """Reservado: la recompensa es sin memoria, se deja por simetria."""

    def evaluar(self, eventos: dict, mundo, terminado: bool) -> float:
        p = self.pesos
        total = p.paso
        total += p.por_metro * float(eventos["movido"])
        if eventos["nueva_celda"]:
            total += p.celda_nueva
        if eventos["recogido"]:
            total += p.recoger
        if eventos["entregado"]:
            total += p.entregar
        if eventos["colision"]:
            total += p.colision
        if eventos["sin_bateria"]:
            total += p.sin_bateria
        elif mundo.bateria < 10.0:
            total += p.bateria_baja
        if terminado and not mundo.basuras:
            total += p.limpieza_total
        return total
