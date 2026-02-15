#!/usr/bin/env python3
"""
Load an OBJ; if trimesh returns a Scene (multiple geometries), merge into one
mesh and export. Use the output with FoundationPose run_demo.py (expects a
single mesh with .vertices / .vertex_normals).

Usage:
    python export_single_mesh_obj.py /path/to/input.obj [/path/to/output.obj]
    If output is omitted, writes to <input_stem>_single.obj in the same directory.
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Export OBJ as single mesh (merge Scene).")
    parser.add_argument("input_obj", type=str, help="Input OBJ path")
    parser.add_argument("output_obj", type=str, nargs="?", default=None, help="Output OBJ path (default: <stem>_single.obj)")
    args = parser.parse_args()

    try:
        import trimesh
    except ImportError:
        print("Error: trimesh required.", file=sys.stderr)
        sys.exit(1)

    inpath = os.path.abspath(args.input_obj)
    if not os.path.isfile(inpath):
        print(f"Error: Not found: {inpath}", file=sys.stderr)
        sys.exit(1)

    loaded = trimesh.load(inpath)
    if isinstance(loaded, trimesh.Scene):
        mesh = trimesh.util.concatenate(list(loaded.geometry.values()))
        print(f"Loaded Scene with {len(loaded.geometry)} geometries -> merged to single mesh.")
    else:
        mesh = loaded
        print("Loaded single mesh.")

    if args.output_obj:
        outpath = os.path.abspath(args.output_obj)
    else:
        d = os.path.dirname(inpath)
        stem = os.path.splitext(os.path.basename(inpath))[0]
        outpath = os.path.join(d, f"{stem}_single.obj")

    os.makedirs(os.path.dirname(outpath) or ".", exist_ok=True)
    mesh.export(outpath)
    print(f"Wrote: {outpath}")


if __name__ == "__main__":
    main()
