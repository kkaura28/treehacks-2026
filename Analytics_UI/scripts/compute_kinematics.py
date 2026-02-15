"""
Compute GOALS-style kinematic metrics from instrument tracking data.

Outputs kinematics.json with per-instrument metrics for the Skills tab.
Each instrument is treated independently — no cross-alignment needed.

Data sources:
  - tracked_tips_tweezer.csv  (optical flow, 2D pixel)
  - tracked_tips_blade.csv    (optical flow, 2D pixel)
  - centroids.json            (FoundationPose, 2D pixel)
  - rgb_mesh/*.obj            (HaMeR hand meshes, 3D world coords)

Usage:
    python compute_kinematics.py
    (outputs to ../public/data/kinematics.json and hand_trajectories.csv)
"""

import json, csv, os, re
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "public" / "data"
FPS = 24  # surgery_video.mp4 is 24 fps


def load_csv(path, cols):
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append([float(row[c]) for c in cols])
    return np.array(rows)


def load_centroids(path):
    with open(path) as f:
        raw = json.load(f)
    pts = []
    for i in range(len(raw)):
        e = raw[f"{i:06d}.png"]
        pts.append([e["x"], e["y"]])
    return np.array(pts)


# ── HaMeR hand mesh processing ──────────────────────────────

def _obj_centroid(path):
    """Parse an OBJ file and return its vertex centroid (x, y, z)."""
    xs, ys, zs = [], [], []
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                xs.append(float(p[1]))
                ys.append(float(p[2]))
                zs.append(float(p[3]))
    return np.array([np.mean(xs), np.mean(ys), np.mean(zs)])


def load_hand_meshes(mesh_dir):
    """Load per-frame hand centroids from HaMeR OBJ files.

    Returns (left_hand, right_hand) as (N, 3) arrays, plus a CSV of raw data.
    Hands are assigned by x-sign convention (negative-x → left, positive → right).
    When multiple detections exist on the same side, the one closest to the
    previous frame is kept (nearest-neighbour tracking).
    """
    mesh_dir = Path(mesh_dir)
    if not mesh_dir.exists():
        return None, None, None

    # Discover frame IDs
    frame_ids = sorted({f[:6] for f in os.listdir(mesh_dir) if f.endswith(".obj")})
    if not frame_ids:
        return None, None, None

    # Parse all centroids per frame
    frame_data = {}  # frame_id -> list of (idx, centroid)
    for fid in frame_ids:
        objs = sorted(mesh_dir.glob(f"{fid}_*.obj"))
        centroids = []
        for obj_path in objs:
            idx = int(obj_path.stem.split("_")[1])
            centroids.append((idx, _obj_centroid(obj_path)))
        frame_data[fid] = centroids

    # Assign left/right per frame using x-sign + nearest-neighbour
    left_pts, right_pts = [], []
    prev_left, prev_right = None, None

    for fid in frame_ids:
        dets = frame_data[fid]
        lefts = [(i, c) for i, c in dets if c[0] < 0]
        rights = [(i, c) for i, c in dets if c[0] >= 0]

        # Pick best left
        if lefts:
            if prev_left is not None and len(lefts) > 1:
                lefts.sort(key=lambda x: np.linalg.norm(x[1] - prev_left))
            prev_left = lefts[0][1]
            left_pts.append(prev_left)
        elif prev_left is not None:
            left_pts.append(prev_left.copy())  # carry forward
        else:
            left_pts.append(np.array([0.0, 0.0, 0.0]))

        # Pick best right
        if rights:
            if prev_right is not None and len(rights) > 1:
                rights.sort(key=lambda x: np.linalg.norm(x[1] - prev_right))
            prev_right = rights[0][1]
            right_pts.append(prev_right)
        elif prev_right is not None:
            right_pts.append(prev_right.copy())
        else:
            right_pts.append(np.array([0.0, 0.0, 0.0]))

    left_arr = np.array(left_pts)
    right_arr = np.array(right_pts)

    # Filter outlier frames: replace any frame where displacement > threshold
    # with linear interpolation (HaMeR occasionally produces bad meshes)
    def _smooth_outliers(pts, max_disp=0.5):
        """Replace frames with implausible jumps via linear interpolation."""
        disps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        bad = np.where(disps > max_disp)[0]
        for idx in bad:
            # Replace idx+1 with average of neighbours
            lo = max(0, idx)
            hi = min(len(pts) - 1, idx + 2)
            pts[idx + 1] = (pts[lo] + pts[hi]) / 2
        return pts

    left_arr = _smooth_outliers(left_arr)
    right_arr = _smooth_outliers(right_arr)

    # Build CSV rows
    csv_rows = []
    for i, fid in enumerate(frame_ids):
        csv_rows.append({
            "frame_idx": int(fid),
            "left_x": round(left_arr[i, 0], 6),
            "left_y": round(left_arr[i, 1], 6),
            "left_z": round(left_arr[i, 2], 6),
            "right_x": round(right_arr[i, 0], 6),
            "right_y": round(right_arr[i, 1], 6),
            "right_z": round(right_arr[i, 2], 6),
            "n_detections": len(frame_data[fid]),
        })

    return left_arr, right_arr, csv_rows


