"""Manejo manual del simulador: teclado, tres escenarios, marcador en vivo.

    python main.py                 # chatarreria
    python main.py --escenario patio
    python main.py --sin-ventana   # prueba de humo headless (CI)

Sin ventana corre un piloto automatico tonto durante N pasos y devuelve el
resumen; sirve para CI y para comprobar que la fisica no se rompio.
"""
from __future__ import annotations

import argparse
import sys

from simulador import ACCIONES, Escena, escenarios


def _utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


MAPA_TECLAS = {
    "flecha_arriba": 0,   # avanzar
    "flecha_izquierda": 1,
    "flecha_derecha": 2,
    "espacio": 3,         # recoger / entregar
}


def headless(escenario: str, pasos: int) -> int:
    escena = Escena(escenario, semilla=7)
    for _ in range(pasos):
        _, terminado, truncado = escena.paso(0)
        if terminado or truncado:
            break
    estado = escena.mundo.estado()
    print(
        f"[headless] escenario={escenario} pasos={estado['pasos']} "
        f"bateria={estado['bateria']:.1f} x={estado['x']:.2f} y={estado['y']:.2f} "
        f"choques={estado['colisiones']} distancia={estado['distancia']:.2f}m"
    )
    return 0


def jugar(escenario: str, semilla: int | None) -> int:
    try:
        import pygame
    except ImportError:
        print("[error] falta pygame para abrir la ventana.")
        print("        Windows:  .\\.venv\\Scripts\\python.exe -m pip install pygame")
        print("        Cualquier SO:  python -m pip install pygame")
        print("        Sin ventana tambien se puede:  python main.py --sin-ventana --pasos 200")
        return 1

    from simulador.render import Dibujante, tamano_ventana

    pygame.init()
    pygame.display.set_caption("Simulador WALL-E")
    escena = Escena(escenario, semilla=semilla)
    ancho, alto = tamano_ventana(escena)
    pantalla = pygame.display.set_mode((ancho, alto))
    dibujante = Dibujante(escena, ancho, alto)
    reloj = pygame.time.Clock()
    mensaje = ""

    corriendo = True
    while corriendo:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                corriendo = False
            elif evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    corriendo = False
                elif evento.key == pygame.K_r:
                    escena.reiniciar()
                    mensaje = ""
                elif evento.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    indice = evento.key - pygame.K_1
                    nombre = escenarios.ESCENARIOS[indice]
                    escena = Escena(nombre, semilla=semilla)
                    ancho, alto = tamano_ventana(escena)
                    pantalla = pygame.display.set_mode((ancho, alto))
                    dibujante = Dibujante(escena, ancho, alto)
                    mensaje = f"escenario {nombre}"

        teclas = pygame.key.get_pressed()
        accion = None
        if teclas[pygame.K_UP]:
            accion = MAPA_TECLAS["flecha_arriba"]
        elif teclas[pygame.K_LEFT]:
            accion = MAPA_TECLAS["flecha_izquierda"]
        elif teclas[pygame.K_RIGHT]:
            accion = MAPA_TECLAS["flecha_derecha"]
        elif teclas[pygame.K_SPACE]:
            accion = MAPA_TECLAS["espacio"]

        if accion is not None:
            eventos, terminado, truncado = escena.paso(accion)
            if eventos["recogido"]:
                mensaje = "cubo recogido"
            if eventos["entregado"]:
                mensaje = "entrega completada"
            if terminado or truncado:
                motivo = "sin basura" if not escena.mundo.basuras else (
                    "bateria agotada" if eventos["sin_bateria"] else "tiempo"
                )
                mensaje = f"episodio terminado ({motivo}) - R para reiniciar"
                escena.reiniciar()

        pantalla.blit(dibujante.dibujar(mensaje), (0, 0))
        pygame.display.flip()
        reloj.tick(30)

    pygame.quit()
    return 0


def principal() -> int:
    _utf8()
    parser = argparse.ArgumentParser(description="Simulador 2D de WALL-E")
    parser.add_argument("--escenario", default="chatarreria", choices=escenarios.ESCENARIOS)
    parser.add_argument("--semilla", type=int, default=None)
    parser.add_argument("--sin-ventana", action="store_true", help="prueba headless, sin pygame")
    parser.add_argument("--pasos", type=int, default=120)
    args = parser.parse_args()

    if args.sin_ventana:
        return headless(args.escenario, args.pasos)
    return jugar(args.escenario, args.semilla)


if __name__ == "__main__":
    raise SystemExit(principal())
