"""Percepcion: como el Agente sabe donde esta parado.

Tres backends:
  simulado -> lee el estado del Simulador (siempre disponible, sirve para probar)
  manual   -> el operador describe lo que ve (sin camara, sin inventos)
  camara   -> captura con opencv y, si hay modelo de vision, lo resume

La camara es opcional: si falta opencv, se dice y se cae al backend manual.
"""
from __future__ import annotations

import base64
from typing import Callable

from .actuadores import Actuador, ActuadorSimulado


class Percepcion:
    nombre = "base"

    def describir(self) -> str:
        raise NotImplementedError


class PercepcionSimulada(Percepcion):
    nombre = "simulado"

    def __init__(self, actuador: ActuadorSimulado) -> None:
        self.actuador = actuador

    def describir(self) -> str:
        estado = self.actuador.estado()
        cercana = estado.get("basura_cercana")
        if cercana:
            basura = (
                f"basura mas cercana a {cercana['distancia']} m "
                f"(desplazamiento dx={cercana['dx']}, dy={cercana['dy']})"
            )
        else:
            basura = "no quedan cubos de basura"
        return (
            f"Cuerpo: simulador en {estado['escenario']}. "
            f"Posicion ({estado['x']}, {estado['y']}), rumbo {estado['rumbo_grados']} grados. "
            f"Bateria {estado['bateria']}%, cargando {estado['cargando']} de 2 cubos. "
            f"{estado['basura_restante']} cubos en el suelo, {estado['entregadas']} entregados. "
            f"Contenedor a {estado['distancia_contenedor']} m. {basura}. "
            f"Recorrido {estado['distancia']} m, {estado['calorias']} kcal."
        )


class PercepcionManual(Percepcion):
    nombre = "manual"

    def __init__(self, lector: Callable[[str], str] | None = None) -> None:
        self._lector = lector or (lambda pregunta: input(pregunta))

    def describir(self) -> str:
        return self._lector("Describe lo que ves (una linea): ").strip() or "no hay descripcion"


class PercepcionCamara(Percepcion):
    nombre = "camara"

    def __init__(self, indice: int = 0) -> None:
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "percepcion por camara: falta opencv (pip install opencv-python). "
                "Mientras tanto usa percepcion 'manual' o 'simulado'."
            ) from exc
        self._cv2 = cv2
        self.captura = cv2.VideoCapture(indice)
        if not self.captura.isOpened():
            raise RuntimeError(f"no pude abrir la camara {indice}")

    def fotograma_base64(self) -> str:
        ok, fotograma = self.captura.read()
        if not ok:
            raise RuntimeError("la camara no devolvio imagen")
        ok, jpg = self._cv2.imencode(".jpg", fotograma, [int(self._cv2.IMWRITE_JPEG_QUALITY), 70])
        if not ok:
            raise RuntimeError("no pude codificar el fotograma")
        return base64.b64encode(jpg.tobytes()).decode("ascii")

    def describir(self) -> str:
        return (
            "Camara activa. Fotograma lista para un modelo de vision; "
            "sin resumen automatico configurado."
        )

    def cerrar(self) -> None:
        self.captura.release()


def crear_percepcion(actuador: Actuador, modo: str = "auto") -> Percepcion:
    if modo == "auto":
        if isinstance(actuador, ActuadorSimulado):
            return PercepcionSimulada(actuador)
        return PercepcionManual()
    if modo == "simulado":
        if not isinstance(actuador, ActuadorSimulado):
            raise ValueError("la percepcion 'simulado' necesita un cuerpo simulado")
        return PercepcionSimulada(actuador)
    if modo == "manual":
        return PercepcionManual()
    if modo == "camara":
        return PercepcionCamara()
    raise ValueError(f"modo de percepcion desconocido: {modo!r}")
