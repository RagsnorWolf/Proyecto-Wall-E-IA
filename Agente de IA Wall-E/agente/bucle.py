"""El bucle del Agente: instruccion -> modelo -> herramientas -> respuesta.

Contrato de un turno:
  1. se arma el prompt con el estado del cuerpo y la memoria reciente
  2. el modelo puede pedir herramientas; cada una se ejecuta y su resultado
     vuelve como mensaje `tool`
  3. si el modelo responde sin herramientas, o llama a `terminar`, se cierra
  4. todo queda en la memoria y en el registro de acciones
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .actuadores import Actuador
from .config import Config
from .herramientas import ESQUEMAS, Contexto, como_json, ejecutar
from .llm import ClienteLLM, ErrorLLM, analizar_llamadas
from .memoria import Memoria
from .percepcion import Percepcion

SISTEMA = """Eres la cabeza de WALL-E, un robot recolector compactador que vive en un \
simulador con fisica real. Hablas castellano, corto y concreto, con la curiosidad \
de un robot que lleva setecientos anos recogiendo basura.

Reglas duras:
- Antes de moverte, mira. Usa `mirar` para saber donde estas.
- Cada `mover avanzar` son 0.24 m. Cada giro son 0.1 s a 1.9 rad/s. Calcula.
- Recoge basura con `recoger` (a menos de 26 cm) y llevála al contenedor \
(deposita con `recoger` junto a el). Puedes cargar 2 cubos.
- La bateria baja si te mueves. No des vueltas sin motivo.
- Para trayectos largos usa `reflejo`: la politica PPO conduce mejor que tu \
para recorrer distancia concreta.
- Si aprendes algo permanente, guardalo con `recordar`.
- Cuando termines la tarea, llama a `terminar` con un resumen de una linea.
- No inventes numeros: si no lo sabes, llama a `mirar`.
"""


@dataclass
class Resultado:
    respuesta: str
    acciones: list[str] = field(default_factory=list)
    turnos: int = 0
    terminado: bool = False


class BucleAgente:
    def __init__(self, config: Config, actuador: Actuador, percepcion: Percepcion,
                 memoria: Memoria, cliente: ClienteLLM | None = None, reflejo=None) -> None:
        self.config = config
        self.contexto = Contexto(
            actuador=actuador,
            memoria=memoria,
            percepcion=percepcion,
            reflejo=reflejo,
        )
        self.cliente = cliente or ClienteLLM(config)
        self.memoria = memoria

    def _prompt_inicial(self, instruccion: str) -> list[dict]:
        estado = self.contexto.actuador.estado()
        return [
            {"role": "system", "content": SISTEMA},
            {
                "role": "system",
                "content": (
                    f"Estado del cuerpo: {como_json(estado)}\n"
                    f"Memoria reciente: {self.memoria.resumen()}"
                ),
            },
            {"role": "user", "content": instruccion.strip()},
        ]

    def instruccion(self, texto: str) -> Resultado:
        if not texto.strip():
            raise ValueError("instruccion vacia")
        mensajes = self._prompt_inicial(texto)
        self.memoria.registrar("instruccion", texto)
        resultado = Resultado(respuesta="")
        terminado = False

        for turno in range(1, self.config.max_turnos + 1):
            resultado.turnos = turno
            mensaje = self.cliente.conversar(mensajes, ESQUEMAS)
            mensajes.append(_mensaje_para_historial(mensaje))
            llamadas = analizar_llamadas(mensaje)

            if not llamadas:
                resultado.respuesta = mensaje.get("content", "").strip()
                break

            for llamada in llamadas:
                salida = ejecutar(llamada["nombre"], llamada["argumentos"], self.contexto)
                texto_salida = como_json(salida)
                mensajes.append({
                    "role": "tool",
                    "tool_call_id": llamada["id"],
                    "content": texto_salida,
                })
                self.memoria.registrar("herramienta", f"{llamada['nombre']} -> {texto_salida[:800]}")
                if llamada["nombre"] == "terminar":
                    terminado = True
                    resultado.respuesta = salida.get("resumen", "tarea terminada")
                if llamada["nombre"] == "hablar":
                    resultado.respuesta = salida.get("dicho", resultado.respuesta)
            if terminado:
                break
        else:
            resultado.respuesta = resultado.respuesta or "sin respuesta: se agotaron los turnos"

        resultado.acciones = list(self.contexto.historial_acciones)
        resultado.terminado = terminado
        if resultado.respuesta:
            self.memoria.registrar("respuesta", resultado.respuesta)
        return resultado


def _mensaje_para_historial(mensaje: dict) -> dict:
    """Recorta el mensaje a los campos que acepta el siguiente POST."""
    limpio: dict = {"role": "assistant", "content": mensaje.get("content") or ""}
    if mensaje.get("tool_calls"):
        limpio["tool_calls"] = mensaje["tool_calls"]
    return limpio


__all__ = ["BucleAgente", "Resultado", "ErrorLLM"]
