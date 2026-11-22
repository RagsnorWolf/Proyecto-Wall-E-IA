r"""
transplant_v6_to_v7.py -- arrancar el cerebro V7 con lo que ya sabe el V6.

El problema: el V6 observa 66 numeros (14 base + 36 LiDAR + 8 de contexto) y el
V7 observa 74 (los mismos 66 mas 8 de comprension del entorno). Un V7 desde
cero tira los 624 096 pasos ya entrenados y vuelve a aprender a no girar en el
sitio, que es justo lo que costo esas horas.

La solucion es la misma que se uso para V4 -> V5: los primeros 66 numeros son
EXACTAMENTE los mismos, en el mismo orden. Asi que se copian todos los pesos y
solo se ensancha la entrada del MLP de 66 a 74, dejando las 8 columnas nuevas
en cero. Al principio la politica se comporta igual que el V6; el entrenamiento
decide despues si las usa.

Se copia tambien el `.pkl` de `VecNormalize`. Sin el, el critico recibe un
salto de escala en la primera reanudacion y la politica colapsa: paso tres
veces antes de que se entendiera por que.

Uso:

    python transplant_v6_to_v7.py
    python transplant_v6_to_v7.py --source models\checkpoints\walle_v6_620000_steps.zip
    python transplant_v6_to_v7.py --out models\walle_ppo_model_v7.zip --steps 200
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch
from sb3_contrib import RecurrentPPO

from walle_env_v3 import OBS_DIM, WallEEnvV3

# Una sola muestra por prediccion. Con los 8 hilos por defecto en un Ryzen de 4
# nucleos el LSTM pasa mas tiempo sincronizando hilos que multiplicando: cada
# predict tardaba ~1.5 s. Aca no hay entrenamiento, no se pierde nada.
torch.set_num_threads(1)

POLICY_KWARGS = dict(
    net_arch=[256, 256],
    lstm_hidden_size=256,
    n_lstm_layers=1,
    enable_critic_lstm=True,
)


def buscar_pkl(checkpoint: str) -> str | None:
    """El .pkl de VecNormalize que corresponde a un checkpoint.

    `CheckpointCallback` lo guarda como `walle_v6_vecnormalize_620000_steps.pkl`,
    con la version delante y el paso en medio, asi que no vale con cambiar la
    extension del .zip. Se busca por el numero de pasos en la misma carpeta.
    """
    carpeta, nombre = os.path.split(checkpoint)
    directo = checkpoint[: -len(".zip")] + "_vecnormalize.pkl"
    if os.path.exists(directo):
        return directo
    coincidencia = re.search(r"_(\d+)_steps\.zip$", nombre)
    pasos = coincidencia.group(1) if coincidencia else ""
    candidatos = []
    for otro in sorted(os.listdir(carpeta or ".")):
        if not otro.endswith(".pkl") or "vecnormalize" not in otro:
            continue
        if not pasos or pasos in otro:
            candidatos.append(os.path.join(carpeta, otro))
    return candidatos[-1] if candidatos else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trasplante V6 (66D) -> V7 (74D)"
    )
    parser.add_argument(
        "--source",
        default="models/checkpoints/walle_v6_620000_steps.zip",
        help="checkpoint V6 de origen",
    )
    parser.add_argument(
        "--out", default="models/walle_ppo_model_v7.zip", help="modelo de salida"
    )
    parser.add_argument(
        "--steps", type=int, default=200, help="pasos de verificacion"
    )
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"No existe el modelo origen: {args.source}")
        return 1

    print(f"Cargando {args.source} ...")
    v6 = RecurrentPPO.load(args.source, device="cpu")
    src = v6.policy.state_dict()
    src_obs = int(np.prod(v6.observation_space.shape))
    print(f"  V6: obs {src_obs}D, {v6.num_timesteps:,} pasos entrenados")

    env = WallEEnvV3(
        render_mode=None, stage=3, obstacle_count=6, connect_options="DIRECT"
    )
    dst_obs = int(np.prod(env.observation_space.shape))
    if dst_obs != OBS_DIM:
        print(f"El entorno dice {dst_obs}D y OBS_DIM dice {OBS_DIM}D: no sigo.")
        env.close()
        return 1
    if src_obs >= dst_obs:
        print(
            f"El origen ya tiene {src_obs}D y el destino {dst_obs}D: "
            "no hay nada que ensanchar. Usar el modelo tal cual."
        )
        env.close()
        return 1
    print(f"  V7: obs {dst_obs}D  (se ensancha la entrada en {dst_obs - src_obs})")

    model = RecurrentPPO(
        "MlpLstmPolicy",
        env,
        device="cpu",
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=256,
        n_epochs=8,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.02,
        policy_kwargs=POLICY_KWARGS,
    )

    dst = model.policy.state_dict()
    merged = {}
    copiados: list[str] = []
    ensanchados: list[tuple[str, tuple[int, ...], tuple[int, ...]]] = []
    nuevos: list[str] = []

    for clave, destino in dst.items():
        origen = src.get(clave)
        if origen is None:
            merged[clave] = destino
            nuevos.append(clave)
            continue
        if origen.shape == destino.shape:
            merged[clave] = origen.clone()
            copiados.append(clave)
            continue
        # Capa de entrada: (256, 66) -> (256, 74). Se copian las 66 columnas
        # viejas y se dejan las 8 nuevas en cero, para que al principio no
        # aporten nada y la politica se comporte como el V6.
        if (
            origen.dim() == 2
            and origen.shape[0] == destino.shape[0]
            and origen.shape[1] < destino.shape[1]
        ):
            ancho = torch.zeros_like(destino)
            ancho[:, : origen.shape[1]] = origen
            merged[clave] = ancho
            ensanchados.append((clave, tuple(origen.shape), tuple(destino.shape)))
            continue
        print(
            f"  OJO: {clave} no encaja "
            f"({tuple(origen.shape)} vs {tuple(destino.shape)}), queda al azar"
        )
        merged[clave] = destino
        nuevos.append(clave)

    model.policy.load_state_dict(merged)
    # El contador se arrastra del V6: si queda en 0, el proximo --resume cree
    # que el cerebro es nuevo y el presupuesto de pasos miente.
    model.num_timesteps = int(v6.num_timesteps)
    model._total_timesteps = int(v6.num_timesteps)

    print(f"  pesos copiados: {len(copiados)}")
    print(f"  entradas ensanchadas: {len(ensanchados)}")
    for clave, viejo, nuevo in ensanchados:
        print(f"    {clave}: {viejo} -> {nuevo}")
    if nuevos:
        print(f"  sin origen (quedan al azar): {len(nuevos)}")
        for clave in nuevos[:8]:
            print(f"    {clave}")

    # --- verificacion: que no se pase la vida girando --------------------- #
    obs, _info = env.reset()
    lstm = None
    ep_start = np.ones((1,), dtype=bool)
    acciones = []
    for _ in range(args.steps):
        accion, lstm = model.predict(
            obs, state=lstm, episode_start=ep_start, deterministic=True
        )
        ep_start = np.zeros((1,), dtype=bool)
        acciones.append(np.asarray(accion, dtype=float))
        obs, _r, terminado, truncado, _info = env.step(accion)
        if terminado or truncado:
            obs, _info = env.reset()
            lstm = None
            ep_start = np.ones((1,), dtype=bool)

    arr = np.array(acciones)
    gira = int((np.sign(arr[:, 0]) != np.sign(arr[:, 1])).sum())
    print()
    print(f"verificacion ({len(arr)} pasos):")
    print(f"  media L={arr[:, 0].mean():+.3f}  R={arr[:, 1].mean():+.3f}")
    print(f"  gira (signos opuestos): {gira}/{len(arr)}")
    print(f"  avanza (mismo signo):   {len(arr) - gira}/{len(arr)}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    model.save(args.out)
    print()
    print(f"Guardado: {args.out}")

    # --- estadisticas de recompensa --------------------------------------- #
    # norm_obs=False, asi que las estadisticas de observacion no se usan; lo
    # que importa es la media y la varianza del retorno, que es lo que calibra
    # el critico. Se copian tal cual.
    pkl_origen = buscar_pkl(args.source)
    if pkl_origen is None:
        print(
            "AVISO: no hay .pkl de VecNormalize junto al checkpoint. "
            "Las estadisticas de recompensa arrancan de cero."
        )
    else:
        import pickle

        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

        pkl_destino = args.out[: -len(".zip")] + "_vecnormalize.pkl"
        # Esta version de SB3 guarda el objeto `VecNormalize` entero, no un
        # dict, y `VecNormalize.load` le vuelve a enganchar el entorno
        # comparando formas: un pkl de 66 columnas no se puede cargar sobre un
        # entorno de 74. Asi que se arma uno nuevo y se le traslada `ret_rms`,
        # que es la media movil del retorno y lo unico que calibra el critico
        # (con norm_obs=False las estadisticas de observacion ni se crean).
        with open(pkl_origen, "rb") as archivo:
            viejo = pickle.load(archivo)
        venv = DummyVecEnv([lambda: env])
        normalizado = VecNormalize(
            venv,
            norm_obs=False,
            norm_reward=bool(getattr(viejo, "norm_reward", True)),
            clip_reward=float(getattr(viejo, "clip_reward", 10.0)),
            gamma=float(getattr(viejo, "gamma", 0.99)),
        )
        normalizado.ret_rms = viejo.ret_rms
        normalizado.training = True
        normalizado.save(pkl_destino)
        print(
            f"Guardado: {pkl_destino}  "
            f"(recompensa: media {normalizado.ret_rms.mean:.3f}, "
            f"var {normalizado.ret_rms.var:.3f})"
        )

    env.close()
    print()
    print("Listo. Reanudar con:")
    print(f"  python train_walle_v5.py --resume {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
