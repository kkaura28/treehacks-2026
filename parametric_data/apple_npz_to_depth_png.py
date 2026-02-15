#!/usr/bin/env python3
"""
Convert per-frame NPZ depth files (e.g. from Apple Depth Pro) into FoundationPose
depth PNGs. Each NPZ must contain a 'depth' array (H, W) in meters; outputs one
16-bit PNG per NPZ (depth in mm, invalid=0).

Before processing, all other files and subdirectories in the input folder are
deleted (only .npz files are kept).

Usage:
    python apple_npz_to_depth_png.py /path/to/chobani/apple
    python apple_npz_to_depth_png.py /path/to/chobani/apple --output-dir /path/to/chobani/depth

Output:
    <output_dir>/000000.png, 000001.png, ... (same base names as the NPZ files)
"""

import argparse
import os
import shutil
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(
        description="Convert per-frame NPZ depth files to FoundationPose depth PNGs (16-bit mm)."
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="Folder containing .npz files (each with 'depth' array in meters)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for depth PNGs (default: <input_dir>/../depth)",
    )
    parser.add_argument(
        "--invalid-value",
        type=float,
        default=0.0,
        help="Depth values below this (meters) are written as 0 (default: 0)",
    )
    parser.add_argument(
        "--max-mm",
        type=float,
        default=65535.0,
        help="Depth values above this (mm) are clamped; output is always 16-bit (default: 65535)",
    )
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    if not os.path.isdir(input_dir):
        print(f"Error: Not a directory: {input_dir}", file=sys.stderr)
        sys.exit(1)

    # Remove everything in the folder that is not an .npz file.
    for name in os.listdir(input_dir):
        path = os.path.join(input_dir, name)
        if os.path.isfile(path):
            if not name.lower().endswith(".npz"):
                os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)

    npz_files = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(".npz")])
    if not npz_files:
        print(f"Error: No .npz files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    if args.output_dir is None:
        args.output_dir = os.path.join(os.path.dirname(input_dir), "depth")
    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    try:
        import cv2
    except ImportError:
        print("Error: opencv-python (cv2) required. pip install opencv-python", file=sys.stderr)
        sys.exit(1)

    try:
        from tqdm import tqdm
        file_iter = tqdm(npz_files, desc="NPZ → PNG", unit="file")
    except ImportError:
        file_iter = npz_files

    for fn in file_iter:
        npz_path = os.path.join(input_dir, fn)
        stem, _ = os.path.splitext(fn)
        out_path = os.path.join(out_dir, stem + ".png")

        data = np.load(npz_path)
        if "depth" not in data:
            print(f"Warning: skipping {fn} (no 'depth' array)", file=sys.stderr)
            data.close()
            continue
        depth_m = np.asarray(data["depth"], dtype=np.float64).squeeze()
        data.close()

        if depth_m.ndim != 2:
            print(f"Warning: skipping {fn} (depth shape {depth_m.shape}, expected 2D)", file=sys.stderr)
            continue

        invalid = (depth_m < args.invalid_value) | (~np.isfinite(depth_m))
        depth_m = np.where(invalid, 0.0, depth_m)
        depth_mm = depth_m * 1000.0
        if args.max_mm > 0:
            depth_mm = np.clip(depth_mm, 0.0, args.max_mm)
        depth_u16 = np.clip(depth_mm, 0, 65535).astype(np.uint16)

        cv2.imwrite(out_path, depth_u16)

    print(f"Wrote {len(npz_files)} depth PNGs to {out_dir}")


if __name__ == "__main__":
    main()
