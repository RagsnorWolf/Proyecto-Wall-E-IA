"""Punto de entrada del Agente de IA de WALL-E.

    python main.py                       # consola interactiva con el simulador
    python main.py --demo                # una instruccion de ejemplo y sale
    python main.py --cuerpo consola      # sin simulador, solo registra ordenes
    python main.py --reflejo 200         # deja que la politica PPO conduzca 200 pasos
    python main.py --probar              # comprueba credenciales del modelo
    python main.py --sin-llm             # solo cuerpo y reflejo, sin modelo remoto

La clave del modelo va en la variable de entorno WALLE_API_KEY
(se puede cambiar con `variable_clave` en config.json).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agente import BucleAgente, ClienteLLM, Config, Reflejo, cargar
from agente.actuadores import ActuadorSimulado, crear
from agente.llm import ErrorLLM
from agente.memoria import Memoria
from agente.percepcion import crear_percepcion

INSTRUCCION_DEMO = (
    "Recoge dos cubos de basura y lleválos al contenedor. Di una frase cuando termines."
)


def _utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _imprimir_estado(actuador) -> None:
    estado = actuador.estado()
    piezas = [f"{clave}={valor}" for clave, valor in estado.items() if clave != "basura_cercana"]
    print("  estado: " + "  ".join(piezas))


def _solo_reflejo(config: Config, pasos: int) -> int:
    reflejo = Reflejo.cargar_si_existe(config.ruta_politica())
    if reflejo is None:
        print(f"[reflejo] no hay modelo en {config.ruta_politica()}")
        print("          entrena el Cerebro: cd \"Cerebro Wall-E (Actividad Fisica + PPO) .py\"")
        print("                              python entrenar_ppo.py --pasos 60000")
        return 1
    actuador = ActuadorSimulado(config.escenario)
    resultado = reflejo.pasos(actuador, pasos)
    print(
        f"[reflejo] {resultado['pasos']} pasos  entregas={resultado['entregas']}  "
        f"recogidas={resultado['recogidas']}  choques={resultado['choques']}"
    )
    _imprimir_estado(actuador)
    return 0


def _probar(config: Config) -> int:
    try:
        cliente = ClienteLLM(config)
        print(f"[probar] {config.base_url} modelo={config.modelo} -> {cliente.ping()!r}")
        return 0
    except ErrorLLM as exc:
        print(f"[probar] fallo: {exc}")
        return 1


def principal() -> int:
    _utf8()
    parser = argparse.ArgumentParser(description="Agente de IA de WALL-E")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--cuerpo", choices=["simulado", "serial", "consola"], default=None)
    parser.add_argument("--escenario", default=None)
    parser.add_argument("--percepcion", choices=["auto", "simulado", "manual", "camara"], default="auto")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--probar", action="store_true")
    parser.add_argument("--reflejo", type=int, default=None, metavar="PASOS")
    parser.add_argument("--sin-llm", action="store_true")
    parser.add_argument("--instruccion", default=None, help="ejecuta una instruccion y sale")
    args = parser.parse_args()

    config = cargar(args.config)
    if args.cuerpo:
        config.cuerpo = args.cuerpo
    if args.escenario:
        config.escenario = args.escenario

    if args.reflejo is not None:
        return _solo_reflejo(config, args.reflejo)
    if args.probar:
        return _probar(config)

    actuador = crear(config)
    memoria = Memoria(config.ruta_memoria())
    try:
        percepcion = crear_percepcion(actuador, args.percepcion)
        reflejo = Reflejo.cargar_si_existe(config.ruta_politica())
        if reflejo is None:
            print("[aviso] sin politica PPO: la herramienta `reflejo` no estara disponible")
        if args.sin_llm:
            print("[modo] sin modelo remoto: solo cuerpo y reflejo")
            if isinstance(actuador, ActuadorSimulado):
                if reflejo is None:
                    print("[modo] tampoco hay politica; nada que mover")
                    return 1
                resultado = reflejo.pasos(actuador, 200)
                print(f"[reflejo] {resultado['pasos']} pasos, entregas={resultado['entregas']}")
                _imprimir_estado(actuador)
            return 0

        bucle = BucleAgente(config, actuador, percepcion, memoria, reflejo=reflejo)
        print(f"[agente] cuerpo={config.cuerpo} escenario={config.escenario} modelo={config.modelo}")

        if args.demo or args.instruccion:
            resultado = bucle.instruccion(args.instruccion or INSTRUCCION_DEMO)
            print(f"WALL-E: {resultado.respuesta}")
            print(f"  turnos={resultado.turnos} acciones={len(resultado.acciones)} "
                  f"terminado={resultado.terminado}")
            for accion in resultado.acciones:
                print(f"   - {accion}")
            _imprimir_estado(actuador)
            return 0

        print("Escribi una orden. Vacio o 'salir' para cortar.")
        while True:
            try:
                linea = input("vos> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not linea or linea.lower() in ("salir", "exit", "quit"):
                break
            try:
                resultado = bucle.instruccion(linea)
            except ErrorLLM as exc:
                print(f"[error] {exc}")
                continue
            print(f"WALL-E: {resultado.respuesta}")
            if resultado.acciones:
                print("  hecho: " + " | ".join(resultado.acciones[-6:]))
        return 0
    finally:
        actuador.cerrar()
        memoria.cerrar()


if __name__ == "__main__":
    raise SystemExit(principal())
