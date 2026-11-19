"""Rutas compartidas: el Cerebro importa la fisica del Simulador.

Las carpetas del repo llevan espacios y parentesis en el nombre, asi que no
son paquetes importables por nombre. Se agregan al sys.path y se importa el
paquete real (`simulador`, `cerebro`). Una sola definicion de la raiz.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
CARPETA_SIMULADOR = RAIZ_REPO / "Simulador Wall-E"
CARPETA_CEREBRO = Path(__file__).resolve().parents[1]
CARPETA_AGENTE = RAIZ_REPO / "Agente de IA Wall-E"
RUTA_MODELO = CARPETA_CEREBRO / "modelo" / "politica.json"


def conectar_simulador() -> Path:
    """Deja `import simulador` disponible y devuelve la carpeta."""
    ruta = str(CARPETA_SIMULADOR)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    return CARPETA_SIMULADOR