# ── metric helpers ───────────────────────────────────────────

def path_length(pts):
    """Total Euclidean path length."""
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


def motion_economy(pts):
    """Straight-line distance / total path length  (1.0 = perfect)."""
    pl = path_length(pts)
    if pl == 0:
        return 1.0
    straight = float(np.linalg.norm(pts[-1] - pts[0]))
    return round(straight / pl, 4)


def idle_fraction(pts, threshold_px=1.5):
    """Fraction of frames where instrument moved < threshold."""
    disps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    return round(float((disps < threshold_px).sum()) / max(len(disps), 1), 4)


def movement_count(pts, threshold_px=1.5):
    """Number of discrete movement segments (idle→moving transitions)."""
    disps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    moving = disps >= threshold_px
    transitions = np.diff(moving.astype(int))
    return int((transitions == 1).sum()) + (1 if moving[0] else 0)


def velocity_profile(pts, fps):
    """Returns per-frame speed in px/s."""
    disps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    return disps * fps


def sparc_smoothness(vel, fps):
    """Spectral Arc Length (SPARC) — more negative = less smooth."""
    if len(vel) < 4:
        return 0.0
    N = len(vel)
    freq = np.fft.rfftfreq(N, d=1.0 / fps)
    spec = np.abs(np.fft.rfft(vel / vel.max())) if vel.max() > 0 else np.zeros(len(freq))
    # Arc length of normalised magnitude spectrum up to movement bandwidth
    bw_mask = freq <= 10.0  # 10 Hz upper bound
    if bw_mask.sum() < 2:
        return 0.0
    dfreq = np.diff(freq[bw_mask])
    dspec = np.diff(spec[bw_mask])
    arc = float(np.sum(np.sqrt(dfreq**2 + dspec**2)))
    return round(-arc, 4)


def tremor_index(pts, fps):
    """RMS amplitude of the high-frequency (>5 Hz) position component."""
    if len(pts) < 8:
        return 0.0
    results = []
    for dim in range(pts.shape[1]):
        sig = pts[:, dim] - np.mean(pts[:, dim])
        N = len(sig)
        freq = np.fft.rfftfreq(N, d=1.0 / fps)
        spec = np.fft.rfft(sig)
        hf_mask = freq > 5.0
        spec_hf = np.zeros_like(spec)
        spec_hf[hf_mask] = spec[hf_mask]
        hf_signal = np.fft.irfft(spec_hf, n=N)
        results.append(float(np.sqrt(np.mean(hf_signal**2))))
    return round(float(np.mean(results)), 4)


def bimanual_correlation(tip0, tip1):
    """Pearson correlation of velocity between two tips (bimanual coordination)."""
    v0 = np.linalg.norm(np.diff(tip0, axis=0), axis=1)
    v1 = np.linalg.norm(np.diff(tip1, axis=0), axis=1)
    if v0.std() == 0 or v1.std() == 0:
        return 0.0
    return round(float(np.corrcoef(v0, v1)[0, 1]), 4)


def tip_spread_consistency(tip0, tip1):
    """Std of distance between two tips — lower = more consistent grip."""
    dists = np.linalg.norm(tip0 - tip1, axis=1)
    return round(float(dists.std()), 2)


# ── per-instrument computation ───────────────────────────────

def compute_instrument(name, pts, fps, unit="px", idle_thresh=1.5):
    vel = velocity_profile(pts, fps)
    pl = path_length(pts)
    return {
        "name": name,
        "frames": len(pts),
        "duration_seconds": round(len(pts) / fps, 2),
        "unit": unit,
        "path_length": round(pl, 4 if unit == "m" else 1),
        "motion_economy": motion_economy(pts),
        "idle_fraction": idle_fraction(pts, threshold_px=idle_thresh),
        "movement_count": movement_count(pts, threshold_px=idle_thresh),
        "smoothness_sparc": sparc_smoothness(vel, fps),
        "tremor_index": tremor_index(pts, fps),
        "mean_speed": round(float(vel.mean()), 4 if unit == "m" else 2),
        "max_speed": round(float(vel.max()), 4 if unit == "m" else 2),
    }


