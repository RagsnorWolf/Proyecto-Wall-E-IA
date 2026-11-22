"""Genera las piezas de color de WALL-E a partir de la textura UV.

Por que existe
--------------
El renderer OpenGL2 de esta PC ignora la textura del MTL: el OBJ con
`material_0.png` se ve gris plano. La solucion es partir la malla en piezas
de color solido, una por cluster de color de la textura, y pintar cada pieza
con `rgbaColor`.

El problema del primer intento
------------------------------
Agrupar solo por color mezcla las orugas con el chasis: la textura pinta las
orugas del mismo naranja que el cuerpo, asi que el K-means las mete en el
mismo cluster y WALL-E sale entero amarillo. La oruga tiene que ser goma
oscura, no chapa.

La solucion
-----------
La malla se parte primero por FAMILIA geometrica y despues por color:

- `tread`: caras laterales bajas (`|y| > 0.17` y `z < 0.10`) y todo el piso
  del chasis (`z < -0.10`). Se pintan en escala de grises oscura, asi se
  conserva el dibujo de las placas de la oruga sin que se vuelva amarilla.
- `body`: todo lo demas. Se mapea a la paleta de WALL-E de `walle_look.py`.

Cada familia tiene su propio K-means, con su propio numero de clusters.

Uso:
    python walle_piezas.py            # regenera si hace falta
    python walle_piezas.py --force    # regenera siempre
"""

from __future__ import annotations

import argparse
import colorsys
import json
from pathlib import Path
from typing import Any

import numpy as np

from walle_look import WALLE_RUBBER, walle_body_color

# Version del formato de piezas. Subirla obliga a regenerar la cache.
PART_VERSION = 4

# Reparto de clusters. El cuerpo necesita mas detalle que la oruga.
BODY_CLUSTERS = 20
TREAD_CLUSTERS = 4

# Umbrales geometricos, medidos sobre walle_visual.obj:
#   x [-0.207, 0.207]  y [-0.236, 0.236]  z [-0.150, 0.350]
# El chasis central llega hasta |y| ~ 0.16; de ahi para afuera estan las
# orugas. Por debajo de z = 0.10 la banda lateral es oruga casi pura (el
# percentil 90 de esa banda es z = 0.049).
TREAD_SIDE_Y = 0.17
TREAD_TOP_Z = 0.10
TREAD_FLOOR_Z = -0.10


def _face_families(centroids: np.ndarray) -> np.ndarray:
    """Etiqueta cada cara como 0 (cuerpo) o 1 (oruga)."""
    abs_y = np.abs(centroids[:, 1])
    z = centroids[:, 2]
    side = (abs_y > TREAD_SIDE_Y) & (z < TREAD_TOP_Z)
    floor = z < TREAD_FLOOR_Z
    return (side | floor).astype(np.int64)


