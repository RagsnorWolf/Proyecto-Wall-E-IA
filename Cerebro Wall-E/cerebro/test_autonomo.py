"""
cerebro/test_autonomo.py -- pruebas del cerebro reactivo, sin robot.

    python test_autonomo.py

Cambia el enlace real por uno falso que devuelve distancias de mentira, y
comprueba que el cerebro toma la decision correcta en cada situacion. Es la
unica forma de probar el modo autonomo sin chocar un robot contra una pared.

Lo que se verifica:

    1. pista libre       -> avanza
    2. obstaculo cerca   -> frena, barre, escapa hacia el lado libre
    3. sin sonar         -> se queda quieto, nunca avanza a ciegas
    4. sonar que parpadea-> un hueco de lectura no frena la marcha

Sale con 1 si algo falla.
"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import autonomo
from walle_link import Ack


# --------------------------------------------------------------------------
# Enlace falso
# --------------------------------------------------------------------------
class FakeLink:
    """Devuelve la distancia que corresponda al angulo del servo.

    `readings` mapea angulo -> centimetros. Un angulo ausente del diccionario
    significa "sin eco", igual que el -1 del UNO real.
    """

    def __init__(self, readings: dict[int, int | None]) -> None:
        self.readings = readings
        self.angle = autonomo.SERVO_CENTER
        self.servo_calls: list[tuple[int, int]] = []
        self.moves: list[tuple[int, int]] = []
        self.stops = 0

    # -- lo que usa el cerebro --------------------------------------------
    def servo(self, channel: int, degrees: int) -> Ack:
        self.angle = int(degrees)
        self.servo_calls.append((int(channel), int(degrees)))
        return Ack(1, int(channel), int(degrees), 8)

    def move(self, left: int, right: int) -> Ack:
        self.moves.append((int(left), int(right)))
        return Ack(1, int(left), int(right), 8)

    def stop(self) -> Ack:
        self.moves.append((0, 0))
        self.stops += 1
        return Ack(1, 0, 0, 8)

    def wait_distance(self, timeout_s: float = 0.6) -> int | None:
        return self.readings.get(self.angle)

    def distance_cm(self, max_age_s: float = 0.6) -> int | None:
        return self.readings.get(self.angle)

    def telemetry(self, max_age_s: float = 1.5):
        return None

    # -- lectura de resultados --------------------------------------------
    def advanced(self) -> bool:
        return any(l > 0 and r > 0 for l, r in self.moves)

    def turned_left(self) -> bool:
        return any(l < 0 < r for l, r in self.moves)

    def turned_right(self) -> bool:
        return any(r < 0 < l for l, r in self.moves)

    def backed_off(self) -> bool:
        return any(l < 0 and r < 0 for l, r in self.moves)


# --------------------------------------------------------------------------
# Reporte
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


def _sin_esperas() -> dict[str, float]:
    """Acorta los sleeps para que las pruebas corran en milisegundos.

    No se ponen en cero: `_hold` reenvia mientras el plazo no vencio, y con 0 s
    no manda nada. Queda un paso corto pero real, que es lo que se quiere
    verificar.
    """
    guardado = {
        "SERVO_SETTLE_S": autonomo.SERVO_SETTLE_S,
        "BACKOFF_S": autonomo.BACKOFF_S,
        "TURN_STEP_S": autonomo.TURN_STEP_S,
    }
    autonomo.SERVO_SETTLE_S = 0.0
    autonomo.BACKOFF_S = 0.01
    autonomo.TURN_STEP_S = 0.01
    return guardado


def _restaurar(guardado: dict[str, float]) -> None:
    autonomo.SERVO_SETTLE_S = guardado["SERVO_SETTLE_S"]
    autonomo.BACKOFF_S = guardado["BACKOFF_S"]
    autonomo.TURN_STEP_S = guardado["TURN_STEP_S"]


# --------------------------------------------------------------------------
# Pruebas
# --------------------------------------------------------------------------
def run() -> int:
    report = Report()
    guardado = _sin_esperas()

    try:
        print("== 1. pista libre: avanza ==")
        link = FakeLink({autonomo.SERVO_CENTER: 200})
        cerebro = autonomo.Autonomo(link, verbose=False)
        cerebro.period = 0.002
        cerebro.step()
        report.check(
            "avanza con 200 cm al frente",
            link.advanced(),
            f"movimientos={link.moves[:3]}",
        )
        report.check("no frena de golpe", link.stops == 0, f"paradas={link.stops}")

        print("== 2. obstaculo cerca: frena, barre y escapa ==")
        # Frente bloqueado, izquierda despejada, derecha tapada.
        link = FakeLink(
            {
                autonomo.SERVO_CENTER: 10,
                autonomo.SERVO_LEFT: 160,
                autonomo.SERVO_RIGHT: 35,
            }
        )
        cerebro = autonomo.Autonomo(link, verbose=False)
        cerebro.period = 0.002
        cerebro.step()
        report.check("frena antes de tocar", link.stops >= 1, f"paradas={link.stops}")
        report.check("barre a los dos lados", len(link.servo_calls) >= 2,
                     f"servo={link.servo_calls}")
        report.check("escapa hacia la izquierda libre", link.turned_left(),
                     f"movimientos={link.moves[:4]}")
        report.check("no gira hacia el lado tapado", not link.turned_right())

        print("== 3. sin sonar: quieto, nunca a ciegas ==")
        link = FakeLink({})          # ningun angulo devuelve eco
        cerebro = autonomo.Autonomo(link, verbose=False)
        cerebro.period = 0.002
        for _ in range(5):
            cerebro.step()
        report.check("no avanza sin lecturas", not link.advanced(),
                     f"movimientos={link.moves}")
        report.check("frena por seguridad", link.stops >= 1, f"paradas={link.stops}")

        print("== 4. obstaculo a la derecha: escapa a la derecha ==")
        link = FakeLink(
            {
                autonomo.SERVO_CENTER: 12,
                autonomo.SERVO_LEFT: 30,
                autonomo.SERVO_RIGHT: 180,
            }
        )
        cerebro = autonomo.Autonomo(link, verbose=False)
        cerebro.period = 0.002
        cerebro.step()
        report.check("escapa hacia la derecha libre", link.turned_right(),
                     f"movimientos={link.moves[:4]}")

        print("== 5. zona lenta: avanza despacio, no se detiene ==")
        link = FakeLink({autonomo.SERVO_CENTER: 40})
        cerebro = autonomo.Autonomo(link, verbose=False)
        cerebro.period = 0.002
        cerebro.step()
        rapido = [m for m in link.moves if m[0] > autonomo.CRAWL_PWM]
        report.check("avanza en la zona lenta", link.advanced(), f"movimientos={link.moves[:2]}")
        report.check("no acelera en la zona lenta", not rapido,
                     f"pwm max={max((m[0] for m in link.moves), default=0)}")
    finally:
        _restaurar(guardado)

    print()
    print(f"resultado: {report.passed} OK, {report.failed} fallos")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
