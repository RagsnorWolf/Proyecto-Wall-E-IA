"""
cerebro/test_link.py -- prueba del puente WALL-E sin robot y con robot.

Dos modos:

    python test_link.py --loopback
        Levanta un ESP32+UNO falsos en 127.0.0.1 y corre el protocolo completo
        contra ellos: camino feliz, rechazo del UNO, perdida de paquetes y
        timeout. Sirve para validar el cliente antes de tocar hardware.

    python test_link.py --host 192.168.1.50 --demo
        Habla con el robot real: ping, avance, servos, parada. Imprime el RTT
        de cada orden y la telemetria del ESP32.

Codigos de salida: 0 todo bien, 1 algun paso fallo.
"""

from __future__ import annotations

import argparse
import random
import socket
import threading
import time
from typing import Optional

from walle_link import (
    PROTO,
    DEFAULT_PORT,
    LinkError,
    LinkRejected,
    LinkTimeout,
    WalleLink,
)

TELEMETRY_INTERVAL_S = 0.1


# --------------------------------------------------------------------------
# ESP32 + UNO falsos, en localhost
# --------------------------------------------------------------------------
class LoopbackBridge:
    """Emula el puente entero: valida como el UNO y contesta como el ESP32."""

    def __init__(
        self,
        *,
        loss: float = 0.0,
        uno_delay_ms: float = 8.0,
        seed: int = 1234,
    ) -> None:
        self._rng = random.Random(seed)
        self._loss = max(0.0, min(1.0, float(loss)))
        self._delay_ms = float(uno_delay_ms)

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.settimeout(0.05)
        self.host, self.port = self._sock.getsockname()

        self._closing = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, name="loopback-bridge", daemon=True
        )

        self.motors = (0, 0)
        self.servos = [90, 90, 90, 90]
        self.last_id = 0
        self.log: list[str] = []

        self._peer: Optional[tuple[str, int]] = None
        self._dropped = 0
        self._handled = 0

    # -- ciclo -------------------------------------------------------------

    def start(self) -> "LoopbackBridge":
        self._thread.start()
        return self

    def close(self) -> None:
        self._closing.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "LoopbackBridge":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- bucle -------------------------------------------------------------

    def _loop(self) -> None:
        last_telemetry = 0.0
        while not self._closing.is_set():
            try:
                data, peer = self._sock.recvfrom(512)
            except socket.timeout:
                data = None
                peer = None
            except OSError:
                break

            if data is not None and peer is not None:
                self._peer = peer
                if self._rng.random() < self._loss:
                    self._dropped += 1
                else:
                    line = data.decode("ascii", "replace").strip()
                    self._handle(line, peer)

            now = time.monotonic()
            if self._peer is not None and now - last_telemetry >= TELEMETRY_INTERVAL_S:
                last_telemetry = now
                self._send_telemetry(self._peer)

    def _send(self, peer: tuple[str, int], text: str) -> None:
        try:
            self._sock.sendto(text.encode("ascii"), peer)
        except OSError:
            pass

    def _send_telemetry(self, peer: tuple[str, int]) -> None:
        uptime = int(time.monotonic() * 1000) & 0x7FFFFFFF
        rssi = -52 + self._rng.randint(-4, 4)
        text = f"{PROTO} T {uptime} {rssi} 1 {self.last_id} 0"
        self._send(peer, text)

    def _rtt(self) -> int:
        return int(self._delay_ms + self._rng.uniform(0.0, 2.0))

    def _ok(self, peer: tuple[str, int], msg_id: int, v1: int, v2: int) -> None:
        self._send(peer, f"{PROTO} {msg_id} OK {v1} {v2} {self._rtt()}")

    def _er(self, peer: tuple[str, int], msg_id: int, code: int) -> None:
        self._send(peer, f"{PROTO} {msg_id} ER {code} {self._rtt()}")

    def _handle(self, line: str, peer: tuple[str, int]) -> None:
        # Misma validacion que el sketch del UNO. Si esto acepta algo que el
        # UNO rechaza, la prueba miente.
        if not line.startswith(PROTO + " "):
            return
        fields = line[len(PROTO) + 1:].split()
        if len(fields) < 2:
            return

        try:
            msg_id = int(fields[0])
        except ValueError:
            return
        if msg_id <= 0:
            return

        op = fields[1]
        if len(op) != 1:
            self._er(peer, msg_id, 2)
            return

        args: list[Optional[int]] = []
        for token in fields[2:]:
            try:
                args.append(int(token))
            except ValueError:
                args.append(None)

        self._handled += 1
        self.last_id = msg_id
        self.log.append(line)

        if op == "M":
            if len(args) < 2 or args[0] is None or args[1] is None:
                self._er(peer, msg_id, 1)
                return
            left, right = int(args[0]), int(args[1])
            if not (-1000 <= left <= 1000 and -1000 <= right <= 1000):
                self._er(peer, msg_id, 3)
                return
            self.motors = (left, right)
            self._ok(peer, msg_id, left, right)
            return

        if op == "V":
            if len(args) < 2 or args[0] is None or args[1] is None:
                self._er(peer, msg_id, 1)
                return
            channel, degrees = int(args[0]), int(args[1])
            if not (0 <= channel <= 3 and 0 <= degrees <= 180):
                self._er(peer, msg_id, 3)
                return
            self.servos[channel] = degrees
            self._ok(peer, msg_id, channel, degrees)
            return

        if op == "X":
            self.motors = (0, 0)
            self._ok(peer, msg_id, 0, 0)
            return

        if op == "P":
            self._ok(peer, msg_id, 0, 0)
            return

        self._er(peer, msg_id, 2)

    # -- informe -----------------------------------------------------------

    def summary(self) -> str:
        return (
            f"ordenes ejecutadas={self._handled} descartadas={self._dropped} "
            f"motores={self.motors} servos={self.servos}"
        )


