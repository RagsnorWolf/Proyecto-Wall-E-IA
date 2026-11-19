"""Geometria, cinematica y colisiones del mundo de WALL-E.

Modulo puro de Python: sin pygame, sin numpy. Es el nucleo determinista que
comparten el visor manual y el entrenamiento del Cerebro PPO, asi el
simulador y el cerebro nunca se desincronizan.

Unidades: metros, segundos, radianes. Bateria en porcentaje 0-100.
"""
from __future__ import annotations

import math
import random
from typing import Iterable, Sequence

# --- Constantes fisicas ---------------------------------------------------
RADIO_ROBOT = 0.16        # m, radio del chasis
RADIO_BASURA = 0.07       # m
RADIO_CONTENEDOR = 0.38   # m
ALCANCE_RECOGIDA = 0.26   # m, distancia maxima para agarrar un cubo
VEL_LINEAL = 0.24         # m/s
VEL_ANGULAR = 1.9         # rad/s
DT = 0.1                  # s por paso de simulacion
PASOS_MAX = 900           # tope de pasos por episodio (90 s de reloj)

# Energia: trabajo mecanico real, no una cifra decorativa.
MASA_ROBOT = 20.0         # kg
GRAVEDAD = 9.81           # m/s^2
COEF_RODADURA = 0.05      # rueda sobre chatarra compactada
JULIOS_POR_KCAL = 4184.0

ACCIONES = ("avanzar", "izquierda", "derecha", "recoger", "esperar")
N_ACCIONES = len(ACCIONES)

BATERIA_MAX = 100.0
BATERIA_POR_METRO = 1.2
BATERIA_IDLE_POR_PASO = 0.005

N_RAYOS = 8
ALCANCE_RAYO = 1.2
PASO_RAYO = 0.05
CELDA_COBERTURA = 0.5     # m, lado de la celda de cobertura

Rect = tuple[float, float, float, float]  # x, y, ancho, alto


# --- Geometria ------------------------------------------------------------
def distancia_punto_rect(px: float, py: float, rect: Rect) -> float:
    """Distancia euclidiana de un punto al rectangulo (0 si esta dentro)."""
    x, y, w, h = rect
    cx = min(max(px, x), x + w)
    cy = min(max(py, y), y + h)
    return math.hypot(px - cx, py - cy)


def colision_circulo_rect(px: float, py: float, radio: float, rect: Rect) -> bool:
    return distancia_punto_rect(px, py, rect) < radio


