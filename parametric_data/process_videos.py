#!/usr/bin/env python3
"""
Run Depth-Anything-3 video_to_depth on a video and save outputs in parametric_data/<video_name>/.

Usage:
    python process_videos.py /path/to/video.MOV
    python process_videos.py /path/to/video.MOV --output-base /other/base
    python process_videos.py /path/to/video.MOV --chunk-size 0 --model-dir depth-anything/DA3-BASE  # full sequence, smaller model

Monocular only: use a smaller model and chunk-size 0 to run the entire sequence in one pass (no batching).
Smaller models: DA3-BASE (0.12B), DA3-SMALL (0.08B) use less GPU memory but output relative depth, not meters.
Metric depth (meters): use default Nested model or DA3NESTED-GIANT-LARGE-1.1; if OOM, increase --chunk-size (e.g. 30).
"""

import argparse
import os
import subprocess
import sys

import numpy as np


def extract_frames_no_depth(video_path: str, output_dir: str, sample_ratio: float):
    """Extract frames: sample_ratio 1.0 = every frame, 0.5 = every other frame. Save to output_dir/rgb/. Create depth.npz with intrinsics only (no depth)."""
    try:
        import cv2
    except ImportError:
        print("Error: --no-depth requires opencv-python (cv2). pip install opencv-python", file=sys.stderr)
        sys.exit(1)
    rgb_dir = os.path.join(output_dir, "rgb")
    os.makedirs(rgb_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video: {video_path}", file=sys.stderr)
        sys.exit(1)
    ratio = max(1e-6, min(1.0, float(sample_ratio)))
    frame_interval = max(1, int(round(1.0 / ratio)))
    frame_paths = []
    frame_count = 0
    saved_count = 0
    h, w = None, None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % frame_interval == 0:
            if h is None:
                h, w = frame.shape[:2]
            path = os.path.join(rgb_dir, f"{saved_count:06d}.png")
            cv2.imwrite(path, frame)
            frame_paths.append(path)
            saved_count += 1
        frame_count += 1
    cap.release()
    if not frame_paths:
        print("Error: No frames extracted.", file=sys.stderr)
        sys.exit(1)
    n = len(frame_paths)
    # Default intrinsics: fx=fy=max(W,H), cx=W/2, cy=H/2
    fx = fy = float(max(w, h))
    cx, cy = w / 2.0, h / 2.0
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)
    intrinsics = np.tile(K[np.newaxis, ...], (n, 1, 1))
    npz_path = os.path.join(output_dir, "depth.npz")
    np.savez_compressed(npz_path, intrinsics=intrinsics)
    print(f"Extracted {n} frames to {rgb_dir}; wrote {npz_path} (intrinsics only, no depth).")


def main():
    parser = argparse.ArgumentParser(
        description="Process a video with Depth-Anything-3 and save depth outputs in parametric_data."
    )
    parser.add_argument(
        "video_path",
        type=str,
        help="Path to input video file (e.g. redbull.MOV)",
    )
    parser.add_argument(
        "--output-base",
        type=str,
        default=os.path.dirname(os.path.abspath(__file__)),
        help="Base directory for output (default: parametric_data directory)",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="depth-anything/DA3NESTED-GIANT-LARGE-1.1",
        help="HuggingFace model: Nested for metric depth (default); DA3-BASE / DA3-SMALL for smaller GPU use (relative depth)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=0,
        metavar="N",
        help="Frames per batch; 0 = entire sequence in one pass (default). Use 30–40 if OOM.",
    )
    parser.add_argument(
        "--process-res",
        type=int,
        default=504,
        metavar="R",
        help="Depth processing resolution (max side). Lower = less GPU memory (default: 504). Ignored if --scale-factor set.",
    )
    parser.add_argument(
        "--scale-factor",
        type=float,
        default=None,
        metavar="S",
        help="Resize input by this factor before depth (e.g. 0.5 = half res). Use for full-sequence-in-one-pass.",
    )
    parser.add_argument(
        "--sample-ratio",
        type=float,
        default=1.0,
        metavar="R",
        help="Fraction of frames to keep: 1.0 = every frame, 0.5 = every other frame (default: 1.0). Lower = fewer frames, less VRAM.",
    )
    parser.add_argument(
        "--no-depth",
        action="store_true",
        help="Only extract RGB frames and write cam_K-ready intrinsics (no depth model). Use with main.py --no-depth.",
    )
    args = parser.parse_args()

    video_path = os.path.abspath(args.video_path)
    if not os.path.isfile(video_path):
        print(f"Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    # Output folder name = video filename without extension
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_base = os.path.abspath(args.output_base)
    output_dir = os.path.join(output_base, video_name)

    if args.no_depth:
        extract_frames_no_depth(video_path, output_dir, args.sample_ratio)
        print(f"Done. Results in {output_dir}")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    video_to_depth = os.path.join(repo_root, "Depth-Anything-3", "video_to_depth.py")
    if not os.path.isfile(video_to_depth):
        print(f"Error: video_to_depth.py not found at {video_to_depth}", file=sys.stderr)
        sys.exit(1)

    # Save only depth + intrinsics in npz; keep extracted RGB frames (no cleanup).
    cmd = [
        sys.executable,
        video_to_depth,
        video_path,
        "--output-dir",
        output_dir,
        "--model-dir",
        args.model_dir,
        "--sample-ratio",
        str(args.sample_ratio),
        "--depth-only",
        "--save-intrinsics",
        "--no-cleanup",
        "--quiet",
    ]
    if args.chunk_size > 0:
        cmd.extend(["--chunk-size", str(args.chunk_size)])
    else:
        cmd.extend(["--chunk-size", "0"])
    cmd.extend(["--process-res", str(args.process_res)])
    if args.scale_factor is not None:
        cmd.extend(["--scale-factor", str(args.scale_factor)])
    env = {**os.environ, "DA3_LOG_LEVEL": "WARN"}
    result = subprocess.run(cmd, cwd=repo_root, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)

    input_frames_dir = os.path.join(output_dir, "input_frames")
    rgb_dir = os.path.join(output_dir, "rgb")
    if os.path.isdir(input_frames_dir):
        os.rename(input_frames_dir, rgb_dir)

    print(f"Done. Results in {output_dir}")


if __name__ == "__main__":
    main()
