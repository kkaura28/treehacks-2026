"""
annotate_video_final.py — Overlay tracked points from multiple CSVs onto a video.
Each CSV can have its own start_skip/end_skip.
"""

import os, sys, csv
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from analysis.src.track_tool_tip_sam3 import (
    read_video_frames_sampled,
    _draw_tracking_marker,
)

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
    """Read wide-format CSV → list of per-point dicts {frame_idx: (x, y)}."""
    with open(csv_path, "r") as f:
        header = next(csv.reader(f))
    num_points = (len(header) - 1) // 2
    pos_maps = [{} for _ in range(num_points)]
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            fi = int(row[0])
            for p in range(num_points):
                x_val, y_val = row[1 + 2 * p], row[2 + 2 * p]
                if x_val and y_val:
                    pos_maps[p][fi] = (float(x_val), float(y_val))
    return pos_maps


def smooth_positions_gaussian(pos_map, sigma):
    """Gaussian-smooth x and y series in a {frame_idx: (x,y)} dict."""
    if sigma <= 0 or len(pos_map) < 2:
        return pos_map
    frames = sorted(pos_map.keys())
    xs = np.array([pos_map[f][0] for f in frames])
    ys = np.array([pos_map[f][1] for f in frames])
    xs = gaussian_filter1d(xs, sigma=sigma)
    ys = gaussian_filter1d(ys, sigma=sigma)
    return {f: (float(xs[i]), float(ys[i])) for i, f in enumerate(frames)}


def _one_euro_filter_1d(values, min_cutoff, beta):
    """Apply One Euro Filter to a 1D array of values."""
    def smoothing_factor(te, cutoff):
        r = 2 * np.pi * cutoff * te
        return r / (r + 1)

    out = np.zeros_like(values, dtype=float)
    out[0] = values[0]
    dx = 0.0
    for i in range(1, len(values)):
        te = 1.0  # uniform time step
        # Derivative estimate (smoothed)
        a_d = smoothing_factor(te, min_cutoff)
        dx = a_d * (values[i] - out[i - 1]) / te + (1 - a_d) * dx
        # Adaptive cutoff
        cutoff = min_cutoff + beta * abs(dx)
        a = smoothing_factor(te, cutoff)
        out[i] = a * values[i] + (1 - a) * out[i - 1]
    return out


def smooth_positions(pos_map, min_cutoff, beta):
    """One Euro Filter on x and y series in a {frame_idx: (x,y)} dict."""
    if len(pos_map) < 2:
        return pos_map
    frames = sorted(pos_map.keys())
    xs = np.array([pos_map[f][0] for f in frames])
    ys = np.array([pos_map[f][1] for f in frames])
    xs = _one_euro_filter_1d(xs, min_cutoff, beta)
    ys = _one_euro_filter_1d(ys, min_cutoff, beta)
    return {f: (float(xs[i]), float(ys[i])) for i, f in enumerate(frames)}


def remove_outliers(pos_map, max_displacement=50.0, median_window=11):
    """Remove outlier points using local median, then linearly interpolate gaps."""
    if len(pos_map) < 3:
        return pos_map
    frames = sorted(pos_map.keys())
    xs = np.array([pos_map[f][0] for f in frames])
    ys = np.array([pos_map[f][1] for f in frames])
    n = len(frames)

    # Compute local median for each point
    half = median_window // 2
    valid = np.ones(n, dtype=bool)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        med_x = np.median(xs[lo:hi])
        med_y = np.median(ys[lo:hi])
        dist = np.sqrt((xs[i] - med_x) ** 2 + (ys[i] - med_y) ** 2)
        if dist > max_displacement:
            valid[i] = False

    # Interpolate gaps from nearest valid neighbors
    valid_idxs = np.where(valid)[0]
    if len(valid_idxs) == 0:
        return pos_map  # everything is outlier, give up
    xs_clean = np.interp(np.arange(n), valid_idxs, xs[valid_idxs])
    ys_clean = np.interp(np.arange(n), valid_idxs, ys[valid_idxs])

    return {f: (float(xs_clean[i]), float(ys_clean[i])) for i, f in enumerate(frames)}


def annotate_video(
    video_path, csv_configs, output_path,
    sample_rate=1,
    crop_region=None,
    smooth_min_cutoff=1.0,
    smooth_beta=0.0,
    sigma=1.0,
    outlier_max_displacement=0,
    outlier_median_window=11,
):
    """
    csv_configs: list of dicts, each with:
        - "path": str (CSV file path)
        - "start_skip": int
        - "end_skip": int
    """
    # Load full video (no skip), just sample + crop
    frames, original_fps = read_video_frames_sampled(
        video_path, sample_rate=sample_rate, start_skip=0, end_skip=0,
    )
    effective_fps = original_fps / max(sample_rate, 1)

    if crop_region is not None:
        x1, y1, x2, y2 = crop_region
        frames = [f[y1:y2, x1:x2] for f in frames]

    n_frames = len(frames)

    # For each CSV, compute the global sampled-frame offset and load positions.
    # CSV frame i was generated from original frame (start_skip + i * sample_rate),
    # which in our full sampled array is at index (start_skip // sample_rate) + i.
    csv_data = []  # list of (color, [pos_map remapped to global frame index])
    for ci, cfg in enumerate(csv_configs):
        color = CSV_COLORS[ci % len(CSV_COLORS)]
        pos_maps = read_csv_positions(cfg["path"])
        offset = cfg["start_skip"] // sample_rate
        # Remap CSV frame indices to global sampled indices, then smooth
        remapped = []
        for pm in pos_maps:
            rm = {(offset + fi): (x, y) for fi, (x, y) in pm.items()}
            if smooth_beta > 0 or smooth_min_cutoff < 1.0:
                rm = smooth_positions(rm, smooth_min_cutoff, smooth_beta)
                # rm = smooth_positions_gaussian(rm, sigma=sigma)
            if outlier_max_displacement > 0:
                rm = remove_outliers(rm, outlier_max_displacement, outlier_median_window)
            remapped.append(rm)
        csv_data.append((color, remapped))

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
                        inner_radius=6, outer_radius=20, crosshair_length=28,
                        thickness=2, inner_color=color,
                    )
        writer.write(ann)

    writer.release()
    print(f"[annotate] Saved → {output_path} ({n_frames} frames)")


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":

    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    OUT = os.path.join(ROOT, "analysis/outputs/track_tool_final")

    annotate_video(
        video_path=os.path.join(ROOT, "analysis/data/sam3/surgery_video.mp4"),
        csv_configs=[
            {"path": os.path.join(OUT, "tracked_tips_blade.csv"),
             "start_skip": 265, "end_skip": 723},
            {"path": os.path.join(OUT, "tracked_tips_tweezer.csv"),
             "start_skip": 506, "end_skip": 482},
        ],
        output_path=os.path.join(OUT, "annotated_all.mp4"),
        sample_rate=1,
        crop_region=None,
        smooth_min_cutoff=0.02,
        smooth_beta=0.2,
        sigma=3.0,
        outlier_max_displacement=30.0,
        outlier_median_window=11,
    )
