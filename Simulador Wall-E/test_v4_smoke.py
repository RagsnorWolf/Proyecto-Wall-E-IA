"""Smoke test V7: obs 74D, dos planos de escaneo y 24 sentidos.

Comprueba lo que rompia el sensor y lo que agrega la version V7:

  - el anillo de 72 y el abanico de 36 se llenan de verdad (no todo 6.0 m)
  - las distancias vienen del paragolpes: 0 = tocando
  - un obstaculo bajo (12 cm) entra en la lectura
  - el plano alto distingue una caja baja (trepable) de una pared (bloquea)
  - los 24 extras describen el problema, incluidos techo, tiempo al impacto
    y tipo de obstaculo
  - contacto y recompensa son finitos y coherentes

Uso:
    python test_v4_smoke.py
"""

from __future__ import annotations

import numpy as np
import pybullet as p

from walle_env_v3 import (
    BODY_HALF_X,
    HEADROOM_FOOT_Z,
    LIDAR_MAX_DIST,
    LIDAR_RAYS,
    OBS_EXTRAS,
    OBS_DIM,
    SENSOR_COUNT,
    WallEEnvV3,
)

# Indices de los extras, en el orden en que los arma _problem_obs.
E_FRENTE = 0
E_IZQ = 8
E_DER = 9
E_HUECO_ANCHO = 10
E_OBJETIVO = 12
E_DETRAS = 13
E_VEL = 14
E_LIBRE = 15
E_DERRAPE = 16
E_TIEMPO = 17
E_TECHO_FRENTE = 18
E_RATIO_BAJO = 21
E_RATIO_ALTO = 22
E_COSTADO = 23


def alejar_todo(env: WallEEnvV3) -> None:
    """Manda todos los solidos del entorno lejos y centra el robot."""
    cuerpos = (
        env.obstacle_ids
        + env.cylinder_ids
        + env.l_wall_ids
        + env.ramp_ids
        + list(getattr(env, "long_wall_ids", []))
    )
    for otro in cuerpos:
        p.resetBasePositionAndOrientation(otro, [0, 60, 0], [0, 0, 0, 1])
    p.resetBasePositionAndOrientation(
        env.robot, [0.0, 0.0, env.BASE_Z], [0, 0, 0, 1]
    )


def poner_obstaculo_delante(
    env: WallEEnvV3, distancia_centro: float
) -> int:
    """Deja el primer obstaculo del entorno justo enfrente y el resto lejos."""
    alejar_todo(env)
    cuerpo = env.obstacle_ids[0]
    alto = 2.0 * env.obstacle_half_sizes[0][2]
    p.resetBasePositionAndOrientation(
        cuerpo, [distancia_centro, 0.0, alto / 2.0], [0, 0, 0, 1]
    )
    return cuerpo


def caja(env: WallEEnvV3, x: float, semialto: float, masa: float = 0.0) -> int:
    """Caja de 0.5 x 0.5 m con la altura pedida, apoyada en el piso."""
    forma = p.createCollisionShape(
        p.GEOM_BOX, halfExtents=[0.25, 0.25, semialto]
    )
    return p.createMultiBody(masa, forma, -1, [x, 0.0, semialto])


