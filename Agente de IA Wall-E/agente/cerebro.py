"""Reflejo: la politica PPO del Cerebro, usada como musculo del Agente.

Reparto de trabajo: el modelo de lenguaje piensa (decide que hacer y por que),
la politica PPO conduce (mueve las ruedas metro a metro). Eso mantiene el
bucle barato y rapido, que es justo lo que un robot necesita en el suelo.
"""
from __future__ import annotations

from pathlib import Path

from .rutas import conectar_cerebro


class Reflejo:
    def __init__(self, ruta_modelo: str | Path | None = None) -> None:
        conectar_cerebro()
        from cerebro.politica import PoliticaRefleja  # noqa: WPS433

        self.politica = PoliticaRefleja.cargar(ruta_modelo)
        self.acciones_ejecutadas = 0

    @classmethod
    def cargar_si_existe(cls, ruta_modelo: str | Path | None = None) -> "Reflejo | None":
        conectar_cerebro()
        from cerebro.rutas import RUTA_MODELO  # noqa: WPS433
        from cerebro.politica import PoliticaRefleja  # noqa: WPS433

        destino = Path(ruta_modelo) if ruta_modelo else RUTA_MODELO
        if not destino.is_file():
            return None
        reflejo = cls.__new__(cls)
        reflejo.politica = PoliticaRefleja.cargar(destino)
        reflejo.acciones_ejecutadas = 0
        return reflejo

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
