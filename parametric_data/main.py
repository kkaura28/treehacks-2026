#!/usr/bin/env python3
"""Run process_videos.py on a video, or FoundationPose run_demo. Usage: python main.py --option 1 /path/to/video.MOV | --option 2 /path/to/scene_dir"""

import argparse
import glob
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Parametric data pipeline or FoundationPose run_demo.")
    parser.add_argument("--option", type=int, choices=(1, 2, 3), default=None,
                        help="1 = full pipeline (video); 2 = FoundationPose (scene_dir); 3 = hand joints (video)")
    parser.add_argument("path", type=str, nargs="?", default=None,
                        help="Video path (option 1 or 3) or scene directory (option 2)")
    args = parser.parse_args()

    if args.option is None:
        parser.error("--option is required (1, 2, or 3)")

    if args.option == 3:
        if not args.path:
            parser.error("path (video path) is required when --option 3")
        video_path = os.path.abspath(args.path)
        if not os.path.isfile(video_path):
            print(f"Error: Video file not found: {video_path}", file=sys.stderr)
            sys.exit(1)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        hand_dir = os.path.join(script_dir, video_name, "hand")
        os.makedirs(hand_dir, exist_ok=True)
        json_path = os.path.join(hand_dir, "hand_joints.json")
        overlay_path = os.path.join(hand_dir, "joints_overlay.mp4")
        video_to_hand = os.path.join(script_dir, "video_to_hand_joints.py")
        if not os.path.isfile(video_to_hand):
            print(f"Error: video_to_hand_joints.py not found at {video_to_hand}", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            [
                sys.executable,
                video_to_hand,
                video_path,
                "--output", json_path,
                "--output-video", overlay_path,
            ],
            cwd=script_dir,
        )
        sys.exit(result.returncode)

    if args.option == 2:
        if not args.path:
            parser.error("path (scene directory) is required when --option 2")
        scene_dir = os.path.abspath(args.path)
        if not os.path.isdir(scene_dir):
            print(f"Error: Scene directory not found: {scene_dir}", file=sys.stderr)
            sys.exit(1)
        mesh_dir = os.path.join(scene_dir, "mesh")
        obj_files = glob.glob(os.path.join(mesh_dir, "*.obj"))
        if not obj_files:
            print(f"Error: No .obj file found in {mesh_dir}", file=sys.stderr)
            sys.exit(1)
        mesh_file = obj_files[0]
        debug_dir = os.path.join(scene_dir, "output")
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        run_demo = os.path.join(repo_root, "FoundationPose", "run_demo.py")
        if not os.path.isfile(run_demo):
            print(f"Error: run_demo.py not found at {run_demo}", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            [
                sys.executable,
                run_demo,
                "--mesh_file", mesh_file,
                "--test_scene_dir", scene_dir,
                "--est_refine_iter", "10",
                "--track_refine_iter", "10",
                "--debug", "2",
                "--debug_dir", debug_dir,
            ],
            cwd=os.path.join(repo_root, "FoundationPose"),
        )
        sys.exit(result.returncode)

    # option == 1: full pipeline
    if not args.path:
        parser.error("path (video path) is required when --option 1")
    video_path = os.path.abspath(args.path)
    if not os.path.isfile(video_path):
        print(f"Error: Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    process_videos = os.path.join(script_dir, "process_videos.py")
    npz_to_png = os.path.join(script_dir, "npz_to_png.py")
    calculate_intrinsics = os.path.join(script_dir, "calculate_intrinsics.py")
    downscale_rgb = os.path.join(script_dir, "downscale_rgb_to_depth.py")
    if not os.path.isfile(process_videos):
        print(f"Error: process_videos.py not found at {process_videos}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(npz_to_png):
        print(f"Error: npz_to_png.py not found at {npz_to_png}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(calculate_intrinsics):
        print(f"Error: calculate_intrinsics.py not found at {calculate_intrinsics}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(downscale_rgb):
        print(f"Error: downscale_rgb_to_depth.py not found at {downscale_rgb}", file=sys.stderr)
        sys.exit(1)

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    result = subprocess.run(
        [sys.executable, process_videos, video_path],
        cwd=script_dir,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    npz_path = os.path.join(script_dir, video_name, "depth.npz")
    if not os.path.isfile(npz_path):
        print(f"Error: depth.npz not found at {npz_path}", file=sys.stderr)
        sys.exit(1)
    result = subprocess.run(
        [sys.executable, npz_to_png, npz_path],
        cwd=script_dir,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    result = subprocess.run(
        [sys.executable, calculate_intrinsics, npz_path],
        cwd=script_dir,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    result = subprocess.run(
        [sys.executable, downscale_rgb, npz_path],
        cwd=script_dir,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
