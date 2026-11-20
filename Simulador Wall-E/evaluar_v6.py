"""
evaluar_v6.py · Banco de pruebas del cerebro (observación de 66 números)

Entrena que el modelo aprenda; esto mide si aprendió. Corre N episodios con
el mismo conjunto de semillas para todos los modelos y saca una tabla que se
puede comparar entre versiones sin adivinar.

Mide lo que importa para el robot real:

  distancia neta      cuánto se alejó del punto de partida (metros)
  camino recorrido    suma de desplazamientos, aunque vuelva sobre sus pasos
  contactos           veces que tocó algo, no pasos: una vez por evento
  tiempo en contacto  fracción de pasos pegados a un obstáculo
  atascos             veces que se quedó sin moverse 0.75 s
  chunks              celdas de 1 m descubiertas
  recompensa          el retorno del episodio, comparable con el entrenamiento
  velocidad media     m/s reales sobre el eje del chasis

Uso:
    python evaluar_v6.py                                  # modelo v6, 10 episodios
    python evaluar_v6.py --model models/walle_ppo_model_v6.zip
    python evaluar_v6.py --episodes 20 --obstacles 12
    python evaluar_v6.py --compare v6 v5                  # dos modelos, mismas semillas
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import numpy as np  # noqa: E402
import pybullet as p  # noqa: E402
from sb3_contrib import RecurrentPPO  # noqa: E402
from stable_baselines3 import PPO  # noqa: E402

from walle_env_v3 import OBS_DIM, WallEEnvV3  # noqa: E402

MODELOS = {
    "v6": "walle_ppo_model_v6.zip",
    "v5": "walle_ppo_model_v5_recovery.zip",
    "v4": "walle_ppo_model_v4_lidar.zip",
}


def cargar_modelo(ruta: Path):
    """Carga RecurrentPPO o PPO. Devuelve (modelo, es_recurrente)."""
    try:
        return RecurrentPPO.load(str(ruta), device="cpu"), True
    except Exception:
        pass
    return PPO.load(str(ruta), device="cpu"), False


def correr_episodio(env, modelo, recurrente: bool, semilla: int) -> dict:
    """Un episodio completo, con métricas acumuladas."""
    obs, _ = env.reset(seed=semilla)
    estado = None
    inicio = None
    pos_anterior = None
    camino = 0.0
    contactos = 0
    pasos_contacto = 0
    atascos = 0
    chunks = 0
    velocidades: list[float] = []
    recompensa = 0.0
    paso = 0
    en_contacto = False

    while True:
        if recurrente:
            accion, estado = modelo.predict(
                obs, state=estado, episode_start=np.array([paso == 0]),
                deterministic=True,
            )
        else:
            accion, _ = modelo.predict(obs, deterministic=True)
        obs, premio, terminado, truncado, info = env.step(accion)
        recompensa += float(premio)
        paso += 1

        pos, quat = p.getBasePositionAndOrientation(env.robot)
        pos = np.asarray(pos, dtype=np.float64)
        if inicio is None:
            inicio = pos.copy()
        if pos_anterior is not None:
            camino += float(np.linalg.norm(pos[:2] - pos_anterior[:2]))
        pos_anterior = pos[:2].copy()

        yaw = float(p.getEulerFromQuaternion(quat)[2])
        lin_vel, _ = p.getBaseVelocity(env.robot)
        velocidades.append(
            float(lin_vel[0]) * np.cos(yaw) + float(lin_vel[1]) * np.sin(yaw)
        )

        tocando = bool(info.get("contact", False))
        if tocando and not en_contacto:
            contactos += 1
        en_contacto = tocando
        pasos_contacto += int(tocando)
        atascos += int(bool(info.get("stuck", False)))
        chunks += int(info.get("chunks_discovered", 0))

        if terminado or truncado:
            break

    final = np.asarray(p.getBasePositionAndOrientation(env.robot)[0])
    return {
        "distancia_neta": float(np.linalg.norm(final[:2] - inicio[:2])),
        "camino": camino,
        "contactos": contactos,
        "tiempo_contacto": pasos_contacto / max(1, paso),
        "atascos": atascos,
        "chunks": chunks,
        "recompensa": recompensa,
        "pasos": paso,
        "vel_media": float(np.mean(velocidades)) if velocidades else 0.0,
    }


def resumir(nombre: str, filas: list[dict]) -> str:
    """Una fila de tabla con media ± desviación de cada métrica."""

    def m(clave: str, escala: float = 1.0) -> str:
        valores = [f[clave] * escala for f in filas]
        media = statistics.fmean(valores)
        if len(valores) < 2:
            return f"{media:7.2f}"
        desvio = statistics.pstdev(valores)
        return f"{media:7.2f}±{desvio:4.2f}"

    return (
        f"{nombre:<22} {m('distancia_neta'):>14} {m('camino'):>14} "
        f"{m('contactos'):>9} {m('tiempo_contacto', 100.0):>9}% "
        f"{m('atascos'):>8} {m('chunks'):>8} "
        f"{m('vel_media'):>13} {m('recompensa'):>13}"
    )


def evaluar(ruta: Path, episodios: int, obstaculos: int) -> list[dict]:
    env = WallEEnvV3(
        render_mode=None,
        stage=3,
        max_episode_steps=1200,
        max_wheel_speed=2.5,
        max_force=0.5,
        arena_half_size=12.0,
        obstacle_count=obstaculos,
        stage3_min_obstacle_distance=2.0,
        obstacle_max_distance=10.0,
        obstacle_min_separation=1.5,
        enable_sensors=True,
        sensor_noise_std=0.02,
        collision_terminates=False,
    )
    modelo, recurrente = cargar_modelo(ruta)
    forma = tuple(getattr(modelo.observation_space, "shape", ()) or ())
    if forma != (OBS_DIM,):
        env.close()
        raise SystemExit(
            f"{ruta.name} espera observación {forma}, el entorno usa {(OBS_DIM,)}"
        )
    filas = []
    for i in range(episodios):
        filas.append(correr_episodio(env, modelo, recurrente, 1000 + i))
    env.close()
    return filas


def main() -> int:
    parser = argparse.ArgumentParser(description="Banco de pruebas del cerebro")
    parser.add_argument(
        "--model", type=str, default="",
        help="ruta al .zip; por defecto models/walle_ppo_model_v6.zip",
    )
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--obstacles", type=int, default=8)
    parser.add_argument(
        "--compare", nargs="+", choices=sorted(MODELOS), default=None,
        help="compara varias versiones con las mismas semillas",
    )
    args = parser.parse_args()

    modelos_dir = SCRIPT_DIR / "models"
    if args.compare:
        candidatos = [
            (nombre, modelos_dir / MODELOS[nombre])
            for nombre in args.compare
            if (modelos_dir / MODELOS[nombre]).exists()
        ]
        if not candidatos:
            print("No hay ningún modelo de los pedidos en models\\.")
            return 1
    else:
        ruta = Path(args.model) if args.model else modelos_dir / MODELOS["v6"]
        if not ruta.exists():
            print(f"No encuentro {ruta}.")
            return 1
        candidatos = [(ruta.stem.replace("walle_ppo_model_", ""), ruta)]

    print(
        f"{args.episodes} episodios por modelo · {args.obstacles} obstáculos · "
        f"observación {OBS_DIM}D · acciones deterministas"
    )
    print()
    cabecera = (
        f"{'modelo':<22} {'dist. neta':>14} {'camino':>14} "
        f"{'contactos':>9} {'t. contacto':>9} "
        f"{'atascos':>8} {'chunks':>8} "
        f"{'vel. media':>13} {'recompensa':>13}"
    )
    print(cabecera)
    print("-" * len(cabecera))
    for nombre, ruta in candidatos:
        filas = evaluar(ruta, args.episodes, args.obstacles)
        print(resumir(nombre, filas))
    print()
    print("dist. neta y camino en metros · t. contacto en % de pasos")
    print("contactos y atascos son eventos, no pasos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
