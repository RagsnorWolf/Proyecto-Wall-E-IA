"""Cliente HTTP para cualquier API compatible con OpenAI (`/chat/completions`).

Sin SDK: urllib de la biblioteca estandar. Funciona igual contra OpenAI,
Groq, Together, DeepSeek, OpenRouter, Ollama (`/v1` local) o cualquier
servidor que hable el mismo dialecto.

Soporta tool calling (function calling) y devuelve el mensaje crudo del
modelo. Los reintentos solo cubren fallos de red y 5xx/429; un 400 se
propaga porque significa que el payload esta mal y reintentar no arregla nada.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .config import Config


class ErrorLLM(RuntimeError):
    """El proveedor no respondio o respondio algo que no es un mensaje."""


class ClienteLLM:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.clave = os.environ.get(config.variable_clave, "").strip()
        if not self.clave and config.proveedor not in ("ollama", "local"):
            raise ErrorLLM(
                f"falta la clave del modelo. Define {config.variable_clave} en el entorno, "
                f"por ejemplo:  $env:{config.variable_clave}=\"tu-clave\""
            )

    # --- HTTP -------------------------------------------------------------
    def _url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/chat/completions"

    def _post(self, payload: dict) -> dict:
        cuerpo = json.dumps(payload).encode("utf-8")
        cabeceras = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "wall-e-agente/1.0",
        }
        if self.clave:
            cabeceras["Authorization"] = f"Bearer {self.clave}"

        ultimo_error = ""
        for intento in range(1, self.config.reintentos + 1):
            peticion = urllib.request.Request(
                self._url(), data=cuerpo, headers=cabeceras, method="POST"
            )
            try:
                with urllib.request.urlopen(peticion, timeout=self.config.tiempo_limite) as respuesta:
                    crudo = respuesta.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(crudo)
                except json.JSONDecodeError as exc:
                    raise ErrorLLM(f"respuesta no es JSON: {crudo[:200]!r}") from exc
            except urllib.error.HTTPError as exc:
                detalle = exc.read().decode("utf-8", errors="replace")[:400]
                if exc.code in (408, 429) or 500 <= exc.code < 600:
                    ultimo_error = f"HTTP {exc.code}: {detalle}"
                    time.sleep(min(2.0 ** intento, 8.0))
                    continue
                raise ErrorLLM(f"HTTP {exc.code} de {self.config.base_url}: {detalle}") from exc
            except urllib.error.URLError as exc:
                ultimo_error = f"red: {exc.reason}"
                time.sleep(min(2.0 ** intento, 8.0))
            except TimeoutError:
                ultimo_error = "tiempo agotado"
                time.sleep(min(2.0 ** intento, 8.0))
        raise ErrorLLM(f"sin respuesta tras {self.config.reintentos} intentos ({ultimo_error})")

    # --- API --------------------------------------------------------------
    def conversar(self, mensajes: list[dict], herramientas: list[dict] | None = None) -> dict:
        """Devuelve el mensaje del asistente: {role, content, tool_calls?}."""
        payload: dict = {
            "model": self.config.modelo,
            "messages": mensajes,
            "temperature": self.config.temperatura,
            "max_tokens": self.config.max_tokens,
        }
        if herramientas:
            payload["tools"] = herramientas
            payload["tool_choice"] = "auto"

        datos = self._post(payload)
        try:
            mensaje = datos["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ErrorLLM(f"respuesta sin choices[0].message: {str(datos)[:200]}") from exc

        mensaje.setdefault("role", "assistant")
        mensaje["content"] = mensaje.get("content") or ""
        return mensaje

    def ping(self) -> str:
        """Una llamada minima para comprobar credenciales y modelo."""
        mensaje = self.conversar([{"role": "user", "content": "Responde solo: ok"}])
        return (mensaje.get("content") or "").strip()


def analizar_llamadas(mensaje: dict) -> list[dict]:
    """Normaliza tool_calls a [{id, nombre, argumentos(dict)}]."""
    crudas = mensaje.get("tool_calls") or []
    llamadas: list[dict] = []
    for llamada in crudas:
        funcion = llamada.get("function") or {}
        nombre = funcion.get("name") or ""
        crudos = funcion.get("arguments") or "{}"
        if isinstance(crudos, dict):
            argumentos = crudos
        else:
            try:
                argumentos = json.loads(crudos)
            except json.JSONDecodeError:
                argumentos = {"_crudo": crudos}
        if not isinstance(argumentos, dict):
            argumentos = {"_crudo": argumentos}
        llamadas.append({
            "id": llamada.get("id") or f"llamada_{len(llamadas)}",
            "nombre": nombre,
            "argumentos": argumentos,
        })
    return llamadas
