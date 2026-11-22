"""Capturas headless del simulador para revisar el aspecto sin abrir la GUI.

Conecta PyBullet en modo DIRECT con el rasterizador por software
(ER_TINY_RENDERER), arma el mismo suelo, los mismos solidos y el mismo
WALL-E que la GUI, y guarda PNGs en `capturas/`.

Asi se puede comparar la paleta cruda de la textura contra la paleta
canonica de `walle_look.py` sin depender del driver de video: el renderer
OpenGL de esta PC no permite leer el framebuffer.

Uso:
    python tools_vista_previa.py
    python tools_vista_previa.py --out capturas --size 900
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import pybullet as p
import pybullet_data

from walle_look import (
    GROUND_RGBA,
    SKY_RGB,
    SOLID_PALETTE,
    WALL_RGBA,
)

SCRIPT_DIR = Path(__file__).resolve().parent
COLOR_PARTS_DIR = SCRIPT_DIR / "walle_color_parts"
MANIFEST = COLOR_PARTS_DIR / "manifest.json"


def cargar_piezas() -> list[tuple[Path, tuple[float, float, float]]]:
    """Lee el manifiesto de piezas de color generado desde la textura."""
    if not MANIFEST.exists():
        raise SystemExit(
            f"Falta {MANIFEST}. Corré la GUI una vez para que genere las piezas."
        )
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    piezas: list[tuple[Path, tuple[float, float, float]]] = []
    for item in data.get("parts", []):
        path = COLOR_PARTS_DIR / item["file"]
        if not path.exists():
            continue
        color = tuple(float(c) for c in item["color"])
        piezas.append((path, color))  # type: ignore[arg-type]
    return piezas


def construir_escena(
    piezas: list[tuple[Path, tuple[float, float, float]]],
) -> int:
    """Suelo, paredes, solidos y WALL-E. Devuelve el id del cuerpo visual."""
    # Suelo: caja del tamano de la arena, no el plano con textura checker.
    arena = 12.0
    suelo_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[arena, arena, 0.01])
    suelo_vis = p.createVisualShape(
        p.GEOM_BOX,
        halfExtents=[arena, arena, 0.01],
        rgbaColor=list(GROUND_RGBA),
        specularColor=[0.045, 0.045, 0.055],
    )
    p.createMultiBody(
        baseMass=0,
        baseCollisionShapeIndex=suelo_col,
        baseVisualShapeIndex=suelo_vis,
        basePosition=[0.0, 0.0, -0.01],
    )

    # Paredes perimetrales.
    for pos, half in [
        ([arena, 0.0, 0.8], [0.3, arena, 0.8]),
        ([-arena, 0.0, 0.8], [0.3, arena, 0.8]),
        ([0.0, arena, 0.8], [arena, 0.3, 0.8]),
        ([0.0, -arena, 0.8], [arena, 0.3, 0.8]),
    ]:
        col = p.createCollisionShape(p.GEOM_BOX, halfExtents=half)
        vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=half,
            rgbaColor=list(WALL_RGBA),
            specularColor=[0.06, 0.06, 0.07],
        )
        p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=col,
            baseVisualShapeIndex=vis,
            basePosition=pos,
        )

    # Solidos de referencia: cajas y un cilindro, como en la arena real.
    for index, (x, y, sx, sy, sz) in enumerate(
        [
            (1.6, -0.9, 0.30, 0.30, 0.55),
            (2.3, 0.8, 0.45, 0.22, 0.90),
            (-1.4, 1.5, 0.25, 0.25, 0.35),
            (-2.2, -1.1, 0.60, 0.35, 0.70),
        ]
    ):
        col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[sx, sy, sz])
        vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[sx, sy, sz],
            rgbaColor=list(SOLID_PALETTE[index % len(SOLID_PALETTE)]),
        )
        p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=col,
            baseVisualShapeIndex=vis,
            basePosition=[x, y, sz],
        )

    col = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.28, height=1.4)
    vis = p.createVisualShape(
        p.GEOM_CYLINDER,
        radius=0.28,
        length=1.4,
        rgbaColor=list(SOLID_PALETTE[1]),
    )
    p.createMultiBody(
        baseMass=0,
        baseCollisionShapeIndex=col,
        baseVisualShapeIndex=vis,
        basePosition=[0.4, 2.4, 0.7],
    )

    # WALL-E: una pieza visual por cluster de color. Los colores del
    # manifiesto ya vienen mapeados a la paleta del personaje por
    # walle_piezas.py, asi que se usan tal cual.
    visual_ids: list[int] = []
    for path, color in piezas:
        visual_ids.append(
            p.createVisualShape(
                p.GEOM_MESH,
                fileName=str(path),
                meshScale=[1.0, 1.0, 1.0],
                rgbaColor=[color[0], color[1], color[2], 1.0],
                specularColor=[0.22, 0.21, 0.19],
            )
        )
    count = len(visual_ids)
    cuerpo = p.createMultiBody(
        baseMass=0,
        baseCollisionShapeIndex=-1,
        baseVisualShapeIndex=-1,
        basePosition=[0.0, 0.0, 0.15],
        # El OBJ mira hacia -X: se gira para que el frente quede en +X, igual
        # que en la GUI.
        baseOrientation=p.getQuaternionFromEuler([0.0, 0.0, math.pi]),
        linkMasses=[0.0] * count,
        linkCollisionShapeIndices=[-1] * count,
        linkVisualShapeIndices=visual_ids,
        linkPositions=[[0.0, 0.0, 0.0]] * count,
        linkOrientations=[[0.0, 0.0, 0.0, 1.0]] * count,
        linkInertialFramePositions=[[0.0, 0.0, 0.0]] * count,
        linkInertialFrameOrientations=[[0.0, 0.0, 0.0, 1.0]] * count,
        linkParentIndices=[0] * count,
        linkJointTypes=[p.JOINT_FIXED] * count,
        linkJointAxis=[[0.0, 0.0, 1.0]] * count,
    )
    return cuerpo


def capturar(
    ruta: Path,
    objetivo: tuple[float, float, float],
    distancia: float,
    yaw: float,
    pitch: float,
    ancho: int,
    alto: int,
) -> None:
    view = p.computeViewMatrixFromYawPitchRoll(
        cameraTargetPosition=list(objetivo),
        distance=distancia,
        yaw=yaw,
        pitch=pitch,
        roll=0.0,
        upAxisIndex=2,
    )
    proj = p.computeProjectionMatrixFOV(
        fov=48.0,
        aspect=ancho / alto,
        nearVal=0.05,
        farVal=60.0,
    )
    _w, _h, rgba, _depth, _seg = p.getCameraImage(
        width=ancho,
        height=alto,
        viewMatrix=view,
        projectionMatrix=proj,
        renderer=p.ER_TINY_RENDERER,
        lightDirection=[-0.45, 0.35, 0.82],
        lightColor=[1.0, 1.0, 1.0],
        lightDistance=12.0,
        lightAmbientCoeff=0.55,
        lightDiffuseCoeff=0.75,
        lightSpecularCoeff=0.25,
        shadow=1,
        flags=p.ER_NO_SEGMENTATION_MASK,
    )
    guardar_png(ruta, rgba, ancho, alto)


def guardar_png(ruta: Path, rgba: bytes, ancho: int, alto: int) -> None:
    """PNG sin dependencias: si hay Pillow se usa, si no se escribe BMP."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image

        img = Image.frombytes("RGBA", (ancho, alto), bytes(rgba))
        img.convert("RGB").save(ruta)
        print(f"  {ruta.name}")
        return
    except ImportError:
        pass
    bmp = ruta.with_suffix(".bmp")
    _escribir_bmp(bmp, rgba, ancho, alto)
    print(f"  {bmp.name} (sin Pillow, BMP)")


