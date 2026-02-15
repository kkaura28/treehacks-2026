#!/usr/bin/env python3
"""
Create 8 OBJ meshes from one input: all combinations of 0° and 90° rotation
around X, Y, Z. Names: <stem>_X0Y0Z0.obj, _X0Y0Z90.obj, _X0Y90Z0.obj, ...
(X, Y, Z order: rot_x, rot_y, rot_z in degrees).

Usage:
  python reorient_mesh_all8.py surgery/mesh/scalpel_scaled.obj
  python reorient_mesh_all8.py surgery/mesh/scalpel_scaled.obj --out-dir surgery/mesh
"""
import argparse
import os
import sys

import numpy as np


def rotation_matrix_x(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def rotation_matrix_y(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rotation_matrix_z(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def main():
    parser = argparse.ArgumentParser(description="Create 8 reoriented OBJs (0/90 deg on X,Y,Z).")
    parser.add_argument("mesh_path", type=str, help="Input OBJ")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory (default: same as input)")
    args = parser.parse_args()

    try:
        import trimesh
    except ImportError:
        print("Error: trimesh required. pip install trimesh", file=sys.stderr)
        sys.exit(1)

    mesh_path = os.path.abspath(args.mesh_path)
    if not os.path.isfile(mesh_path):
        print(f"Error: Not found {mesh_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.dirname(mesh_path) if args.out_dir is None else os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(mesh_path))[0]

    loaded = trimesh.load(mesh_path)
    if isinstance(loaded, trimesh.Scene):
        base_mesh = trimesh.util.concatenate(list(loaded.geometry.values()))
    else:
        base_mesh = loaded.copy()

    for x in (0, 90):
        for y in (0, 90):
            for z in (0, 90):
                name = f"{stem}_X{x}Y{y}Z{z}.obj"
                out_path = os.path.join(out_dir, name)
                R = np.eye(4)
                R[:3, :3] = (
                    rotation_matrix_x(x) @ rotation_matrix_y(y) @ rotation_matrix_z(z)
                )
                mesh = base_mesh.copy()
                mesh.apply_transform(R)
                mesh.export(out_path)
                print(out_path)

    print("Done. 8 files written to", out_dir)


if __name__ == "__main__":
    main()
