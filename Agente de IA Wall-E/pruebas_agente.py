"""Pruebas del Agente: bucle completo contra un servidor OpenAI falso local.

    python -m unittest -v pruebas_agente

El servidor falso devuelve un tool_call a `mirar` y despues a `terminar`, asi
se verifica de punta a punta: formato de mensajes, despacho de herramientas,
memoria, y cierre del bucle. Sin red y sin claves.
"""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agente import BucleAgente, ClienteLLM, Config, Reflejo
from agente.actuadores import ActuadorSimulado
from agente.memoria import Memoria
from agente.percepcion import PercepcionSimulada


class _Manejador(BaseHTTPRequestHandler):
    llamadas: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 - firma de la libreria
        largo = int(self.headers.get("Content-Length", "0"))
        cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        _Manejador.llamadas.append(cuerpo)
        turno = len(_Manejador.llamadas)
        if turno == 1:
            mensaje = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "mirar", "arguments": "{}"},
                }],
            }
        else:
            mensaje = {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "terminar",
                        "arguments": json.dumps({"resumen": "mire el mundo y cerre"}),
                    },
                }],
            }
        datos = json.dumps({"choices": [{"message": mensaje}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, formato: str, *args) -> None:  # silencio en los tests
        pass


class PruebaBucle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Manejador)
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()
        puerto = cls.servidor.server_address[1]
        cls.config = Config(base_url=f"http://127.0.0.1:{puerto}/v1", modelo="falso", max_turnos=6)
        import os
        os.environ.setdefault(cls.config.variable_clave, "clave-de-prueba")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def setUp(self) -> None:
        _Manejador.llamadas.clear()

    def test_bucle_completo(self) -> None:
        actuador = ActuadorSimulado("chatarreria", semilla=3)
        memoria = Memoria(_ruta_temporal(self))
        try:
            percepcion = PercepcionSimulada(actuador)
            bucle = BucleAgente(self.config, actuador, percepcion, memoria)
            resultado = bucle.instruccion("mira donde estas")
            self.assertTrue(resultado.terminado)
            self.assertIn("mire el mundo", resultado.respuesta)
            self.assertGreaterEqual(len(_Manejador.llamadas), 2)
            # El segundo POST debe llevar el resultado de la herramienta.
            segundo = _Manejador.llamadas[1]["messages"]
            papeles = [m["role"] for m in segundo]
            self.assertIn("tool", papeles)
            self.assertEqual(segundo[-1]["role"], "tool")
            self.assertIn("herramienta", json.dumps(memoria.ultimos_eventos(5)))
        finally:
            memoria.cerrar()

    def test_percepcion_describe_el_mundo(self) -> None:
        actuador = ActuadorSimulado("patio", semilla=2)
        texto = PercepcionSimulada(actuador).describir()
        self.assertIn("Bateria", texto)
        self.assertIn("basura", texto.lower())

    def test_memoria_busca_por_palabra(self) -> None:
        memoria = Memoria(_ruta_temporal(self))
        try:
            memoria.recordar("el contenedor esta en la esquina noreste", "contenedor")
            encontrados = memoria.buscar("donde esta el contenedor")
            self.assertTrue(encontrados)
            self.assertIn("noreste", encontrados[0])
        finally:
            memoria.cerrar()

    def test_cliente_sin_clave_avisa(self) -> None:
        config = Config(variable_clave="VARIABLE_QUE_NO_EXISTE_123")
        from agente.llm import ErrorLLM
        with self.assertRaises(ErrorLLM):
            ClienteLLM(config)


class PruebaReflejo(unittest.TestCase):
    def test_reflejo_inexistente_es_none(self) -> None:
        self.assertIsNone(Reflejo.cargar_si_existe("no_existe.json"))


def _ruta_temporal(caso: unittest.TestCase):
    import tempfile
    from pathlib import Path

    carpeta = Path(tempfile.mkdtemp(prefix="walle_prueba_"))
    caso.addCleanup(lambda: _limpiar(carpeta))
    return carpeta / "memoria.db"


def _limpiar(carpeta) -> None:
    import shutil

    shutil.rmtree(carpeta, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
