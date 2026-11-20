"""
cerebro/walle_link.py -- cliente UDP del puente WALL-E.

Lado PC del protocolo descrito en ../protocolo.md:

    PC --UDP--> ESP32 --UART--> UNO
    PC <--UDP-- ESP32 <--UART-- UNO

Una orden no se da por buena hasta que el ACK del UNO vuelve convertido en
respuesta del ESP32. Si el ESP32 esta vivo pero el UNO no, la orden termina en
LinkRejected / LinkTimeout: eso es exactamente la verificacion de ida y vuelta
que pide el diseno.

Uso:

    from walle_link import WalleLink

    with WalleLink("192.168.1.50") as link:
        link.ping()
        link.move(600, 600)      # adelante
        link.servo(0, 40)
        link.stop()

Todos los metodos bloquean hasta ACK o timeout. Un unico hilo receptor reparte
los datagramas entre ACK pendientes y telemetria, asi que se puede consultar
telemetry() mientras otra orden esta en vuelo.
"""

from __future__ import annotations

import itertools
import socket
import threading
import time
from collections import namedtuple
from typing import Callable, Optional

PROTO = "WALLE/1"
DEFAULT_PORT = 4210
DEFAULT_ACK_TIMEOUT_S = 0.40
DEFAULT_RETRIES = 3
ID_SPACE = 2_000_000_000
RECV_BUFFER = 512
RX_POLL_S = 0.05

MOTOR_MIN = -1000
MOTOR_MAX = 1000
SERVO_CHANNELS = 4
SERVO_MIN_DEG = 0
SERVO_MAX_DEG = 180

# Codigos de error que devuelve el puente en un ER.
ERROR_CODES = {
    1: "timeout del UNO",
    2: "linea invalida",
    3: "cola llena",
    4: "UNO sin init",
}

Ack = namedtuple("Ack", "id v1 v2 rtt_ms")
Telemetry = namedtuple("Telemetry", "uptime_ms rssi uno_ok last_id queue age_s")


class LinkError(RuntimeError):
    """Falla del enlace PC <-> ESP32."""


class LinkTimeout(LinkError):
    """El ESP32 (o el UNO detras de el) no contesto dentro del plazo."""


class LinkRejected(LinkError):
    """El ESP32 contesto ER: la orden llego pero el UNO no la aplico."""

    def __init__(self, code: int, rtt_ms: int) -> None:
        reason = ERROR_CODES.get(code, f"codigo {code}")
        super().__init__(f"orden rechazada: {reason}")
        self.code = code
        self.rtt_ms = rtt_ms


def _clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value


