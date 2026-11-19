"""Cuerpos del Agente: simulador, placa serial o consola.

Interfaz comun (todo lo que el Agente puede hacer con un cuerpo):

    avanzar(repeticiones)      girar(direccion, repeticiones)
    recoger()                  esperar(repeticiones)
    estado() -> dict           cerrar()

El backend serial habla un protocolo de linea, pensado para un Arduino o una
ESP32 con el firmware de `firmware_walle.ino`:

    PC -> placa :  AVANZAR 3\\n        GIRAR IZQ 2\\n   RECOGER\\n   ESTADO\\n
    placa -> PC :  OK {"bateria": 88.2, "basura": 3}\\n
                   ERR bateria baja\\n

`ESTADO` debe devolver un objeto JSON de una sola linea.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import Config


class ErrorActuador(RuntimeError):
    pass


class Actuador:
    nombre = "base"

    def avanzar(self, repeticiones: int = 1) -> dict:
        raise NotImplementedError

    def girar(self, direccion: str, repeticiones: int = 1) -> dict:
        raise NotImplementedError

    def recoger(self) -> dict:
        raise NotImplementedError

    def esperar(self, repeticiones: int = 1) -> dict:
        raise NotImplementedError

    def estado(self) -> dict:
        raise NotImplementedError

    def cerrar(self) -> None:
        pass

    @staticmethod
    def _limitar(repeticiones: int, maximo: int = 40) -> int:
        try:
            valor = int(repeticiones)
        except (TypeError, ValueError):
            valor = 1
        return max(1, min(valor, maximo))


class ActuadorConsola(Actuador):
    """Solo deja constancia de las ordenes: util sin robot a mano."""

    nombre = "consola"

    def __init__(self) -> None:
        self.registro: list[str] = []

    def _anotar(self, texto: str) -> dict:
        self.registro.append(texto)
        return {"ok": True, "accion": texto, "cuerpo": self.nombre}

    def avanzar(self, repeticiones: int = 1) -> dict:
        return self._anotar(f"avanzar x{self._limitar(repeticiones)}")

    def girar(self, direccion: str, repeticiones: int = 1) -> dict:
        lado = "izquierda" if str(direccion).lower().startswith("i") else "derecha"
        return self._anotar(f"girar {lado} x{self._limitar(repeticiones)}")

    def recoger(self) -> dict:
        return self._anotar("recoger")

    def esperar(self, repeticiones: int = 1) -> dict:
        return self._anotar(f"esperar x{self._limitar(repeticiones)}")

    def estado(self) -> dict:
        return {"ok": True, "cuerpo": self.nombre, "ordenes": len(self.registro)}


class ActuadorSimulado(Actuador):
    """Mueve el WALL-E del Simulador: mismo mundo que usa el Cerebro."""

    nombre = "simulado"

    def __init__(self, escenario: str = "chatarreria", semilla: int | None = None) -> None:
        from .rutas import conectar_simulador

        conectar_simulador()
        from simulador.entorno import Escena  # noqa: WPS433

        self.escena = Escena(escenario, semilla=semilla)
        self.ultimos_eventos: dict = {}

    def _paso(self, accion: int, repeticiones: int) -> dict:
        resumen = {"ok": True, "cuerpo": self.nombre, "pasos": 0,
                   "recogido": False, "entregado": False, "colision": 0}
        for _ in range(self._limitar(repeticiones, maximo=200)):
            eventos, terminado, truncado = self.escena.paso(accion)
            resumen["pasos"] += 1
            resumen["recogido"] |= eventos["recogido"]
            resumen["entregado"] |= eventos["entregado"]
            resumen["colision"] += int(eventos["colision"])
            self.ultimos_eventos = eventos
            if terminado or truncado:
                resumen["episodio_terminado"] = True
                break
        resumen.update(self.estado())
        return resumen

    def avanzar(self, repeticiones: int = 1) -> dict:
        return self._paso(0, repeticiones)

    def girar(self, direccion: str, repeticiones: int = 1) -> dict:
        accion = 1 if str(direccion).lower().startswith("i") else 2
        return self._paso(accion, repeticiones)

    def recoger(self) -> dict:
        return self._paso(3, 1)

    def esperar(self, repeticiones: int = 1) -> dict:
        return self._paso(4, repeticiones)

    def estado(self) -> dict:
        mundo = self.escena.mundo
        cercana = mundo.basura_mas_cercana()
        return {
            "ok": True,
            "cuerpo": self.nombre,
            "escenario": self.escena.nombre,
            "x": round(mundo.x, 2),
            "y": round(mundo.y, 2),
            "rumbo_grados": round(mundo.theta * 57.2958, 1),
            "bateria": round(mundo.bateria, 1),
            "cargando": mundo.llevando,
            "basura_restante": len(mundo.basuras),
            "recogidas": mundo.recogidas,
            "entregadas": mundo.entregadas,
            "distancia_contenedor": round(mundo.distancia_contenedor(), 2),
            "basura_cercana": (
                None if cercana is None else
                {"dx": round(cercana[0], 2), "dy": round(cercana[1], 2), "distancia": round(cercana[2], 2)}
            ),
            "distancia": round(mundo.distancia, 2),
            "calorias": round(mundo.calorias(), 4),
        }

    def reiniciar(self) -> None:
        self.escena.reiniciar()


class ActuadorSerial(Actuador):
    """Placa real por USB. Requiere pyserial (`pip install pyserial`)."""

    nombre = "serial"

    def __init__(self, puerto: str, baudios: int = 115200, tiempo_limite: float = 2.0) -> None:
        try:
            import serial  # type: ignore
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise ErrorActuador(
                "el backend serial necesita pyserial: pip install pyserial"
            ) from exc
        self._serial = serial.Serial(puerto, baudios, timeout=tiempo_limite)
        self._serial.reset_input_buffer()
        self.puerto = puerto
        self.baudios = baudios

    def _orden(self, linea: str) -> dict:
        self._serial.write((linea + "\n").encode("ascii", errors="replace"))
        self._serial.flush()
        respuesta = self._serial.readline().decode("utf-8", errors="replace").strip()
        if not respuesta:
            raise ErrorActuador(f"la placa no respondio a {linea!r}")
        if respuesta.startswith("ERR"):
            raise ErrorActuador(respuesta[3:].strip() or "error de la placa")
        if respuesta.startswith("OK"):
            resto = respuesta[2:].strip()
            if not resto:
                return {"ok": True, "cuerpo": self.nombre}
            try:
                datos = json.loads(resto)
            except json.JSONDecodeError:
                return {"ok": True, "cuerpo": self.nombre, "crudo": resto}
            if not isinstance(datos, dict):
                datos = {"valor": datos}
            datos.setdefault("ok", True)
            datos.setdefault("cuerpo", self.nombre)
            return datos
        raise ErrorActuador(f"respuesta inesperada: {respuesta[:120]!r}")

    def avanzar(self, repeticiones: int = 1) -> dict:
        return self._orden(f"AVANZAR {self._limitar(repeticiones)}")

    def girar(self, direccion: str, repeticiones: int = 1) -> dict:
        lado = "IZQ" if str(direccion).lower().startswith("i") else "DER"
        return self._orden(f"GIRAR {lado} {self._limitar(repeticiones)}")

    def recoger(self) -> dict:
        return self._orden("RECOGER")

    def esperar(self, repeticiones: int = 1) -> dict:
        return self._orden(f"ESPERAR {self._limitar(repeticiones)}")

    def estado(self) -> dict:
        return self._orden("ESTADO")

    def cerrar(self) -> None:
        try:
            self._serial.close()
        except Exception:  # noqa: BLE001 - cerrar nunca debe tumbar el proceso
            pass


def crear(config: Config, escenario: str | None = None) -> Actuador:
    cuerpo = config.cuerpo
    if cuerpo == "simulado":
        return ActuadorSimulado(escenario or config.escenario)
    if cuerpo == "serial":
        return ActuadorSerial(config.puerto_serial, config.baudios)
    if cuerpo == "consola":
        return ActuadorConsola()
    raise ErrorActuador(f"cuerpo desconocido: {cuerpo!r}")
