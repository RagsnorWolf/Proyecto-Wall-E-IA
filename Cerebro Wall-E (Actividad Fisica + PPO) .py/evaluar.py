"""Mira la politica entrenada jugando sola.

    python evaluar.py                       # 3 episodios, sin ventana
    python evaluar.py --ventana             # con visor pygame
    python evaluar.py --escenario patio --episodios 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cerebro import AgentePPO, EntornoActividad


def _utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def principal() -> int:
    _utf8()
    from entrenar_ppo import MODELO

    parser = argparse.ArgumentParser(description="Evalua el Cerebro PPO")
    parser.add_argument("--modelo", type=Path, default=MODELO)
    parser.add_argument("--escenario", default="chatarreria")
    parser.add_argument("--episodios", type=int, default=3)
    parser.add_argument("--semilla", type=int, default=1234)
    parser.add_argument("--ventana", action="store_true", help="dibuja la partida en pygame")
    parser.add_argument("--muestreo", action="store_true",
                        help="usa la politica estocastica en vez del argmax")
    args = parser.parse_args()

    if not args.modelo.is_file():
        print(f"[error] no existe {args.modelo}. Entrena primero con entrenar_ppo.py")
        return 1

    agente = AgentePPO.cargar(args.modelo)
    entorno = EntornoActividad(
        args.escenario, semilla=args.semilla, render_mode="human" if args.ventana else None
    )

    print(f"{'ep':>3} {'retorno':>9} {'entregas':>9} {'cobertura':>10} {'pasos':>6} {'choques':>8}")
    retornos: list[float] = []
    for i in range(args.episodios):
        obs, _ = entorno.reset(semilla=args.semilla + i)
        total = 0.0
        pasos = 0
        while True:
            accion, _, _ = agente.actuar(obs, determinista=not args.muestreo)
            obs, recompensa, terminado, truncado, info = entorno.step(accion)
            total += recompensa
            pasos += 1
            if terminado or truncado:
                break
        retornos.append(total)
        print(
            f"{i:>3} {total:>9.2f} {info['entregadas']:>9} "
            f"{info['cobertura']:>9.1f}m2 {pasos:>6} {info['colisiones']:>8}"
        )

    entorno.close()
    media = sum(retornos) / max(len(retornos), 1)
    varianza = sum((r - media) ** 2 for r in retornos) / max(len(retornos), 1)
    print(f"[media] retorno={media:.2f} desviacion={varianza ** 0.5:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