# --------------------------------------------------------------------------
# Pruebas
# --------------------------------------------------------------------------
class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            print(f"  [OK]   {name}" + (f"  ({detail})" if detail else ""))
        else:
            self.failed += 1
            print(f"  [FALLO] {name}" + (f"  ({detail})" if detail else ""))


def run_loopback(args: argparse.Namespace) -> int:
    report = Report()

    print("== 1. camino feliz: ping, motores, servo, parada ==")
    with LoopbackBridge(loss=0.0) as bridge:
        with WalleLink(bridge.host, bridge.port) as link:
            try:
                ack = link.ping()
                report.check("ping con ACK", ack.rtt_ms >= 0, f"rtt={ack.rtt_ms} ms")
            except LinkError as exc:
                report.check("ping con ACK", False, str(exc))

            try:
                ack = link.move(620, -620)
                report.check(
                    "giro sobre el sitio aplicado",
                    ack.v1 == 620 and ack.v2 == -620 and bridge.motors == (620, -620),
                    f"puente={bridge.motors}",
                )
            except LinkError as exc:
                report.check("giro sobre el sitio aplicado", False, str(exc))

            try:
                ack = link.servo(1, 35)
                report.check(
                    "servo 1 a 35 grados",
                    ack.v1 == 1 and ack.v2 == 35 and bridge.servos[1] == 35,
                    f"servos={bridge.servos}",
                )
            except LinkError as exc:
                report.check("servo 1 a 35 grados", False, str(exc))

            try:
                link.stop()
                report.check("parada aplicada", bridge.motors == (0, 0), f"puente={bridge.motors}")
            except LinkError as exc:
                report.check("parada aplicada", False, str(exc))

            time.sleep(0.25)
            tel = link.telemetry()
            report.check(
                "telemetria recibida",
                tel is not None and tel.uno_ok,
                f"rssi={tel.rssi} dBm" if tel else "sin telemetria",
            )

    print("== 2. el UNO rechaza: op desconocida ==")
    with LoopbackBridge(loss=0.0) as bridge:
        with WalleLink(bridge.host, bridge.port) as link:
            try:
                link._exchange("Q", 0, 0)
                report.check("op invalida devuelve ER", False, "contesto OK")
            except LinkRejected as exc:
                report.check("op invalida devuelve ER", exc.code == 2, f"codigo={exc.code}")
            except LinkError as exc:
                report.check("op invalida devuelve ER", False, str(exc))

    print("== 3. perdida del 40%: el reintento salva la orden ==")
    with LoopbackBridge(loss=0.4, seed=7) as bridge:
        with WalleLink(bridge.host, bridge.port, retries=3) as link:
            delivered = 0
            for _ in range(10):
                try:
                    link.move(300, 300)
                    delivered += 1
                except LinkError:
                    pass
            report.check(
                "8 de 10 ordenes sobreviven al 40% de perdida",
                delivered >= 8,
                f"{delivered}/10  descartadas={bridge._dropped}",
            )

    print("== 4. enlace muerto: timeout limpio, sin colgarse ==")
    with LoopbackBridge(loss=1.0) as bridge:
        with WalleLink(bridge.host, bridge.port, ack_timeout=0.08, retries=1) as link:
            started = time.monotonic()
            try:
                link.ping()
                report.check("timeout se dispara", False, "contesto con perdida total")
            except LinkTimeout:
                elapsed = time.monotonic() - started
                report.check(
                    "timeout se dispara",
                    0.12 <= elapsed <= 0.60,
                    f"{elapsed * 1000:.0f} ms",
                )
            except LinkError as exc:
                report.check("timeout se dispara", False, str(exc))

    print()
    print(f"resultado: {report.passed} OK, {report.failed} fallos")
    return 0 if report.failed == 0 else 1