def main() -> None:
    env = WallEEnvV3(
        render_mode=None,
        stage=3,
        max_episode_steps=400,
        obstacle_count=6,
        enable_sensors=True,
        sensor_noise_std=0.0,
        connect_options="DIRECT",
    )
    obs, info = env.reset(seed=42)

    # -- Formas ---------------------------------------------------------- #
    assert obs.shape == (OBS_DIM,), f"obs {obs.shape} != ({OBS_DIM},)"
    assert OBS_DIM == 14 + SENSOR_COUNT + OBS_EXTRAS
    assert env.lidar_meters.shape == (LIDAR_RAYS,), env.lidar_meters.shape
    assert env.fan_meters.shape == (SENSOR_COUNT,), env.fan_meters.shape
    assert env.headroom_meters.shape == (SENSOR_COUNT,), env.headroom_meters.shape
    assert env.observation_space.contains(obs), "obs inicial fuera del espacio"
    assert len(info.get("fan_meters", [])) == SENSOR_COUNT, "info sin abanico"
    print(f"[OK] formas: obs {OBS_DIM}D, abanico {SENSOR_COUNT}, extras {OBS_EXTRAS}")

    # -- El sensor ve, y mide desde el paragolpes ------------------------ #
    for distancia_centro in (1.20, 0.80, 0.55):
        poner_obstaculo_delante(env, distancia_centro)
        env._scan_lidar()
        semiancho = env.obstacle_half_sizes[0][0]
        esperado = max(0.0, distancia_centro - semiancho - BODY_HALF_X)
        medido = float(env.fan_meters.min())
        assert medido < LIDAR_MAX_DIST, (
            f"ciego: obstaculo a {distancia_centro:.2f} m del centro y el "
            f"abanico dice {medido:.2f} m"
        )
        assert abs(medido - esperado) < 0.02, (
            f"distancia mal medida: esperado {esperado:.3f} m desde el "
            f"paragolpes, medido {medido:.3f} m"
        )
    print("[OK] distancias desde el paragolpes, error < 2 cm")

    # -- Obstaculo bajo: lo que el plano a 0.21 m no veia ---------------- #
    alejar_todo(env)
    baja = caja(env, 0.80, 0.06)
    env._scan_lidar()
    esperado = 0.80 - 0.25 - BODY_HALF_X
    medido = float(env.fan_meters.min())
    assert abs(medido - esperado) < 0.02, (
        f"obstaculo de 12 cm invisible o mal medido: esperado {esperado:.3f} m, "
        f"medido {medido:.3f} m"
    )
    p.removeBody(baja)
    print("[OK] caja de 12 cm visible")

    # -- Plano alto: caja baja = trepable, pared = bloquea --------------- #
    # Caja de 12 cm: el plano bajo la toca, el alto pasa por encima.
    alejar_todo(env)
    baja = caja(env, 0.85, 0.06)
    env._scan_lidar()
    trepables = int(env.fan_climbable.sum())
    bloqueantes = int(env.fan_blocking.sum())
    assert trepables > 0, "caja de 12 cm: ningun rayo la marco como trepable"
    assert bloqueantes == 0, (
        f"caja de 12 cm: {bloqueantes} rayos la marcaron como bloqueante; "
        "el plano alto no deberia tocarla"
    )
    p.removeBody(baja)

    # Pared de 1.20 m: los dos planos la tocan.
    alejar_todo(env)
    alta = caja(env, 0.85, 0.60)
    env._scan_lidar()
    trepables = int(env.fan_climbable.sum())
    bloqueantes = int(env.fan_blocking.sum())
    assert bloqueantes > 0, "pared de 1.20 m: ningun rayo la marco como bloqueante"
    assert trepables == 0, (
        f"pared de 1.20 m: {trepables} rayos la marcaron como trepable"
    )
    p.removeBody(alta)
    print("[OK] plano alto distingue caja baja de pared")

    # -- Altura del plano alto ------------------------------------------- #
    assert HEADROOM_FOOT_Z > 0.12, (
        f"el plano alto ({HEADROOM_FOOT_Z:.2f} m) no pasa por encima de una "
        "caja de 12 cm"
    )

    # -- Arena vacia: ni ceros fantasma ni falsos positivos -------------- #
    alejar_todo(env)
    env._scan_lidar()
    assert float(env.fan_meters.min()) > 0.5, (
        f"cero fantasma: abanico minimo {float(env.fan_meters.min()):.3f} m "
        "en una arena vacia"
    )
    assert not bool(env.fan_low_hit.any()), "rayos con impacto en arena vacia"
    libre = env._problem_obs()
    assert libre.shape == (OBS_EXTRAS,), libre.shape
    assert libre.min() >= -1.0 and libre.max() <= 1.0, (
        f"extra fuera de rango: min={libre.min():.3f} max={libre.max():.3f}"
    )
    assert libre[E_LIBRE] > 0.9, (
        f"arena vacia y solo {libre[E_LIBRE]:.2f} del abanico libre"
    )
    assert libre[E_RATIO_BAJO] == 0.0, "arena vacia con obstaculos trepables"
    assert libre[E_RATIO_ALTO] == 0.0, "arena vacia con obstaculos bloqueantes"
    assert libre[E_TECHO_FRENTE] < 0.1, (
        f"arena vacia con techo cerca: {libre[E_TECHO_FRENTE]:.2f}"
    )
    assert libre[E_TIEMPO] == 1.0, (
        f"quieto y sin riesgo deberia dar tiempo al impacto 1.0, "
        f"da {libre[E_TIEMPO]:.2f}"
    )
    print("[OK] arena vacia sin ceros fantasma y extras coherentes")

    # -- Pared al frente: el extra de frente reacciona ------------------- #
    poner_obstaculo_delante(env, 0.70)
    env._scan_lidar()
    pegado = env._problem_obs()
    assert pegado[E_FRENTE] > 0.5, (
        f"pared a 0.70 m del centro y el extra de frente da "
        f"{pegado[E_FRENTE]:.2f}"
    )
    assert pegado[E_RATIO_ALTO] > 0.0, (
        "pared al frente y ningun rayo bloqueante"
    )
    print("[OK] extras de frente y de tipo de obstaculo reaccionan")

    # -- Paso real: recompensa y contacto finitos ------------------------ #
    obs, info = env.reset(seed=7)
    total = 0.0
    for _ in range(30):
        obs, recompensa, terminado, truncado, info = env.step(
            env.action_space.sample()
        )
        assert np.isfinite(recompensa), f"recompensa no finita: {recompensa}"
        assert obs.shape == (OBS_DIM,)
        assert np.all(np.isfinite(obs)), "obs con NaN o inf"
        total += float(recompensa)
        if terminado or truncado:
            obs, info = env.reset(seed=7)
    print(f"[OK] 30 pasos: recompensa acumulada {total:+.2f}")

    env.close()
    print("ENV SMOKE OK (V7)")


if __name__ == "__main__":
    main()
