#!/usr/bin/env python3
"""
Run Depth-Anything-3 video_to_depth on a video and save outputs in parametric_data/<video_name>/.

Usage:
    python process_videos.py /path/to/video.MOV
    python process_videos.py /path/to/video.MOV --output-base /other/base
"""

import argparse
import os
import subprocess
import sys


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
    args = parser.parse_args()

    video_path = os.path.abspath(args.video_path)
    if not os.path.isfile(video_path):
        print(f"Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    # Output folder name = video filename without extension
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_base = os.path.abspath(args.output_base)
    output_dir = os.path.join(output_base, video_name)

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
        "--fps",
        "30",
        "--chunk-size",
        "30",
        "--depth-only",
        "--save-intrinsics",
        "--no-cleanup",
        "--quiet",
    ]
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
