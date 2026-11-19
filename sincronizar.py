"""Copia el nucleo compartido a las carpetas que lo necesitan.

Cada una de las tres carpetas tiene que poder descargarse y correr sola. Para
eso, las que dependen de otra llevan una copia vendorizada:

  Cerebro -> vendor/simulador   (fisica, escenarios, entorno, render)
  Agente  -> vendor/simulador   (el mismo)
  Agente  -> vendor/cerebro     (red, ppo, politica)

La fuente de verdad son siempre `Simulador Wall-E/simulador` y
`Cerebro .../cerebro`. Esto genera copias, nunca las edita a mano.

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
AGENTE = RAIZ / "Agente de IA Wall-E"
SIMULADOR = RAIZ / "Simulador Wall-E"

ARCHIVOS_SIMULADOR = ("__init__.py", "fisica.py", "escenarios.py", "entorno.py", "render.py")
ARCHIVOS_CEREBRO = ("red.py", "ppo.py", "politica.py")

INICIO_CEREBRO = '''"""Politica PPO vendorizada para el Agente.

GENERADO por sincronizar.py desde `Cerebro Wall-E .../cerebro`.
No editar a mano: se sobrescribe en la proxima sincronizacion.
"""
from .politica import PoliticaRefleja, ruta_por_defecto
from .ppo import AgentePPO, Hiperparametros
from .red import RedActorCritica

__all__ = [
    "AgentePPO",
    "Hiperparametros",
    "PoliticaRefleja",
    "RedActorCritica",
    "ruta_por_defecto",
]
'''

# (origen, destino, archivos, contenido_generado_para__init__)
TRABAJOS = [
    (SIMULADOR / "simulador", CEREBRO / "vendor" / "simulador", ARCHIVOS_SIMULADOR, None),
    (SIMULADOR / "simulador", AGENTE / "vendor" / "simulador", ARCHIVOS_SIMULADOR, None),
    (CEREBRO / "cerebro", AGENTE / "vendor" / "cerebro", ARCHIVOS_CEREBRO, INICIO_CEREBRO),
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

    for origen, destino, archivos, inicio in TRABAJOS:
        if not origen.is_dir():
            problemas.append(f"falta el origen {origen}")
            continue
        if not verificar:
            destino.mkdir(parents=True, exist_ok=True)
            (destino / "LEEME.txt").write_text(_texto_aviso(), encoding="utf-8")
        if inicio is not None and not verificar:
            (destino / "__init__.py").write_text(inicio, encoding="utf-8")

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
