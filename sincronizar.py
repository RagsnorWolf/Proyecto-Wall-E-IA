"""Copia el nucleo compartido a las carpetas que lo necesitan.

Cada una de las tres carpetas tiene que poder descargarse y correr sola. La
unica que depende de otra es el Cerebro, que necesita la fisica del Simulador:

  Cerebro -> vendor/simulador   (fisica, escenarios, entorno, render)

El Agente de IA no copia nada: su cerebro es propio (brain/) y no usa el PPO.

La fuente de verdad es siempre `Simulador Wall-E/simulador`. Esto genera
copias, nunca las edita a mano.

    python sincronizar.py              # copia (o actualiza) las copias
    python sincronizar.py --verificar  # solo compara; sale 1 si estan viejas

La CI corre con --verificar, asi que un cambio en el nucleo sin sincronizar
rompe el build en vez de dejar dos versiones distintas circulando.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CEREBRO = RAIZ / "Cerebro Wall-E (Actividad Fisica + PPO) .py"
SIMULADOR = RAIZ / "Simulador Wall-E"

ARCHIVOS_SIMULADOR = ("__init__.py", "fisica.py", "escenarios.py", "entorno.py", "render.py")

# (origen, destino, archivos)
TRABAJOS = [
    (SIMULADOR / "simulador", CEREBRO / "vendor" / "simulador", ARCHIVOS_SIMULADOR),
]

AVISO = (
    "Carpeta generada por sincronizar.py desde la fuente de verdad del repo.\n"
    "No editar a mano: se sobrescribe. Para cambiar algo, editá el original\n"
    "y volvé a correr `python sincronizar.py` desde la raiz.\n"
)


def _texto_aviso() -> str:
    return AVISO


def sincronizar(verificar: bool) -> int:
    problemas: list[str] = []
    copiados = 0

    for origen, destino, archivos in TRABAJOS:
        if not origen.is_dir():
            problemas.append(f"falta el origen {origen}")
            continue
        if not verificar:
            destino.mkdir(parents=True, exist_ok=True)
            (destino / "LEEME.txt").write_text(_texto_aviso(), encoding="utf-8")

        for nombre in archivos:
            fuente = origen / nombre
            objetivo = destino / nombre
            if not fuente.is_file():
                problemas.append(f"falta {fuente}")
                continue
            if verificar:
                if not objetivo.is_file():
                    problemas.append(f"sin copiar: {objetivo}")
                elif not filecmp.cmp(fuente, objetivo, shallow=False):
                    problemas.append(f"desactualizado: {objetivo}")
            else:
                shutil.copy2(fuente, objetivo)
                copiados += 1

    if problemas:
        etiqueta = "verificacion" if verificar else "sincronizacion"
        print(f"[{etiqueta}] {len(problemas)} problema(s):")
        for problema in problemas:
            print(f"  - {problema}")
        if verificar:
            print("  corre: python sincronizar.py")
        return 1

    if verificar:
        print("[verificacion] las copias vendorizadas estan al dia")
    else:
        print(f"[sincronizacion] {copiados} archivo(s) copiados")
    return 0


def principal() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza las copias vendorizadas")
    parser.add_argument("--verificar", action="store_true",
                        help="solo compara, no escribe (usado por la CI)")
    args = parser.parse_args()
    return sincronizar(args.verificar)


if __name__ == "__main__":
    raise SystemExit(principal())
