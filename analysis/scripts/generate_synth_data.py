# analysis/scripts/generate_synth_data.py
"""
Generate a synthetic perception time-series (tool 6D pose + hand joints) that matches
the minimal loader in analysis/src/analysis_pipeline.py, and save to a .json file.

Usage (from repo root):
  1) python analysis/scripts/generate_synth_data.py --out analysis/data/samples/synth_run_0001/frames.json
  2) python -m analysis.src.analysis_pipeline --input analysis/data/samples/synth_run_0001/frames.json --out analysis/outputs/synth_run_0001

Notes:
- Quaternion is wxyz.
- Units are arbitrary (think "meters" if you like).
- The sequence contains idle periods + motion periods so your current motion-event detector triggers cleanly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


Vec3 = Tuple[float, float, float]
QuatWXYZ = Tuple[float, float, float, float]


def yaw_to_quat_wxyz(yaw_rad: float) -> QuatWXYZ:
    """Quaternion for pure yaw about +Z: q = [cos(y/2), 0, 0, sin(y/2)] in (w,x,y,z)."""
    half = 0.5 * yaw_rad
    return (float(np.cos(half)), 0.0, 0.0, float(np.sin(half)))


def synth_tool_position(t: float) -> Vec3:
    """
    Piecewise trajectory:
      [0,2): idle
      [2,6): moving (smooth curve)
      [6,7): idle
      [7,10]: moving (different curve)
    """
    # Base anchor
    p0 = np.array([0.0, 0.0, 0.5], dtype=float)

    if t < 2.0:
        p = p0
    elif t < 6.0:
        tau = t - 2.0
        # Smooth-ish 3D curve
        p = p0 + np.array([
            0.18 * np.sin(2.0 * np.pi * 0.35 * tau),
            0.12 * np.cos(2.0 * np.pi * 0.35 * tau),
            0.05 * np.sin(2.0 * np.pi * 0.18 * tau),
        ])
    elif t < 7.0:
        p = p0 + np.array([0.18 * np.sin(2.0 * np.pi * 0.35 * 4.0), 0.12 * np.cos(2.0 * np.pi * 0.35 * 4.0), 0.0])
    else:
        tau = t - 7.0
        p = p0 + np.array([
            0.10 * np.sin(2.0 * np.pi * 0.55 * tau),
            0.10 * np.sin(2.0 * np.pi * 0.55 * tau + np.pi / 2),
            0.03 * np.cos(2.0 * np.pi * 0.25 * tau),
        ])

    # Add small noise
    p = p + 0.003 * np.random.randn(3)
    return (float(p[0]), float(p[1]), float(p[2]))


def synth_hand_joints(tool_pos: np.ndarray, t: float, side: str) -> Dict[str, Vec3]:
    """
    Minimal joint set for future use:
      wrist, index_tip, thumb_tip
    We keep hands near the tool with small oscillations.
    """
    # Side offsets
    side_sign = -1.0 if side == "left" else 1.0
    base = tool_pos + np.array([0.05 * side_sign, 0.02 * side_sign, -0.10], dtype=float)

    # Small motion (mimics micro-adjustments)
    wiggle = np.array([
        0.005 * np.sin(2 * np.pi * 1.2 * t + (0.4 if side == "left" else 0.0)),
        0.004 * np.cos(2 * np.pi * 1.0 * t),
        0.003 * np.sin(2 * np.pi * 0.8 * t),
    ], dtype=float)

    wrist = base + wiggle + 0.002 * np.random.randn(3)

    # Finger tips relative to wrist
    index_tip = wrist + np.array([0.02 * side_sign, 0.03, 0.01], dtype=float) + 0.0015 * np.random.randn(3)
    thumb_tip = wrist + np.array([0.015 * side_sign, 0.01, 0.015], dtype=float) + 0.0015 * np.random.randn(3)

    return {
        "wrist": (float(wrist[0]), float(wrist[1]), float(wrist[2])),
        "index_tip": (float(index_tip[0]), float(index_tip[1]), float(index_tip[2])),
        "thumb_tip": (float(thumb_tip[0]), float(thumb_tip[1]), float(thumb_tip[2])),
    }


def generate_frames(duration_s: float, fps: float, tool_id: str, tool_type: str) -> List[dict]:
    n = int(np.round(duration_s * fps)) + 1
    ts = np.linspace(0.0, duration_s, n)

    frames: List[dict] = []
    for t in ts:
        pos = synth_tool_position(float(t))
        tool_pos = np.array(pos, dtype=float)

        # Yaw changes during motion blocks; nearly constant during idle blocks
        if 2.0 <= t < 6.0:
            yaw = 0.8 * np.sin(2.0 * np.pi * 0.25 * (t - 2.0))
        elif t >= 7.0:
            yaw = 1.2 * np.sin(2.0 * np.pi * 0.35 * (t - 7.0))
        else:
            yaw = 0.05  # almost fixed
        quat = yaw_to_quat_wxyz(float(yaw))

        hands = {
            "left": {
                "confidence": 0.95,
                "joints": synth_hand_joints(tool_pos, float(t), "left"),
            },
            "right": {
                "confidence": 0.95,
                "joints": synth_hand_joints(tool_pos, float(t), "right"),
            },
        }

        frame = {
            "t": float(t),
            "tool": {
                "tool_id": tool_id,
                "tool_type": tool_type,
                "confidence": 0.98,
                "pose": {
                    "position": list(pos),
                    "quaternion_wxyz": list(quat),
                },
            },
            "hands": hands,
            "meta": {
                "source": "synthetic",
            },
        }
        frames.append(frame)

    return frames


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output path (.json). Example: analysis/data/samples/synth_run_0001/frames.json")
    ap.add_argument("--duration", type=float, default=10.0, help="Seconds")
    ap.add_argument("--fps", type=float, default=30.0, help="Frames per second")
    ap.add_argument("--tool_id", type=str, default="tool0")
    ap.add_argument("--tool_type", type=str, default="scalpel_like")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    np.random.seed(args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    frames = generate_frames(args.duration, args.fps, args.tool_id, args.tool_type)
    out_path.write_text(json.dumps(frames, indent=2))
    print(f"Wrote {len(frames)} frames -> {out_path}")


if __name__ == "__main__":
    main()
