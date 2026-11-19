"""Lanzador de la cabina de WALL-E.

Abre el servidor local si no está corriendo y muestra la interfaz en el
navegador. Pensado para el acceso directo del escritorio: no deja ventanas
negras ni consolas abiertas.

Si el puerto 8765 ya está ocupado por otra cosa (otra copia del proyecto, un
servidor viejo, cualquier programa), busca el primero libre y abre esa URL:
la interfaz siempre habla con el servidor que la sirvió, así que funciona en
cualquier puerto.

Uso:
    pythonw launcher.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "datos" / "servidor.log"
MARCA = "walle-cockpit"
PUERTOS = tuple(range(8765, 8775))
ESPERA = 40.0


# --------------------------------------------------------------------- util
def http_json(port: int, ruta: str, timeout: float = 1.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{ruta}", timeout=timeout) as r:
            if r.status != 200:
                return None
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def es_nuestra(port: int) -> bool:
    """True solo si en ese puerto responde *esta* cabina, no otra cosa."""
    data = http_json(port, "/api/health", timeout=0.8)
    return bool(data and data.get("app") == MARCA)


def puerto_libre(port: int) -> bool:
    """Bind real, sin SO_REUSEADDR: en Windows esa opción deja 'reservar'
    un puerto que ya está escuchando, y el lanzador elegiría uno ocupado."""
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def python_command() -> str:
    """Prefiere pythonw para no abrir consola en Windows."""
    for nombre in ("pythonw.exe", "python.exe"):
        candidato = Path(sys.executable).with_name(nombre)
        if candidato.exists():
            return str(candidato)
    return sys.executable


def arrancar(port: int) -> subprocess.Popen:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "ab", buffering=0)
    log.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} puerto {port} ===\n".encode())
    # sin buffer: si el servidor muere, el registro ya tiene la causa escrita
    entorno = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    extra = {}
    if sys.platform == "win32":
        extra["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    else:
        extra["start_new_session"] = True
    return subprocess.Popen(
        [python_command(), str(ROOT / "server.py"), "--no-browser", "--port", str(port)],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        env=entorno,
        **extra,
    )


def avisar(titulo: str, texto: str) -> None:
    """Ventana de error visible incluso con pythonw (sin consola)."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10)
            return
        except Exception:  # pragma: no cover - solo si falta user32
            pass
    print(f"{titulo}\n{texto}", file=sys.stderr)


def cola_del_log(lineas: int = 12) -> str:
    try:
        contenido = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(no hay registro)"
    return "\n".join(contenido[-lineas:])


# --------------------------------------------------------------------- main
def main() -> int:
    for port in PUERTOS:
        if es_nuestra(port):
            webbrowser.open(f"http://127.0.0.1:{port}/")
            return 0

    elegido = next((p for p in PUERTOS if puerto_libre(p)), None)
    if elegido is None:
        avisar(
            "WALL-E",
            "No hay ningún puerto libre entre 8765 y 8774.\n"
            "Cerrá el programa que los está usando y volvé a intentar.",
        )
        return 1

    proceso = arrancar(elegido)
    limite = time.time() + ESPERA
    while time.time() < limite:
        if proceso.poll() is not None:
            break
        if es_nuestra(elegido):
            webbrowser.open(f"http://127.0.0.1:{elegido}/")
            return 0
        time.sleep(0.25)

    avisar(
        "WALL-E no pudo arrancar",
        "El servidor no respondió en el puerto "
        f"{elegido}.\n\nÚltimas líneas de {LOG}:\n\n{cola_del_log()}",
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
