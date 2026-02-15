#!/usr/bin/env python3
"""
Compute center of mass (x, y) of white pixels for each binary mask in a folder.
Outputs a JSON file with centroid pixel coordinates per frame.

Requires: pip install Pillow (or use the Depth-Anything-3 conda env which has it).

Example (Depth-Anything-3 conda env):
  conda activate Depth-Anything-3
  python mask_centroids.py surgery/masks -o surgery/masks/centroids.json

Example (from parametric_data dir):
  python mask_centroids.py surgery/masks -o surgery/masks/centroids.json
"""

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image


def centroid_of_mask(arr: np.ndarray) -> tuple[float | None, float | None]:
    """
    Compute centroid (x, y) of white pixels in a binary mask (vectorized).
    Returns (cx, cy) in pixel coordinates, or (None, None) if no white pixels.
    """
    ys, xs = np.where(arr > 0)
    if xs.size == 0:
        return (None, None)
    return (float(np.mean(xs)), float(np.mean(ys)))


def _process_one(path: Path) -> tuple[str, float | None, float | None]:
    """Load one mask and return (filename, cx, cy)."""
    arr = np.array(Image.open(path).convert("L"))
    cx, cy = centroid_of_mask(arr)
    return (path.name, cx, cy)


def main():
    parser = argparse.ArgumentParser(
        description="Compute centroid of white pixels per mask frame; output JSON."
    )
    parser.add_argument(
        "mask_folder",
        type=Path,
        default=Path("surgery/masks"),
        nargs="?",
        help="Folder containing binary mask images (default: surgery/masks)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: <mask_folder>/centroids.json)",
    )
    parser.add_argument(
        "--ext",
        type=str,
        default=".png",
        help="Mask file extension (default: .png)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=0,
        help="Parallel jobs (default: 0 = single process). Use e.g. 8 for 8 workers.",
    )
    args = parser.parse_args()

    mask_folder = args.mask_folder.resolve()
    if not mask_folder.is_dir():
        raise SystemExit(f"Not a directory: {mask_folder}")

    output_path = args.output
    if output_path is None:
        output_path = mask_folder / "centroids.json"
    output_path = output_path.resolve()

    paths = sorted(mask_folder.glob(f"*{args.ext}"))
    if not paths:
        raise SystemExit(f"No files matching *{args.ext} in {mask_folder}")

    results = {}
    if args.jobs <= 0:
        for path in paths:
            arr = np.array(Image.open(path).convert("L"))
            cx, cy = centroid_of_mask(arr)
            results[path.name] = {"x": cx, "y": cy}
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for name, cx, cy in ex.map(_process_one, paths):
                results[name] = {"x": cx, "y": cy}

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Wrote centroids for {len(results)} frames to {output_path}")


if __name__ == "__main__":
    main()
