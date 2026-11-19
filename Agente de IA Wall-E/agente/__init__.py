"""Agente de IA de WALL-E: cabeza (modelo de lenguaje) + cuerpo (simulador/placa)."""
from .actuadores import ActuadorConsola, ActuadorSerial, ActuadorSimulado, crear
from .bucle import BucleAgente, Resultado
from .cerebro import Reflejo
from .config import Config, cargar
from .llm import ClienteLLM, ErrorLLM
from .memoria import Memoria
from .percepcion import PercepcionCamara, PercepcionManual, PercepcionSimulada, crear_percepcion

__all__ = [
    "Config",
    "cargar",
    "BucleAgente",
    "Resultado",
    "Reflejo",
    "ClienteLLM",
    "ErrorLLM",
    "Memoria",
    "crear",
    "crear_percepcion",
    "ActuadorSimulado",
    "ActuadorSerial",
    "ActuadorConsola",
    "PercepcionSimulada",
    "PercepcionManual",
    "PercepcionCamara",
]
