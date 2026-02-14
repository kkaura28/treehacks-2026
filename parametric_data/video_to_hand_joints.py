#!/usr/bin/env python3
"""
Extract hand joint (landmark) positions per frame from a video using MediaPipe Hands.
Outputs a JSON file and optionally a video with joints drawn. Uses MediaPipe Tasks API (0.10.31+).

Usage:
    python video_to_hand_joints.py /path/to/video.mp4
    python video_to_hand_joints.py /path/to/video.mp4 --output joints.json
    python video_to_hand_joints.py /path/to/video.mp4 --output-video out.mp4
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

# Default hand landmarker model URL (MediaPipe hosted)
HAND_LANDMARKER_TASK_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# MediaPipe 21 hand landmarks: skeleton edges (pairs of landmark indices)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),       # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),       # index
    (0, 9), (9, 10), (10, 11), (11, 12),  # middle
    (0, 13), (13, 14), (14, 15), (15, 16),  # ring
    (0, 17), (17, 18), (18, 19), (19, 20),  # pinky
    (5, 9), (9, 13), (13, 17),             # palm
]


def draw_hand_landmarks_cv2(frame_bgr, hand_landmarks, joint_radius=4, line_thickness=2):
    """Draw hand landmarks and connections on a BGR frame. hand_landmarks: list of objects with .x, .y (normalized 0-1)."""
    import cv2
    h, w = frame_bgr.shape[:2]
    pts = []
    for lm in hand_landmarks:
        px = int(lm.x * w)
        py = int(lm.y * h)
        pts.append((px, py))
    for (i, j) in HAND_CONNECTIONS:
        if i < len(pts) and j < len(pts):
            cv2.line(frame_bgr, pts[i], pts[j], (0, 255, 0), line_thickness)
    for (px, py) in pts:
        cv2.circle(frame_bgr, (px, py), joint_radius, (0, 0, 255), -1)


def get_model_path(script_dir: str) -> str:
    """Return path to hand_landmarker.task, downloading if needed."""
    path = os.path.join(script_dir, "hand_landmarker.task")
    if os.path.isfile(path):
        return path
    try:
        import urllib.request
        print("Downloading hand_landmarker.task (one-time)...", file=sys.stderr)
        urllib.request.urlretrieve(HAND_LANDMARKER_TASK_URL, path)
        return path
    except Exception as e:
        print(f"Error: Could not download model: {e}", file=sys.stderr)
        print("Download manually from:", HAND_LANDMARKER_TASK_URL, file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Extract hand landmarks per frame from video; write JSON.",
    )
    parser.add_argument(
        "video_path",
        type=str,
        help="Path to input video file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSON path (default: <video_stem>_hand_joints.json next to video)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Sample frames at this FPS (default: use video FPS). Ignored if --output-video is set.",
    )
    parser.add_argument(
        "--max-hands",
        type=int,
        default=2,
        choices=(1, 2),
        help="Max number of hands to detect (default: 2)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="Min detection confidence (default: 0.5)",
    )
    parser.add_argument(
        "--output-video",
        type=str,
        default=None,
        metavar="PATH",
        help="Also write a video with joints drawn on the hands",
    )
    args = parser.parse_args()

    video_path = os.path.abspath(args.video_path)
    if not os.path.isfile(video_path):
        print(f"Error: Video not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import cv2
        import numpy as np
    except ImportError as e:
        print(f"Error: {e}. Install: pip install opencv-python numpy", file=sys.stderr)
        sys.exit(1)

    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision
    except ImportError as e:
        print(f"Error: {e}. Install: pip install mediapipe", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        stem = os.path.splitext(os.path.basename(video_path))[0]
        args.output = os.path.join(os.path.dirname(video_path), f"{stem}_hand_joints.json")
    out_path = os.path.abspath(args.output)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = get_model_path(script_dir)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video: {video_path}", file=sys.stderr)
        sys.exit(1)

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_interval = 1.0
    if args.fps is not None and args.fps > 0 and not args.output_video:
        frame_interval = max(1, int(video_fps / args.fps))

    write_overlay = args.output_video is not None
    if write_overlay:
        out_video_path = os.path.abspath(args.output_video)
        os.makedirs(os.path.dirname(out_video_path) or ".", exist_ok=True)
        frames_dir = tempfile.mkdtemp(prefix="hand_joints_frames_")
    else:
        out_video_path = None
        frames_dir = None

    base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=args.max_hands,
        min_hand_detection_confidence=args.min_confidence,
        min_hand_presence_confidence=0.3,
        min_tracking_confidence=0.3,
    )
    detector = vision.HandLandmarker.create_from_options(options)
    try:
        num_landmarks = 21
        frames_out = []
        frame_idx = -1

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if not write_overlay and args.fps is not None and frame_idx % frame_interval != 0:
                continue

            t_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 if video_fps else frame_idx / max(1, video_fps)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_mp = np.ascontiguousarray(rgb).astype(np.uint8)

            # MediaPipe Image from numpy (RGB)
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_mp)
            except (AttributeError, TypeError):
                from mediapipe.tasks.python.components.containers import ImageFormat, ImageFrame
                mp_image = ImageFrame(image_format=ImageFormat.SRGB, data=rgb_mp)
            detection_result = detector.detect(mp_image)

            hands_list = []
            if detection_result.hand_landmarks:
                for h, hand_lms in enumerate(detection_result.hand_landmarks):
                    if h >= args.max_hands:
                        break
                    landmarks = [
                        {"x": round(lm.x, 6), "y": round(lm.y, 6), "z": round(lm.z, 6)}
                        for lm in hand_lms
                    ]
                    handedness = "Unknown"
                    if detection_result.handedness and h < len(detection_result.handedness):
                        cat = detection_result.handedness[h]
                        if cat and len(cat) > 0:
                            handedness = cat[0].category_name
                    hands_list.append({"handedness": handedness, "landmarks": landmarks})

            if write_overlay and frames_dir is not None:
                annot_frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                if detection_result.hand_landmarks:
                    for hand_landmarks in detection_result.hand_landmarks:
                        draw_hand_landmarks_cv2(annot_frame, hand_landmarks, joint_radius=4, line_thickness=2)
                frame_path = os.path.join(frames_dir, f"frame_{frame_idx:06d}.png")
                cv2.imwrite(frame_path, annot_frame)

            frames_out.append({
                "frame": frame_idx,
                "time_sec": round(t_sec, 4),
                "hands": hands_list,
            })

    finally:
        detector.close()
    cap.release()

    if not frames_out:
        print("Error: No frames read.", file=sys.stderr)
        sys.exit(1)

    if write_overlay and frames_dir is not None:
        input_pattern = os.path.join(frames_dir, "frame_%06d.png")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(video_fps),
            "-i", input_pattern,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            out_video_path,
        ]
        result = subprocess.run(cmd)
        shutil.rmtree(frames_dir, ignore_errors=True)
        if result.returncode != 0:
            print("Error: ffmpeg failed to create overlay video.", file=sys.stderr)
            sys.exit(result.returncode)

    data = {"video_path": video_path, "video_fps": video_fps, "frames": frames_out}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {len(frames_out)} frames to {out_path}")
    if write_overlay:
        print(f"Wrote overlay video to {out_video_path}")


if __name__ == "__main__":
    main()
