#!/usr/bin/env python3
"""
Load per-frame intrinsics from depth.npz, average them, and write cam_K.txt
(FoundationPose format: 3 lines, 3 space-separated numbers per line).

Usage:
    python calculate_intrinsics.py /path/to/redbull/depth.npz
    python calculate_intrinsics.py /path/to/redbull/depth.npz --output /path/to/redbull/cam_K.txt

Averaging over frames smooths per-frame noise from the model. Intrinsics (fx, fy,
cx, cy) do not change with camera motion—only with zoom or lens change—so for a
slowly moving camera with fixed focal length, averaging is appropriate and gives
one stable K. Not a substitute for proper calibration if you need metric accuracy.
"""

import argparse
import os
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(
        description="Average per-frame intrinsics from depth.npz and save cam_K.txt.",
    )
    parser.add_argument(
        "npz_path",
        type=str,
        help="Path to depth.npz (must contain 'intrinsics' array, shape (N, 3, 3))",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for cam_K.txt (default: same directory as npz, file cam_K.txt)",
    )
    args = parser.parse_args()

    npz_path = os.path.abspath(args.npz_path)
    if not os.path.isfile(npz_path):
        print(f"Error: File not found: {npz_path}", file=sys.stderr)
        sys.exit(1)

    data = np.load(npz_path)
    if "intrinsics" not in data:
        print("Error: npz must contain 'intrinsics' array.", file=sys.stderr)
        sys.exit(1)
    K_all = data["intrinsics"]  # (N, 3, 3)
    data.close()

    K_mean = np.mean(K_all, axis=0)
    # Keep bottom row exactly [0, 0, 1] for a valid intrinsics matrix
    K_mean[2, :] = [0.0, 0.0, 1.0]

    if args.output is None:
        args.output = os.path.join(os.path.dirname(npz_path), "cam_K.txt")
    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    np.savetxt(out_path, K_mean)
    print(f"Saved averaged intrinsics ({K_all.shape[0]} frames) to {out_path}")


if __name__ == "__main__":
    main()