class WalleLink:
    """Enlace UDP con ACK obligatorio contra el ESP32 puente."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        ack_timeout: float = DEFAULT_ACK_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.ack_timeout = float(ack_timeout)
        self.retries = max(0, int(retries))
        self._log = logger or (lambda _msg: None)

        self._sock: Optional[socket.socket] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._closing = threading.Event()
        self._lock = threading.Lock()
        self._pending: dict[int, dict] = {}
        self._telemetry: Optional[Telemetry] = None
        self._ids = itertools.count(1)

        self.stats = {
            "sent": 0,
            "retries": 0,
            "acks": 0,
            "timeouts": 0,
            "rejected": 0,
            "last_rtt_ms": 0,
        }

    # -- ciclo de vida -----------------------------------------------------

    def open(self) -> "WalleLink":
        if self._sock is not None:
            return self
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Puerto efimero: el ESP32 aprende la direccion de retorno del primer
        # datagrama y manda la telemetria ahi.
        sock.bind(("", 0))
        sock.settimeout(RX_POLL_S)
        self._sock = sock
        self._closing.clear()
        self._rx_thread = threading.Thread(
            target=self._rx_loop, name="walle-link-rx", daemon=True
        )
        self._rx_thread.start()
        self._log(f"enlace abierto hacia {self.host}:{self.port}")
        return self

    def close(self) -> None:
        if self._sock is None:
            return
        self._closing.set()
        thread = self._rx_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        try:
            self._sock.close()
        except OSError:
            pass
        self._sock = None
        self._rx_thread = None
        self._log("enlace cerrado")

    def __enter__(self) -> "WalleLink":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- ordenes -----------------------------------------------------------

    def move(self, left: int, right: int) -> Ack:
        """Orugas en -1000..1000. Negativo = atras."""
        return self._exchange(
            "M", _clamp(int(left), MOTOR_MIN, MOTOR_MAX),
            _clamp(int(right), MOTOR_MIN, MOTOR_MAX),
        )

    def servo(self, channel: int, degrees: int) -> Ack:
        """Servo 0..3 al angulo 0..180."""
        channel = int(channel)
        if not 0 <= channel < SERVO_CHANNELS:
            raise ValueError(f"canal de servo fuera de 0..{SERVO_CHANNELS - 1}")
        return self._exchange("V", channel, _clamp(int(degrees), SERVO_MIN_DEG, SERVO_MAX_DEG))

    def stop(self) -> Ack:
        """Parada inmediata de motores. Los servos quedan donde estan."""
        return self._exchange("X", 0, 0)

    def ping(self) -> Ack:
        """Ida y vuelta sin tocar el robot."""
        return self._exchange("P", 0, 0)

    def telemetry(self, max_age_s: float = 1.5) -> Optional[Telemetry]:
        """Ultima telemetria recibida, o None si esta vieja o no hubo."""
        snap = self._telemetry
        if snap is None:
            return None
        if time.monotonic() - snap.age_s > max_age_s:
            return None
        return snap

    def alive(self) -> bool:
        try:
            self.ping()
            return True
        except LinkError:
            return False

    # -- transporte --------------------------------------------------------

    def _next_id(self) -> int:
        value = next(self._ids)
        if value > ID_SPACE:
            self._ids = itertools.count(1)
            value = 1
        return value

    def _exchange(self, op: str, a: int = 0, b: int = 0) -> Ack:
        sock = self._sock
        if sock is None:
            raise LinkError("el enlace no esta abierto")

        msg_id = self._next_id()
        payload = f"{PROTO} {msg_id} {op} {a} {b}".encode("ascii")
        slot = {"event": threading.Event(), "ack": None, "err": None}
        with self._lock:
            self._pending[msg_id] = slot

        try:
            for attempt in range(self.retries + 1):
                if attempt:
                    self.stats["retries"] += 1
                try:
                    sock.sendto(payload, (self.host, self.port))
                except OSError as exc:
                    raise LinkError(f"no se pudo enviar: {exc}") from exc
                self.stats["sent"] += 1
                if slot["event"].wait(self.ack_timeout):
                    break
            else:
                self.stats["timeouts"] += 1
                raise LinkTimeout(
                    f"sin ACK para {op} id={msg_id} "
                    f"tras {self.retries + 1} intento(s)"
                )

            if slot["err"] is not None:
                code, rtt = slot["err"]
                self.stats["rejected"] += 1
                raise LinkRejected(code, rtt)

            ack: Ack = slot["ack"]
            self.stats["acks"] += 1
            self.stats["last_rtt_ms"] = ack.rtt_ms
            return ack
        finally:
            with self._lock:
                self._pending.pop(msg_id, None)

    def _rx_loop(self) -> None:
        while not self._closing.is_set():
            sock = self._sock
            if sock is None:
                break
            try:
                data, _peer = sock.recvfrom(RECV_BUFFER)
            except socket.timeout:
                continue
            except OSError:
                break

            line = data.decode("ascii", "replace").strip()
            if not line.startswith(PROTO + " "):
                continue
            fields = line[len(PROTO) + 1:].split()
            if not fields:
                continue
            try:
                if fields[0] == "T":
                    self._on_telemetry(fields[1:])
                else:
                    self._on_ack(fields)
            except (ValueError, IndexError):
                self._log(f"trama ilegible: {line!r}")

    def _on_telemetry(self, fields: list[str]) -> None:
        # T <uptime_ms> <rssi> <uno_ok> <ultimo_id> <cola>
        if len(fields) < 5:
            return
        self._telemetry = Telemetry(
            uptime_ms=int(fields[0]),
            rssi=int(fields[1]),
            uno_ok=fields[2] == "1",
            last_id=int(fields[3]),
            queue=int(fields[4]),
            age_s=time.monotonic(),
        )

    def _on_ack(self, fields: list[str]) -> None:
        # <id> OK <v1> <v2> <rtt>   |   <id> ER <codigo> <rtt>
        msg_id = int(fields[0])
        status = fields[1]
        with self._lock:
            slot = self._pending.get(msg_id)
            if slot is None:
                return          # ACK de algo ya resuelto: se ignora
            if status == "OK":
                if len(fields) < 5:
                    return
                slot["ack"] = Ack(msg_id, int(fields[2]), int(fields[3]), int(fields[4]))
            else:
                if len(fields) < 4:
                    return
                slot["err"] = (int(fields[2]), int(fields[3]))
            slot["event"].set()


# --------------------------------------------------------------------------
# Prueba directa desde consola:  python walle_link.py 192.168.1.50
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    with WalleLink(host, port, logger=print) as link:
        try:
            ack = link.ping()
            print(f"ping OK  rtt={ack.rtt_ms} ms")
            link.move(500, 500)
            time.sleep(0.8)
            link.stop()
            tel = link.telemetry()
            print(f"telemetria: {tel}")
            print(f"stats: {link.stats}")
        except LinkError as exc:
            print(f"FALLO: {exc}")
            raise SystemExit(1)
