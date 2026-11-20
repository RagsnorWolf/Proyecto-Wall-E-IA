"""
cerebro/sim_link.py -- adaptador entre el simulador PyBullet y el robot real.

El simulador habla en rad/s de rueda (walle_env_v2.max_wheel_speed = 5.0).
El UNO habla en -1000..1000. Este modulo traduce y, sobre todo, mantiene el
enlace vivo:

  - El ESP32 frena los motores si pasan 1000 ms sin paquetes de la PC.
  - Por eso el adaptador reenvia la ultima orden a 4 Hz aunque no cambie.
  - Si el simulador deja de llamar a drive() por mas de stale_s, manda X en vez
    de repetir la ultima orden: un simulador colgado no deja al robot andando.

Uso desde el simulador:

    from sim_link import open_wheel_link

    wheels = open_wheel_link("192.168.1.50")     # o dry_run=True
    wheels.drive(left_rad_s, right_rad_s)
    ...
    wheels.close()
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from walle_link import DEFAULT_PORT, LinkError, WalleLink

MOTOR_FULL = 1000
DEFAULT_MAX_WHEEL_RAD_S = 5.0     # tope de walle_env_v2
DEFAULT_KEEPALIVE_HZ = 4.0
DEFAULT_STALE_S = 1.5             # por debajo del dead-man del ESP32 + margen
MAX_SEND_HZ = 20.0                # techo de trafico: el PID cambia a 60 Hz


def _clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


class DryRunWheelLink:
    """Misma interfaz sin hardware: guarda lo que se habria mandado."""

    def __init__(self, logger=None) -> None:
        self._log = logger or (lambda _msg: None)
        self.history: list[tuple[float, float, int, int]] = []
        self.last_pwm = (0, 0)
        self.closed = False

    def drive(self, left_rad_s: float, right_rad_s: float) -> None:
        left = int(round(_clamp(left_rad_s / DEFAULT_MAX_WHEEL_RAD_S, -1.0, 1.0) * MOTOR_FULL))
        right = int(round(_clamp(right_rad_s / DEFAULT_MAX_WHEEL_RAD_S, -1.0, 1.0) * MOTOR_FULL))
        self.last_pwm = (left, right)
        self.history.append((time.monotonic(), left_rad_s, left, right))
        self._log(f"[dry] drive {left_rad_s:+.2f}/{right_rad_s:+.2f} rad/s -> {left}/{right}")

    def halt(self) -> None:
        self.last_pwm = (0, 0)
        self._log("[dry] halt")

    def close(self) -> None:
        self.closed = True
        self._log("[dry] cerrado")


class UdpWheelLink:
    """Traduce rad/s a PWM y mantiene el latido del ESP32 satisfecho."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        max_wheel_rad_s: float = DEFAULT_MAX_WHEEL_RAD_S,
        keepalive_hz: float = DEFAULT_KEEPALIVE_HZ,
        stale_s: float = DEFAULT_STALE_S,
        logger=None,
    ) -> None:
        self._log = logger or (lambda _msg: None)
        self._link = WalleLink(host, port, logger=self._log).open()
        self._max_rad_s = float(max_wheel_rad_s)
        self._keepalive_s = 1.0 / max(0.5, float(keepalive_hz))
        self._stale_s = float(stale_s)
        self._min_send_s = 1.0 / MAX_SEND_HZ

        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._last_pwm = (0, 0)
        self._last_sent_pwm = (0, 0)
        self._last_drive_s = 0.0
        self._last_send_s = 0.0
        self._halted = True
        self._closing = threading.Event()

        self.last_pwm = (0, 0)
        self.errors = 0
        self._thread = threading.Thread(
            target=self._loop, name="walle-keepalive", daemon=True
        )
        self._thread.start()

    # -- API del simulador -------------------------------------------------

    def drive(self, left_rad_s: float, right_rad_s: float) -> None:
        """Anota la consigna y despierta al emisor. No bloquea: el tick manda."""
        pwm = self._to_pwm(left_rad_s, right_rad_s)
        with self._lock:
            self._last_pwm = pwm
            self._last_drive_s = time.monotonic()
            self._halted = False
        self.last_pwm = pwm
        self._wake.set()

    def halt(self) -> None:
        """Parada pedida por el simulador. La manda el hilo, sin bloquear."""
        with self._lock:
            self._last_pwm = (0, 0)
            self._halted = True
        self._wake.set()

    def close(self) -> None:
        self._closing.set()
        self._wake.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.5)
        # Ultima parada sincrona: si falla, se cierra igual.
        try:
            self._link.stop()
        except LinkError as exc:
            self.errors += 1
            self._log(f"parada final no confirmada: {exc}")
        self._link.close()

    # -- interno -----------------------------------------------------------

    def _to_pwm(self, left_rad_s: float, right_rad_s: float) -> tuple[int, int]:
        scale = MOTOR_FULL / self._max_rad_s
        left = int(round(_clamp(left_rad_s * scale, -MOTOR_FULL, MOTOR_FULL)))
        right = int(round(_clamp(right_rad_s * scale, -MOTOR_FULL, MOTOR_FULL)))
        return left, right

    def _loop(self) -> None:
        while not self._closing.is_set():
            self._wake.wait(self._keepalive_s)
            self._wake.clear()
            if self._closing.is_set():
                break

            now = time.monotonic()
            with self._lock:
                pwm = self._last_pwm
                halted = self._halted
                age = now - self._last_drive_s
                sent = self._last_sent_pwm
                since_send = now - self._last_send_s

            # Sin consigna fresca o con el simulador colgado: parada, nunca
            # repetir la ultima orden.
            stopping = halted or age > self._stale_s
            target = (0, 0) if stopping else pwm

            changed = target != sent
            if not changed and since_send < self._keepalive_s:
                continue
            if changed and since_send < self._min_send_s:
                continue          # el siguiente latido lo alcanza

            try:
                if stopping:
                    self._link.stop()
                else:
                    self._link.move(*target)
            except LinkError as exc:
                self.errors += 1
                self._log(f"latido perdido: {exc}")
                continue

            with self._lock:
                self._last_sent_pwm = target
                self._last_send_s = time.monotonic()

    def __enter__(self) -> "UdpWheelLink":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def open_wheel_link(
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
    *,
    dry_run: bool = False,
    logger=None,
    max_wheel_rad_s: float = DEFAULT_MAX_WHEEL_RAD_S,
):
    """Devuelve el adaptador real o el de mentira, con la misma interfaz."""
    if dry_run or not host:
        return DryRunWheelLink(logger=logger)
    return UdpWheelLink(
        host, port, max_wheel_rad_s=max_wheel_rad_s, logger=logger
    )


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else None
    dry = target is None or target == "dry"

    wheels = open_wheel_link(target, dry_run=dry, logger=print)
    try:
        print("adelante 2 s")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            wheels.drive(2.5, 2.5)
            time.sleep(0.05)

        print("giro 1.5 s")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            wheels.drive(-2.0, 2.0)
            time.sleep(0.05)
    finally:
        wheels.halt()
        wheels.close()
        print("cerrado")
