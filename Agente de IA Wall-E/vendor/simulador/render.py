"""Visor pygame del simulador. Solo dibuja: no toca la fisica."""
from __future__ import annotations

import math

import pygame

from .fisica import RADIO_BASURA, RADIO_CONTENEDOR, RADIO_ROBOT

FONDO = (34, 38, 42)
SUELO = (58, 62, 66)
REJILLA = (66, 71, 76)
MURO = (104, 110, 116)
MURO_BORDE = (140, 146, 152)
BASURA = (186, 148, 62)
BASURA_BORDE = (122, 92, 34)
ROBOT = (198, 202, 206)
ROBOT_OSCURO = (128, 134, 140)
OJOS = (238, 206, 92)
CONTENEDOR = (74, 118, 92)
TEXTO = (226, 230, 234)
TEXTO_TENUE = (150, 158, 166)

ESCALA = 84  # pixeles por metro


class Dibujante:
    """Convierte metros a pixeles y dibuja un frame de la escena."""

    def __init__(self, escena, ancho_ventana: int, alto_ventana: int) -> None:
        self.escena = escena
        self.ancho_ventana = ancho_ventana
        self.alto_ventana = alto_ventana
        self.sup = pygame.Surface((ancho_ventana, alto_ventana))
        self.fuente = pygame.font.SysFont("consolas", 16)
        self.fuente_chica = pygame.font.SysFont("consolas", 13)

    def _px(self, x: float, y: float) -> tuple[int, int]:
        return int(x * ESCALA), int(y * ESCALA)

    def dibujar(self, mensaje: str = "") -> pygame.Surface:
        mundo = self.escena.mundo
        self.sup.fill(FONDO)
        self._suelo(mundo)
        self._contenedor(mundo)
        for bx, by in mundo.basuras:
            self._basura(bx, by)
        self._robot(mundo)
        self._hud(mundo, mensaje)
        return self.sup

    # --- piezas -----------------------------------------------------------
    def _suelo(self, mundo) -> None:
        pygame.draw.rect(self.sup, SUELO, (0, 0, int(mundo.ancho * ESCALA), int(mundo.alto * ESCALA)))
        paso = int(ESCALA)
        for x in range(0, int(mundo.ancho) + 1):
            pygame.draw.line(self.sup, REJILLA, (x * paso, 0), (x * paso, int(mundo.alto * ESCALA)))
        for y in range(0, int(mundo.alto) + 1):
            pygame.draw.line(self.sup, REJILLA, (0, y * paso), (int(mundo.ancho * ESCALA), y * paso))
        for x, y, w, h in mundo.obstaculos:
            rect = pygame.Rect(*self._px(x, y), int(w * ESCALA), int(h * ESCALA))
            pygame.draw.rect(self.sup, MURO, rect)
            pygame.draw.rect(self.sup, MURO_BORDE, rect, 2)

    def _contenedor(self, mundo) -> None:
        cx, cy = self._px(*mundo.contenedor)
        pygame.draw.circle(self.sup, CONTENEDOR, (cx, cy), int(RADIO_CONTENEDOR * ESCALA))
        pygame.draw.circle(self.sup, MURO_BORDE, (cx, cy), int(RADIO_CONTENEDOR * ESCALA), 2)
        pygame.draw.line(self.sup, MURO_BORDE, (cx - 14, cy - 4), (cx + 14, cy - 4), 2)

    def _basura(self, bx: float, by: float) -> None:
        cx, cy = self._px(bx, by)
        r = int(RADIO_BASURA * ESCALA)
        pygame.draw.rect(self.sup, BASURA, (cx - r, cy - r, r * 2, r * 2), border_radius=3)
        pygame.draw.rect(self.sup, BASURA_BORDE, (cx - r, cy - r, r * 2, r * 2), 2, border_radius=3)

    def _robot(self, mundo) -> None:
        cx, cy = self._px(mundo.x, mundo.y)
        cuerpo = int(RADIO_ROBOT * ESCALA)
        # Direccion: una linea fina marca el frente del chasis.
        fx = cx + math.cos(mundo.theta) * cuerpo
        fy = cy + math.sin(mundo.theta) * cuerpo
        pygame.draw.line(self.sup, ROBOT_OSCURO, (cx, cy), (fx, fy), 3)
        # Tracks a los costados, perpendiculares al frente.
        px, py = -math.sin(mundo.theta), math.cos(mundo.theta)
        for lado in (-1, 1):
            ax = cx + px * cuerpo * 0.85 * lado
            ay = cy + py * cuerpo * 0.85 * lado
            bx = cx + px * cuerpo * 0.85 * lado - math.cos(mundo.theta) * cuerpo * 0.8
            by = cy + py * cuerpo * 0.85 * lado - math.sin(mundo.theta) * cuerpo * 0.8
            pygame.draw.line(self.sup, ROBOT_OSCURO, (ax, ay), (bx, by), 5)
        pygame.draw.circle(self.sup, ROBOT, (cx, cy), cuerpo)
        pygame.draw.circle(self.sup, ROBOT_OSCURO, (cx, cy), cuerpo, 2)
        # Ojos: dos lentes en el morro, apuntando al frente.
        for desvio in (-0.35, 0.35):
            ox = cx + math.cos(mundo.theta) * cuerpo * 0.45 - math.sin(mundo.theta) * cuerpo * desvio
            oy = cy + math.sin(mundo.theta) * cuerpo * 0.45 + math.cos(mundo.theta) * cuerpo * desvio
            pygame.draw.circle(self.sup, OJOS, (int(ox), int(oy)), 3)
        # Cubo cargado encima del chasis.
        if mundo.llevando:
            pygame.draw.rect(
                self.sup, BASURA, (cx - 7, cy - cuerpo - 12, 14, 12), border_radius=2
            )
            pygame.draw.rect(
                self.sup, BASURA_BORDE, (cx - 7, cy - cuerpo - 12, 14, 12), 2, border_radius=2
            )

    def _hud(self, mundo, mensaje: str) -> None:
        lineas = [
            f"escenario {self.escena.nombre}   pasos {mundo.pasos}",
            f"bateria {mundo.bateria:5.1f}%   cargando {mundo.llevando}/2",
            f"recogidas {mundo.recogidas}   entregadas {mundo.entregadas}   "
            f"distancia {mundo.distancia:5.1f} m",
            f"kcal {mundo.calorias():6.4f}   choques {mundo.colisiones}",
        ]
        y = 6
        for linea in lineas:
            self.sup.blit(self.fuente.render(linea, True, TEXTO_TENUE), (8, y))
            y += 16
        ayuda = mensaje or "flechas mover   espacio recoger/entregar   R reiniciar   1-3 escenario   ESC salir"
        self.sup.blit(self.fuente_chica.render(ayuda, True, TEXTO), (8, self.alto_ventana - 20))


def tamano_ventana(escena) -> tuple[int, int]:
    return int(escena.mundo.ancho * ESCALA), int(escena.mundo.alto * ESCALA)
