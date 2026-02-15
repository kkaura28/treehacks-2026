"""
track_tool_tip_sam3_reg.py — SAM3 re-segmentation every S frames + LK tracking.
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
    detect_tip,
    save_tip_sanity_check,
    save_all_corners_image,
    save_annotated_video,
    track_point_lk,
)


def run_pipeline(
    video_path, output_dir, text_prompt,
    # Frame sampling
    sample_rate=1, start_skip=0, end_skip=0,
    # SAM3
    model_name="facebook/sam3", sam_threshold=0.5,
    # Tip detection
    tip_strategy="farthest_from_centroid",
    max_corners=25, quality_level=0.01, min_distance=10, block_size=3,
    # LK
    lk_win_size=(15, 15), lk_max_level=3,
    lk_criteria_max_count=30, lk_criteria_eps=0.01,
    # Re-segmentation interval
    reseg_interval=50,
    # Crop region (x1, y1, x2, y2) or None for full frame
    crop_region=None,
    # Output filenames
    csv_filename="tracked_tip.csv",
    sanity_check_filename="tip_sanity_check.png",
    all_corners_filename="all_corners.png",
    annotated_video_filename="tracked_tip_video.mp4",
    # Pre-loaded model
    model=None, processor=None, device=None,
):
    os.makedirs(output_dir, exist_ok=True)

    # 1. Read frames
    frames, original_fps = read_video_frames_sampled(
        video_path, sample_rate=sample_rate,
        start_skip=start_skip, end_skip=end_skip,
    )
    effective_fps = original_fps / max(sample_rate, 1)

    # Crop all frames if requested
    if crop_region is not None:
        x1, y1, x2, y2 = crop_region
        frames = [f[y1:y2, x1:x2] for f in frames]
        print(f"[reg] Cropped frames to ({x1},{y1})→({x2},{y2}), "
              f"size {x2-x1}×{y2-y1}")

    n_frames = len(frames)

    # 2. Load SAM3
    if model is None or processor is None or device is None:
        model, processor, device = load_model(model_name)

    # 3. SAM3 on first frame → detect tip
    def sam_detect_tip(frame_bgr):
        pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        results = run_segmentation(model, processor, pil, text_prompt, device, sam_threshold)
        mask, _ = get_top_mask(results)
        tip, corners = detect_tip(
            mask, strategy=tip_strategy, max_corners=max_corners,
            quality_level=quality_level, min_distance=min_distance,
            block_size=block_size,
        )
        return tip, corners, mask

    sanity_dir = os.path.join(output_dir, "sanity_checks")
    os.makedirs(sanity_dir, exist_ok=True)

    def save_sanity(mask, tip, corners, frame_idx):
        base = os.path.splitext(sanity_check_filename)[0]
        save_tip_sanity_check(mask, tip, os.path.join(sanity_dir, f"{base}_f{frame_idx}.png"))
        base_c = os.path.splitext(all_corners_filename)[0]
        save_all_corners_image(mask, corners, tip, os.path.join(sanity_dir, f"{base_c}_f{frame_idx}.png"))

    tip, corners, mask = sam_detect_tip(frames[0])
    save_sanity(mask, tip, corners, 0)

    # 4. Chunk-wise tracking: LK within each chunk, SAM3 resets at chunk boundaries
    lk_kwargs = dict(
        lk_win_size=lk_win_size, lk_max_level=lk_max_level,
        lk_criteria_max_count=lk_criteria_max_count, lk_criteria_eps=lk_criteria_eps,
    )

    S = reseg_interval
    all_positions = []
    chunk_start = 0

    while chunk_start < n_frames:
        chunk_end = min(chunk_start + S, n_frames)
        chunk_frames = frames[chunk_start:chunk_end]

        init_pt = np.array([[float(tip[0]), float(tip[1])]], dtype=np.float32)
        chunk_positions = track_point_lk(chunk_frames, init_pt, **lk_kwargs)

        # Remap frame indices to global
        for fi, x, y in chunk_positions:
            all_positions.append((chunk_start + fi, x, y))

        print(f"[reg] Chunk frames {chunk_start}–{chunk_end - 1} done "
              f"({len(chunk_positions)} pts)")

        # Re-segment at the next chunk boundary
        chunk_start = chunk_end
        if chunk_start < n_frames:
            try:
                tip, corners, mask = sam_detect_tip(frames[chunk_start])
                save_sanity(mask, tip, corners, chunk_start)
                print(f"[reg] SAM3 re-seg at frame {chunk_start} → "
                      f"tip=({tip[0]:.1f}, {tip[1]:.1f})")
            except Exception as e:
                # SAM3 failed — keep the last known tip and let LK continue
                print(f"[reg] SAM3 failed at frame {chunk_start}: {e} — "
                      f"continuing with LK from last tip")

    # 5. Save outputs
    csv_path = os.path.join(output_dir, csv_filename)
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame_idx", "x", "y"])
        w.writerows(all_positions)
    print(f"[reg] Saved CSV → {csv_path}")

    save_annotated_video(frames, all_positions,
                         os.path.join(output_dir, annotated_video_filename),
                         effective_fps)

    print(f"[reg] ✓ Done — {len(all_positions)} positions, outputs in {output_dir}")
    return all_positions, model, processor, device


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    run_pipeline(
        video_path=os.path.join(ROOT, "analysis/data/sam3/banana_surgery.mp4"),
        output_dir=os.path.join(ROOT, "analysis/outputs/track_tool_tip_sam3_reg"),
        text_prompt="blade",
        # Frame sampling
        sample_rate=1,
        start_skip=120,
        end_skip=480,
        # SAM3
        model_name="facebook/sam3",
        sam_threshold=0.5,
        # Tip detection
        tip_strategy="leftmost",
        max_corners=25,
        quality_level=0.01,
        min_distance=10.0,
        block_size=3,
        # LK
        lk_win_size=(20, 10),
        lk_max_level=3,
        lk_criteria_max_count=30,
        lk_criteria_eps=0.01,
        # Re-segmentation
        reseg_interval=2,              # SAM3 re-detects tip every S frames
        # Crop region (x1, y1, x2, y2) or None for full frame
        crop_region=(0, 300, 463, 610),
        # Output
        csv_filename="tracked_tip.csv",
        sanity_check_filename="tip_sanity_check.png",
        all_corners_filename="all_corners.png",
        annotated_video_filename="tracked_tip_video.mp4",
    )
