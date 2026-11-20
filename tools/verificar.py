#!/usr/bin/env python3
"""Chequeos del proyecto que corren igual en Windows y en Linux.

Existen como archivo y no como heredoc porque `python - <<'PY'` es sintaxis de
bash: en el runner de Windows, que usa PowerShell, no existe.

Uso:
    python tools/verificar.py bat        lanzadores sanos
    python tools/verificar.py obs        la observacion del entorno V5
    python tools/verificar.py contexto   README y 00-CONTEXTO en cada carpeta
    python tools/verificar.py todo       los tres

Sale con 1 si algo falla. Sin dependencias: stdlib pura, para que corra antes
de instalar nada.
"""
from __future__ import annotations

import ast
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CARPETAS = ("Cerebro Wall-E", "Simulador Wall-E", "Asistente IA Wall-E")

# Rutas que no son parte del proyecto y no se revisan.
EXCLUIR = (".venv", "venv", "node_modules", "__pycache__", ".git")


def _es_proyecto(p: pathlib.Path) -> bool:
    return not any(parte in EXCLUIR for parte in p.parts)


def chequear_bat() -> int:
    """Un .bat con BOM, con acentos o con una ruta absoluta rompe cmd."""
    fallos: list[str] = []
    bats = [p for p in RAIZ.rglob("*.bat") if _es_proyecto(p)]
    if not bats:
        print("no se encontro ningun .bat")
        return 1

    for p in bats:
        rel = p.relative_to(RAIZ)
        datos = p.read_bytes()

        if datos.startswith(b"\xef\xbb\xbf"):
            fallos.append(f"{rel}: tiene BOM")

        altos = [b for b in datos if b > 127]
        if altos:
            fallos.append(f"{rel}: {len(altos)} bytes no ASCII (un acento rompe cmd)")

        texto = datos.decode("utf-8", "replace")
        for mala in ("E:\\", "C:\\Users\\", "D:\\"):
            if mala in texto:
                fallos.append(f"{rel}: ruta absoluta clavada ({mala})")

        # INSTALAR.bat es el que crea el venv, asi que puede no tenerlo.
        # El resto tiene que resolver su ruta solo.
        if "%~dp0" not in texto and "cd /d" not in texto:
            fallos.append(f"{rel}: no resuelve su ruta con %~dp0")

        print(f"OK {rel}")

    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print("  -", f)
        return 1

    print(f"\n{len(bats)} lanzadores sanos")
    return 0


def chequear_obs() -> int:
    """OBS_DIM no es un literal: es 14 + SENSOR_COUNT + OBS_EXTRAS.

    Se evalua contra las constantes del modulo, sin importarlo: importar
    walle_env_v3 pide pybullet y torch, que no van en CI.
    """
    env = RAIZ / "Simulador Wall-E" / "walle_env_v3.py"
    if not env.exists():
        print(f"FALTA {env.relative_to(RAIZ)}")
        return 1

    arbol = ast.parse(env.read_text(encoding="utf-8"))
    constantes: dict[str, object] = {}

    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            destino = nodo.targets[0]
            if isinstance(destino, ast.Name):
                try:
                    constantes[destino.id] = ast.literal_eval(nodo.value)
                except Exception:
                    constantes.setdefault(destino.id, ast.unparse(nodo.value))

    interesantes = ("OBS_DIM", "OBS_EXTRAS", "SENSOR_COUNT", "LIDAR_RAYS")
    print("constantes:", {k: v for k, v in constantes.items() if k in interesantes})

    expr = constantes.get("OBS_DIM")
    if expr is None:
        print("no se encontro OBS_DIM")
        return 1

    # Solo aritmetica sobre nombres conocidos: nada de exec arbitrario.
    valor = eval(str(expr), {"__builtins__": {}}, dict(constantes))  # noqa: S307
    # La referencia se recalcula, no se escribe a mano: si el entorno gana
    # sentidos, este chequeo no tiene que cambiar.
    referencia = 14 + int(constantes["SENSOR_COUNT"]) + int(
        constantes["OBS_EXTRAS"]
    )
    if valor != referencia:
        print(f"OBS_DIM deberia ser {referencia}, evalua a {valor}")
        return 1

    print(f"OBS_DIM = {valor} OK")

    # El abanico tiene que cerrar: si alguien cambia un tramo y no el total,
    # el entorno levanta RuntimeError al importar y el entrenamiento no arranca.
    faltan = [
        k
        for k in ("FAN_INNER_RAYS", "FAN_OUTER_RAYS", "SENSOR_COUNT",
                  "FRONT_CONE_DEG")
        if k not in constantes
    ]
    if faltan:
        print(f"faltan constantes del abanico: {faltan}")
        return 1

    total = int(constantes["FAN_INNER_RAYS"]) + 2 * int(
        constantes["FAN_OUTER_RAYS"]
    )
    if total != int(constantes["SENSOR_COUNT"]):
        print(
            f"el abanico no cierra: {constantes['FAN_INNER_RAYS']} + "
            f"2x{constantes['FAN_OUTER_RAYS']} = {total}, "
            f"SENSOR_COUNT = {constantes['SENSOR_COUNT']}"
        )
        return 1

    print(
        f"abanico = {total} rayos "
        f"({constantes['FAN_INNER_RAYS']} al frente, "
        f"{constantes['FAN_OUTER_RAYS']} por costado) OK"
    )
    return 0