def _escribir_bmp(
    ruta: Path, rgba: bytes, ancho: int, alto: int
) -> None:
    import struct

    fila = ancho * 3
    relleno = (4 - fila % 4) % 4
    tam_fila = fila + relleno
    tam_datos = tam_fila * alto
    cabecera = struct.pack("<2sIHHI", b"BM", 54 + tam_datos, 0, 0, 54)
    info = struct.pack(
        "<IiiHHIIiiII",
        40, ancho, alto, 1, 24, 0, tam_datos, 2835, 2835, 0, 0,
    )
    with ruta.open("wb") as fh:
        fh.write(cabecera)
        fh.write(info)
        for y in range(alto - 1, -1, -1):
            base = y * ancho * 4
            fila_datos = bytearray()
            for x in range(ancho):
                i = base + x * 4
                fila_datos += bytes((rgba[i + 2], rgba[i + 1], rgba[i]))
            fh.write(bytes(fila_datos))
            fh.write(b"\x00" * relleno)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capturas headless del simulador WALL-E."
    )
    parser.add_argument(
        "--out", default=str(SCRIPT_DIR / "capturas"), help="Carpeta de salida"
    )
    parser.add_argument("--size", type=int, default=800, help="Ancho en pixeles")
    args = parser.parse_args()

    ancho = int(args.size)
    alto = int(ancho * 0.75)
    salida = Path(args.out)

    piezas = cargar_piezas()
    print(f"[VISTA] {len(piezas)} piezas de color")

    p.connect(p.DIRECT)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0.0, 0.0, -9.81)
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)

    construir_escena(piezas)
    for nombre, objetivo, distancia, yaw, pitch in [
        ("frente", (0.0, 0.0, 0.20), 1.05, 145.0, -10.0),
        ("lado", (0.0, 0.0, 0.20), 1.05, 205.0, -8.0),
        ("espalda", (0.0, 0.0, 0.20), 1.05, 35.0, -10.0),
        ("escena", (0.6, 0.4, 0.30), 4.60, 130.0, -24.0),
    ]:
        capturar(
            salida / f"walle_{nombre}.png",
            objetivo,
            distancia,
            yaw,
            pitch,
            ancho,
            alto,
        )

    p.disconnect()
    print(f"[VISTA] Listo en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
