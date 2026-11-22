#!/usr/bin/env python3
"""probe_clientes.py - comprueba que cada entorno vive en su propio mundo.

PyBullet identifica cada conexion con un `physicsClientId` y usa el cliente 0
cuando no se le pasa. El entorno crea su conexion pero llamaba a `p.*` sin el
id: el primer entorno funcionaba de casualidad (su id es 0) y el segundo
construia su robot en el mundo del primero.

La prueba no se fia de comparar posiciones —dos entornos pueden arrancar en el
mismo punto— sino de un objeto que solo existe en un mundo: se le clava una
pared delante al entorno A y se mira si el LiDAR de B la ve. Si la ve, estan
compartiendo cliente.

Uso:
    python probe_clientes.py
Sale con 1 si los entornos comparten mundo.
"""
from __future__ import annotations

import sys

import pybullet as p

from walle_env_v3 import WallEEnvV3

# Entornos vivos del proceso, para poder cerrarlos en el `finally` del main.
_ENTORNOS: list[WallEEnvV3] = []


def crear(seed: int) -> WallEEnvV3:
    env = WallEEnvV3(
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
        sensor_noise_std=0.0,
        collision_terminates=False,
    )
    env.reset(seed=seed, options={"start_pos": [0.0, 0.0, 0.15], "start_yaw": 0.0})
    _ENTORNOS.append(env)
    return env


def main() -> int:
    a = crear(1)
    b = crear(2)

    print(f"cliente de A: {a.client_id}   cliente de B: {b.client_id}")
    if a.client_id == b.client_id:
        print("[FALLO] los dos entornos comparten el mismo physicsClientId.")
        return 1

    cuerpos_a = a.p.getNumBodies()
    cuerpos_b = b.p.getNumBodies()
    print(f"cuerpos en A: {cuerpos_a}   cuerpos en B: {cuerpos_b}")
    if cuerpos_a == 0 or cuerpos_b == 0:
        print("[FALLO] un entorno construyo su mundo en el cliente equivocado.")
        return 1

    # La prueba que no se puede falsear: una pared que solo existe en A.
    caja = a.p.createCollisionShape(a.p.GEOM_BOX, halfExtents=[0.05, 0.5, 0.5])
    a.p.createMultiBody(0, caja, basePosition=[0.8, 0.0, 0.5])
    a.p.setGravity(0, 0, -9.81)
    for _ in range(5):
        a.p.stepSimulation()

    b._scan_lidar()
    frente_b = float(min(b.fan_meters))
    print(f"LiDAR de B con una pared clavada en A: {frente_b:.2f} m")

    a._scan_lidar()
    frente_a = float(min(a.fan_meters))
    print(f"LiDAR de A con la pared:              {frente_a:.2f} m")

    if frente_b < 1.0:
        print("[FALLO] B ve la pared de A: comparten mundo.")
        return 1
    if frente_a >= 1.0:
        print("[FALLO] A no ve su propia pared: el barrido apunta a otro cliente.")
        return 1

    # Y el camino real del entorno: dos pasos y comprobar que cada robot se mueve
    # en su mundo, no en el del vecino.
    antes_a = a.p.getBasePositionAndOrientation(a.robot)[0]
    antes_b = b.p.getBasePositionAndOrientation(b.robot)[0]
    for _ in range(20):
        a.step([1.0, 1.0])
        b.step([-1.0, -1.0])
    despues_a = a.p.getBasePositionAndOrientation(a.robot)[0]
    despues_b = b.p.getBasePositionAndOrientation(b.robot)[0]

    movio_a = abs(despues_a[0] - antes_a[0]) > 1e-4
    movio_b = abs(despues_b[0] - antes_b[0]) > 1e-4
    print(f"A se movio: {movio_a}   B se movio: {movio_b}")
    if not (movio_a and movio_b):
        print("[FALLO] alguno de los dos no se mueve en su propio mundo.")
        return 1

    print()
    print("VEREDICTO: cada entorno tiene su mundo, su robot y su LiDAR.")
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    finally:
        # Cada entorno tiene su cliente; `p.disconnect()` a secas solo apaga el
        # cliente 0 y deja el otro vivo hasta que muera el proceso.
        for entorno in _ENTORNOS:
            try:
                entorno.close()
            except Exception:
                pass
        try:
            p.disconnect()
        except Exception:
            pass
    sys.exit(codigo)
