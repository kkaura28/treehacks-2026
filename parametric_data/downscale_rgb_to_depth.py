#!/usr/bin/env python3
"""
Downscale RGB frames in rgb/ to match the resolution of the depth frames
so that rgb, depth, and cam_K are all in the same coordinate frame.

Usage:
    python downscale_rgb_to_depth.py /path/to/redbull/depth.npz
    python downscale_rgb_to_depth.py /path/to/redbull/depth.npz --rgb-dir /path/to/redbull/rgb

Reads depth shape (N, H, W) from depth.npz; resizes each image in rgb/ to (W, H)
and overwrites it. Uses cv2.INTER_AREA for downscaling.
"""

import argparse
import os
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(
        description="Downscale RGB frames to depth resolution (in-place).",
    )
    parser.add_argument(
        "npz_path",
        type=str,
        help="Path to depth.npz (used to get depth shape H, W)",
    )
    parser.add_argument(
        "--rgb-dir",
        type=str,
        default=None,
        help="Directory containing RGB PNGs (default: <npz_dir>/rgb)",
    )
    args = parser.parse_args()

    npz_path = os.path.abspath(args.npz_path)
    if not os.path.isfile(npz_path):
        print(f"Error: File not found: {npz_path}", file=sys.stderr)
        sys.exit(1)

    data = np.load(npz_path)
    if "depth" not in data:
        print("Error: npz must contain 'depth' array.", file=sys.stderr)
        sys.exit(1)
    n_depth, h, w = data["depth"].shape
    data.close()
    target_size = (w, h)  # cv2 resize (width, height)

    if args.rgb_dir is None:
        args.rgb_dir = os.path.join(os.path.dirname(npz_path), "rgb")
    rgb_dir = os.path.abspath(args.rgb_dir)
    if not os.path.isdir(rgb_dir):
        print(f"Error: RGB directory not found: {rgb_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        import cv2
    except ImportError:
        print("Error: opencv-python (cv2) required. pip install opencv-python", file=sys.stderr)
        sys.exit(1)

    names = sorted(f for f in os.listdir(rgb_dir) if f.lower().endswith((".png", ".jpg", ".jpeg")))
    if not names:
        print(f"Error: No images in {rgb_dir}", file=sys.stderr)
        sys.exit(1)
    if len(names) != n_depth:
        print(f"Warning: rgb has {len(names)} images, depth has {n_depth} frames.", file=sys.stderr)

    try:
        from tqdm import tqdm
        name_iter = tqdm(names, desc="Downscale RGB", unit="frame")
    except ImportError:
        name_iter = names
    for name in name_iter:
        path = os.path.join(rgb_dir, name)
        img = cv2.imread(path)
        if img is None:
            print(f"Warning: Could not read {path}", file=sys.stderr)
            continue
        resized = cv2.resize(img, target_size, interpolation=cv2.INTER_AREA)
        cv2.imwrite(path, resized)
    print(f"Downscaled {len(names)} RGB frames to {w}x{h}")


if __name__ == "__main__":
    main()
