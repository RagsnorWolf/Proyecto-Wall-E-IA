"""Herramientas del Agente: esquemas JSON + despacho.

Cada herramienta devuelve un dict serializable. Los errores se devuelven como
`{"ok": false, "error": "..."}` en vez de propagarse: el modelo necesita leer
el fallo y corregir, no matar el bucle.

El catalogo es cerrado. Si el modelo pide algo que no esta aqui, se responde
con un error explicito y la lista de herramientas validas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .actuadores import Actuador, ActuadorSimulado, ErrorActuador
from .memoria import Memoria
from .percepcion import Percepcion


@dataclass
class Contexto:
    actuador: Actuador
    memoria: Memoria
    percepcion: Percepcion
    reflejo: object | None = None          # agente.cerebro.Reflejo
    historial_acciones: list[str] = field(default_factory=list)


ESQUEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "mirar",
            "description": "Devuelve el estado actual del mundo: posicion, bateria, "
                           "cubos, distancia al contenedor.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mover",
            "description": "Mueve el chasis. Cada 'avanzar' son 0.24 m; cada giro son "
                           "1.9 rad/s durante 0.1 s. Maximo 40 repeticiones por llamada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "accion": {"type": "string", "enum": ["avanzar", "izquierda", "derecha", "esperar"]},
                    "repeticiones": {"type": "integer", "minimum": 1, "maximum": 40},
                },
                "required": ["accion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recoger",
            "description": "Agarra un cubo que este a menos de 26 cm, o deposita los "
                           "cubos cargados si estas junto al contenedor.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reflejo",
            "description": "Deja que la politica PPO entrenada conduzca durante N pasos. "
                           "Util para trayectos largos: es rapida y no gasta tokens. "
                           "Solo funciona con el cuerpo simulado.",
            "parameters": {
                "type": "object",
                "properties": {"pasos": {"type": "integer", "minimum": 1, "maximum": 400}},
                "required": ["pasos"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recordar",
            "description": "Guarda un hecho corto en la memoria de largo plazo.",
            "parameters": {
                "type": "object",
                "properties": {"texto": {"type": "string"}, "clave": {"type": "string"}},
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_memoria",
            "description": "Busca en la memoria de largo plazo por palabras clave.",
            "parameters": {
                "type": "object",
                "properties": {"consulta": {"type": "string"}},
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hablar",
            "description": "Dice una frase al operador. Una o dos frases cortas.",
            "parameters": {
                "type": "object",
                "properties": {"mensaje": {"type": "string"}},
                "required": ["mensaje"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminar",
            "description": "Cierra la tarea. Entrega un resumen de lo hecho en una linea.",
            "parameters": {
                "type": "object",
                "properties": {"resumen": {"type": "string"}},
                "required": ["resumen"],
            },
        },
    },
]

NOMBRES = [esquema["function"]["name"] for esquema in ESQUEMAS]


def ejecutar(nombre: str, argumentos: dict, contexto: Contexto) -> dict:
    """Despacha una herramienta por nombre. Nunca lanza: devuelve el error."""
    if nombre not in NOMBRES:
        return {"ok": False, "error": f"herramienta desconocida: {nombre}", "validas": NOMBRES}
    try:
        return _DESPACHO[nombre](argumentos or {}, contexto)
    except ErrorActuador as exc:
        return {"ok": False, "error": f"fallo del cuerpo: {exc}"}
    except (TypeError, ValueError, KeyError) as exc:
        return {"ok": False, "error": f"argumentos invalidos para {nombre}: {exc}"}


# --- implementaciones ------------------------------------------------------
def _mirar(args: dict, contexto: Contexto) -> dict:
    estado = contexto.actuador.estado()
    estado["descripcion"] = contexto.percepcion.describir()
    return estado


def _mover(args: dict, contexto: Contexto) -> dict:
    accion = str(args.get("accion", "avanzar")).lower()
    repeticiones = int(args.get("repeticiones", 1) or 1)
    if accion == "avanzar":
        salida = contexto.actuador.avanzar(repeticiones)
    elif accion in ("izquierda", "derecha"):
        salida = contexto.actuador.girar(accion, repeticiones)
    elif accion == "esperar":
        salida = contexto.actuador.esperar(repeticiones)
    else:
        raise ValueError(f"accion no valida: {accion}")
    contexto.historial_acciones.append(f"mover {accion} x{repeticiones}")
    return salida


def _recoger(args: dict, contexto: Contexto) -> dict:
    salida = contexto.actuador.recoger()
    contexto.historial_acciones.append("recoger")
    return salida


def _reflejo(args: dict, contexto: Contexto) -> dict:
    if contexto.reflejo is None:
        return {"ok": False, "error": "no hay politica PPO cargada; entrena el Cerebro primero"}
    if not isinstance(contexto.actuador, ActuadorSimulado):
        return {"ok": False, "error": "el reflejo solo conduce el cuerpo simulado"}
    pasos = int(args.get("pasos", 50) or 50)
    return contexto.reflejo.pasos(contexto.actuador, pasos)


def _recordar(args: dict, contexto: Contexto) -> dict:
    texto = str(args.get("texto", "")).strip()
    if not texto:
        raise ValueError("texto vacio")
    identificador = contexto.memoria.recordar(texto, str(args.get("clave", "")))
    return {"ok": True, "id": identificador, "guardado": texto}


def _consultar_memoria(args: dict, contexto: Contexto) -> dict:
    consulta = str(args.get("consulta", "")).strip()
    return {"ok": True, "consulta": consulta, "resultados": contexto.memoria.buscar(consulta)}


def _hablar(args: dict, contexto: Contexto) -> dict:
    mensaje = str(args.get("mensaje", "")).strip()
    if not mensaje:
        raise ValueError("mensaje vacio")
    contexto.historial_acciones.append(f"hablar: {mensaje}")
    return {"ok": True, "dicho": mensaje[:400]}


def _terminar(args: dict, contexto: Contexto) -> dict:
    resumen = str(args.get("resumen", "")).strip() or "tarea terminada"
    contexto.historial_acciones.append(f"terminar: {resumen}")
    return {"ok": True, "terminado": True, "resumen": resumen[:400]}


_DESPACHO = {
    "mirar": _mirar,
    "mover": _mover,
    "recoger": _recoger,
    "reflejo": _reflejo,
    "recordar": _recordar,
    "consultar_memoria": _consultar_memoria,
    "hablar": _hablar,
    "terminar": _terminar,
}


def como_json(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)
