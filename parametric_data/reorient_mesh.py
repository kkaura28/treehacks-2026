#!/usr/bin/env python3
"""
Reorient an OBJ mesh by applying a fixed rotation (and optional scale). Use when the
mesh's principal axis doesn't match the real object (e.g. blade along Z but pose
keeps box vertical). Export a new OBJ so FoundationPose uses the reoriented mesh.

Usage:
  python reorient_mesh.py mesh.obj --rot-z 90              # 90° around Z
  python reorient_mesh.py mesh.obj --rot-y 90              # 90° around Y (blade Z -> X)
  python reorient_mesh.py mesh.obj --rot-x 90 --output out.obj

Rotations are applied in degrees, in order: --rot-x then --rot-y then --rot-z.
Right-hand rule: positive angle = counterclockwise when looking along axis.
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
    parser = argparse.ArgumentParser(description="Reorient mesh by rotation (degrees).")
    parser.add_argument("mesh_path", type=str, help="Input OBJ")
    parser.add_argument("--rot-x", type=float, default=0, help="Rotation around X (degrees)")
    parser.add_argument("--rot-y", type=float, default=0, help="Rotation around Y (degrees)")
    parser.add_argument("--rot-z", type=float, default=0, help="Rotation around Z (degrees)")
    parser.add_argument("--output", type=str, default=None, help="Output OBJ (default: <stem>_reorient.obj)")
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

    loaded = trimesh.load(mesh_path)
    if isinstance(loaded, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(loaded.geometry.values()))
    else:
        mesh = loaded.copy()

    R = np.eye(4)
    R[:3, :3] = rotation_matrix_x(args.rot_x) @ rotation_matrix_y(args.rot_y) @ rotation_matrix_z(args.rot_z)
    mesh.apply_transform(R)

    if args.output:
        out_path = os.path.abspath(args.output)
    else:
        d = os.path.dirname(mesh_path)
        stem = os.path.splitext(os.path.basename(mesh_path))[0]
        out_path = os.path.join(d, f"{stem}_reorient.obj")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    mesh.export(out_path)
    print(f"Wrote: {out_path}")
    print("  Tip: If the box was vertical when the scalpel was horizontal, try --rot-y 90 so the blade axis (was Z) becomes X.")


if __name__ == "__main__":
    main()