def run_real(args: argparse.Namespace) -> int:
    report = Report()

    def log(message: str) -> None:
        if args.verbose:
            print(f"    {message}")

    print(f"== enlace real contra {args.host}:{args.port} ==")
    with WalleLink(args.host, args.port, logger=log) as link:
        try:
            ack = link.ping()
            report.check("ping", True, f"rtt={ack.rtt_ms} ms")
        except LinkError as exc:
            report.check("ping", False, str(exc))
            print()
            print("El ESP32 no contesta. Revisar: alimentacion, SSID en config.h,")
            print("IP correcta y que el monitor serie del ESP32 muestre la IP.")
            return 1

        tel = link.telemetry()
        if tel is not None:
            print(f"  telemetria: rssi={tel.rssi} dBm  uno_ok={tel.uno_ok}  cola={tel.queue}")
            report.check("UNO responde detras del ESP32", tel.uno_ok, "uno_ok=1" if tel.uno_ok else "uno_ok=0")
        else:
            print("  sin telemetria: el ESP32 no esta mandando el latido a 10 Hz")
            report.check("telemetria", False, "no llego ningun paquete T")

        if not args.demo:
            print()
            print(f"resultado: {report.passed} OK, {report.failed} fallos")
            return 0 if report.failed == 0 else 1

        print("-- avance 1.2 s --")
        try:
            link.move(500, 500)
            time.sleep(1.2)
        except LinkError as exc:
            report.check("avance", False, str(exc))
        finally:
            try:
                link.stop()
            except LinkError:
                pass
        report.check("avance", True, "motores en 500/500 y parada enviada")

        print("-- barrido de servos --")
        try:
            for channel in range(4):
                for degrees in (40, 90, 140, 90):
                    link.servo(channel, degrees)
                    time.sleep(0.35)
            report.check("barrido de 4 servos", True, "16 posiciones")
        except LinkError as exc:
            report.check("barrido de 4 servos", False, str(exc))

        print("-- giro sobre el sitio --")
        try:
            link.move(-600, 600)
            time.sleep(1.0)
            link.stop()
            report.check("giro", True, "1 s a -600/600")
        except LinkError as exc:
            report.check("giro", False, str(exc))

        print(f"  stats: {link.stats}")

    print()
    print(f"resultado: {report.passed} OK, {report.failed} fallos")
    return 0 if report.failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba del puente WALL-E")
    parser.add_argument("--loopback", action="store_true", help="probar contra el puente falso")
    parser.add_argument("--host", default=None, help="IP del ESP32")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="puerto UDP")
    parser.add_argument("--demo", action="store_true", help="mover el robot de verdad")
    parser.add_argument("--verbose", action="store_true", help="mostrar trazas del enlace")
    args = parser.parse_args()

    if args.loopback:
        return run_loopback(args)
    if args.host:
        return run_real(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
