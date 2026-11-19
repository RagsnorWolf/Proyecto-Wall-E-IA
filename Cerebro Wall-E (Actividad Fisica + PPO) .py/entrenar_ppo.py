"""Entrenamiento PPO del Cerebro de WALL-E. Solo biblioteca estandar.

    python entrenar_ppo.py --pasos 60000
    python entrenar_ppo.py --pasos 60000 --escenario patio --semilla 3
    python entrenar_ppo.py --pasos 20000 --reanudar

Guarda el checkpoint en `modelo/politica.json` y una linea por actualizacion
en `modelo/entrenamiento.csv` para poder graficar la curva despues.

Nota de rendimiento: todo el gradiente es Python puro. Con la red 48-48 son
unos 6.000 parametros; el coste esta en las actualizaciones, no en el entorno.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from pathlib import Path

from cerebro import AgentePPO, EntornoActividad, Hiperparametros

CARPETA = Path(__file__).resolve().parent
MODELO = CARPETA / "modelo" / "politica.json"
REGISTRO = CARPETA / "modelo" / "entrenamiento.csv"

CABECERA_CSV = [
    "pasos", "episodios", "recompensa_media", "entregas_media", "cobertura_media",
    "distancia_media", "perdida_politica", "perdida_valor", "entropia", "segundos",
]


def _utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def evaluar(agente: AgentePPO, escenario: str, episodios: int, semilla: int) -> dict:
    entorno = EntornoActividad(escenario, semilla=semilla)
    retornos: list[float] = []
    entregas: list[int] = []
    coberturas: list[float] = []
    for i in range(episodios):
        obs, _ = entorno.reset(semilla=semilla + i)
        total = 0.0
        while True:
            accion, _, _ = agente.actuar(obs, determinista=True)
            obs, recompensa, terminado, truncado, info = entorno.step(accion)
            total += recompensa
            if terminado or truncado:
                break
        retornos.append(total)
        entregas.append(info["entregadas"])
        coberturas.append(info["cobertura"])
    entorno.close()
    n = max(len(retornos), 1)
    return {
        "retorno": sum(retornos) / n,
        "entregas": sum(entregas) / n,
        "cobertura": sum(coberturas) / n,
    }


def principal() -> int:
    _utf8()
    parser = argparse.ArgumentParser(description="Entrena el Cerebro PPO de WALL-E")
    parser.add_argument("--pasos", type=int, default=60_000, help="pasos totales de entorno")
    parser.add_argument("--escenario", default="chatarreria")
    parser.add_argument("--semilla", type=int, default=0)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--rollout", type=int, default=1024)
    parser.add_argument("--epocas", type=int, default=4)
    parser.add_argument("--mini-lote", type=int, default=256)
    parser.add_argument("--reanudar", action="store_true", help="continua desde modelo/politica.json")
    parser.add_argument("--guardar", type=Path, default=MODELO)
    parser.add_argument("--registro", type=Path, default=REGISTRO)
    parser.add_argument("--eval-episodios", type=int, default=3)
    args = parser.parse_args()

    random.seed(args.semilla)

    entorno = EntornoActividad(args.escenario, semilla=args.semilla)
    hparams = Hiperparametros(
        lr=args.lr, pasos_rollout=args.rollout, epocas=args.epocas, mini_lote=args.mini_lote
    )
    if args.reanudar and args.guardar.is_file():
        agente = AgentePPO.cargar(args.guardar)
        print(f"[reanudar] {args.guardar} ({agente.pasos_entrenados} pasos previos)")
    else:
        agente = AgentePPO(entorno.tam_observacion, entorno.n_acciones, hparams, semilla=args.semilla)
    print(
        f"[config] obs={entorno.tam_observacion} acciones={entorno.n_acciones} "
        f"ocultas={hparams.ocultas} rollout={args.rollout} escenario={args.escenario}"
    )

    args.registro.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not args.registro.is_file()
    archivo = args.registro.open("a", newline="", encoding="utf-8")
    escritor = csv.writer(archivo)
    if nuevo:
        escritor.writerow(CABECERA_CSV)

    obs, _ = entorno.reset()
    pasos = 0
    episodios = 0
    retorno_actual = 0.0
    recientes: list[float] = []
    entregas: list[int] = []
    coberturas: list[float] = []
    distancias: list[float] = []
    inicio = time.time()
    ultima = inicio

    while pasos < args.pasos:
        accion, logprob, valor = agente.actuar(obs)
        siguiente, recompensa, terminado, truncado, info = entorno.step(accion)
        agente.guardar_paso(obs, accion, logprob, valor, recompensa, terminado or truncado)
        obs = siguiente
        pasos += 1
        retorno_actual += recompensa

        if terminado or truncado:
            episodios += 1
            recientes = (recientes + [retorno_actual])[-20:]
            entregas = (entregas + [info["entregadas"]])[-20:]
            coberturas = (coberturas + [info["cobertura"]])[-20:]
            distancias = (distancias + [info["distancia"]])[-20:]
            retorno_actual = 0.0
            obs, _ = entorno.reset()

        if agente.lleno():
            estadisticas = agente.actualizar(obs)
            ahora = time.time()
            fila = [
                pasos,
                episodios,
                f"{sum(recientes) / len(recientes):.3f}" if recientes else "0",
                f"{sum(entregas) / len(entregas):.2f}" if entregas else "0",
                f"{sum(coberturas) / len(coberturas):.2f}" if coberturas else "0",
                f"{sum(distancias) / len(distancias):.2f}" if distancias else "0",
                f"{estadisticas['perdida_politica']:.4f}",
                f"{estadisticas['perdida_valor']:.4f}",
                f"{estadisticas['entropia']:.4f}",
                f"{ahora - inicio:.1f}",
            ]
            escritor.writerow(fila)
            archivo.flush()
            velocidad = args.rollout / max(ahora - ultima, 1e-6)
            print(
                f"[{pasos:>7}] eps={episodios:<4} ret={fila[2]:>9} entregas={fila[3]:>4} "
                f"cob={fila[4]:>6}m2 dist={fila[5]:>6}m "
                f"pi={estadisticas['perdida_politica']:+.3f} "
                f"v={estadisticas['perdida_valor']:.3f} "
                f"H={estadisticas['entropia']:.3f} "
                f"kl={estadisticas['aprox_kl']:+.4f} "
                f"{velocidad:,.0f} pasos/s"
            )
            ultima = ahora

    archivo.close()
    entorno.close()

    agente.guardar(args.guardar)
    print(f"[guardado] {args.guardar}")
    resumen = evaluar(agente, args.escenario, args.eval_episodios, args.semilla + 100)
    print(
        f"[evaluacion] retorno={resumen['retorno']:.2f} entregas={resumen['entregas']:.2f} "
        f"cobertura={resumen['cobertura']:.1f} m2 ({args.eval_episodios} episodios, determinista)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
