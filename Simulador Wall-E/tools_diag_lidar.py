"""
Diagnóstico del LiDAR: mide qué ve realmente el sensor, sin adivinar.

Corre con el venv del simulador:
    ".venv\\Scripts\\python.exe" tools_diag_lidar.py
"""
from __future__ import annotations

import math

import numpy as np
import pybullet as p

from walle_env_v3 import (
    BODY_HALF_X,
    LIDAR_MAX_DIST,
    LIDAR_RAYS,
    SENSOR_COUNT,
    SENSOR_FOOT_Z,
    WallEEnvV3,
)

env = WallEEnvV3(stage=3, obstacle_count=0, enable_sensors=True)
env.reset(seed=1)

# Arena limpia: los obstáculos se van lejos para medir sin ruido.
for body in env.obstacle_ids + env.cylinder_ids + env.l_wall_ids + env.ramp_ids:
    p.resetBasePositionAndOrientation(body, [0, 60, 0], [0, 0, 0, 1])


def scan_con_caja(centro_x: float, media: float, altura: float):
    """Pone una caja delante y devuelve (rayo0, plano_z, base_z)."""
    for body in getattr(scan_con_caja, "ids", []):
        p.removeBody(body)
    half = [media, media, altura / 2.0]
    col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half)
    vis = p.createVisualShape(p.GEOM_BOX, halfExtents=half, rgbaColor=[1, 0, 0, 1])
    body = p.createMultiBody(0.0, col, vis, basePosition=[centro_x, 0.0, altura / 2.0])
    scan_con_caja.ids = [body]

    p.resetBasePositionAndOrientation(env.robot, [0.0, 0.0, env.BASE_Z], [0, 0, 0, 1])
    env._scan_lidar()
    pos, _ = p.getBasePositionAndOrientation(env.robot)
    return float(env.fan_meters[len(env.fan_meters) // 2]), pos[2], body


print("=" * 66)
print("1. Distancia desde el PARAGOLPES (el choque ocurre en el borde)")
print("=" * 66)
print(f"   chasis: semilongitud {BODY_HALF_X:.3f} m")
print(f"   {'centro':>8} {'real':>8} {'medido':>8} {'error':>8}   veredicto")
for centro, media, altura in [
    (2.00, 0.30, 0.60),
    (1.20, 0.30, 0.60),
    (0.80, 0.30, 0.60),
    (0.50, 0.30, 0.60),
    (0.47, 0.30, 0.60),
]:
    medido, base_z, _ = scan_con_caja(centro, media, altura)
    real = max(0.0, centro - media - BODY_HALF_X)
    error = medido - real
    ok = abs(error) < 0.01
    print(
        f"   {centro:8.2f} {real:8.3f} {medido:8.3f} {error:+8.3f}   "
        f"{'OK' if ok else 'MAL'}"
    )

print()
print("=" * 66)
print("2. Objetos bajos: lo que el plano viejo a 0.21 m no veía")
print("=" * 66)
print(f"   plano de escaneo: {SENSOR_FOOT_Z:.3f} m sobre el suelo local")
print(f"   {'alto':>6} {'dist real':>10} {'medido':>8}   veredicto")
for alto in (0.08, 0.12, 0.20, 0.40):
    medido, base_z, _ = scan_con_caja(1.00, 0.25, alto)
    real = 1.00 - 0.25 - BODY_HALF_X
    ok = medido < LIDAR_MAX_DIST
    print(
        f"   {alto:6.2f} {real:10.3f} {medido:8.3f}   "
        f"{'LO VE' if ok else 'CIEGO'}"
    )

print()
print("=" * 66)
print("3. Reparto del abanico de la observación")
print("=" * 66)
grados = np.degrees(env.fan_angles)
print(f"   cantidad: {SENSOR_COUNT} rayos, de {grados[0]:.1f}° a {grados[-1]:.1f}°")
separaciones = np.diff(grados)
print(f"   separación al frente: {separaciones[SENSOR_COUNT // 2]:.2f}°")
print(f"   separación al costado: {separaciones[0]:.2f}°")
en_cono = int(np.sum(np.abs(grados) <= 30.0))
print(f"   rayos dentro del cono de ±30°: {en_cono}  (antes: 13)")
print(f"   ángulos: {[round(float(g), 1) for g in grados]}")

print()
print("=" * 66)
print("4. El anillo de 72 sigue completo")
print("=" * 66)
medido, base_z, _ = scan_con_caja(0.80, 0.30, 0.60)
print(f"   forma del anillo: {env.lidar_meters.shape} (esperado ({LIDAR_RAYS},))")
print(f"   mínimo del anillo: {float(env.lidar_meters.min()):.3f} m")
print(f"   rayo 0 del anillo: {float(env.lidar_meters[0]):.3f} m")
print(f"   ¿coincide con el centro del abanico?: "
      f"{abs(float(env.lidar_meters[0]) - medido) < 0.02}")
print(f"   base_z={base_z:.3f}  plano_z={base_z - env.BASE_Z + SENSOR_FOOT_Z:.3f}")

print()
print("=" * 66)
print("5. Observación: dimensiones intactas")
print("=" * 66)
obs, info = env.reset(seed=2)
print(f"   obs.shape = {obs.shape}  (debe ser (58,))")
print(f"   sensor_space = {env.observation_space.shape}")
print(f"   fan en info: {len(info.get('fan_meters', []))} valores")
print(f"   front_clearance(30) = {env.front_clearance():.3f} m")

env.close()
print()
print("listo")
