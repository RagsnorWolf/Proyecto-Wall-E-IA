"""Rutas del Cerebro: encuentra la fisica del Simulador.

Dos modos, sin tocar codigo:
  - repo completo: usa la carpeta hermana `Simulador Wall-E`
  - carpeta sola : usa la copia vendorizada en `vendor/simulador` (la crea
    `sincronizar.py` desde la raiz del repo)

Las carpetas del repo llevan espacios y parentesis, asi que no son paquetes
importables por nombre: se agregan al sys.path y se importa `simulador`.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
CARPETA_CEREBRO = Path(__file__).resolve().parents[1]
CARPETA_AGENTE = RAIZ_REPO / "Agente de IA Wall-E"
CARPETA_SIMULADOR = RAIZ_REPO / "Simulador Wall-E"
VENDOR = CARPETA_CEREBRO / "vendor"


def raiz_simulador() -> Path | None:
    """Carpeta que contiene el paquete `simulador` que se va a usar."""
    if (VENDOR / "simulador" / "fisica.py").is_file():
        return VENDOR
    if (CARPETA_SIMULADOR / "simulador" / "fisica.py").is_file():
        return CARPETA_SIMULADOR
    return None


def conectar_simulador() -> Path:
    raiz = raiz_simulador()
    if raiz is None:
        raise ImportError(
            "no encuentro el paquete `simulador`. Si bajaste solo esta carpeta, "
            "corre `python sincronizar.py` desde la raiz del repo, o copia "
            "`Simulador Wall-E/simulador` a `vendor/simulador`."
        )
    ruta = str(raiz)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    return raiz
