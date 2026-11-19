"""Rutas del Agente: la raiz del repo y el acceso al Simulador.

Las carpetas del repo llevan espacios en el nombre, asi que se agregan al
sys.path y se importa el paquete real. Una sola definicion de la raiz.
"""
from __future__ import annotations

import sys
from pathlib import Path

CARPETA_AGENTE = Path(__file__).resolve().parents[1]
RAIZ_REPO = CARPETA_AGENTE.parent
CARPETA_SIMULADOR = RAIZ_REPO / "Simulador Wall-E"
CARPETA_CEREBRO = RAIZ_REPO / "Cerebro Wall-E (Actividad Fisica + PPO) .py"


def conectar_simulador() -> Path:
    ruta = str(CARPETA_SIMULADOR)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    return CARPETA_SIMULADOR


def conectar_cerebro() -> Path:
    ruta = str(CARPETA_CEREBRO)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    return CARPETA_CEREBRO
