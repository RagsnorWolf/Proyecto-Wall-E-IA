#!/usr/bin/env python3
"""tools_soak_entorno.py - banco de fatiga del entorno V5.

El entrenamiento largo moria con 0xC0000005 alrededor de los 20 000 pasos. Un
access violation no deja traza de Python, asi que la unica forma de ubicarlo es
apretar el entorno solo, sin PPO ni torch, y medir que se acumula.

Corre exactamente la misma configuracion que `train_walle_v5.py`: N entornos
creados con `make_env`, acciones aleatorias y resets, que es el camino donde se
sospecha la fuga.

Uso:
    python tools_soak_entorno.py                     # 2 entornos, 20 000 pasos
    python tools_soak_entorno.py --envs 1 --steps 50000
    python tools_soak_entorno.py --envs 2 --steps 20000 --csv soak.csv

Salida: una linea por bloque con RSS actual, pico, cuerpos vivos en PyBullet y
pasos por segundo. Al final imprime la pendiente de memoria: si el RSS crece de
forma sostenida con los pasos, hay fuga; si se aplana, el problema esta arriba.
"""
from __future__ import annotations

import argparse
import ctypes
import csv
import os
import sys
import time
import traceback

import numpy as np


def rss_mb() -> float:
    """Working set del proceso. psutil no esta garantizado en una instalacion
    limpia, asi que se pide a Windows y se cae a 0 en otros sistemas."""
    if os.name != "nt":
        try:
            with open("/proc/self/statm", encoding="ascii") as fh:
                paginas = int(fh.read().split()[1])
            return paginas * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)
        except Exception:
            return 0.0

    class _Cnt(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    cnt = _Cnt()
    cnt.cb = ctypes.sizeof(_Cnt)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        handle, ctypes.byref(cnt), cnt.cb
    ):
        return 0.0
    return cnt.WorkingSetSize / (1024 * 1024)


def cuerpo_vivos(pybullet) -> int:
    try:
        return int(pybullet.getNumBodies())
    except Exception:
        return -1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Banco de fatiga del entorno V5")
    parser.add_argument("--envs", type=int, default=2, help="entornos en proceso")
    parser.add_argument("--steps", type=int, default=20000, help="pasos totales")
    parser.add_argument("--bloque", type=int, default=1000, help="pasos por linea")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--csv", type=str, default="", help="volcar muestras")
    args = parser.parse_args(argv[1:])

    # Import tardio: asi --help funciona aunque falte pybullet.
    import pybullet as p

    from train_walle_v5 import make_env

    print(f"[SOAK] {args.envs} entornos, {args.steps} pasos, bloque {args.bloque}")
    print(f"[SOAK] RSS inicial: {rss_mb():.1f} MB")

    envs = []
    for i in range(args.envs):
        envs.append(make_env(args.seed + i)())

    obs = [e.reset()[0] for e in envs]
    acciones = [e.action_space.sample() for e in envs]

    muestras: list[tuple[int, float, int]] = []
    inicio = time.time()
    paso = 0
    ultimo_informe = 0
    episodios = 0

    try:
        while paso < args.steps:
            for i, env in enumerate(envs):
                nuevo_obs, _rew, terminated, truncated, _info = env.step(acciones[i])
                obs[i] = nuevo_obs
                if terminated or truncated:
                    obs[i], _ = env.reset()
                    episodios += 1
                acciones[i] = env.action_space.sample()
                paso += 1

            if paso - ultimo_informe >= args.bloque:
                ultimo_informe = paso
                mb = rss_mb()
                cuerpos = cuerpo_vivos(p)
                muestras.append((paso, mb, cuerpos))
                tasa = paso / max(1e-9, time.time() - inicio)
                print(
                    f"paso {paso:7d}  RSS {mb:7.1f} MB  cuerpos {cuerpos:5d}  "
                    f"episodios {episodios:5d}  {tasa:6.0f} pasos/s",
                    flush=True,
                )
                if args.csv:
                    with open(args.csv, "a", newline="", encoding="utf-8") as fh:
                        csv.writer(fh).writerows(
                            [(s, round(m, 1), c) for s, m, c in muestras[-1:]]
                        )
    except BaseException:
        print("[SOAK] el proceso murio dentro del bucle:", flush=True)
        traceback.print_exc()
        return 1

    for env in envs:
        try:
            env.close()
        except Exception:
            pass

    if len(muestras) >= 2:
        # Pendiente por regresion lineal simple: MB por cada 1000 pasos.
        xs = np.array([m[0] for m in muestras], dtype=np.float64)
        ys = np.array([m[1] for m in muestras], dtype=np.float64)
        pendiente = float(np.polyfit(xs, ys, 1)[0] * 1000.0)
        primero = muestras[0][1]
        ultimo = muestras[-1][1]
        print(
            f"\n[SOAK] RSS {primero:.1f} -> {ultimo:.1f} MB en {args.steps} pasos"
        )
        print(f"[SOAK] pendiente: {pendiente:+.3f} MB por 1000 pasos")
        print(
            "[SOAK] veredicto: "
            + (
                "FUGA (el RSS sube con los pasos)"
                if pendiente > 2.0
                else "estable (el RSS se aplana)"
            )
        )

    print(f"[SOAK] sobrevivio {args.steps} pasos con {args.envs} entornos")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