def _kmeans(
    colors: np.ndarray, k: int, iterations: int = 40, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """K-means simple y determinista. Devuelve (centros, etiquetas)."""
    if len(colors) == 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros(0, dtype=np.int64)
    k = max(1, min(k, len(colors)))
    rng = np.random.default_rng(seed)
    centers = colors[rng.choice(len(colors), k, replace=False)].copy()
    labels = np.zeros(len(colors), dtype=np.int64)
    for _ in range(iterations):
        distances = ((colors[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = distances.argmin(axis=1)
        updated = centers.copy()
        for index in range(k):
            mask = labels == index
            if mask.any():
                updated[index] = colors[mask].mean(axis=0)
        if np.allclose(updated, centers, atol=1e-5):
            centers = updated
            break
        centers = updated
    return centers, labels


def _tread_color(sampled: tuple[float, float, float]) -> tuple[float, float, float]:
    """Goma: el brillo de la textura se conserva, el color no.

    Las placas de la oruga son mas claras que el hueco entre ellas. Pasando
    solo la luminancia a una rampa oscura, ese dibujo sobrevive y la oruga
    deja de ser amarilla.
    """
    luminance = (
        0.2126 * float(sampled[0])
        + 0.7152 * float(sampled[1])
        + 0.0722 * float(sampled[2])
    )
    level = 0.10 + 0.26 * min(1.0, luminance)
    return (
        WALLE_RUBBER[0] + (level - WALLE_RUBBER[0]) * 0.55,
        WALLE_RUBBER[1] + (level - WALLE_RUBBER[1]) * 0.55,
        WALLE_RUBBER[2] + (level - WALLE_RUBBER[2]) * 0.55,
    )


def _write_obj(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """OBJ minimo: solo vertices y caras, con los indices ya remapeados."""
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# {path.name}: pieza de color generada por walle_piezas.py\n")
        for vtx in vertices:
            fh.write(f"v {vtx[0]:.6f} {vtx[1]:.6f} {vtx[2]:.6f}\n")
        for face in faces:
            fh.write(f"f {face[0] + 1} {face[1] + 1} {face[2] + 1}\n")


def _signature(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"mtime_ns": int(stat.st_mtime_ns), "size": int(stat.st_size)}


def ensure_colored_parts(
    visual_obj: Path,
    texture_png: Path,
    out_dir: Path,
    force: bool = False,
) -> list[tuple[str, tuple[float, float, float], int]]:
    """Devuelve [(ruta_obj, rgb, caras)] listo para `createVisualShape`.

    Cachea en `out_dir` con un manifiesto que lleva la firma de los archivos
    de origen: si cambia la textura o el OBJ, se regenera solo.
    """
    if not visual_obj.exists() or not texture_png.exists():
        return []

    try:
        import trimesh
        from PIL import Image
    except ImportError as exc:
        print(
            f"[WALL-E] Sin trimesh/Pillow no se pueden generar las piezas "
            f"({exc}). Se usara el proxy visual simple.",
            flush=True,
        )
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    source_obj = _signature(visual_obj)
    source_png = _signature(texture_png)

    if manifest_path.exists() and not force:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            valid = (
                manifest.get("version") == PART_VERSION
                and manifest.get("body_clusters") == BODY_CLUSTERS
                and manifest.get("tread_clusters") == TREAD_CLUSTERS
                and manifest.get("source_obj") == source_obj
                and manifest.get("source_png") == source_png
            )
            if valid:
                parts: list[tuple[str, tuple[float, float, float], int]] = []
                for item in manifest.get("parts", []):
                    part_path = out_dir / item["file"]
                    if not part_path.exists():
                        valid = False
                        break
                    parts.append(
                        (
                            str(part_path),
                            tuple(float(c) for c in item["color"]),
                            int(item.get("faces", 0)),
                        )
                    )
                if valid and parts:
                    print(
                        f"[WALL-E] Piezas de color en cache: {len(parts)}.",
                        flush=True,
                    )
                    return parts
        except Exception:
            pass

    try:
        mesh = trimesh.load(str(visual_obj), force="mesh")
        image = Image.open(texture_png).convert("RGB")
        uv = np.asarray(mesh.visual.uv, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        vertices = np.asarray(mesh.vertices, dtype=np.float64)

        # Color de cada cara: media de las tres UV en la textura.
        face_uv = uv[faces].mean(axis=1)
        u = np.mod(face_uv[:, 0], 1.0)
        v = np.mod(face_uv[:, 1], 1.0)
        xs = np.clip((u * (image.width - 1)).astype(np.int64), 0, image.width - 1)
        ys = np.clip(
            ((1.0 - v) * (image.height - 1)).astype(np.int64),
            0,
            image.height - 1,
        )
        colors = np.asarray(image, dtype=np.float32)[ys, xs] / 255.0

        centroids = vertices[faces].mean(axis=1)
        family = _face_families(centroids)

        new_parts: list[dict[str, Any]] = []
        for family_id, family_name, clusters in (
            (0, "body", BODY_CLUSTERS),
            (1, "tread", TREAD_CLUSTERS),
        ):
            mask_family = family == family_id
            if not mask_family.any():
                continue
            indices = np.nonzero(mask_family)[0]
            centers, labels = _kmeans(
                colors[indices], clusters, seed=family_id + 1
            )
            for cluster_index in range(len(centers)):
                local = labels == cluster_index
                if not local.any():
                    continue
                face_ids = indices[local]
                sampled = tuple(float(c) for c in centers[cluster_index])
                if family_name == "tread":
                    rgb = _tread_color(sampled)
                else:
                    rgb = walle_body_color(sampled)

                sub_faces = faces[face_ids]
                used = np.unique(sub_faces)
                remap = -np.ones(len(vertices), dtype=np.int64)
                remap[used] = np.arange(len(used))
                part_name = f"part_{family_name}_{cluster_index:02d}.obj"
                _write_obj(
                    out_dir / part_name,
                    vertices[used],
                    remap[sub_faces],
                )
                new_parts.append(
                    {
                        "file": part_name,
                        "family": family_name,
                        "color": [round(float(c), 6) for c in rgb],
                        "faces": int(len(face_ids)),
                    }
                )

        # Limpieza de piezas de versiones anteriores.
        written = {item["file"] for item in new_parts}
        for stale in out_dir.glob("part_*.obj"):
            if stale.name not in written:
                try:
                    stale.unlink()
                except OSError:
                    pass

        manifest = {
            "version": PART_VERSION,
            "body_clusters": BODY_CLUSTERS,
            "tread_clusters": TREAD_CLUSTERS,
            "tread_side_y": TREAD_SIDE_Y,
            "tread_top_z": TREAD_TOP_Z,
            "tread_floor_z": TREAD_FLOOR_Z,
            "source_obj": source_obj,
            "source_png": source_png,
            "parts": new_parts,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        result = [
            (
                str(out_dir / item["file"]),
                tuple(float(c) for c in item["color"]),
                int(item["faces"]),
            )
            for item in new_parts
        ]
        body_faces = sum(
            item["faces"] for item in new_parts if item["family"] == "body"
        )
        tread_faces = sum(
            item["faces"] for item in new_parts if item["family"] == "tread"
        )
        print(
            f"[WALL-E] Piezas generadas: {len(result)} "
            f"({body_faces} caras de cuerpo, {tread_faces} de oruga).",
            flush=True,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        print(
            f"[WALL-E] No se pudieron generar las piezas ({exc}). "
            "Se usara el proxy visual simple.",
            flush=True,
        )
        return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenera las piezas de color de WALL-E."
    )
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parent),
        help="Carpeta del simulador",
    )
    parser.add_argument(
        "--force", action="store_true", help="Ignorar la cache y regenerar"
    )
    args = parser.parse_args()

    base = Path(args.dir)
    parts = ensure_colored_parts(
        base / "walle_visual.obj",
        base / "material_0.png",
        base / "walle_color_parts",
        force=args.force,
    )
    if not parts:
        print("[WALL-E] Sin piezas.")
        return 1
    for path, rgb, faces in parts:
        hue, saturation, value = colorsys.rgb_to_hsv(*rgb)
        print(
            f"  {Path(path).name:26s} {faces:5d} caras  "
            f"rgb=({rgb[0]:.3f},{rgb[1]:.3f},{rgb[2]:.3f})  "
            f"hsv=({hue:.2f},{saturation:.2f},{value:.2f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
