"""Configuracion del Agente: JSON en disco, variables de entorno por encima.

Prioridad: argumento -> variable de entorno -> archivo -> valor por defecto.
La clave de API nunca se escribe en el JSON; se lee del entorno.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

CARPETA = Path(__file__).resolve().parents[1]
CONFIG_POR_DEFECTO = CARPETA / "config.json"
CONFIG_EJEMPLO = CARPETA / "config.ejemplo.json"


@dataclass
class Config:
    # --- modelo de lenguaje (API compatible con OpenAI) ---
    proveedor: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    modelo: str = "gpt-4o-mini"
    variable_clave: str = "WALLE_API_KEY"
    temperatura: float = 0.2
    max_tokens: int = 1200
    tiempo_limite: float = 60.0
    reintentos: int = 3
    # --- cuerpo del robot ---
    cuerpo: str = "simulado"          # simulado | serial | consola
    puerto_serial: str = "COM5"
    baudios: int = 115200
    escenario: str = "chatarreria"
    # --- politica entrenada ---
    modelo_politica: str = ""          # vacio = modelo/politica.json del Cerebro
    # --- bucle ---
    max_turnos: int = 12
    memoria: str = ""                  # vacio = datos/memoria.db
    idioma: str = "es"

    def ruta_memoria(self) -> Path:
        return Path(self.memoria) if self.memoria else CARPETA / "datos" / "memoria.db"

    def ruta_politica(self) -> Path:
        if self.modelo_politica:
            return Path(self.modelo_politica)
        return CARPETA.parent / "Cerebro Wall-E (Actividad Fisica + PPO) .py" / "modelo" / "politica.json"


def _leer_json(ruta: Path) -> dict:
    if not ruta.is_file():
        return {}
    with ruta.open("r", encoding="utf-8") as f:
        datos = json.load(f)
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta} debe contener un objeto JSON")
    return datos


def cargar(ruta: str | Path | None = None) -> Config:
    """Carga configuracion. Ignora claves desconocidas del JSON en vez de reventar."""
    destino = Path(ruta) if ruta else CONFIG_POR_DEFECTO
    datos = _leer_json(destino)
    validas = {f.name for f in fields(Config)}
    limpias = {k: v for k, v in datos.items() if k in validas}
    config = Config(**limpias)

    # Variables de entorno puntuales, utiles para CI y para no tocar el archivo.
    if os.environ.get("WALLE_MODELO"):
        config.modelo = os.environ["WALLE_MODELO"]
    if os.environ.get("WALLE_BASE_URL"):
        config.base_url = os.environ["WALLE_BASE_URL"].rstrip("/")
    if os.environ.get("WALLE_CUERPO"):
        config.cuerpo = os.environ["WALLE_CUERPO"]
    if os.environ.get("WALLE_PORT_SERIAL"):
        config.puerto_serial = os.environ["WALLE_PORT_SERIAL"]

    if config.cuerpo not in ("simulado", "serial", "consola"):
        raise ValueError(f"cuerpo desconocido: {config.cuerpo!r}")
    if not 0.0 <= config.temperatura <= 2.0:
        raise ValueError("temperatura fuera de rango")
    if config.max_turnos < 1:
        raise ValueError("max_turnos debe ser >= 1")
    return config


def guardar_ejemplo(ruta: str | Path | None = None) -> Path:
    """Escribe un config de ejemplo sin la clave de API."""
    destino = Path(ruta) if ruta else CONFIG_EJEMPLO
    destino.write_text(json.dumps(asdict(Config()), indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    return destino
