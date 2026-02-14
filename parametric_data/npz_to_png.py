#!/usr/bin/env python3
"""
Convert a depth.npz (from video_to_depth / process_videos) into per-frame PNGs
for FoundationPose. Depth in the npz is in meters; output PNGs are in millimeters
(16-bit) as required by FoundationPose.

Usage:
    python npz_to_png.py /path/to/redbull/depth.npz
    python npz_to_png.py /path/to/redbull/depth.npz --output-dir /path/to/redbull/depth

Output:
    <output_dir>/000000.png, 000001.png, ... (16-bit depth in mm, same naming as rgb/)
"""

import argparse
import os
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(
        description="Convert depth.npz to per-frame PNGs for FoundationPose (depth in mm, 16-bit)."
    )
    parser.add_argument(
        "npz_path",
        type=str,
        help="Path to depth.npz (must contain 'depth' array, shape (N, H, W), values in meters)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for depth PNGs (default: <npz_dir>/depth)",
    )
    parser.add_argument(
        "--invalid-value",
        type=float,
        default=0.0,
        help="Depth values below this (meters) are written as 0 in the PNG (default: 0)",
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
    depth_m = data["depth"]  # (N, H, W), meters
    data.close()

    n_frames, h, w = depth_m.shape

    if args.output_dir is None:
        args.output_dir = os.path.join(os.path.dirname(npz_path), "depth")
    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    # FoundationPose: depth in millimeters, 16-bit PNG; invalid = 0
    depth_m = np.asarray(depth_m, dtype=np.float64)
    invalid = (depth_m < args.invalid_value) | (~np.isfinite(depth_m))
    depth_m[invalid] = 0
    depth_mm = (depth_m * 1000.0).astype(np.float64)
    # Clip to uint16 range; 0 = invalid
    depth_mm = np.clip(depth_mm, 0, 65535).astype(np.uint16)

    try:
        import cv2
    except ImportError:
        print("Error: opencv-python (cv2) required. pip install opencv-python", file=sys.stderr)
        sys.exit(1)

    pad_width = len(str(n_frames - 1)) if n_frames > 1 else 1
    pad_width = max(6, pad_width)  # at least 000000, 000001, ...

    try:
        from tqdm import tqdm
        frame_iter = tqdm(range(n_frames), desc="Frames", unit="frame")
    except ImportError:
        frame_iter = range(n_frames)
    for i in frame_iter:
        name = str(i).zfill(pad_width) + ".png"
        path = os.path.join(out_dir, name)
        cv2.imwrite(path, depth_mm[i])
    print(f"Wrote {n_frames} depth frames to {out_dir}")


if __name__ == "__main__":
    main()
