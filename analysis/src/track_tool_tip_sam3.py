"""
track_tool_tip_sam3.py — SAM3-based tool-tip detection + Lucas-Kanade tracking.

Pipeline:
    1. Extract the first frame from an input video.
    2. Run SAM 3 text-prompted segmentation on that frame → pick the
       top-scoring binary mask.
    3. Detect the tool tip on the mask (Shi-Tomasi corner detection +
       a pluggable selection strategy).
    4. Save a sanity-check image (mask + red dot at the detected tip).
    5. Track the detected tip through every frame of the video using
       pyramidal Lucas-Kanade optical flow.
    6. Save the trajectory to a CSV.

Usage:
    1. Edit the hyperparameters in the ``if __name__ == "__main__"`` block.
    2. Run:  python analysis/src/track_tool_tip_sam3.py
"""

import os
import sys

# Allow direct execution: python analysis/src/track_tool_tip_sam3.py ...
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import cv2
import numpy as np
from PIL import Image

from analysis.src.sam3 import load_model, run_segmentation
from analysis.src.track_tool_tip import (
    init_tracking_point,
    save_to_csv,
)


# ══════════════════════════════════════════════════════════════════════
# 1.  Video → frames (with start/end skip & sampling)
# ══════════════════════════════════════════════════════════════════════

