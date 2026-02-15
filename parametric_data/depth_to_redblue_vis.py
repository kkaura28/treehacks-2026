#!/usr/bin/env python3
"""
Visualize depth PNG(s) as red-blue images: red = near, blue = far.
By default uses absolute depth mapping (same depth value = same color across all images).
Use --relative to scale per image (min/max of each image).

Usage:
    python depth_to_redblue_vis.py /path/to/depth/000104.png
    python depth_to_redblue_vis.py /path/to/depth --min-depth 300 --max-depth 2000  # explicit range (mm)
    python depth_to_redblue_vis.py /path/to/depth --relative  # per-image scale (old behavior)
"""

import argparse
import os
import glob
import numpy as np
from PIL import Image


def depth_to_redblue(
    depth_path: str,
    output_path: str,
    *,
    depth_min_mm: float,
    depth_max_mm: float,
) -> None:
    """Map depth (mm) to red-blue: depth_min_mm -> red, depth_max_mm -> blue. Same value = same color."""
    d = np.array(Image.open(depth_path))
    valid = d > 0
    if not np.any(valid):
        rgb = np.zeros((*d.shape, 3), dtype=np.uint8)
        Image.fromarray(rgb).save(output_path)
        print(f"{depth_path} -> {output_path} (no valid depth)")
        return
    span = depth_max_mm - depth_min_mm
    if span <= 0:
        span = 1.0
    t = np.zeros_like(d, dtype=np.float64)
    t[valid] = (d[valid].astype(np.float64) - depth_min_mm) / span
    t[valid] = np.clip(t[valid], 0.0, 1.0)
    rgb = np.zeros((*d.shape, 3), dtype=np.uint8)
    rgb[valid, 0] = (255 * (1 - t[valid])).astype(np.uint8)
    rgb[valid, 1] = 0
    rgb[valid, 2] = (255 * t[valid]).astype(np.uint8)
    rgb[~valid] = 0
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    Image.fromarray(rgb).save(output_path)
    print(f"{depth_path} -> {output_path}  (red={depth_min_mm} mm, blue={depth_max_mm} mm)")


def main():
    parser = argparse.ArgumentParser(
        description="Red-blue depth visualization (red=near, blue=far). Absolute mapping by default."
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to a depth PNG or to a directory of depth PNGs",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Output directory. Default: <input_parent>/../output/depth_vis for a file, <input>/depth_vis for a dir",
    )
    parser.add_argument(
        "--min-depth",
        type=float,
        default=300.0,
        help="Depth (mm) that maps to red. Used for absolute coloring (default: 300)",
    )
    parser.add_argument(
        "--max-depth",
        type=float,
        default=2000.0,
        help="Depth (mm) that maps to blue. Used for absolute coloring (default: 2000)",
    )
    parser.add_argument(
        "--relative",
        action="store_true",
        help="Scale per image (min/max of each image) instead of absolute depth range",
    )
    args = parser.parse_args()

    if os.path.isfile(args.input):
        paths = [args.input]
        if args.output_dir is None:
            parent = os.path.dirname(args.input)
            args.output_dir = os.path.normpath(os.path.join(parent, "..", "output", "depth_vis"))
    elif os.path.isdir(args.input):
        paths = sorted(glob.glob(os.path.join(args.input, "*.png")))
        if not paths:
            print(f"No *.png in {args.input}", flush=True)
            return 1
        if args.output_dir is None:
            args.output_dir = os.path.join(os.path.dirname(args.input.rstrip(os.sep)), "output", "depth_vis")
    else:
        print(f"Not a file or directory: {args.input}", flush=True)
        return 1

    for p in paths:
        name = os.path.basename(p)
        out_path = os.path.join(args.output_dir, name)
        if args.relative:
            d = np.array(Image.open(p))
            valid = d > 0
            if np.any(valid):
                d_min, d_max = float(d[valid].min()), float(d[valid].max())
                depth_to_redblue(p, out_path, depth_min_mm=d_min, depth_max_mm=d_max)
            else:
                depth_to_redblue(p, out_path, depth_min_mm=0.0, depth_max_mm=1.0)
        else:
            depth_to_redblue(
                p, out_path,
                depth_min_mm=args.min_depth,
                depth_max_mm=args.max_depth,
            )
    return 0


if __name__ == "__main__":
    exit(main() or 0)
