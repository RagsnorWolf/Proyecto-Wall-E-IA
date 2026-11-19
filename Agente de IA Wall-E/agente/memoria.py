"""Memoria del Agente en SQLite: eventos del dia y hechos que debe recordar.

Dos tablas y ningun ORM. Los eventos son el registro cronologico (que hizo y
que respondio el modelo); los hechos son frases cortas reutilizables, con
busqueda por palabra clave y por solapamiento para no depender de embeddings.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    momento REAL NOT NULL,
    tipo TEXT NOT NULL,
    texto TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eventos_momento ON eventos(momento);

CREATE TABLE IF NOT EXISTS hechos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    momento REAL NOT NULL,
    clave TEXT NOT NULL,
    texto TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hechos_clave ON hechos(clave);
"""


class Memoria:
    def __init__(self, ruta: str | Path) -> None:
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.conexion = sqlite3.connect(self.ruta)
        self.conexion.row_factory = sqlite3.Row
        self.conexion.execute("PRAGMA journal_mode=WAL")
        self.conexion.executescript(ESQUEMA)
        self.conexion.commit()

    # --- escritura --------------------------------------------------------
    def registrar(self, tipo: str, texto: str) -> None:
        self.conexion.execute(
            "INSERT INTO eventos(momento, tipo, texto) VALUES (?, ?, ?)",
            (time.time(), tipo, texto[:4000]),
        )
        self.conexion.commit()

    def recordar(self, texto: str, clave: str = "") -> int:
        clave = clave or self._primera_palabra(texto)
        cursor = self.conexion.execute(
            "INSERT INTO hechos(momento, clave, texto) VALUES (?, ?, ?)",
            (time.time(), clave.lower(), texto[:600]),
        )
        self.conexion.commit()
        return int(cursor.lastrowid or 0)

    # --- lectura ----------------------------------------------------------
    def buscar(self, consulta: str, limite: int = 5) -> list[str]:
        """Devuelve hechos que comparten palabras con la consulta, mejor primero."""
        terminos = {p for p in _palabras(consulta) if len(p) > 2}
        filas = self.conexion.execute("SELECT texto FROM hechos ORDER BY id DESC LIMIT 200").fetchall()
        puntuados: list[tuple[float, str]] = []
        for fila in filas:
            texto = fila["texto"]
            comunes = terminos & set(_palabras(texto))
            if comunes:
                puntuados.append((len(comunes), texto))
        puntuados.sort(key=lambda par: par[0], reverse=True)
        return [texto for _, texto in puntuados[:limite]]

    def ultimos_eventos(self, limite: int = 10) -> list[dict]:
        filas = self.conexion.execute(
            "SELECT momento, tipo, texto FROM eventos ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
        return [{"momento": f["momento"], "tipo": f["tipo"], "texto": f["texto"]} for f in filas]

    def resumen(self) -> str:
        """Texto corto para meter en el prompt sin arrastrar toda la tabla."""
        hechos = self.conexion.execute("SELECT texto FROM hechos ORDER BY id DESC LIMIT 8").fetchall()
        if not hechos:
            return "sin hechos guardados"
        return "; ".join(f"\"{f['texto']}\"" for f in hechos)

    def cerrar(self) -> None:
        self.conexion.close()

    # --- utilidades -------------------------------------------------------
    @staticmethod
    def _primera_palabra(texto: str) -> str:
        palabras = _palabras(texto)
        return palabras[0] if palabras else "nota"


def _palabras(texto: str) -> list[str]:
    limpio = []
    actual = []
    for caracter in texto.lower():
        if caracter.isalnum() or caracter in "áéíóúüñ":
            actual.append(caracter)
        elif actual:
            limpio.append("".join(actual))
            actual = []
    if actual:
        limpio.append("".join(actual))
    return limpio
