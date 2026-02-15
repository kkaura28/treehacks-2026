"""
annotate_video.py — Overlay tracked points from multiple CSVs onto a video.
"""

import os, sys, csv
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import cv2
import numpy as np
from analysis.src.track_tool_tip_sam3 import (
    read_video_frames_sampled,
    _draw_tracking_marker,
)

# One color per CSV file (BGR)
CSV_COLORS = [
    (0, 0, 255),    # red
    (255, 0, 0),    # blue
    (0, 180, 0),    # green
    (255, 0, 255),  # magenta
    (0, 165, 255),  # orange
    (128, 0, 128),  # purple
    (0, 255, 255),  # yellow
    (255, 255, 0),  # cyan
]


def read_csv_positions(csv_path):
    """Read a wide-format CSV → list of per-point dicts {frame_idx: (x, y)}."""
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
    # Number of points = (len(header) - 1) / 2
    num_points = (len(header) - 1) // 2
    pos_maps = [{} for _ in range(num_points)]
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            fi = int(row[0])
            for p in range(num_points):
                x_val, y_val = row[1 + 2 * p], row[2 + 2 * p]
                if x_val and y_val:
                    pos_maps[p][fi] = (float(x_val), float(y_val))
    return pos_maps


def annotate_video(
    video_path, csv_paths, output_path,
    sample_rate=1, start_skip=0, end_skip=0,
    crop_region=None,
):
    frames, original_fps = read_video_frames_sampled(
        video_path, sample_rate=sample_rate,
        start_skip=start_skip, end_skip=end_skip,
    )
    effective_fps = original_fps / max(sample_rate, 1)

    if crop_region is not None:
        x1, y1, x2, y2 = crop_region
        frames = [f[y1:y2, x1:x2] for f in frames]

    # Load all CSVs: list of (color, [pos_map_per_point])
    csv_data = []
    for ci, csv_path in enumerate(csv_paths):
        color = CSV_COLORS[ci % len(CSV_COLORS)]
        pos_maps = read_csv_positions(csv_path)
        csv_data.append((color, pos_maps))

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    writer = cv2.VideoWriter(output_path, fourcc, effective_fps, (w, h))

    for i, frame in enumerate(frames):
        ann = frame.copy()
        for color, pos_maps in csv_data:
            for pm in pos_maps:
                if i in pm:
                    x, y = pm[i]
                    _draw_tracking_marker(
                        ann, (int(round(x)), int(round(y))),
                        inner_radius=3, outer_radius=10, crosshair_length=14,
                        thickness=1, inner_color=color,
                    )
        writer.write(ann)

    writer.release()
    print(f"[annotate] Saved → {output_path} ({len(frames)} frames)")


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    OUT = os.path.join(ROOT, "analysis/outputs/track_tool_tips_sam3_reg")

    annotate_video(
        video_path=os.path.join(ROOT, "analysis/data/sam3/banana_surgery.mp4"),
        csv_paths=[
            os.path.join(OUT, "tracked_tips_blade.csv"),
            os.path.join(OUT, "tracked_tips_tweezer.csv"),
        ],
        output_path=os.path.join(OUT, "annotated_all.mp4"),
        sample_rate=1,
        start_skip=120,
        end_skip=480,
        crop_region=(0, 200, 463, 610),
    )
