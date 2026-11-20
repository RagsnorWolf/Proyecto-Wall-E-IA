"""
cerebro/consola.py -- hablarle al robot en castellano, sin simulador.

    python consola.py --host 192.168.1.50

    > avanza 2 metros
    > gira 90 grados
    > detente

No abre PyBullet ni nada pesado: es una consola que traduce la orden a
velocidades de oruga, las manda por WiFi al ESP32 y espera el ACK de cada una.

Aviso importante sobre las distancias: el robot no tiene encoders, asi que
"avanza 2 metros" es en realidad "mueve las orugas este tiempo a esta
velocidad". Si las ruedas patinan o la bateria esta baja, avanza menos. Los
dos numeros de calibracion estan abajo, en CALIBRACION.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:  # consolas viejas de Windows
    pass

from walle_link import DEFAULT_PORT, LinkError, LinkRejected, WalleLink

# --------------------------------------------------------------------------
# CALIBRACION -- medir en el robot real y ajustar estos dos numeros
# --------------------------------------------------------------------------
# Velocidad de avance a PWM 1000, en metros por segundo.
# Procedimiento: "avanza 2 metros", medir con cinta, y corregir:
#   VMAX_MS_nuevo = VMAX_MS_viejo * (metros_reales / 2.0)
VMAX_MS = 0.45

# Grados por segundo girando sobre el sitio a PWM 1000 en las dos orugas
# (una adelante, una atras).
# Procedimiento: "gira 180 grados" y medir el angulo real.
TURN_DEG_S = 170.0

# PWM que se usa para los movimientos. 600 = 60%: suficiente para mover y
# suave como para no arrancar una rueda en falso.
CRUISE_PWM = 600

# Frecuencia de reenvio. El dead-man del ESP32 corta a 1 s sin paquetes, asi
# que hay margen de sobra.
SEND_HZ = 20.0

# Techo de seguridad: ninguna orden simple dura mas que esto.
MAX_ORDER_S = 20.0


# --------------------------------------------------------------------------
# Parseo de la orden
# --------------------------------------------------------------------------
NUM = r"(-?\d+(?:[.,]\d+)?)"


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def parse_order(text: str):
    """Devuelve (accion, valor) o None si no se entiende."""
    t = text.strip().lower()
    if not t:
        return None

    if re.fullmatch(r"(detente|para|parar|stop|quieto)", t):
        return ("stop", 0.0)

    if re.fullmatch(r"(salir|exit|quit|chau)", t):
        return ("exit", 0.0)

    if re.fullmatch(r"(estado|status|telemetria|info)", t):
        return ("status", 0.0)

    if re.fullmatch(r"(distancia|sensor|sonar|que ves)", t):
        return ("distance", 0.0)

    m = re.fullmatch(r"(avanza|avanzar|adelante)\s+" + NUM + r"\s*(m|metro|metros|cm|centimetros)?", t)
    if m:
        value = _num(m.group(2))
        if (m.group(3) or "m") in ("cm", "centimetros"):
            value /= 100.0
        return ("forward", value)

    m = re.fullmatch(r"(retrocede|retroceder|atras)\s+" + NUM + r"\s*(m|metro|metros|cm|centimetros)?", t)
    if m:
        value = _num(m.group(2))
        if (m.group(3) or "m") in ("cm", "centimetros"):
            value /= 100.0
        return ("backward", value)

    m = re.fullmatch(r"(gira|girar|rota|rotar)\s+" + NUM + r"\s*(grados|grado)?", t)
    if m:
        return ("turn", _num(m.group(2)))

    m = re.fullmatch(r"servo\s+([0-3])\s+(?:a\s+)?" + NUM + r"\s*(?:grados|grado)?", t)
    if m:
        return ("servo", (int(m.group(1)), _num(m.group(2))))

    if re.fullmatch(r"(izquierda|a la izquierda)", t):
        return ("spin", -1.0)
    if re.fullmatch(r"(derecha|a la derecha)", t):
        return ("spin", 1.0)
    if re.fullmatch(r"(adelante|avanza)", t):
        return ("continuous", 1.0)
    if re.fullmatch(r"(atras|retrocede)", t):
        return ("continuous", -1.0)

    return None


# --------------------------------------------------------------------------
# Ejecucion
# --------------------------------------------------------------------------
class Consola:
    def __init__(self, link: WalleLink, cruise_pwm: int = CRUISE_PWM) -> None:
        self.link = link
        self.period = 1.0 / SEND_HZ
        self.pwm = max(60, min(1000, int(cruise_pwm)))

    # -- primitivas --------------------------------------------------------

    def _run_for(self, left: int, right: int, seconds: float, label: str) -> None:
        """Mantiene la consigna durante `seconds` reenviando a SEND_HZ."""
        seconds = min(max(0.0, seconds), MAX_ORDER_S)
        if seconds <= 0.0:
            return
        print(f"  {label}: {seconds:.2f} s a ({left}, {right})")
        deadline = time.monotonic() + seconds
        last_ack_ms = 0
        try:
            while True:
                now = time.monotonic()
                if now >= deadline:
                    break
                ack = self.link.move(left, right)
                last_ack_ms = ack.rtt_ms
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(self.period, remaining))
            print(f"  listo (ultimo rtt {last_ack_ms} ms)")
        finally:
            self.link.stop()

    def _speed_for(self, pwm: int) -> float:
        return VMAX_MS * (pwm / 1000.0)

    def _turn_rate_for(self, pwm: int) -> float:
        return TURN_DEG_S * (pwm / 1000.0)

    # -- ordenes -----------------------------------------------------------

    def forward(self, meters: float) -> None:
        meters = abs(meters)
        speed = self._speed_for(self.pwm)
        if speed <= 0:
            return
        self._run_for(self.pwm, self.pwm, meters / speed, f"avanzar {meters:.2f} m")

    def backward(self, meters: float) -> None:
        meters = abs(meters)
        speed = self._speed_for(self.pwm)
        if speed <= 0:
            return
        self._run_for(-self.pwm, -self.pwm, meters / speed, f"retroceder {meters:.2f} m")

    def turn(self, degrees: float) -> None:
        """Positivo gira a la izquierda, negativo a la derecha."""
        rate = self._turn_rate_for(self.pwm)
        if rate <= 0:
            return
        seconds = abs(degrees) / rate
        if degrees >= 0:
            self._run_for(-self.pwm, self.pwm, seconds, f"girar {degrees:+.0f} grados")
        else:
            self._run_for(self.pwm, -self.pwm, seconds, f"girar {degrees:+.0f} grados")

    def spin(self, direction: float) -> None:
        pwm = self.pwm if direction > 0 else -self.pwm
        print(f"  girando {'a la derecha' if direction > 0 else 'a la izquierda'}")
        try:
            while True:
                self.link.move(pwm, -pwm)
                time.sleep(self.period)
        except KeyboardInterrupt:
            pass
        finally:
            self.link.stop()
            print("  detenido")

    def continuous(self, direction: float) -> None:
        pwm = self.pwm if direction > 0 else -self.pwm
        print("  avanzando (Ctrl+C o 'detente' en otra consola para parar)")
        try:
            while True:
                self.link.move(pwm, pwm)
                time.sleep(self.period)
        except KeyboardInterrupt:
            pass
        finally:
            self.link.stop()
            print("  detenido")

    def stop(self) -> None:
        self.link.stop()
        print("  motores frenados")

    def servo(self, channel: int, degrees: float) -> None:
        ack = self.link.servo(channel, int(round(degrees)))
        print(f"  servo {ack.v1} a {ack.v2} grados")

    def status(self) -> None:
        tel = self.link.telemetry()
        if tel is None:
            print("  sin telemetria: el ESP32 no esta mandando el latido")
            return
        print(
            f"  rssi={tel.rssi} dBm  uno_ok={tel.uno_ok}  "
            f"ultimo_id={tel.last_id}  cola={tel.queue}"
        )
        print(f"  enlace: {self.link.stats}")

    def distance(self) -> None:
        cm = self.link.distance_cm(1.0)
        if cm is None:
            print("  sin lectura del sonar (o esta vieja)")
            return
        print(f"  obstaculo al frente: {cm} cm")


# --------------------------------------------------------------------------
# Bucle
# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Consola en castellano para el robot WALL-E")
    parser.add_argument("--host", required=True, help="IP del ESP32")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="puerto UDP")
    parser.add_argument(
        "--pwm", type=int, default=CRUISE_PWM, help="PWM de crucero (por defecto: %(default)s)"
    )
    parser.add_argument(
        "--status", action="store_true", help="imprime el estado del enlace y sale"
    )
    args = parser.parse_args()

    with WalleLink(args.host, args.port) as link:
        try:
            ack = link.ping()
        except LinkError as exc:
            print(f"No hay enlace con {args.host}: {exc}")
            print("Revisar que el ESP32 este encendido, en la misma red, y la IP.")
            return 1

        tel = link.telemetry()
        print(f"Conectado a {args.host}  (rtt {ack.rtt_ms} ms)")
        if tel is not None:
            print(f"  rssi={tel.rssi} dBm  uno_ok={tel.uno_ok}")
        if tel is not None and not tel.uno_ok:
            print("  OJO: el ESP32 responde pero el UNO no. Revisar el cable serie.")

        if args.status:
            # El sonar emite a 6,6 Hz: hay que esperar la primera lectura, no
            # leer el hueco de antes de que el UNO muestreara.
            cm = link.wait_distance(1.0)
            print(f"  distancia: {cm} cm" if cm is not None else "  distancia: sin lectura")
            print(f"  enlace: {link.stats}")
            return 0

        print()
        print("Ordenes: avanza 2 metros | retrocede 1 m | gira 90 grados |")
        print("         detente | izquierda | derecha | servo 0 45 |")
        print("         distancia | estado | salir")
        print()

        consola = Consola(link, args.pwm)
        while True:
            try:
                text = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            order = parse_order(text)
            if order is None:
                print("  no entendi. proba: avanza 2 metros / gira 90 grados / detente")
                continue

            action, value = order
            if action == "exit":
                break

            try:
                if action == "stop":
                    consola.stop()
                elif action == "status":
                    consola.status()
                elif action == "distance":
                    consola.distance()
                elif action == "forward":
                    consola.forward(value)
                elif action == "backward":
                    consola.backward(value)
                elif action == "turn":
                    consola.turn(value)
                elif action == "spin":
                    consola.spin(value)
                elif action == "continuous":
                    consola.continuous(value)
                elif action == "servo":
                    consola.servo(value[0], value[1])
            except LinkRejected as exc:
                print(f"  el UNO rechazo la orden: {exc}")
            except LinkError as exc:
                print(f"  se corto el enlace: {exc}")
            except KeyboardInterrupt:
                print()
                consola.stop()

        print("Cerrando: parada enviada.")
        try:
            link.stop()
        except LinkError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