def read_video_frames_sampled(video_path, sample_rate=1,
                              start_skip=0, end_skip=0):
    """Read video frames, optionally skipping start/end and sub-sampling.

    Parameters
    ----------
    video_path : str
        Path to the video file.
    sample_rate : int
        Keep every *sample_rate*-th frame (1 = keep all).
    start_skip : int
        Number of frames to skip at the beginning.
    end_skip : int
        Number of frames to skip at the end.

    Returns
    -------
    frames : list of np.ndarray
        Selected BGR frames.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[tip-sam3] Video: {total} frames, {fps:.1f} fps")

    # Read all frames first
    all_frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        all_frames.append(frame)
    cap.release()

    # Apply start/end skip
    end_idx = len(all_frames) - end_skip
    trimmed = all_frames[start_skip:end_idx]

    # Sub-sample
    frames = trimmed[::sample_rate]

    print(f"[tip-sam3] Loaded {len(all_frames)} total frames → "
          f"skip_start={start_skip}, skip_end={end_skip}, "
          f"sample_rate={sample_rate} → {len(frames)} frames kept")
    return frames, fps


# ══════════════════════════════════════════════════════════════════════
# 2.  SAM 3 segmentation → best binary mask
# ══════════════════════════════════════════════════════════════════════

def get_top_mask(results, rank=0):
    """Select the mask with the highest (or Nth-highest) confidence score.

    Parameters
    ----------
    results : dict
        Output of ``run_segmentation`` (keys ``'masks'``, ``'scores'``).
    rank : int
        0 = top score, 1 = second-highest, etc.

    Returns
    -------
    binary_mask : np.ndarray, dtype uint8
        Binary mask — 255 for the object, 0 for background.
    best_score : float
        The confidence score of the selected mask.
    """
    masks = results["masks"]
    scores = results["scores"].cpu().numpy()

    if len(masks) == 0:
        raise RuntimeError("SAM3 returned no masks.")

    sorted_idxs = np.argsort(scores)[::-1]  # descending
    best_idx = int(sorted_idxs[min(rank, len(sorted_idxs) - 1)])
    best_mask = masks[best_idx].cpu().numpy()
    best_score = float(scores[best_idx])

    binary_mask = (best_mask * 255).astype(np.uint8)
    print(f"[tip-sam3] Selected mask {best_idx} with score {best_score:.4f}")
    return binary_mask, best_score


# ══════════════════════════════════════════════════════════════════════
# 3.  Tip detection  (modular: detection + strategy)
# ══════════════════════════════════════════════════════════════════════

# ── 3a. Corner detection ─────────────────────────────────────────────

def detect_corners_shi_tomasi(mask, max_corners=25, quality_level=0.01,
                              min_distance=10, block_size=3):
    """Detect corners on a binary mask via Shi-Tomasi (goodFeaturesToTrack).

    Parameters
    ----------
    mask : np.ndarray, dtype uint8
        Binary mask (0 / 255).
    max_corners : int
    quality_level : float
    min_distance : float
    block_size : int

    Returns
    -------
    corners : np.ndarray, shape (N, 2)
        Detected corner coordinates as ``(x, y)`` pairs, sorted by
        descending quality (OpenCV default).
    """
    corners = cv2.goodFeaturesToTrack(
        mask,
        maxCorners=max_corners,
        qualityLevel=quality_level,
        minDistance=min_distance,
        blockSize=block_size,
    )
    if corners is None or len(corners) == 0:
        raise RuntimeError("Shi-Tomasi detected no corners on the mask.")

    corners = corners.reshape(-1, 2)  # (N, 2) — each row is (x, y)
    print(f"[tip-sam3] Shi-Tomasi detected {len(corners)} corner(s)")
    return corners


# ── 3b. Tip-selection strategies ─────────────────────────────────────

def select_tip_farthest_from_centroid(mask, corners):
    """Pick the corner farthest from the mask centroid.

    Rationale: the tip of an elongated tool is usually at an extremity.

    Parameters
    ----------
    mask : np.ndarray
        Binary mask (used to compute the centroid).
    corners : np.ndarray, shape (N, 2)

    Returns
    -------
    tip : np.ndarray, shape (2,)
        ``(x, y)`` of the selected tip.
    """
    ys, xs = np.where(mask > 0)
    centroid_x, centroid_y = float(np.mean(xs)), float(np.mean(ys))

    dists = np.sqrt((corners[:, 0] - centroid_x) ** 2 +
                    (corners[:, 1] - centroid_y) ** 2)
    best_idx = int(np.argmax(dists))
    tip = corners[best_idx]

    print(f"[tip-sam3] Mask centroid: ({centroid_x:.1f}, {centroid_y:.1f})")
    print(f"[tip-sam3] Selected tip (farthest): ({tip[0]:.1f}, {tip[1]:.1f})  "
          f"dist={dists[best_idx]:.1f}")
    return tip


def select_tip_best_quality(mask, corners):
    """Pick the highest-quality corner (first in the Shi-Tomasi output).

    Parameters
    ----------
    mask : np.ndarray  (unused, kept for API consistency)
    corners : np.ndarray, shape (N, 2)

    Returns
    -------
    tip : np.ndarray, shape (2,)
    """
    tip = corners[0]
    print(f"[tip-sam3] Selected tip (best quality): ({tip[0]:.1f}, {tip[1]:.1f})")
    return tip


def select_tip_leftmost(mask, corners):
    """Pick the corner with the smallest x coordinate (left-most).

    Parameters
    ----------
    mask : np.ndarray  (unused, kept for API consistency)
    corners : np.ndarray, shape (N, 2)

    Returns
    -------
    tip : np.ndarray, shape (2,)
    """
    best_idx = int(np.argmin(corners[:, 0]))
    tip = corners[best_idx]
    print(f"[tip-sam3] Selected tip (leftmost): ({tip[0]:.1f}, {tip[1]:.1f})")
    return tip


def select_tip_rightmost(mask, corners):
    """Pick the corner with the largest x coordinate (right-most).

    Parameters
    ----------
    mask : np.ndarray  (unused, kept for API consistency)
    corners : np.ndarray, shape (N, 2)

    Returns
    -------
    tip : np.ndarray, shape (2,)
    """
    best_idx = int(np.argmax(corners[:, 0]))
    tip = corners[best_idx]
    print(f"[tip-sam3] Selected tip (rightmost): ({tip[0]:.1f}, {tip[1]:.1f})")
    return tip


# Registry — add new strategies here
TIP_SELECTION_STRATEGIES = {
    "farthest_from_centroid": select_tip_farthest_from_centroid,
    "best_quality": select_tip_best_quality,
    "leftmost": select_tip_leftmost,
    "rightmost": select_tip_rightmost,
}


def detect_tip(mask, strategy="farthest_from_centroid",
               max_corners=25, quality_level=0.01,
               min_distance=10, block_size=3):
    """Detect the tool tip on a binary mask.

    Combines Shi-Tomasi corner detection with a pluggable selection
    strategy.

    Parameters
    ----------
    mask : np.ndarray, dtype uint8
        Binary mask (0 / 255).
    strategy : str
        Key into ``TIP_SELECTION_STRATEGIES``.
    max_corners, quality_level, min_distance, block_size
        Shi-Tomasi hyperparameters.

    Returns
    -------
    tip : np.ndarray, shape (2,)
        ``(x, y)`` pixel coordinate of the detected tip.
    corners : np.ndarray, shape (N, 2)
        All detected corners (useful for debugging / visualization).
    """
    if strategy not in TIP_SELECTION_STRATEGIES:
        raise ValueError(
            f"Unknown strategy '{strategy}'. "
            f"Available: {list(TIP_SELECTION_STRATEGIES.keys())}"
        )

    corners = detect_corners_shi_tomasi(
        mask,
        max_corners=max_corners,
        quality_level=quality_level,
        min_distance=min_distance,
        block_size=block_size,
    )

    select_fn = TIP_SELECTION_STRATEGIES[strategy]
    tip = select_fn(mask, corners)

    return tip, corners


# ══════════════════════════════════════════════════════════════════════
# 4.  Sanity-check image
# ══════════════════════════════════════════════════════════════════════

def save_tip_sanity_check(mask, tip, output_path,
                          dot_radius=8, dot_color=(0, 0, 255)):
    """Save the binary mask with a red dot annotated at the detected tip.

    Parameters
    ----------
    mask : np.ndarray, dtype uint8
        Binary mask (0 / 255).
    tip : array-like, shape (2,)
        ``(x, y)`` pixel coordinate.
    output_path : str
        Where to write the PNG.
    dot_radius : int
        Radius of the annotation dot.
    dot_color : tuple of int
        BGR color of the dot (default red).
    """
    vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    center = (int(round(tip[0])), int(round(tip[1])))
    cv2.circle(vis, center, dot_radius, dot_color, -1)
    cv2.circle(vis, center, dot_radius + 2, (255, 255, 255), 2)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cv2.imwrite(output_path, vis)
    print(f"[tip-sam3] Saved sanity-check image → {output_path}")


# ══════════════════════════════════════════════════════════════════════
# 4b. All-corners visualization
# ══════════════════════════════════════════════════════════════════════

def save_all_corners_image(mask, corners, tip, output_path,
                           corner_radius=5, corner_color=(255, 0, 0),
                           tip_radius=8, tip_color=(0, 0, 255)):
    """Save the mask with ALL detected corners drawn, highlighting the selected tip.

    Corners are drawn as blue circles; the chosen tip is drawn larger in red
    with a white outline so it stands out.

    Parameters
    ----------
    mask : np.ndarray, dtype uint8
        Binary mask (0 / 255).
    corners : np.ndarray, shape (N, 2)
        All detected corner coordinates as ``(x, y)``.
    tip : array-like, shape (2,)
        The selected tip ``(x, y)``.
    output_path : str
        Where to write the PNG.
    corner_radius : int
        Radius for non-tip corner dots.
    corner_color : tuple of int
        BGR color for non-tip corners (default blue).
    tip_radius : int
        Radius for the selected tip dot.
    tip_color : tuple of int
        BGR color for the selected tip (default red).
    """
    vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    # Draw all corners first (blue)
    for cx, cy in corners:
        center = (int(round(cx)), int(round(cy)))
        cv2.circle(vis, center, corner_radius, corner_color, -1)

    # Draw the selected tip on top (red + white outline)
    tip_center = (int(round(tip[0])), int(round(tip[1])))
    cv2.circle(vis, tip_center, tip_radius, tip_color, -1)
    cv2.circle(vis, tip_center, tip_radius + 2, (255, 255, 255), 2)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cv2.imwrite(output_path, vis)
    print(f"[tip-sam3] Saved all-corners image ({len(corners)} corners) → {output_path}")


# ══════════════════════════════════════════════════════════════════════
# 4c. Annotated tracking video
# ══════════════════════════════════════════════════════════════════════

def _draw_tracking_marker(image, center, inner_radius=6, outer_radius=18,
                          inner_color=(0, 0, 255), outer_color=(0, 255, 255),
                          crosshair_length=28, crosshair_color=(0, 255, 255),
                          thickness=2):
    """Draw a highly visible tracking marker: yellow ring + red dot + crosshair.

    Parameters
    ----------
    image : np.ndarray
        BGR image to draw on (modified in-place).
    center : tuple of int
        ``(x, y)`` pixel coordinate.
    inner_radius : int
        Radius of the filled inner dot.
    outer_radius : int
        Radius of the outer ring.
    inner_color : tuple of int
        BGR color of the inner dot (default red).
    outer_color : tuple of int
        BGR color of the outer ring and crosshair (default yellow).
    crosshair_length : int
        Half-length of the crosshair arms.
    crosshair_color : tuple of int
        BGR color of the crosshair lines.
    thickness : int
        Line thickness for ring and crosshair.
    """
    cx, cy = center
    # Crosshair lines
    cv2.line(image, (cx - crosshair_length, cy), (cx + crosshair_length, cy),
             crosshair_color, thickness)
    cv2.line(image, (cx, cy - crosshair_length), (cx, cy + crosshair_length),
             crosshair_color, thickness)
    # Outer ring
    cv2.circle(image, center, outer_radius, outer_color, thickness)
    # Inner filled dot
    cv2.circle(image, center, inner_radius, inner_color, -1)


def save_annotated_video(frames, tracked_positions, output_path, fps,
                         inner_radius=6, outer_radius=18,
                         inner_color=(0, 0, 255), outer_color=(0, 255, 255),
                         crosshair_length=28, codec="mp4v"):
    """Re-render the video frames with a visible tracking marker overlaid.

    The marker consists of a yellow outer ring, red inner dot, and a
    yellow crosshair — designed to be clearly visible on surgical footage.

    Parameters
    ----------
    frames : list of np.ndarray
        BGR video frames (same list used for tracking).
    tracked_positions : list of (frame_idx, x, y)
        Output of ``track_point_lk``.
    output_path : str
        Where to write the output video (e.g. ``".mp4"``).
    fps : float
        Frames per second for the output video.
    inner_radius : int
        Radius of the filled inner dot.
    outer_radius : int
        Radius of the outer ring.
    inner_color : tuple of int
        BGR color of the inner dot (default red).
    outer_color : tuple of int
        BGR color of the outer ring / crosshair (default yellow).
    crosshair_length : int
        Half-length of the crosshair arms.
    codec : str
        FourCC codec string (default ``"mp4v"``).
    """
    if len(frames) == 0:
        print("[tip-sam3] No frames to write.")
        return

    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*codec)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    # Build a quick lookup: frame_idx → (x, y)
    pos_map = {int(fi): (x, y) for fi, x, y in tracked_positions}

    for i, frame in enumerate(frames):
        annotated = frame.copy()
        if i in pos_map:
            x, y = pos_map[i]
            center = (int(round(x)), int(round(y)))
            _draw_tracking_marker(
                annotated, center,
                inner_radius=inner_radius,
                outer_radius=outer_radius,
                inner_color=inner_color,
                outer_color=outer_color,
                crosshair_length=crosshair_length,
            )
        writer.write(annotated)

    writer.release()
    print(f"[tip-sam3] Saved annotated video ({len(frames)} frames, "
          f"{fps:.1f} fps) → {output_path}")


# ══════════════════════════════════════════════════════════════════════
# 5.  LK tracking (with exposed hyperparameters)
# ══════════════════════════════════════════════════════════════════════

def track_point_lk(frames, init_pt,
                   lk_win_size=(15, 15), lk_max_level=3,
                   lk_criteria_max_count=30, lk_criteria_eps=0.01):
    """Track a single point across video frames using pyramidal LK.

    This is a re-implementation of
    ``analysis.src.track_tool_tip.track_point_lk`` with all Lucas-Kanade
    hyperparameters exposed as arguments.

    Parameters
    ----------
    frames : list of np.ndarray
        BGR video frames.
    init_pt : np.ndarray, shape (1, 2)
        Starting point as ``[[x, y]]`` float32.
    lk_win_size : tuple of int
        Search window size for each pyramid level.
    lk_max_level : int
        Maximum number of pyramid levels.
    lk_criteria_max_count : int
        Termination criteria — max iterations.
    lk_criteria_eps : float
        Termination criteria — epsilon.

    Returns
    -------
    tracked_positions : list of (frame_idx, x, y)
    """
    lk_params = dict(
        winSize=lk_win_size,
        maxLevel=lk_max_level,
        criteria=(
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            lk_criteria_max_count,
            lk_criteria_eps,
        ),
    )

    prev_pts = init_pt.copy()
    prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)

    tracked_positions = [(0, float(prev_pts[0][0]), float(prev_pts[0][1]))]

    n_frames = len(frames)
    for i in range(1, n_frames):
        frame_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)

        next_pts, status, _err = cv2.calcOpticalFlowPyrLK(
            prev_gray, frame_gray, prev_pts, None, **lk_params
        )

        if status[0][0] == 0:
            # Lost track — keep previous position
            next_pts = prev_pts.copy()

        x, y = next_pts[0]
        tracked_positions.append((i, float(x), float(y)))

        prev_gray = frame_gray.copy()
        prev_pts = next_pts.copy()

        if i % 100 == 0:
            print(f"  [tip-sam3] Tracked {i}/{n_frames} frames ...")

    print(f"[tip-sam3] Tracking complete — {len(tracked_positions)} positions")
    return tracked_positions


# ══════════════════════════════════════════════════════════════════════
# 6.  Main pipeline orchestrator
# ══════════════════════════════════════════════════════════════════════

def run_pipeline(
    video_path,
    output_dir,
    text_prompt,
    # Frame sampling hyperparams
    sample_rate=1,
    start_skip=0,
    end_skip=0,
    # SAM3 hyperparams
    model_name="facebook/sam3",
    sam_threshold=0.5,
    # Tip-detection hyperparams
    tip_strategy="farthest_from_centroid",
    max_corners=25,
    quality_level=0.01,
    min_distance=10,
    block_size=3,
    # LK optical-flow hyperparams
    lk_win_size=(15, 15),
    lk_max_level=3,
    lk_criteria_max_count=30,
    lk_criteria_eps=0.01,
    # Output filenames
    csv_filename="tracked_tip.csv",
    sanity_check_filename="tip_sanity_check.png",
    all_corners_filename="all_corners.png",
    annotated_video_filename="tracked_tip_video.mp4",
    # Pre-loaded model (optional, avoids reloading)
    model=None,
    processor=None,
    device=None,
):
    """End-to-end pipeline: SAM3 → tip detection → LK tracking → CSV.

    All tuneable knobs are exposed as keyword arguments so they can be
    set from the CLI or a calling script.

    Returns
    -------
    tracked_positions : list of (frame_idx, x, y)
    tip : np.ndarray, shape (2,)
    model, processor, device
        The (possibly freshly-loaded) SAM3 artefacts for reuse.
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── 1. Read & sub-sample frames (done first, before anything else) ─
    frames, original_fps = read_video_frames_sampled(
        video_path,
        sample_rate=sample_rate,
        start_skip=start_skip,
        end_skip=end_skip,
    )
    if len(frames) == 0:
        raise RuntimeError("No frames remaining after start/end skip + sampling.")
    effective_fps = original_fps / max(sample_rate, 1)

    # ── 2. Load SAM3 model (if not provided) ──────────────────────────
    if model is None or processor is None or device is None:
        model, processor, device = load_model(model_name)

    # ── 3. First frame → SAM3 → top mask ─────────────────────────────
    first_frame_pil = Image.fromarray(
        cv2.cvtColor(frames[0], cv2.COLOR_BGR2RGB)
    )

    results = run_segmentation(
        model, processor, first_frame_pil, text_prompt, device, sam_threshold
    )
    binary_mask, best_score = get_top_mask(results)

    # ── 4. Detect tip ─────────────────────────────────────────────────
    tip, corners = detect_tip(
        binary_mask,
        strategy=tip_strategy,
        max_corners=max_corners,
        quality_level=quality_level,
        min_distance=min_distance,
        block_size=block_size,
    )

    # ── 5. Sanity-check image ─────────────────────────────────────────
    sanity_path = os.path.join(output_dir, sanity_check_filename)
    save_tip_sanity_check(binary_mask, tip, sanity_path)

    # ── 5b. All-corners image ─────────────────────────────────────────
    all_corners_path = os.path.join(output_dir, all_corners_filename)
    save_all_corners_image(binary_mask, corners, tip, all_corners_path)

    # ── 6. Track through all (sampled) frames ─────────────────────────
    tip = (tip[0] + 5, tip[1] + 1)
    init_pt = init_tracking_point(float(tip[0]), float(tip[1]))

    tracked_positions = track_point_lk(
        frames, init_pt,
        lk_win_size=lk_win_size,
        lk_max_level=lk_max_level,
        lk_criteria_max_count=lk_criteria_max_count,
        lk_criteria_eps=lk_criteria_eps,
    )

    # ── 7. Save CSV ───────────────────────────────────────────────────
    csv_path = os.path.join(output_dir, csv_filename)
    save_to_csv(tracked_positions, csv_path)

    # ── 8. Annotated tracking video ───────────────────────────────────
    video_out_path = os.path.join(output_dir, annotated_video_filename)
    save_annotated_video(frames, tracked_positions, video_out_path, effective_fps)

    print(f"[tip-sam3] ✓ Pipeline complete — outputs in: {output_dir}")
    return tracked_positions, tip, model, processor, device


