#!/usr/bin/env python3
"""
Scale an OBJ mesh to match the object size observed in depth + mask (meters).
Uses the first frame's depth, mask, and cam_K to build a 3D point cloud of the
object, then scales the mesh so its extent matches.

Usage:
    python scale_mesh_from_depth.py /path/to/scene_dir /path/to/mesh.obj
    python scale_mesh_from_depth.py /path/to/scene_dir /path/to/mesh.obj --frame 5 --output /path/to/mesh_scaled.obj

Output:
    Writes <mesh_stem>_scaled.obj in the same directory as the input mesh (or --output).
"""

import argparse
import os
import sys

import numpy as np


def unproject_depth_mask(depth_m, mask, K):
    """Return (N,3) points in camera frame (meters) where mask is True and depth valid."""
    H, W = depth_m.shape
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    valid = (mask > 0) & (depth_m >= 0.001) & np.isfinite(depth_m)
    v, u = np.where(valid)
    z = depth_m[v, u]
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    return np.stack([x, y, z], axis=1)


def main():
    parser = argparse.ArgumentParser(description="Scale mesh to match depth+mask object size (meters).")
    parser.add_argument("scene_dir", type=str, help="Scene dir with rgb/, depth/, masks/, cam_K.txt")
    parser.add_argument("mesh_path", type=str, help="Path to input OBJ mesh")
    parser.add_argument("--frame", type=int, default=0, help="Frame index to use (default 0)")
    parser.add_argument("--output", type=str, default=None, help="Output OBJ path (default: <mesh_dir>/<stem>_scaled.obj)")
    args = parser.parse_args()

    try:
        import cv2
        import trimesh
    except ImportError as e:
        print(f"Error: {e}. Need opencv-python and trimesh.", file=sys.stderr)
        sys.exit(1)

    scene_dir = os.path.abspath(args.scene_dir)
    mesh_path = os.path.abspath(args.mesh_path)
    if not os.path.isdir(scene_dir):
        print(f"Error: Scene dir not found: {scene_dir}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(mesh_path):
        print(f"Error: Mesh not found: {mesh_path}", file=sys.stderr)
        sys.exit(1)

    K = np.loadtxt(os.path.join(scene_dir, "cam_K.txt")).reshape(3, 3)
    rgb_dir = os.path.join(scene_dir, "rgb")
    depth_dir = os.path.join(scene_dir, "depth")
    masks_dir = os.path.join(scene_dir, "masks")
    rgb_files = sorted(os.listdir(rgb_dir))
    if not rgb_files:
        print("Error: No files in rgb/", file=sys.stderr)
        sys.exit(1)
    stem = os.path.splitext(rgb_files[args.frame])[0]
    depth_path = os.path.join(depth_dir, f"{stem}.png")
    mask_path = os.path.join(masks_dir, f"{stem}.png")
    if not os.path.isfile(depth_path):
        print(f"Error: Depth not found: {depth_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(mask_path):
        print(f"Error: Mask not found: {mask_path}", file=sys.stderr)
        sys.exit(1)

    depth = cv2.imread(depth_path, -1)
    if depth is None:
        print("Error: Could not read depth image.", file=sys.stderr)
        sys.exit(1)
    depth_m = depth.astype(np.float64) / 1000.0  # mm -> meters
    mask_img = cv2.imread(mask_path, -1)
    if mask_img is None:
        print("Error: Could not read mask image.", file=sys.stderr)
        sys.exit(1)
    if len(mask_img.shape) == 3:
        mask = (mask_img.sum(axis=2) > 0).astype(np.uint8)
    else:
        mask = (mask_img > 0).astype(np.uint8)
    Hd, Wd = depth_m.shape
    if mask.shape[0] != Hd or mask.shape[1] != Wd:
        mask = cv2.resize(mask.astype(np.uint8), (Wd, Hd), interpolation=cv2.INTER_NEAREST)
        mask = (mask > 0).astype(np.uint8)
    if mask.sum() == 0:
        print("Error: Mask is empty.", file=sys.stderr)
        sys.exit(1)

    pts = unproject_depth_mask(depth_m, mask, K)
    if len(pts) < 10:
        print("Error: Too few valid depth points under mask.", file=sys.stderr)
        sys.exit(1)
    real_extent = float(np.max(pts.max(axis=0) - pts.min(axis=0)))
    print(f"Object extent from depth+mask (meters): {real_extent:.4f}")

    loaded = trimesh.load(mesh_path)
    if isinstance(loaded, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(loaded.geometry.values()))
    else:
        mesh = loaded.copy()
    mesh_extent = float(np.max(mesh.vertices.max(axis=0) - mesh.vertices.min(axis=0)))
    print(f"Mesh extent (current units): {mesh_extent:.4f}")
    scale = real_extent / mesh_extent
    print(f"Scale factor: {scale:.6f}")
    mesh.vertices *= scale

    if args.output:
        out_path = os.path.abspath(args.output)
    else:
        mesh_dir = os.path.dirname(mesh_path)
        stem = os.path.splitext(os.path.basename(mesh_path))[0]
        out_path = os.path.join(mesh_dir, f"{stem}_scaled.obj")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    mesh.export(out_path)
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
