"""Rutas del Agente: encuentra el Simulador y el Cerebro.

Orden de busqueda:
  1. `vendor/` dentro de esta carpeta (modo carpeta suelta)
  2. las carpetas hermanas del repo (modo repo completo)

Nada de rutas absolutas ni de variables de entorno: el que copia la carpeta se
lleva todo lo que necesita.
"""
from __future__ import annotations

import sys
from pathlib import Path

CARPETA_AGENTE = Path(__file__).resolve().parents[1]
RAIZ_REPO = CARPETA_AGENTE.parent
VENDOR = CARPETA_AGENTE / "vendor"

CARPETA_SIMULADOR = RAIZ_REPO / "Simulador Wall-E"
CARPETA_CEREBRO = RAIZ_REPO / "Cerebro Wall-E (Actividad Fisica + PPO) .py"


def raiz_simulador() -> Path | None:
    if (VENDOR / "simulador" / "fisica.py").is_file():
        return VENDOR
    if (CARPETA_SIMULADOR / "simulador" / "fisica.py").is_file():
        return CARPETA_SIMULADOR
    return None


def raiz_cerebro() -> Path | None:
    if (VENDOR / "cerebro" / "politica.py").is_file():
        return VENDOR
    if (CARPETA_CEREBRO / "cerebro" / "politica.py").is_file():
        return CARPETA_CEREBRO
    return None


def _agregar(raiz: Path | None) -> Path | None:
    if raiz is None:
        return None
    ruta = str(raiz)
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
    return raiz


def conectar_simulador() -> Path:
    raiz = _agregar(raiz_simulador())
    if raiz is None:
        raise ImportError(
            "no encuentro el paquete `simulador`. Corre `python sincronizar.py` "
            "desde la raiz del repo, o copia `Simulador Wall-E/simulador` a "
            "`Agente de IA Wall-E/vendor/simulador`."
        )
    return raiz


def conectar_cerebro() -> Path:
    raiz = _agregar(raiz_cerebro())
    if raiz is None:
        raise ImportError(
            "no encuentro el paquete `cerebro`. Corre `python sincronizar.py` "
            "desde la raiz del repo, o copia los archivos de la politica a "
            "`Agente de IA Wall-E/vendor/cerebro`."
        )
    return raiz
