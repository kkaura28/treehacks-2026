#!/usr/bin/env python3
"""Run process_videos.py on a video, or FoundationPose run_demo. Usage: python main.py --option 1 /path/to/video.MOV | --option 2 /path/to/scene_dir"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time


def thin_rgb_to_match_depth(scene_dir: str, depth_npz_path: str) -> None:
    """If rgb has more frames than depth, keep evenly spaced rgb frames and renumber so counts and timing match."""
    import numpy as np
    rgb_dir = os.path.join(scene_dir, "rgb")
    if not os.path.isdir(rgb_dir):
        return
    data = np.load(depth_npz_path)
    if "depth" not in data:
        data.close()
        return
    n_depth = data["depth"].shape[0]
    data.close()
    rgb_files = sorted(glob.glob(os.path.join(rgb_dir, "*.png")))
    n_rgb = len(rgb_files)
    if n_rgb <= n_depth:
        return
    # Keep n_depth frames evenly spaced from 0..n_rgb-1; then renumber to 000000, 000001, ...
    if n_depth <= 0:
        return
    if n_depth == 1:
        keep_indices = [0]
    else:
        keep_indices = [int(round(i * (n_rgb - 1) / (n_depth - 1))) for i in range(n_depth)]
    tmp_dir = tempfile.mkdtemp(prefix="rgb_thin_")
    try:
        for i, src_idx in enumerate(keep_indices):
            src = rgb_files[src_idx]
            dst = os.path.join(tmp_dir, f"{i:06d}.png")
            shutil.copy2(src, dst)
        for f in rgb_files:
            os.remove(f)
        for i in range(n_depth):
            shutil.move(os.path.join(tmp_dir, f"{i:06d}.png"), os.path.join(rgb_dir, f"{i:06d}.png"))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"Thinned rgb from {n_rgb} to {n_depth} frames (temporal match with depth).", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Parametric data pipeline or FoundationPose run_demo.")
    parser.add_argument("--option", type=int, choices=(1, 2, 3, 4), default=None,
                        help="1 = full pipeline (video); 2 = FoundationPose (scene_dir); 3 = hand joints (video); 4 = Apple Depth Pro + depth PNGs (rgb folder)")
    parser.add_argument("path", type=str, nargs="?", default=None,
                        help="Video path (option 1 or 3), scene directory (option 2), or rgb folder (option 4)")
    parser.add_argument("--long_way", action="store_true",
                        help="(Option 2 only) Run FoundationPose on consecutive two-frame windows for the full sequence")
    parser.add_argument("--mesh", type=str, default=None,
                        help="(Option 2 only) Path to mesh .obj (default: first .obj in scene_dir/mesh/)")
    parser.add_argument("--model-dir", type=str, default=None,
                        help="(Option 1 only) Depth model: depth-anything/DA3-BASE for whole sequence at once (relative depth); default Nested (metric)")
    parser.add_argument("--chunk-size", type=int, default=None, metavar="N",
                        help="(Option 1 only) Depth frames per batch; 0 = whole sequence at once. Omit to use process_videos default.")
    parser.add_argument("--process-res", type=int, default=None, metavar="R",
                        help="(Option 1 only) Depth processing resolution. Lower = less VRAM.")
    parser.add_argument("--scale-factor", type=float, default=None, metavar="S",
                        help="(Option 1 only) Resize input by this factor before depth (e.g. 0.5 = half res). For full-sequence-in-one-pass.")
    parser.add_argument("--sample-ratio", type=float, default=None, metavar="R",
                        help="(Option 1 only) Fraction of frames to keep: 1.0 = every frame, 0.5 = every other frame. Omit for default (1.0).")
    parser.add_argument("--no-depth", action="store_true",
                        help="(Option 1 only) Run full pipeline (including depth) for real intrinsics, then delete depth/ and depth.npz at the end.")
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

    if args.option == 4:
        if not args.path:
            parser.error("path (rgb folder) is required when --option 4")
        rgb_folder = os.path.abspath(args.path)
        if not os.path.isdir(rgb_folder):
            print(f"Error: RGB folder not found: {rgb_folder}", file=sys.stderr)
            sys.exit(1)
        parent_dir = os.path.dirname(rgb_folder)
        apple_dir = os.path.join(parent_dir, "apple")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Find ml-depth-pro: sibling of parametric_data (repo_root) or inside parametric_data
        repo_root = os.path.dirname(script_dir)
        ml_depth_pro_dir = os.path.join(repo_root, "ml-depth-pro")
        if not os.path.isdir(ml_depth_pro_dir):
            ml_depth_pro_dir = os.path.join(script_dir, "ml-depth-pro")
        ml_depth_pro_dir = os.path.abspath(ml_depth_pro_dir)
        if not os.path.isdir(ml_depth_pro_dir):
            print(f"Error: ml-depth-pro not found at {ml_depth_pro_dir}. Option 4 requires the ml-depth-pro repo.", file=sys.stderr)
            sys.exit(1)
        checkpoint_path = os.path.join(ml_depth_pro_dir, "checkpoints", "depth_pro.pt")
        if not os.path.isfile(checkpoint_path):
            print(f"Error: Checkpoint not found at {checkpoint_path}. Run 'source get_pretrained_models.sh' in the ml-depth-pro repo.", file=sys.stderr)
            sys.exit(1)
        depth_pro_run = shutil.which("depth-pro-run")
        if not depth_pro_run:
            print("Error: depth-pro-run not found on PATH. Activate the depth-pro env or install ml-depth-pro.", file=sys.stderr)
            sys.exit(1)
        n_rgb = len([f for f in os.listdir(rgb_folder) if os.path.isfile(os.path.join(rgb_folder, f))])
        # Run depth-pro; if apple reaches 2*n_rgb files (all frames done), wait 15s then terminate and continue
        proc = subprocess.Popen(
            [depth_pro_run, "-i", rgb_folder, "-o", apple_dir],
            cwd=ml_depth_pro_dir,
        )
        target_count = 2 * n_rgb
        while True:
            ret = proc.poll()
            if ret is not None:
                if ret != 0:
                    sys.exit(ret)
                break
            if n_rgb > 0 and os.path.isdir(apple_dir):
                n_apple = len(os.listdir(apple_dir))
                if n_apple >= target_count:
                    time.sleep(15)
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    break
            time.sleep(5)
        # 2) apple_npz_to_depth_png.py <apple_dir> -> creates parent_dir/depth/
        apple_npz_script = os.path.join(script_dir, "apple_npz_to_depth_png.py")
        if not os.path.isfile(apple_npz_script):
            print(f"Error: apple_npz_to_depth_png.py not found at {apple_npz_script}", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            [sys.executable, apple_npz_script, apple_dir],
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
        if args.mesh:
            mesh_file = os.path.abspath(args.mesh)
            if not os.path.isfile(mesh_file):
                print(f"Error: Mesh file not found: {mesh_file}", file=sys.stderr)
                sys.exit(1)
        else:
            obj_files = sorted(glob.glob(os.path.join(mesh_dir, "*.obj")))
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

        if args.long_way:
            color_files = sorted(glob.glob(os.path.join(scene_dir, "rgb", "*.png")))
            batch_size = 3
            if len(color_files) < batch_size:
                print(f"Error: Need at least {batch_size} frames in {scene_dir}/rgb for --long_way", file=sys.stderr)
                sys.exit(1)
            depth_dir = os.path.join(scene_dir, "depth")
            masks_dir = os.path.join(scene_dir, "masks")
            cam_K_path = os.path.join(scene_dir, "cam_K.txt")
            if not os.path.isfile(cam_K_path):
                print(f"Error: cam_K.txt not found in {scene_dir}", file=sys.stderr)
                sys.exit(1)
            os.makedirs(debug_dir, exist_ok=True)
            os.makedirs(os.path.join(debug_dir, "ob_in_cam"), exist_ok=True)
            os.makedirs(os.path.join(debug_dir, "track_vis"), exist_ok=True)
            fp_cwd = os.path.join(repo_root, "FoundationPose")
            demo_args = [
                sys.executable, run_demo,
                "--mesh_file", mesh_file,
                "--est_refine_iter", "10",
                "--track_refine_iter", "10",
                "--debug", "2",
            ]
            num_batches = (len(color_files) + batch_size - 1) // batch_size
            for batch_idx in range(num_batches):
                start = batch_idx * batch_size
                batch_frames = color_files[start:start + batch_size]
                n_batch = len(batch_frames)
                if n_batch == 0:
                    continue
                tmp = tempfile.mkdtemp(prefix="fp_long_way_")
                try:
                    for sub in ("rgb", "depth", "masks"):
                        os.makedirs(os.path.join(tmp, sub), exist_ok=True)
                    shutil.copy(cam_K_path, os.path.join(tmp, "cam_K.txt"))
                    for j, src_rgb in enumerate(batch_frames):
                        local_name = f"{j:06d}.png"
                        base = os.path.basename(src_rgb)
                        shutil.copy2(src_rgb, os.path.join(tmp, "rgb", local_name))
                        src_depth = os.path.join(depth_dir, base)
                        if os.path.isfile(src_depth):
                            shutil.copy2(src_depth, os.path.join(tmp, "depth", local_name))
                        src_mask = os.path.join(masks_dir, base)
                        if os.path.isfile(src_mask):
                            shutil.copy2(src_mask, os.path.join(tmp, "masks", local_name))
                    tmp_debug = os.path.join(tmp, "output")
                    result = subprocess.run(
                        demo_args + ["--test_scene_dir", tmp, "--debug_dir", tmp_debug],
                        cwd=fp_cwd,
                    )
                    if result.returncode != 0:
                        print(f"Error: run_demo failed on frames {start}–{start + n_batch - 1}", file=sys.stderr)
                        shutil.rmtree(tmp, ignore_errors=True)
                        sys.exit(result.returncode)
                    ob_dir = os.path.join(tmp_debug, "ob_in_cam")
                    track_vis_src = os.path.join(tmp_debug, "track_vis")
                    track_vis_dst = os.path.join(debug_dir, "track_vis")
                    for j in range(n_batch):
                        src_pose = os.path.join(ob_dir, f"{j:06d}.txt")
                        if os.path.isfile(src_pose):
                            frame_base = os.path.basename(batch_frames[j]).replace(".png", ".txt")
                            shutil.copy2(src_pose, os.path.join(debug_dir, "ob_in_cam", frame_base))
                        vis_src = os.path.join(track_vis_src, f"{j:06d}.png")
                        if os.path.isfile(vis_src):
                            shutil.copy2(vis_src, os.path.join(track_vis_dst, os.path.basename(batch_frames[j])))
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                if (batch_idx + 1) % 50 == 0 or batch_idx == 0:
                    print(f"Long-way: finished batch {batch_idx + 1}/{num_batches} (frames {start}–{start + n_batch - 1})")
            print(f"Long-way: saved poses to {debug_dir}/ob_in_cam/ and track_vis to {debug_dir}/track_vis/")
            sys.exit(0)
        else:
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
    process_cmd = [sys.executable, process_videos, video_path]
    if args.model_dir is not None:
        process_cmd.extend(["--model-dir", args.model_dir])
    if args.chunk_size is not None:
        process_cmd.extend(["--chunk-size", str(args.chunk_size)])
    if args.process_res is not None:
        process_cmd.extend(["--process-res", str(args.process_res)])
    if args.scale_factor is not None:
        process_cmd.extend(["--scale-factor", str(args.scale_factor)])
    if args.sample_ratio is not None:
        process_cmd.extend(["--sample-ratio", str(args.sample_ratio)])
    result = subprocess.run(process_cmd, cwd=script_dir)
    if result.returncode != 0:
        sys.exit(result.returncode)

    npz_path = os.path.join(script_dir, video_name, "depth.npz")
    if not os.path.isfile(npz_path):
        print(f"Error: depth.npz not found at {npz_path}", file=sys.stderr)
        sys.exit(1)
    scene_dir = os.path.join(script_dir, video_name)

    thin_rgb_to_match_depth(scene_dir, npz_path)
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
    if result.returncode != 0:
        sys.exit(result.returncode)

    if getattr(args, "no_depth", False):
        # Run full pipeline for real intrinsics, then remove depth outputs.
        depth_dir = os.path.join(scene_dir, "depth")
        if os.path.isdir(depth_dir):
            shutil.rmtree(depth_dir)
            print(f"Removed {depth_dir} (--no-depth).", flush=True)
        if os.path.isfile(npz_path):
            os.remove(npz_path)
            print(f"Removed {npz_path} (--no-depth).", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
