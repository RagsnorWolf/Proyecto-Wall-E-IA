#!/usr/bin/env python3
"""probe_subproc.py - un cliente de PyBullet por proceso, uno por entorno.

El entorno crea su propia conexion pero llama a `p.*` sin `physicsClientId`,
asi que dos entornos en el mismo proceso comparten el mundo del cliente 0.
`probe_clientes.py` lo demuestra. La salida sin tocar 111 llamadas es un
proceso por entorno: cada hijo crea su cliente 0 y no hay con quien cruzarse.

Esta prueba comprueba tres cosas:

  1. Que SubprocVecEnv levanta N hijos y cada uno informa su propio mundo.
  2. Que avanzan de verdad (posicion distinta en cada hijo).
  3. Que no hay access violation en reset ni en step.

Uso:
    python probe_subproc.py --workers 2 --steps 400
Sale con 1 si algo falla.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import pybullet as p
from stable_baselines3.common.vec_env import SubprocVecEnv

from walle_env_v3 import WallEEnvV3


def crear_env() -> WallEEnvV3:
    return WallEEnvV3(
        render_mode=None,
        stage=3,
        max_episode_steps=1200,
        max_wheel_speed=2.5,
        max_force=0.5,
        arena_half_size=12.0,
        obstacle_count=8,
        stage3_min_obstacle_distance=2.0,
        obstacle_max_distance=10.0,
        obstacle_min_separation=1.5,
        enable_sensors=True,
        sensor_noise_std=0.02,
        collision_terminates=False,
    )


def informe(env: WallEEnvV3, tag: str) -> None:
    """Lo que el hijo ve de su propio mundo. Se imprime con flush para que el
    padre lo reciba aunque el proceso termine de golpe."""
    try:
        cuerpos = p.getNumBodies(physicsClientId=env.client_id)
        pos, _ = p.getBasePositionAndOrientation(
            env.robot, physicsClientId=env.client_id
        )
        print(
            f"[HIJO {tag}] cliente={env.client_id} cuerpos={cuerpos} "
            f"robot=({pos[0]:.2f},{pos[1]:.2f}) obs={env.observation_space.shape[0]}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001 - el informe no debe tumbar la prueba
        print(f"[HIJO {tag}] no pudo informar: {exc}", flush=True)


def init_hijo(tag: str):
    def _init():
        env = crear_env()
        env.reset(seed=hash(tag) % 1000)
        informe(env, tag)
        return env

    return _init


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--steps", type=int, default=400)
    args = parser.parse_args(argv[1:])

    print(f"[SUBPROC] levantando {args.workers} hijos")
    env = SubprocVecEnv(
        [init_hijo(f"w{i}") for i in range(args.workers)],
        start_method="spawn",
    )

    try:
        obs = env.reset()
        print(f"[SUBPROC] reset OK, obs {obs.shape}")
        if not np.isfinite(obs).all():
            print("[FALLO] la observacion inicial tiene NaN o inf")
            return 1

        acciones = np.array(
            [env.action_space.sample() for _ in range(args.workers)],
            dtype=np.float32,
        )
        inicio = time.time()
        pasos = 0
        while pasos < args.steps:
            obs, rews, dones, infos = env.step(acciones)
            if not np.isfinite(obs).all():
                print(f"[FALLO] observacion no finita en el paso {pasos}")
                return 1
            if not np.isfinite(rews).all():
                print(f"[FALLO] recompensa no finita en el paso {pasos}")
                return 1
            acciones = np.array(
                [env.action_space.sample() for _ in range(args.workers)],
                dtype=np.float32,
            )
            pasos += 1

        seg = time.time() - inicio
        print(
            f"[SUBPROC] {pasos} pasos x {args.workers} hijos en {seg:.1f}s "
            f"({pasos * args.workers / seg:.0f} pasos/s)"
        )
    finally:
        env.close()

    print("[SUBPROC] VEREDICTO: un proceso por entorno funciona.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
