"""
track_tool_final.py — Multi-point SAM3 re-seg + LK tracking with mask selection.
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
    detect_corners_shi_tomasi,
    track_point_lk,
    _draw_tracking_marker,
)

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
    n = min(num_points, len(corners))
    if strategy == "leftmost":
        idxs = np.argsort(corners[:, 0])[:n]
    elif strategy == "rightmost":
        idxs = np.argsort(corners[:, 0])[-n:][::-1]
    elif strategy == "best_quality":
        idxs = np.arange(n)
    elif strategy == "farthest_from_centroid":
        ys, xs = np.where(mask > 0)
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        dists = np.sqrt((corners[:, 0] - cx) ** 2 + (corners[:, 1] - cy) ** 2)
        idxs = np.argsort(dists)[-n:][::-1]
    else:
        idxs = np.arange(n)
    return corners[idxs]


def any_tip_in_region(tips, region):
    """Check if at least one tip falls inside (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = region
    for tx, ty in tips:
        if x1 <= tx <= x2 and y1 <= ty <= y2:
            return True
    return False


def choose_mask_from_results(results, tip_strategy, num_points, mask_region,
                             max_corners, quality_level, min_distance, block_size):
    """Iterate masks from highest to lowest score. Return the first whose
    tips have at least one point inside mask_region. Returns None if none qualify."""
    masks = results["masks"]
    scores = results["scores"].cpu().numpy()
    if len(masks) == 0:
        return None

    sorted_idxs = np.argsort(scores)[::-1]
    for idx in sorted_idxs:
        m = masks[int(idx)].cpu().numpy()
        binary = (m * 255).astype(np.uint8)
        try:
            corners = detect_corners_shi_tomasi(
                binary, max_corners=max_corners, quality_level=quality_level,
                min_distance=min_distance, block_size=block_size,
            )
        except RuntimeError:
            continue
        tips = select_tips(binary, corners, tip_strategy, num_points)
        if any_tip_in_region(tips, mask_region):
            print(f"[final] Chose mask idx={idx} score={scores[idx]:.4f} "
                  f"(tips in region)")
            return binary, tips, corners
    return None


def save_multi_annotated_video(frames, all_positions, output_path, fps, num_points):
    if not frames:
        return
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
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
    print(f"[final] Saved annotated video → {output_path}")


def run_pipeline(
    video_path, output_dir, text_prompt,
    sample_rate=1, start_skip=0, end_skip=0,
    model_name="facebook/sam3", sam_threshold=0.5,
    tip_strategy="farthest_from_centroid",
    max_corners=25, quality_level=0.01, min_distance=10, block_size=3,
    lk_win_size=(15, 15), lk_max_level=3,
    lk_criteria_max_count=30, lk_criteria_eps=0.01,
    reseg_interval=50,
    crop_region=None,
    num_points=1,
    choose_mask=False,
    mask_region=None,
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
        print(f"[final] Cropped to ({x1},{y1})→({x2},{y2})")
    n_frames = len(frames)

    # 2. Load SAM3
    if model is None or processor is None or device is None:
        model, processor, device = load_model(model_name)

    corner_kwargs = dict(max_corners=max_corners, quality_level=quality_level,
                         min_distance=min_distance, block_size=block_size)

    # 3. Detect tips — with or without mask selection
    def sam_detect_tips(frame_bgr):
        """Returns (tips, mask) or None if choose_mask is on and nothing qualifies."""
        pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        results = run_segmentation(model, processor, pil, text_prompt, device, sam_threshold)

        if choose_mask and mask_region is not None:
            result = choose_mask_from_results(
                results, tip_strategy, num_points, mask_region, **corner_kwargs)
            if result is None:
                return None
            mask, tips, corners = result
            return tips, mask

        # Default: top-scoring mask
        masks = results["masks"]
        scores = results["scores"].cpu().numpy()
        if len(masks) == 0:
            return None
        best_idx = int(np.argmax(scores))
        mask = (masks[best_idx].cpu().numpy() * 255).astype(np.uint8)
        corners = detect_corners_shi_tomasi(mask, **corner_kwargs)
        tips = select_tips(mask, corners, tip_strategy, num_points)
        return tips, mask

    result = sam_detect_tips(frames[0])
    tips, mask = result
    N = len(tips)

    # 4. Chunk-wise tracking
    lk_kwargs = dict(
        lk_win_size=lk_win_size, lk_max_level=lk_max_level,
        lk_criteria_max_count=lk_criteria_max_count, lk_criteria_eps=lk_criteria_eps,
    )
    S = reseg_interval
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

        print(f"[final] Chunk {chunk_start}–{chunk_end - 1} done ({N} points)")

        # Update tips from last LK positions (fallback if SAM fails)
        for p in range(N):
            last = all_positions[p][-1]
            tips[p] = np.array([last[1], last[2]])

        chunk_start = chunk_end
        if chunk_start < n_frames:
            try:
                result = sam_detect_tips(frames[chunk_start])
                if result is not None:
                    tips, mask = result
                    print(f"[final] SAM3 re-seg at frame {chunk_start}")
                else:
                    print(f"[final] No qualifying mask at frame {chunk_start}, continuing LK")
            except Exception:
                print(f"[final] SAM3 failed at frame {chunk_start}, continuing LK")

    # 5. Save CSV (wide format)
    csv_path = os.path.join(output_dir, csv_filename)
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
    print(f"[final] Saved CSV → {csv_path}")

    # 6. Annotated video
    if save_video:
        save_multi_annotated_video(
            frames, all_positions,
            os.path.join(output_dir, annotated_video_filename),
            effective_fps, N,
        )

    print(f"[final] ✓ Done — {N} points, {n_frames} frames")
    return all_positions, model, processor, device


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    run_pipeline(
        video_path=os.path.join(ROOT, "analysis/data/sam3/surgery_video.mp4"),
        output_dir=os.path.join(ROOT, "analysis/outputs/track_tool_final"),
        text_prompt="blade",
        sample_rate=1,
        start_skip=265,
        end_skip=723,
        model_name="facebook/sam3",
        sam_threshold=0.5,
        tip_strategy="leftmost",
        max_corners=25,
        quality_level=0.01,
        min_distance=10.0,
        block_size=3,
        lk_win_size=(20, 10),
        lk_max_level=3,
        lk_criteria_max_count=30,
        lk_criteria_eps=0.01,
        reseg_interval=2,
        crop_region=None,
        num_points=1,
        # Mask selection
        choose_mask=True,
        mask_region=(500, 270, 1000, 810),              # e.g. (500, 300, 900, 600)
        save_video=False,
        csv_filename="tracked_tips_blade.csv",
        annotated_video_filename="tracked_tips_video_blade.mp4",
    )