def angulo_normalizado(a: float) -> float:
    """Lleva un angulo a (-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


class Mundo:
    """Estado fisico completo: robot, basura, contenedor, bateria, contadores.

    El mundo no sabe de recompensas ni de observaciones de red: eso lo decide
    quien lo envuelve (`Escena`, el Cerebro, o el visor manual).
    """

    def __init__(
        self,
        ancho: float,
        alto: float,
        obstaculos: Sequence[Rect],
        basuras: Iterable[tuple[float, float]],
        contenedor: tuple[float, float],
        inicio: tuple[float, float, float] = (1.0, 1.0, 0.0),
        semilla: int | None = None,
    ) -> None:
        self.ancho = float(ancho)
        self.alto = float(alto)
        self.obstaculos: list[Rect] = [tuple(map(float, o)) for o in obstaculos]
        self.contenedor = (float(contenedor[0]), float(contenedor[1]))
        self.inicio = (float(inicio[0]), float(inicio[1]), float(inicio[2]))
        self._basuras_iniciales = [(float(x), float(y)) for x, y in basuras]
        self.rng = random.Random(semilla)
        self.reiniciar()

    # --- ciclo de vida ----------------------------------------------------
    def reiniciar(self) -> None:
        self.basuras: list[tuple[float, float]] = list(self._basuras_iniciales)
        self.x, self.y, self.theta = self.inicio
        self.bateria = BATERIA_MAX
        self.llevando: int = 0
        self.pasos: int = 0
        self.colisiones: int = 0
        self.distancia: float = 0.0
        self.recogidas: int = 0
        self.entregadas: int = 0
        self.celdas: set[tuple[int, int]] = set()
        self._marcar_celda()

    # --- consultas --------------------------------------------------------
    def libre(self, x: float, y: float, radio: float = RADIO_ROBOT) -> bool:
        if x - radio < 0 or y - radio < 0:
            return False
        if x + radio > self.ancho or y + radio > self.alto:
            return False
        for rect in self.obstaculos:
            if colision_circulo_rect(x, y, radio, rect):
                return False
        return True

    def _celda(self, x: float | None = None, y: float | None = None) -> tuple[int, int]:
        px = self.x if x is None else x
        py = self.y if y is None else y
        return (int(px // CELDA_COBERTURA), int(py // CELDA_COBERTURA))

    def _marcar_celda(self) -> bool:
        clave = self._celda()
        if clave in self.celdas:
            return False
        self.celdas.add(clave)
        return True

    def rayos(self) -> list[float]:
        """8 distancias a obstaculos, ordenadas desde el frente (horario)."""
        distancias: list[float] = []
        for i in range(N_RAYOS):
            angulo = self.theta + (2.0 * math.pi * i / N_RAYOS)
            dx = math.cos(angulo)
            dy = math.sin(angulo)
            distancia = ALCANCE_RAYO
            recorrido = PASO_RAYO
            while recorrido <= ALCANCE_RAYO:
                if not self.libre(self.x + dx * recorrido, self.y + dy * recorrido, radio=0.02):
                    distancia = recorrido
                    break
                recorrido += PASO_RAYO
            distancias.append(distancia)
        return distancias

    def basura_mas_cercana(self) -> tuple[float, float, float] | None:
        if not self.basuras:
            return None
        mejor = min(self.basuras, key=lambda b: math.hypot(b[0] - self.x, b[1] - self.y))
        return mejor[0] - self.x, mejor[1] - self.y, math.hypot(mejor[0] - self.x, mejor[1] - self.y)

    def distancia_contenedor(self) -> float:
        return math.hypot(self.contenedor[0] - self.x, self.contenedor[1] - self.y)

    def estado(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "theta": self.theta,
            "bateria": self.bateria,
            "llevando": self.llevando,
            "basuras": len(self.basuras),
            "recogidas": self.recogidas,
            "entregadas": self.entregadas,
            "colisiones": self.colisiones,
            "distancia": self.distancia,
            "pasos": self.pasos,
            "calorias": self.calorias(),
            "cobertura": len(self.celdas) * CELDA_COBERTURA * CELDA_COBERTURA,
        }

    def calorias(self) -> float:
        """kcal estimadas por rodadura: F = m*g*mu, E = F*d, 1 kcal = 4184 J."""
        julios = MASA_ROBOT * GRAVEDAD * COEF_RODADURA * self.distancia
        return julios / JULIOS_POR_KCAL

    # --- accion -----------------------------------------------------------
    def _mover(self, dx: float, dy: float) -> tuple[float, bool]:
        """Intenta desplazar el chasis. Devuelve (metros recorridos, colision)."""
        nx, ny = self.x + dx, self.y + dy
        if self.libre(nx, ny):
            self.x, self.y = nx, ny
            metros = math.hypot(dx, dy)
            self.distancia += metros
            self.bateria -= metros * BATERIA_POR_METRO
            return metros, False
        # Choca: se prueba deslizar por cada eje para no clavar al robot en paredes.
        metros = 0.0
        if self.libre(self.x + dx, self.y):
            self.x += dx
            metros += abs(dx)
        if self.libre(self.x, self.y + dy):
            self.y += dy
            metros += abs(dy)
        self.distancia += metros
        self.bateria -= metros * BATERIA_POR_METRO
        self.colisiones += 1
        return metros, True

    def paso(self, accion: int | str) -> dict:
        """Aplica una accion y devuelve los eventos del paso."""
        if isinstance(accion, str):
            if accion not in ACCIONES:
                raise ValueError(f"accion desconocida: {accion!r}")
            accion = ACCIONES.index(accion)
        if not 0 <= accion < N_ACCIONES:
            raise ValueError(f"indice de accion fuera de rango: {accion}")

        self.pasos += 1
        eventos = {
            "movido": 0.0,
            "colision": False,
            "recogido": False,
            "entregado": False,
            "nueva_celda": False,
            "sin_bateria": False,
        }

        nombre = ACCIONES[accion]
        if nombre == "avanzar":
            dx = math.cos(self.theta) * VEL_LINEAL * DT
            dy = math.sin(self.theta) * VEL_LINEAL * DT
            eventos["movido"], eventos["colision"] = self._mover(dx, dy)
        elif nombre == "izquierda":
            self.theta = angulo_normalizado(self.theta - VEL_ANGULAR * DT)
        elif nombre == "derecha":
            self.theta = angulo_normalizado(self.theta + VEL_ANGULAR * DT)
        elif nombre == "recoger":
            if self.llevando < 2:
                for i, (bx, by) in enumerate(self.basuras):
                    if math.hypot(bx - self.x, by - self.y) <= ALCANCE_RECOGIDA:
                        del self.basuras[i]
                        self.llevando += 1
                        self.recogidas += 1
                        eventos["recogido"] = True
                        break
            if self.llevando and self.distancia_contenedor() <= RADIO_CONTENEDOR + RADIO_ROBOT:
                self.entregadas += self.llevando
                self.llevando = 0
                eventos["entregado"] = True

        self.bateria -= BATERIA_IDLE_POR_PASO
        if self.bateria <= 0.0:
            self.bateria = 0.0
            eventos["sin_bateria"] = True

        if not eventos["sin_bateria"]:
            eventos["nueva_celda"] = self._marcar_celda()

        return eventos
