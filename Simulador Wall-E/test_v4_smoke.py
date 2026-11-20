"""Smoke test V5: obs 58D, LiDAR a ras de suelo, abanico de 36 y recompensas.

Comprueba lo que rompía el sensor:
  - el anillo de 72 y el abanico de 36 se llenan de verdad (no todo 6.0 m)
  - las distancias vienen del paragolpes: 0 = tocando
  - un obstáculo bajo (12 cm) entra en la lectura
  - contacto y recompensa son finitos y coherentes
"""

from __future__ import annotations

import numpy as np
import pybullet as p

from walle_env_v3 import (
    BODY_HALF_X,
    LIDAR_MAX_DIST,
    LIDAR_RAYS,
    OBS_DIM,
    SENSOR_COUNT,
    WallEEnvV3,
)


def poner_obstaculo_delante(env: WallEEnvV3, distancia_centro: float):
    """Deja el primer obstáculo del entorno justo enfrente y el resto lejos."""
    cuerpo = env.obstacle_ids[0]
    alto = 2.0 * env.obstacle_half_sizes[0][2]
    p.resetBasePositionAndOrientation(
        cuerpo, [distancia_centro, 0.0, alto / 2.0], [0, 0, 0, 1]
    )
    lejos = env.obstacle_ids[1:] + env.cylinder_ids + env.l_wall_ids + env.ramp_ids
    for otro in lejos:
        p.resetBasePositionAndOrientation(otro, [0, 60, 0], [0, 0, 0, 1])
    p.resetBasePositionAndOrientation(
        env.robot, [0.0, 0.0, env.BASE_Z], [0, 0, 0, 1]
    )
    return cuerpo


def main() -> None:
    env = WallEEnvV3(
        render_mode=None,
        stage=3,
        max_episode_steps=400,
        obstacle_count=6,
        enable_sensors=True,
        sensor_noise_std=0.0,
    )
    obs, info = env.reset(seed=42)

    # ── Formas ────────────────────────────────────────────────────────
    assert obs.shape == (OBS_DIM,), f"obs {obs.shape} != ({OBS_DIM},)"
    assert env.lidar_meters.shape == (LIDAR_RAYS,), env.lidar_meters.shape
    assert env.fan_meters.shape == (SENSOR_COUNT,), env.fan_meters.shape
    assert env.observation_space.contains(obs), "obs inicial fuera del espacio"
    assert len(info.get("fan_meters", [])) == SENSOR_COUNT, "info sin abanico"

    # ── El sensor ve, y mide desde el paragolpes ───────────────────────
    for distancia_centro in (1.20, 0.80, 0.55):
        poner_obstaculo_delante(env, distancia_centro)
        env._scan_lidar()
        semiancho = env.obstacle_half_sizes[0][0]
        esperado = max(0.0, distancia_centro - semiancho - BODY_HALF_X)
        medido = float(env.fan_meters.min())
        assert medido < LIDAR_MAX_DIST, (
            f"ciego: obstáculo a {distancia_centro:.2f} m del centro y el "
            f"abanico dice {medido:.2f} m"
        )
        assert abs(medido - esperado) < 0.02, (
            f"distancia mal medida: esperado {esperado:.3f} m desde el "
            f"paragolpes, medido {medido:.3f} m"
        )

    # ── Obstáculo bajo: lo que el plano a 0.21 m no veía ───────────────
    for otro in env.obstacle_ids + env.cylinder_ids + env.l_wall_ids + env.ramp_ids:
        p.resetBasePositionAndOrientation(otro, [0, 60, 0], [0, 0, 0, 1])
    bajo = p.createCollisionShape(
        p.GEOM_BOX, halfExtents=[0.25, 0.25, 0.06]
    )
    caja_baja = p.createMultiBody(0.0, bajo, -1, [0.80, 0.0, 0.06])
    p.resetBasePositionAndOrientation(
        env.robot, [0.0, 0.0, env.BASE_Z], [0, 0, 0, 1]
    )
    env._scan_lidar()
    esperado = 0.80 - 0.25 - BODY_HALF_X
    medido = float(env.fan_meters.min())
    assert abs(medido - esperado) < 0.02, (
        f"obstáculo de 12 cm invisible o mal medido: esperado {esperado:.3f} m, "
        f"medido {medido:.3f} m"
    )
    p.removeBody(caja_baja)

    # ── Sin obstáculos cerca no hay ceros fantasma ─────────────────────
    for otro in env.obstacle_ids + env.cylinder_ids + env.l_wall_ids:
        p.resetBasePositionAndOrientation(otro, [0, 60, 0], [0, 0, 0, 1])
    p.resetBasePositionAndOrientation(
        env.robot, [0.0, 0.0, env.BASE_Z], [0, 0, 0, 1]
    )
    env._scan_lidar()
    assert float(env.fan_meters.min()) > 0.5, (
        f"cero fantasma: abanico mínimo {float(env.fan_meters.min()):.3f} m "
        "en una arena vacía"
    )

    # ── Episodio completo con acciones aleatorias ──────────────────────
    obs, _ = env.reset(seed=42)
    rewards: list[float] = []
    traps = 0
    contacts = 0
    chunks = 0
    for step in range(400):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert env.observation_space.contains(obs), (
            f"obs fuera del espacio en paso {step}: "
            f"min={obs.min():.3f} max={obs.max():.3f}"
        )
        assert np.isfinite(reward), f"reward no finito en paso {step}"
        rewards.append(float(reward))
        traps += int(bool(info.get("trapped", False)))
        contacts += int(bool(info.get("contact", False)))
        chunks += int(info.get("chunks_discovered", 0))
        if terminated or truncated:
            break

    print(f"Pasos ejecutados: {len(rewards)}")
    print(f"Recompensa total: {sum(rewards):+.2f}")
    print(f"Recompensa media: {np.mean(rewards):+.3f}")
    print(f"Trampas detectadas: {traps}")
    print(f"Pasos con contacto: {contacts}")
    print(f"Chunks nuevos: {chunks}")
    print(
        "LiDAR min/max: "
        f"{float(env.lidar_meters.min()):.2f} / "
        f"{float(env.lidar_meters.max()):.2f} m"
    )
    print(
        "Abanico min/max: "
        f"{float(env.fan_meters.min()):.2f} / "
        f"{float(env.fan_meters.max()):.2f} m"
    )
    env.close()
    print("ENV SMOKE OK")


if __name__ == "__main__":
    main()
