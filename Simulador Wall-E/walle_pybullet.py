#!/usr/bin/env python3
"""walle_pybullet.py - una vista de pybullet atada a una conexion concreta.

PyBullet identifica cada conexion con un `physicsClientId`. Todas sus funciones
lo aceptan y, si no se pasa, usan el cliente 0. Por eso dos entornos creados en
el mismo proceso terminan compartiendo mundo: el segundo crea su robot en el
cliente del primero, y despues lee posiciones y rayos del mundo equivocado.

`Cliente` envuelve el modulo y rellena `physicsClientId` en cada llamada que lo
acepte. Las funciones puras de geometria (cuaterniones, matrices) no lo aceptan:
se descubren solas la primera vez, reintentando sin el parametro, y quedan
anotadas para no volver a fallar.

Por que no se mira la firma: las funciones de pybullet son builtins de C, sin
`__signature__`. `inspect.signature` levanta ValueError y cualquier deteccion
basada en ella devuelve "no acepta cliente" para todas, que es exactamente el
bug que este modulo existe para arreglar.

Uso:

    import pybullet as p
    from walle_pybullet import Cliente

    client_id = p.connect(p.DIRECT)
    pb = Cliente(client_id)
    pb.setGravity(0, 0, -9.81)      # -> setGravity(..., physicsClientId=client_id)
    pb.getQuaternionFromEuler([0, 0, 1.57])   # descubierta como pura
    pb.GEOM_BOX                     # constante, pasa sin tocar
"""
from __future__ import annotations

import functools
from typing import Any

__all__ = ["Cliente"]


class Cliente:
    """Modulo pybullet con el cliente fijado.

    Solo se envuelven las funciones. Las constantes y los tipos se devuelven
    tal cual, asi que `pb.GEOM_BOX`, `pb.GUI` y `pb.getAPIVersion()` siguen
    funcionando despues de haber sido descubiertos.
    """

    __slots__ = ("_client_id", "_modulo", "_cache", "_puras")

    def __init__(self, client_id: int, modulo: Any | None = None) -> None:
        if modulo is None:
            import pybullet as modulo  # noqa: PLC0415 - import tardio a proposito

        object.__setattr__(self, "_client_id", int(client_id))
        object.__setattr__(self, "_modulo", modulo)
        object.__setattr__(self, "_cache", {})
        object.__setattr__(self, "_puras", set())

    # ---------------------------------------------------------------- #
    # Lectura
    # ---------------------------------------------------------------- #
    @property
    def client_id(self) -> int:
        return self._client_id  # type: ignore[attr-defined]

    def __getattr__(self, nombre: str) -> Any:
        cache: dict[str, Any] = self._cache  # type: ignore[attr-defined]
        if nombre in cache:
            return cache[nombre]

        valor = getattr(self._modulo, nombre)  # type: ignore[attr-defined]
        if not callable(valor):
            cache[nombre] = valor
            return valor

        cliente = self._client_id  # type: ignore[attr-defined]
        puras: set[str] = self._puras  # type: ignore[attr-defined]

        if nombre in puras:
            cache[nombre] = valor
            return valor

        @functools.wraps(valor)
        def llamada(*args: Any, **kwargs: Any) -> Any:
            kwargs.setdefault("physicsClientId", cliente)
            try:
                return valor(*args, **kwargs)
            except TypeError:
                # Puede ser una funcion pura o un error real de los argumentos.
                # Se reintenta sin cliente: si el reintento tambien falla, el
                # error que vale es el original.
                sin_cliente = dict(kwargs)
                sin_cliente.pop("physicsClientId", None)
                try:
                    resultado = valor(*args, **sin_cliente)
                except TypeError:
                    raise
                puras.add(nombre)
                cache[nombre] = valor
                return resultado

        cache[nombre] = llamada
        return llamada

    # ---------------------------------------------------------------- #
    # Comodidad
    # ---------------------------------------------------------------- #
    def __repr__(self) -> str:
        return f"Cliente(pybullet, physicsClientId={self._client_id})"

    def __dir__(self) -> list[str]:
        return sorted(set(dir(self._modulo)) | {"client_id"})  # type: ignore[attr-defined]