def goals_score(instruments):
    """Map aggregate kinematics → GOALS 1-5 domain scores.

    Uses pixel-space instruments for efficiency/tissue/autonomy,
    and 3D hand data for depth perception + bimanual dexterity when available.
    """
    # Separate pixel-space and 3D instruments
    px_insts = [i for i in instruments if i.get("unit") == "px"]
    m_insts = [i for i in instruments if i.get("unit") == "m"]
    all_insts = instruments

    avg = lambda k, subset: np.mean([i[k] for i in subset]) if subset else 0

    idle = avg("idle_fraction", px_insts) if px_insts else avg("idle_fraction", all_insts)
    smooth = avg("smoothness_sparc", px_insts) if px_insts else avg("smoothness_sparc", all_insts)
    tremor = avg("tremor_index", px_insts) if px_insts else avg("tremor_index", all_insts)
    moves = avg("movement_count", px_insts) if px_insts else avg("movement_count", all_insts)
    dur = avg("duration_seconds", all_insts)

    def clamp(v, lo=1.0, hi=5.0):
        return round(max(lo, min(hi, v)), 1)

    # Efficiency: reward low idle + reasonable move count
    eff_idle = 5 - (idle - 0.3) * 10
    eff_moves = 5 - (moves - 30) / 50
    efficiency = clamp((eff_idle + eff_moves) / 2)

    # Tissue Handling: smoother & less tremor = better
    sparc_per_s = abs(smooth) / max(dur, 1)
    tis_smooth = clamp(5 - sparc_per_s / 3)
    # Tremor: use 3D hand tremor (in meters) if available, else pixel tremor
    # HaMeR mesh centroids have reconstruction noise ~0.01–0.05m baseline
    if m_insts:
        hand_tremor = avg("tremor_index", m_insts)
        # Hand tremor in meters (calibrated for HaMeR noise):
        # 0.01→5, 0.03→4, 0.06→3, 0.12→1
        tis_tremor = clamp(5 - (hand_tremor - 0.01) / 0.035)
    else:
        tis_tremor = clamp(5 - tremor / 8)
    tissue = clamp((tis_smooth + tis_tremor) / 2)

    bimanual = 3.5
    depth = 3.5

    # Autonomy
    auto_idle = clamp(5 - idle * 6)
    auto_var = clamp(5 - (moves / max(dur, 1)) / 2)
    autonomy = clamp((auto_idle + auto_var) / 2)

    return {
        "Efficiency": efficiency,
        "Tissue Handling": tissue,
        "Bimanual Dexterity": bimanual,
        "Depth Perception": depth,
        "Autonomy": autonomy,
    }


# ── main ─────────────────────────────────────────────────────

