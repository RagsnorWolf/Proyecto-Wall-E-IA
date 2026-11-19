"""Politica entrenada, lista para usarse como reflejo rapido.

Sin acoplamiento a la estructura del repo: la ruta del checkpoint se resuelve
por argumento o, si no, contra `modelo/politica.json` al lado de este paquete.
Asi el mismo archivo funciona en el Cerebro y en la copia vendorizada del
Agente.
"""
from __future__ import annotations

from pathlib import Path

from .ppo import AgentePPO


def ruta_por_defecto() -> Path:
    """`<carpeta que contiene al paquete>/modelo/politica.json`."""
    return Path(__file__).resolve().parents[1] / "modelo" / "politica.json"


class PoliticaRefleja:
    """Carga un checkpoint PPO (JSON) y devuelve acciones sin muestreo."""

    def __init__(self, agente: AgentePPO) -> None:
        self.agente = agente

    @classmethod
    def cargar(cls, ruta: str | Path | None = None) -> "PoliticaRefleja":
        destino = Path(ruta) if ruta else ruta_por_defecto()
        if not destino.is_file():
            raise FileNotFoundError(
                f"no hay modelo en {destino}. Entrena primero: "
                "python entrenar_ppo.py --pasos 60000"
            )
        return cls(AgentePPO.cargar(destino))

    @classmethod
    def cargar_si_existe(cls, ruta: str | Path | None = None) -> "PoliticaRefleja | None":
        destino = Path(ruta) if ruta else ruta_por_defecto()
        if not destino.is_file():
            return None
        return cls(AgentePPO.cargar(destino))

    def actuar(self, obs) -> int:
        accion, _, _ = self.agente.actuar(list(obs), determinista=True)
        return accion