# ══════════════════════════════════════════════════════════════════════
# Run — edit the hyperparameters below, then execute the script
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # Repo root (two levels up from analysis/src/)
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # ── Paths (relative to repo root) ─────────────────────────────────
    video_path              = os.path.join(ROOT, "analysis/data/sam3/surgery_video.mp4")          # Path to input video file
    output_dir              = os.path.join(ROOT, "analysis/outputs/track_tool_tip_sam3")          # Directory to write all outputs

    # ── Frame sampling ────────────────────────────────────────────────
    sample_rate             = 2                           # Keep every Nth frame (1 = all)
    start_skip              = 300                           # Skip this many frames at the start
    end_skip                = 0                           # Skip this many frames at the end

    # ── SAM3 ──────────────────────────────────────────────────────────
    text_prompt             = "blade"                   # What to segment (e.g. "blade", "skin")
    model_name              = "facebook/sam3"            # HuggingFace SAM3 model id
    sam_threshold           = 0.5                        # SAM3 confidence threshold

    # ── Tip detection (Shi-Tomasi) ────────────────────────────────────
    tip_strategy            = "leftmost"   # "farthest_from_centroid" or "best_quality" or "leftmost"
    max_corners             = 25                         # Max corners to detect
    quality_level           = 0.01                       # Minimum accepted quality of corners
    min_distance            = 10.0                       # Minimum distance between detected corners
    block_size              = 3                           # Neighbourhood size for corner detection

    # ── LK optical flow ──────────────────────────────────────────────
    lk_win_size             = (20, 10)                   # Search window size per pyramid level
    lk_max_level            = 3                           # Max pyramid levels
    lk_criteria_max_count   = 30                          # Termination: max iterations
    lk_criteria_eps         = 0.01                        # Termination: epsilon

    # ── Output filenames (saved inside output_dir) ────────────────────
    csv_filename            = "tracked_tip.csv"          # Trajectory CSV
    sanity_check_filename   = "tip_sanity_check.png"     # Mask + red dot at selected tip
    all_corners_filename    = "all_corners.png"          # Mask + all corners (blue) + tip (red)
    annotated_video_filename = "tracked_tip_video.mp4"   # Video with tracked red dot overlay

    # ── Run ───────────────────────────────────────────────────────────
    run_pipeline(
        video_path=video_path,
        output_dir=output_dir,
        text_prompt=text_prompt,
        # Frame sampling
        sample_rate=sample_rate,
        start_skip=start_skip,
        end_skip=end_skip,
        # SAM3
        model_name=model_name,
        sam_threshold=sam_threshold,
        # Tip detection
        tip_strategy=tip_strategy,
        max_corners=max_corners,
        quality_level=quality_level,
        min_distance=min_distance,
        block_size=block_size,
        # LK
        lk_win_size=lk_win_size,
        lk_max_level=lk_max_level,
        lk_criteria_max_count=lk_criteria_max_count,
        lk_criteria_eps=lk_criteria_eps,
        # Output
        csv_filename=csv_filename,
        sanity_check_filename=sanity_check_filename,
        all_corners_filename=all_corners_filename,
        annotated_video_filename=annotated_video_filename,
    )
