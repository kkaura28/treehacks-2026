"""
track_tool_tips_sam3_reg.py — Multi-point SAM3 re-seg + LK tracking.
"""

import os, sys, csv
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import cv2
import numpy as np
from PIL import Image
from analysis.src.sam3 import load_model, run_segmentation
from analysis.src.track_tool_tip_sam3 import (
    read_video_frames_sampled,
    get_top_mask,
    detect_corners_shi_tomasi,
    save_annotated_video,
    track_point_lk,
    _draw_tracking_marker,
)

# Colors for multiple points (BGR)
POINT_COLORS = [
    (0, 0, 255),    # red
    (0, 0, 255),    # red
    (255, 0, 0),    # blue
    (0, 180, 0),    # green
    (255, 0, 255),  # magenta
    (0, 165, 255),  # orange
    (128, 0, 128),  # purple
    (0, 255, 255),  # yellow
    (255, 255, 0),  # cyan
]


def select_tips(mask, corners, strategy, num_points):
    """Select num_points tips from corners using the given strategy."""
    n = min(num_points, len(corners))
    if strategy == "leftmost":
        idxs = np.argsort(corners[:, 0])[:n]
    elif strategy == "rightmost":
        idxs = np.argsort(corners[:, 0])[-n:][::-1]
    elif strategy == "best_quality":
        idxs = np.arange(n)  # already sorted by quality
    elif strategy == "farthest_from_centroid":
        ys, xs = np.where(mask > 0)
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        dists = np.sqrt((corners[:, 0] - cx) ** 2 + (corners[:, 1] - cy) ** 2)
        idxs = np.argsort(dists)[-n:][::-1]
    else:
        idxs = np.arange(n)
    return corners[idxs]


def save_multi_annotated_video(frames, all_positions, output_path, fps, num_points):
    """Render video with markers for each tracked point in different colors."""
    if not frames:
        return
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    # all_positions[p] = list of (frame_idx, x, y) for point p
    pos_maps = []
    for p in range(num_points):
        pos_maps.append({int(fi): (x, y) for fi, x, y in all_positions[p]})

    for i, frame in enumerate(frames):
        ann = frame.copy()
        for p in range(num_points):
            if i in pos_maps[p]:
                x, y = pos_maps[p][i]
                color = POINT_COLORS[p % len(POINT_COLORS)]
                _draw_tracking_marker(ann, (int(round(x)), int(round(y))),
                                      inner_radius=3, outer_radius=10, crosshair_length=14,
                                      thickness=1, inner_color=color)
        writer.write(ann)
    writer.release()
    print(f"[reg-multi] Saved annotated video → {output_path}")