def main():
    instruments = []

    # Tweezer (two tips)
    tweezer_path = DATA_DIR / "tracked_tips_tweezer.csv"
    if tweezer_path.exists():
        raw = load_csv(tweezer_path, ["x0", "y0", "x1", "y1"])
        tip0 = raw[:, :2]
        tip1 = raw[:, 2:]
        midpoint = (tip0 + tip1) / 2

        tw = compute_instrument("Tweezer", midpoint, FPS)
        tw["tip0"] = compute_instrument("Tweezer Tip 0", tip0, FPS)
        tw["tip1"] = compute_instrument("Tweezer Tip 1", tip1, FPS)
        tw["bimanual_correlation"] = bimanual_correlation(tip0, tip1)
        tw["tip_spread_std"] = tip_spread_consistency(tip0, tip1)
        tw["source"] = "optical_flow"
        instruments.append(tw)

    # Blade tip
    blade_path = DATA_DIR / "tracked_tips_blade.csv"
    if blade_path.exists():
        pts = load_csv(blade_path, ["x0", "y0"])
        bl = compute_instrument("Blade (Tip)", pts, FPS)
        bl["source"] = "optical_flow"
        instruments.append(bl)

    # Blade centroid (FoundationPose)
    cent_path = DATA_DIR / "centroids.json"
    if cent_path.exists():
        pts = load_centroids(cent_path)
        ct = compute_instrument("Blade (FoundationPose Centroid)", pts, FPS)
        ct["source"] = "foundation_pose"
        instruments.append(ct)

    # ── HaMeR hand meshes (3D world coordinates) ────────────
    mesh_dir = DATA_DIR / "rgb_mesh"
    left_hand, right_hand, hand_csv_rows = load_hand_meshes(mesh_dir)

    if left_hand is not None:
        # 3D idle threshold: ~0.002 m ≈ 2 mm per frame
        lh = compute_instrument("Left Hand", left_hand, FPS, unit="m", idle_thresh=0.002)
        lh["source"] = "hamer"
        instruments.append(lh)

        rh = compute_instrument("Right Hand", right_hand, FPS, unit="m", idle_thresh=0.002)
        rh["source"] = "hamer"
        instruments.append(rh)

        # Combined hand metrics
        hand_bimanual = bimanual_correlation(left_hand, right_hand)
        hand_spread_std = tip_spread_consistency(left_hand, right_hand)

        # Attach bimanual info to left hand entry (as the "pair" entry)
        lh["bimanual_correlation"] = hand_bimanual
        lh["hand_separation_std"] = round(float(hand_spread_std), 4)
        rh["bimanual_correlation"] = hand_bimanual
        rh["hand_separation_std"] = round(float(hand_spread_std), 4)

        # Write hand trajectories CSV
        hand_csv_path = DATA_DIR / "hand_trajectories.csv"
        with open(hand_csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["frame_idx", "left_x", "left_y", "left_z",
                                              "right_x", "right_y", "right_z", "n_detections"])
            w.writeheader()
            w.writerows(hand_csv_rows)
        print(f"Wrote {hand_csv_path} ({len(hand_csv_rows)} rows)")

    # ── GOALS domain scores ─────────────────────────────────
    g = goals_score(instruments)

    # Override bimanual from tweezer tip correlation + hand bimanual
    bimanual_scores = []
    if any(i["name"] == "Tweezer" for i in instruments):
        tw = next(i for i in instruments if i["name"] == "Tweezer")
        corr = tw["bimanual_correlation"]
        spread_std = tw["tip_spread_std"]
        bimanual_scores.append(max(1, min(5, 2 + corr * 2 + max(0, 3 - spread_std / 20))))

    if left_hand is not None:
        # 3D hand bimanual: correlation + separation consistency
        # separation std in meters: 0.01→5, 0.05→3, 0.1→1
        sep_score = max(1, min(5, 5 - hand_spread_std / 0.03))
        corr_score = max(1, min(5, 2 + hand_bimanual * 3))
        bimanual_scores.append((sep_score + corr_score) / 2)

    if bimanual_scores:
        g["Bimanual Dexterity"] = round(np.mean(bimanual_scores), 1)

    # Depth perception from 3D hand data (we have real Z!)
    if left_hand is not None:
        # Use Z-axis smoothness and tremor as depth perception proxy
        lh_z_tremor = tremor_index(left_hand[:, 2:3], FPS)
        rh_z_tremor = tremor_index(right_hand[:, 2:3], FPS)
        avg_z_tremor = (lh_z_tremor + rh_z_tremor) / 2
        # Z tremor in meters (calibrated for HaMeR noise):
        # 0.01→5, 0.03→4, 0.06→3, 0.12→1
        g["Depth Perception"] = round(max(1, min(5, 5 - (avg_z_tremor - 0.01) / 0.035)), 1)
    elif any("FoundationPose" in i["name"] for i in instruments):
        ct = next(i for i in instruments if "FoundationPose" in i["name"])
        g["Depth Perception"] = round(max(1, min(5, 3 + ct["motion_economy"] * 2)), 1)

    goals_domains = [{"domain": k, "score": v, "max": 5} for k, v in g.items()]
    overall = round(np.mean(list(g.values())) / 5 * 100)

    output = {
        "fps": FPS,
        "instruments": instruments,
        "goals": goals_domains,
        "overall_score": overall,
    }

    out_path = DATA_DIR / "kinematics.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {out_path}")
    print(f"GOALS overall: {overall}/100")
    for d in goals_domains:
        print(f"  {d['domain']}: {d['score']}/5")
    for inst in instruments:
        u = inst["unit"]
        print(f"\n{inst['name']} ({inst['source']}, {inst['frames']} frames, {inst['duration_seconds']}s, {u})")
        print(f"  path_length={inst['path_length']}  motion_economy={inst['motion_economy']}  idle={inst['idle_fraction']}")
        print(f"  smoothness={inst['smoothness_sparc']}  tremor={inst['tremor_index']}  moves={inst['movement_count']}")
        if "bimanual_correlation" in inst:
            print(f"  bimanual_corr={inst['bimanual_correlation']}")


if __name__ == "__main__":
    main()

