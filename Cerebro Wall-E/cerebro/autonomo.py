"""
cerebro/autonomo.py -- el cerebro reactivo del WALL-E real.

    python autonomo.py --host 192.168.1.50

No usa el modelo PPO del simulador. La politica entrenada come 36 rayos LiDAR
que el robot fisico no tiene; correrla con un solo sonar seria mentirse. Esto
es lo que si funciona hoy con el hardware que hay:

    sonar en el servo 0  ->  mira al frente
    libre                ->  avanza, rapido si esta despejado
    cerca                ->  frena y avanza despacio
    obstaculo            ->  barre a izquierda y derecha con el servo,
                             elige el lado mas libre, retrocede un toque y gira

El sonar va montado en el servo 0. Si no esta montado, el servo se queda quieto
y el robot solo sabe lo que tiene adelante: sigue funcionando, pero elige el
lado de escape por turnos en vez de por medicion.

Todo el pensamiento esta aca, en la PC. El ESP32 solo reenvia y el UNO solo
mueve. Si se corta el WiFi, el dead-man del ESP32 frena el robot.

Ctrl+C para parar.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # consolas viejas de Windows
    pass

from walle_link import DEFAULT_PORT, LinkError, WalleLink

# --------------------------------------------------------------------------
# CALIBRACION -- estos numeros se miden en el robot, no se adivinan
# --------------------------------------------------------------------------

# Servo donde esta montado el sonar. -1 si el sonar va fijo al frente.
SONAR_SERVO = 0
SERVO_CENTER = 90
SERVO_LEFT = SERVO_CENTER + 55
SERVO_RIGHT = SERVO_CENTER - 55
SERVO_SETTLE_S = 0.30      # tiempo que tarda el servo en llegar y quedarse quieto

# Umbrales en centimetros.
STOP_CM = 22               # mas cerca que esto: no se avanza, se esquiva
SLOW_CM = 65               # entre STOP y esto: se avanza despacio
CLEAR_CM = 120             # mas lejos que esto: pista libre, velocidad plena

# Velocidades. PWM 1000 = 100%.
CRUISE_PWM = 620           # crucero normal
CRAWL_PWM = 380            # arrimandose a un obstaculo
TURN_PWM = 560             # girando sobre el sitio
BACK_PWM = 520             # retrocediendo para despegarse

# Tiempos de maniobra.
BACKOFF_S = 0.55           # cuanto retrocede al encontrar un obstaculo
TURN_STEP_S = 0.55         # cuanto gira en cada paso del escape
MAX_ESCAPE_STEPS = 6       # tope de pasos girando antes de rendirse y volver a medir

# Bucle.
LOOP_HZ = 12.0
SEND_HZ = 20.0

# Si el sonar no da lectura durante esto, el robot no avanza: se queda quieto.
SONAR_LOST_S = 1.2


# --------------------------------------------------------------------------
# El cerebro
# --------------------------------------------------------------------------
class Autonomo:
    def __init__(self, link: WalleLink, verbose: bool = True) -> None:
        self.link = link
        self.verbose = verbose
        self.period = 1.0 / LOOP_HZ
        self.send_period = 1.0 / SEND_HZ

        self.servo_angle: Optional[int] = None
        self.escape_side = 1          # 1 = izquierda, -1 = derecha
        self.last_sonar_at = 0.0
        self.last_cm: Optional[int] = None

        self.stats = {
            "pasos": 0,
            "avances": 0,
            "frenadas": 0,
            "escapes": 0,
            "sin_sonar": 0,
        }

    # -- utilidades --------------------------------------------------------

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def _look(self, degrees: int) -> Optional[int]:
        """Mueve el servo del sonar y devuelve una lectura de ESA direccion."""
        if SONAR_SERVO < 0:
            return self.link.wait_distance(0.6)

        degrees = max(0, min(180, int(degrees)))
        if degrees != self.servo_angle:
            try:
                self.link.servo(SONAR_SERVO, degrees)
            except LinkError:
                return None
            self.servo_angle = degrees
            time.sleep(SERVO_SETTLE_S)

        cm = self.link.wait_distance(0.6)
        if cm is not None:
            self.last_cm = cm
            self.last_sonar_at = time.monotonic()
        return cm

    def _hold(self, left: int, right: int, seconds: float) -> None:
        """Mantiene una consigna durante `seconds` reenviando a SEND_HZ.

        Reenviar no es opcional: el dead-man del ESP32 corta a 1 s sin paquetes.
        """
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            now = time.monotonic()
            if now >= deadline:
                break
            try:
                self.link.move(left, right)
            except LinkError as exc:
                self._log(f"  enlace caido durante la maniobra: {exc}")
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(self.send_period, remaining))

    def _brake(self) -> None:
        try:
            self.link.stop()
        except LinkError:
            pass

    # -- maniobras ---------------------------------------------------------

    def _backoff(self) -> None:
        self._log(f"  retrocedo {BACKOFF_S:.2f} s")
        self._hold(-BACK_PWM, -BACK_PWM, BACKOFF_S)
        self._brake()

    def _sweep(self) -> int:
        """Mide a los dos lados y devuelve el mas libre. 1 = izq, -1 = der."""
        left = self._look(SERVO_LEFT)
        right = self._look(SERVO_RIGHT)
        self._look(SERVO_CENTER)

        if left is None and right is None:
            # Sin lecturas laterales: alternar para no quedarse trabado.
            side = self.escape_side
            self.escape_side = -self.escape_side
            self._log("  sin lecturas laterales: alterno el lado")
            return side

        if left is None:
            return -1
        if right is None:
            return 1

        # El lado mas libre gana; si empatan, el que ya venia eligiendo.
        if abs(left - right) < 5:
            return self.escape_side
        return 1 if left > right else -1

    def _escape(self, side: int) -> None:
        """Gira sobre el sitio hacia el lado libre, midiendo mientras gira."""
        self.stats["escapes"] += 1
        direction = "izquierda" if side > 0 else "derecha"
        self._log(f"  obstaculo: escape hacia la {direction}")

        self._backoff()

        for step in range(MAX_ESCAPE_STEPS):
            left = -TURN_PWM if side > 0 else TURN_PWM
            right = TURN_PWM if side > 0 else -TURN_PWM
            self._hold(left, right, TURN_STEP_S)
            self._brake()

            # Recien despues de girar se vuelve a mirar al frente: medir antes
            # seria medir la direccion vieja.
            cm = self._look(SERVO_CENTER)
            if cm is None:
                continue
            self._log(f"    paso {step + 1}: frente a {cm} cm")
            if cm > SLOW_CM:
                return

        self._log("  no encontre salida: vuelvo a barrer")

    # -- un paso -----------------------------------------------------------

    def step(self) -> None:
        self.stats["pasos"] += 1

        cm = self._look(SERVO_CENTER)

        if cm is None:
            self.stats["sin_sonar"] += 1
            if time.monotonic() - self.last_sonar_at > SONAR_LOST_S:
                self._brake()
                self._log("  sin lectura del sonar: quieto por seguridad")
            return

        if cm <= STOP_CM:
            self.stats["frenadas"] += 1
            self._brake()
            side = self._sweep()
            self._escape(side)
            return

        if cm < SLOW_CM:
            # Arrimandose: paso corto y velocidad baja, sin frenar en seco.
            pwm = CRAWL_PWM
        elif cm < CLEAR_CM:
            # Interpolacion lineal: mas lejos, mas rapido.
            t = (cm - SLOW_CM) / (CLEAR_CM - SLOW_CM)
            pwm = int(CRAWL_PWM + (CRUISE_PWM - CRAWL_PWM) * t)
        else:
            pwm = CRUISE_PWM

        self.stats["avances"] += 1
        self._hold(pwm, pwm, self.period)
        self._log(f"  {cm} cm  ->  avanza a {pwm}")

    # -- bucle -------------------------------------------------------------

    def run(self) -> int:
        self._log("buscando el centro del servo...")
        self._look(SERVO_CENTER)

        if self.link.distance_cm(1.5) is None:
            self._log("OJO: todavia no llego ninguna lectura del sonar.")
            self._log("     Revisar USE_SONAR=1 en el UNO y el cableado A0/A1.")
            self._log("")

        self._log("autonomo activo. Ctrl+C para parar.")
        self._log("")

        try:
            while True:
                started = time.monotonic()
                self.step()
                elapsed = time.monotonic() - started
                if elapsed < self.period:
                    time.sleep(self.period - elapsed)
        except KeyboardInterrupt:
            self._log("")
            self._log("Ctrl+C: frenando.")
        finally:
            self._brake()
            self._log(f"  {self.stats}")
            self._log("motores frenados")
        return 0


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Modo autonomo del WALL-E: esquiva obstaculos con el sonar"
    )
    parser.add_argument("--host", required=True, help="IP del ESP32")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="puerto UDP")
    parser.add_argument("--quieto", action="store_true", help="sin lineas de estado")
    args = parser.parse_args()

    with WalleLink(args.host, args.port) as link:
        try:
            ack = link.ping()
        except LinkError as exc:
            print(f"No hay enlace con {args.host}: {exc}")
            print("Revisar que el ESP32 este encendido, en la misma red, y la IP.")
            return 1

        print(f"Conectado a {args.host}  (rtt {ack.rtt_ms} ms)")
        tel = link.telemetry()
        if tel is not None and not tel.uno_ok:
            print("OJO: el ESP32 responde pero el UNO no. Revisar el cable serie.")
        print()

        return Autonomo(link, verbose=not args.quieto).run()


if __name__ == "__main__":
    raise SystemExit(main())
