"""Simulador 2D de WALL-E: fisica, escenarios y visor pygame."""
from .entorno import TAM_OBSERVACION, Escena
from .fisica import ACCIONES, N_ACCIONES, PASOS_MAX, Mundo
from .escenarios import ESCENARIOS, crear

__all__ = [
    "Escena",
    "Mundo",
    "ACCIONES",
    "N_ACCIONES",
    "PASOS_MAX",
    "TAM_OBSERVACION",
    "ESCENARIOS",
    "crear",
]
