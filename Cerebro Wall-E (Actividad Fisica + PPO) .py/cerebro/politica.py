"""Politica entrenada, lista para que el Agente la use como reflejo rapido."""
from __future__ import annotations

from pathlib import Path

from .ppo import AgentePPO
from .rutas import RUTA_MODELO


class PoliticaRefleja:
    """Carga un checkpoint PPO (JSON) y devuelve acciones sin muestreo."""

    def __init__(self, agente: AgentePPO) -> None:
        self.agente = agente

    @classmethod
    def cargar(cls, ruta: str | Path | None = None) -> "PoliticaRefleja":
        destino = Path(ruta) if ruta else RUTA_MODELO
        if not destino.is_file():
            raise FileNotFoundError(
                f"no hay modelo en {destino}. Entrena primero: "
                "python entrenar_ppo.py --pasos 60000"
            )
        return cls(AgentePPO.cargar(destino))

    @classmethod
    def cargar_si_existe(cls, ruta: str | Path | None = None) -> "PoliticaRefleja | None":
        destino = Path(ruta) if ruta else RUTA_MODELO
        if not destino.is_file():
            return None
        return cls(AgentePPO.cargar(destino))

    def actuar(self, obs) -> int:
        accion, _, _ = self.agente.actuar(list(obs), determinista=True)
        return accion