def chequear_contexto() -> int:
    """Cada carpeta se descarga sola: tiene que explicarse sola."""
    fallos: list[str] = []

    for nombre in CARPETAS:
        carpeta = RAIZ / nombre
        if not carpeta.is_dir():
            fallos.append(f"{nombre}: no existe")
            continue

        for obligatorio in ("README.md", "00-CONTEXTO.md"):
            archivo = carpeta / obligatorio
            if not archivo.exists():
                fallos.append(f"{nombre}: falta {obligatorio}")
            elif archivo.stat().st_size < 500:
                fallos.append(f"{nombre}: {obligatorio} parece vacio")
            else:
                print(f"OK {nombre}/{obligatorio}")

    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print("  -", f)
        return 1

    print(f"\n{len(CARPETAS)} carpetas con documentacion propia")
    return 0


def chequear_agente() -> int:
    """El agente necesita su personalidad y su build servido.

    Sin system.md el modelo no tiene caracter; sin static/index.html la cabina
    abre en blanco. Los dos son silenciosos hasta que alguien la abre.
    """
    base = RAIZ / "Asistente IA Wall-E"
    fallos: list[str] = []

    personalidad = base / "Modelo AI" / "prompts" / "system.md"
    if not personalidad.exists():
        fallos.append("falta Modelo AI/prompts/system.md")
    else:
        texto = personalidad.read_text(encoding="utf-8", errors="replace")
        if len(texto) < 200:
            fallos.append(f"system.md parece vacio ({len(texto)} caracteres)")
        else:
            print(f"OK system.md ({len(texto)} caracteres)")

    build = base / "Pagina Web" / "cockpit" / "static" / "index.html"
    if not build.exists() or build.stat().st_size == 0:
        fallos.append("falta el build servido (cockpit/static/index.html)")
    else:
        print(f"OK build servido ({build.stat().st_size} bytes)")

    if fallos:
        print("\nFALLOS:")
        for f in fallos:
            print("  -", f)
        return 1

    print("\nagente OK")
    return 0


CHEQUEOS = {
    "bat": chequear_bat,
    "obs": chequear_obs,
    "contexto": chequear_contexto,
    "agente": chequear_agente,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in (*CHEQUEOS, "todo"):
        print(__doc__)
        return 2

    nombres = list(CHEQUEOS) if argv[1] == "todo" else [argv[1]]
    fallo = 0
    for nombre in nombres:
        print(f"\n=== {nombre} ===")
        fallo |= CHEQUEOS[nombre]()
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