def run_pipeline(
    video_path, output_dir, text_prompt,
    sample_rate=1, start_skip=0, end_skip=0,
    model_name="facebook/sam3", sam_threshold=0.5, mask_rank=0,
    tip_strategy="farthest_from_centroid",
    max_corners=25, quality_level=0.01, min_distance=10, block_size=3,
    lk_win_size=(15, 15), lk_max_level=3,
    lk_criteria_max_count=30, lk_criteria_eps=0.01,
    reseg_interval=50,
    crop_region=None,
    num_points=1,
    save_video=True,
    csv_filename="tracked_tips.csv",
    annotated_video_filename="tracked_tips_video.mp4",
    model=None, processor=None, device=None,
):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Read & crop frames
    frames, original_fps = read_video_frames_sampled(
        video_path, sample_rate=sample_rate,
        start_skip=start_skip, end_skip=end_skip,
    )
    effective_fps = original_fps / max(sample_rate, 1)
    if crop_region is not None:
        x1, y1, x2, y2 = crop_region
        frames = [f[y1:y2, x1:x2] for f in frames]
        print(f"[reg-multi] Cropped to ({x1},{y1})→({x2},{y2})")
    n_frames = len(frames)

    # 2. Load SAM3
    if model is None or processor is None or device is None:
        model, processor, device = load_model(model_name)

    # 3. Detect multiple tips from a frame
    def sam_detect_tips(frame_bgr):
        pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        results = run_segmentation(model, processor, pil, text_prompt, device, sam_threshold)
        mask, _ = get_top_mask(results, rank=mask_rank)
        corners = detect_corners_shi_tomasi(
            mask, max_corners=max_corners, quality_level=quality_level,
            min_distance=min_distance, block_size=block_size,
        )
        tips = select_tips(mask, corners, tip_strategy, num_points)
        return tips, corners, mask

    tips, corners, mask = sam_detect_tips(frames[0])
    N = len(tips)  # actual number (may be < num_points if few corners)

    # 4. Chunk-wise tracking for all points
    lk_kwargs = dict(
        lk_win_size=lk_win_size, lk_max_level=lk_max_level,
        lk_criteria_max_count=lk_criteria_max_count, lk_criteria_eps=lk_criteria_eps,
    )
    S = reseg_interval
    # all_positions[p] = list of (global_frame_idx, x, y)
    all_positions = [[] for _ in range(N)]
    chunk_start = 0

    while chunk_start < n_frames:
        chunk_end = min(chunk_start + S, n_frames)
        chunk_frames = frames[chunk_start:chunk_end]

        for p in range(N):
            init_pt = np.array([[float(tips[p][0]), float(tips[p][1])]], dtype=np.float32)
            chunk_pos = track_point_lk(chunk_frames, init_pt, **lk_kwargs)
            for fi, x, y in chunk_pos:
                all_positions[p].append((chunk_start + fi, x, y))

        print(f"[reg-multi] Chunk {chunk_start}–{chunk_end - 1} done ({N} points)")

        chunk_start = chunk_end
        if chunk_start < n_frames:
            try:
                tips, corners, mask = sam_detect_tips(frames[chunk_start])
                print(f"[reg-multi] SAM3 re-seg at frame {chunk_start}")
            except Exception:
                # Keep last tips, LK continues
                print(f"[reg-multi] SAM3 failed at frame {chunk_start}, continuing LK")

    # 5. Save CSV (wide format)
    csv_path = os.path.join(output_dir, csv_filename)
    # Build frame→positions lookup
    frame_data = {}
    for p in range(N):
        for fi, x, y in all_positions[p]:
            if fi not in frame_data:
                frame_data[fi] = {}
            frame_data[fi][p] = (x, y)

    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        header = ["frame_idx"]
        for p in range(N):
            header += [f"x{p}", f"y{p}"]
        w.writerow(header)
        for fi in sorted(frame_data.keys()):
            row = [fi]
            for p in range(N):
                if p in frame_data[fi]:
                    row += [frame_data[fi][p][0], frame_data[fi][p][1]]
                else:
                    row += ["", ""]
            w.writerow(row)
    print(f"[reg-multi] Saved CSV → {csv_path}")

    # 6. Annotated video
    if save_video:
        save_multi_annotated_video(
            frames, all_positions,
            os.path.join(output_dir, annotated_video_filename),
            effective_fps, N,
        )

    print(f"[reg-multi] ✓ Done — {N} points, {n_frames} frames")
    return all_positions, model, processor, device


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    run_pipeline(
        video_path=os.path.join(ROOT, "analysis/data/sam3/surgery_video.mp4"),
        output_dir=os.path.join(ROOT, "analysis/outputs/track_tool_tips_sam3_reg"),
        text_prompt="blade",
        sample_rate=1,
        start_skip=265, # 265+241 # 120,
        end_skip=723, # 723,482 # 480,
        model_name="facebook/sam3",
        sam_threshold=0.5,
        mask_rank=1,
        tip_strategy="leftmost",
        max_corners=25,
        quality_level=0.01,
        min_distance=10.0,
        block_size=3,
        lk_win_size=(20, 10),
        lk_max_level=3,
        lk_criteria_max_count=30,
        lk_criteria_eps=0.01,
        reseg_interval=5,
        crop_region=None, # (0, 200, 463, 610),
        num_points=1,
        save_video=False,
        csv_filename="tracked_tips_blade.csv",
        annotated_video_filename="tracked_tips_video_blade.mp4",
    )
