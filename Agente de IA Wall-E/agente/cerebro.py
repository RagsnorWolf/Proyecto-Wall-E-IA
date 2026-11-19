"""Reflejo: la politica PPO del Cerebro, usada como musculo del Agente.

Reparto de trabajo: el modelo de lenguaje piensa (decide que hacer y por que),
la politica PPO conduce (mueve las ruedas metro a metro). Eso mantiene el
bucle barato y rapido, que es justo lo que un robot necesita en el suelo.

El checkpoint se busca, en orden, en:
  1. la ruta que se pase a mano
  2. `Agente de IA Wall-E/modelo/politica.json`  (carpeta suelta)
  3. `Cerebro Wall-E .../modelo/politica.json`   (repo completo)
"""
from __future__ import annotations

from pathlib import Path

from .rutas import CARPETA_AGENTE, CARPETA_CEREBRO, conectar_cerebro


def rutas_posibles(ruta: str | Path | None = None) -> list[Path]:
    if ruta:
        return [Path(ruta)]
    return [
        CARPETA_AGENTE / "modelo" / "politica.json",
        CARPETA_CEREBRO / "modelo" / "politica.json",
    ]


def primera_existente(ruta: str | Path | None = None) -> Path | None:
    for candidata in rutas_posibles(ruta):
        if candidata.is_file():
            return candidata
    return None


class Reflejo:
    def __init__(self, ruta_modelo: str | Path | None = None) -> None:
        conectar_cerebro()
        from cerebro.politica import PoliticaRefleja  # noqa: WPS433

        destino = primera_existente(ruta_modelo)
        if destino is None:
            raise FileNotFoundError(
                f"no hay checkpoint en {[str(r) for r in rutas_posibles(ruta_modelo)]}"
            )
        self.politica = PoliticaRefleja.cargar(destino)
        self.ruta = destino
        self.acciones_ejecutadas = 0

    @classmethod
    def cargar_si_existe(cls, ruta_modelo: str | Path | None = None) -> "Reflejo | None":
        if primera_existente(ruta_modelo) is None:
            return None
        return cls(ruta_modelo)

    def pasos(self, actuador, pasos: int = 50) -> dict:
        """Conduce el actuador simulado durante N pasos con la politica."""
        pasos = max(1, min(int(pasos), 400))
        resumen = {"ok": True, "pasos": 0, "entregas": 0, "recogidas": 0, "choques": 0}
        for _ in range(pasos):
            observacion = actuador.escena.observacion()
            accion = self.politica.actuar(observacion)
            eventos, terminado, truncado = actuador.escena.paso(accion)
            resumen["pasos"] += 1
            resumen["choques"] += int(eventos["colision"])
            resumen["recogidas"] += int(eventos["recogido"])
            resumen["entregas"] += int(eventos["entregado"])
            self.acciones_ejecutadas += 1
            if terminado or truncado:
                resumen["episodio_terminado"] = True
                break
        resumen.update(actuador.estado())
        return resumen
