"""
Compute GOALS-style kinematic metrics from instrument tracking data.

Outputs kinematics.json with per-instrument metrics for the Skills tab.
Each instrument is treated independently — no cross-alignment needed.

Usage:
    python compute_kinematics.py
    (outputs to ../public/data/kinematics.json)
"""

import json, csv, math, os
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


# ── metric helpers ───────────────────────────────────────────

def path_length(pts):
    """Total Euclidean path length in pixels."""
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

def compute_instrument(name, pts, fps):
    vel = velocity_profile(pts, fps)
    pl = path_length(pts)
    return {
        "name": name,
        "frames": len(pts),
        "duration_seconds": round(len(pts) / fps, 2),
        "path_length_px": round(pl, 1),
        "motion_economy": motion_economy(pts),
        "idle_fraction": idle_fraction(pts),
        "movement_count": movement_count(pts),
        "smoothness_sparc": sparc_smoothness(vel, fps),
        "tremor_index_px": tremor_index(pts, fps),
        "mean_speed_px_s": round(float(vel.mean()), 2),
        "max_speed_px_s": round(float(vel.max()), 2),
    }


def goals_score(instruments):
    """Map aggregate kinematics → GOALS 1-5 domain scores.

    Heuristics calibrated for pixel-space optical-flow / FoundationPose
    tracking at ~24 fps on 960×540 or 1920×1080 surgical video.
    """
    avg = lambda k: np.mean([i[k] for i in instruments])

    me = avg("motion_economy")          # 0–1, typically 0.01–0.1 in surgery
    idle = avg("idle_fraction")          # 0–1, typically 0.3–0.6
    smooth = avg("smoothness_sparc")     # negative; closer to 0 = smoother
    tremor = avg("tremor_index_px")      # px; lower = better
    moves = avg("movement_count")        # int; fewer = more efficient
    mean_spd = avg("mean_speed_px_s")

    def clamp(v, lo=1.0, hi=5.0):
        return round(max(lo, min(hi, v)), 1)

    # Efficiency: reward low idle + reasonable move count
    # idle 0.3→5, idle 0.6→2;  moves 30→5, moves 200→2
    eff_idle = 5 - (idle - 0.3) * 10          # 0.3→5, 0.6→2
    eff_moves = 5 - (moves - 30) / 50         # 30→5, 130→3, 230→1
    efficiency = clamp((eff_idle + eff_moves) / 2)

    # Tissue Handling: smoother & less tremor = better
    # SPARC in our data ranges -100 to -300; normalise per second of video
    dur = avg("duration_seconds")
    sparc_per_s = abs(smooth) / max(dur, 1)   # lower = smoother
    tis_smooth = clamp(5 - sparc_per_s / 3)   # 0→5, 6→3, 12→1
    tis_tremor = clamp(5 - tremor / 8)         # 0→5, 16→3, 32→1
    tissue = clamp((tis_smooth + tis_tremor) / 2)

    bimanual = 3.5  # default; overridden below if tweezer data exists
    depth = 3.5     # requires 6DoF Z; overridden if centroid present

    # Autonomy: fewer pauses, fewer restarts, steadier speed
    auto_idle = clamp(5 - idle * 6)                     # 0→5, 0.5→2
    auto_var = clamp(5 - (moves / max(dur, 1)) / 2)     # moves/s: 0→5, 4→3
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
        tw["tip_spread_std_px"] = tip_spread_consistency(tip0, tip1)
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

    # GOALS domain scores
    g = goals_score(instruments)
    # Override bimanual if we have tweezer data
    if any(i["name"] == "Tweezer" for i in instruments):
        tw = next(i for i in instruments if i["name"] == "Tweezer")
        corr = tw["bimanual_correlation"]
        spread_std = tw["tip_spread_std_px"]
        g["Bimanual Dexterity"] = round(max(1, min(5, 2 + corr * 2 + max(0, 3 - spread_std / 20))), 1)

    # Override depth if centroid present (proxy: having 6DoF data at all)
    if any("FoundationPose" in i["name"] for i in instruments):
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

    print(f"Wrote {out_path}")
    print(f"GOALS overall: {overall}/100")
    for d in goals_domains:
        print(f"  {d['domain']}: {d['score']}/5")
    for inst in instruments:
        print(f"\n{inst['name']} ({inst['source']}, {inst['frames']} frames, {inst['duration_seconds']}s)")
        print(f"  path_length={inst['path_length_px']:.0f}px  motion_economy={inst['motion_economy']}  idle={inst['idle_fraction']}")
        print(f"  smoothness={inst['smoothness_sparc']}  tremor={inst['tremor_index_px']}px  moves={inst['movement_count']}")


if __name__ == "__main__":
    main()

