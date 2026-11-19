"""Pruebas de la cabina: cerebro importable y API viva.

No necesitan red, ni Ollama, ni camara: el servidor degrada solo y estos tests
verifican justamente eso. Levantan `server.py` en un puerto libre, hablan con
la API como lo haria el navegador y lo apagan.

    python -m unittest -v pruebas_agente
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parent


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class PruebasCerebro(unittest.TestCase):
    """El paquete `brain` tiene que importar sin dependencias externas."""

    def test_importa_el_cerebro(self) -> None:
        sys.path.insert(0, str(RAIZ))
        try:
            from brain.agent import Agent  # noqa: WPS433
            from brain.memory import Memory  # noqa: WPS433
            from brain.tools import Tools  # noqa: WPS433
            from hardware.esp32_link import Esp32Link  # noqa: WPS433
            from vision.reflex import Camera  # noqa: WPS433
        finally:
            sys.path.pop(0)

        self.assertTrue(callable(Agent))
        self.assertTrue(callable(Tools))
        self.assertTrue(callable(Memory))
        self.assertTrue(callable(Esp32Link))
        self.assertTrue(callable(Camera))

    def test_memoria_sqlite(self) -> None:
        import tempfile

        sys.path.insert(0, str(RAIZ))
        try:
            from brain.memory import Memory  # noqa: WPS433
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            memoria = Memory(Path(tmp) / "memoria.db")
            try:
                memoria.remember("el cubo azul vive en el patio")
                encontrado = memoria.search("cubo azul")
                self.assertTrue(encontrado)
                self.assertEqual(memoria.count(), 1)
                self.assertIn("cubo azul", encontrado[0]["text"])
            finally:
                memoria.close()

    def test_emociones_responden(self) -> None:
        import tempfile

        sys.path.insert(0, str(RAIZ))
        try:
            from brain.emotions import EmotionState  # noqa: WPS433
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            estado = EmotionState(Path(tmp) / "emociones.json")
            antes = estado.snapshot()["energy"]
            self.assertIsInstance(antes, (int, float))
            estado.interact("saludo")
            despues = estado.snapshot()
            self.assertIn("mood", despues)
            self.assertIn("interactions", despues)


class PruebasServidor(unittest.TestCase):
    """La API HTTP: arranca, responde y se apaga."""

    proceso: subprocess.Popen | None = None
    puerto: int = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls.puerto = puerto_libre()
        cls.proceso = subprocess.Popen(
            [sys.executable, "server.py", "--no-browser", "--port", str(cls.puerto)],
            cwd=str(RAIZ),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        limite = time.time() + 60
        while time.time() < limite:
            if cls.proceso.poll() is not None:
                salida = cls.proceso.stdout.read() if cls.proceso.stdout else ""
                raise AssertionError(f"el servidor murio al arrancar:\n{salida}")
            try:
                with urllib.request.urlopen(cls.url("/api/health"), timeout=1) as r:
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)
        raise AssertionError("el servidor no respondio en 60 s")

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.proceso and cls.proceso.poll() is None:
            cls.proceso.terminate()
            try:
                cls.proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.proceso.kill()

    @classmethod
    def url(cls, ruta: str) -> str:
        return f"http://127.0.0.1:{cls.puerto}{ruta}"

    def pedir(self, ruta: str, datos: dict | None = None) -> dict:
        cuerpo = None
        cabeceras = {"Content-Type": "application/json"}
        if datos is not None:
            cuerpo = json.dumps(datos).encode("utf-8")
        peticion = urllib.request.Request(self.url(ruta), data=cuerpo, headers=cabeceras)
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))

    def test_health(self) -> None:
        self.assertTrue(self.pedir("/api/health")["ok"])

    def test_estado_degradado_sin_dependencias(self) -> None:
        estado = self.pedir("/api/state")
        self.assertTrue(estado["ok"])
        self.assertTrue(estado["ready"])
        # Sin pyserial, opencv ni Ollama la cabina igual queda lista.
        self.assertIn("ollama", estado)
        self.assertIn("camera", estado)
        self.assertIn("emotion", estado)
        self.assertEqual(estado["mode"], "simulacion")

    def test_companion_y_eventos(self) -> None:
        self.assertTrue(self.pedir("/api/companion")["ok"])
        self.assertTrue(self.pedir("/api/events?limit=5")["ok"])

    def test_memoria_por_api(self) -> None:
        agregado = self.pedir("/api/memory", {"text": "prueba automatica de memoria"})
        self.assertTrue(agregado["ok"])
        listado = self.pedir("/api/memory?q=" + quote("prueba automatica"))
        self.assertTrue(listado["ok"])
        entradas = listado.get("items") or listado.get("memories") or []
        self.assertTrue(
            any("prueba automatica" in json.dumps(e, ensure_ascii=False)
                for e in entradas),
            f"la memoria no devolvio lo recien guardado: {listado}",
        )

    def test_voz_falla_limpio_sin_piper(self) -> None:
        try:
            self.pedir("/api/tts", {"text": "hola"})
        except urllib.error.HTTPError as exc:
            self.assertIn(exc.code, (503, 500))

    def test_chat_sin_ollama_no_rompe(self) -> None:
        respuesta = self.pedir("/api/chat", {"message": "quien sos"})
        self.assertTrue(respuesta["ok"])
        self.assertIsInstance(respuesta.get("reply"), str)
        self.assertTrue(respuesta["reply"].strip())

    def test_sirve_la_interfaz(self) -> None:
        with urllib.request.urlopen(self.url("/"), timeout=30) as respuesta:
            html = respuesta.read().decode("utf-8", errors="replace")
        self.assertIn('id="root"', html)
        self.assertIn("assets/index-", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
