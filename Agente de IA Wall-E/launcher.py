"""Lanzador de la cabina de WALL-E.

Abre el servidor local si no está corriendo y muestra la interfaz en el
navegador. Pensado para el acceso directo del escritorio: no deja ventanas
negras ni consolas abiertas.

Uso:
    pythonw launcher.py
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8765/"
HEALTH = URL + "api/health"


def server_is_up(timeout: float = 0.9) -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def python_command() -> str:
    """Prefiere pythonw para no abrir consola en Windows."""
    candidates = [
        Path(sys.executable).with_name("pythonw.exe"),
        Path(sys.executable).with_name("python.exe"),
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def start_server() -> subprocess.Popen:
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return subprocess.Popen(
        [python_command(), str(ROOT / "server.py"), "--no-browser"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def main() -> None:
    if not server_is_up():
        start_server()
        for _ in range(80):
            if server_is_up(0.35):
                break
            time.sleep(0.25)
    webbrowser.open(URL)


if __name__ == "__main__":
    main()
