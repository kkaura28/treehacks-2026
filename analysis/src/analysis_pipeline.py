# analysis/src/analysis_pipeline.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .data_types import Pose6D, HandState, ToolState, Frame, Event
from .analysis_config import AnalysisConfig, load_config


# ---------------------------
# Minimal input parsing
# ---------------------------

def _coerce_vec3(x: Any, default: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Tuple[float, float, float]:
    if x is None:
        return default
    if isinstance(x, (list, tuple)) and len(x) == 3:
        return (float(x[0]), float(x[1]), float(x[2]))
    raise ValueError(f"Expected vec3, got: {x}")


def _coerce_quat_wxyz(q: Any, default: Tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)) -> Tuple[float, float, float, float]:
    if q is None:
        return default
    if isinstance(q, (list, tuple)) and len(q) == 4:
        return (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    raise ValueError(f"Expected quat wxyz, got: {q}")


def _parse_frame(d: Dict[str, Any], idx: int) -> Frame:
    # timestamp
    t = d.get("t", d.get("timestamp", d.get("time_s")))
    if t is None:
        raise ValueError(f"Frame[{idx}] missing timestamp field (t/timestamp/time_s).")

    # tool pose (support a couple schemas)
    tool_block = d.get("tool", None)
    if tool_block is None:
        # flat schema
        pos = d.get("tool_position", d.get("position"))
        quat = d.get("tool_quaternion_wxyz", d.get("quaternion_wxyz"))
        tool_id = d.get("tool_id", "tool0")
        tool_type = d.get("tool_type", None)
        conf = float(d.get("tool_confidence", 1.0))
    else:
        tool_id = tool_block.get("tool_id", tool_block.get("id", "tool0"))
        tool_type = tool_block.get("tool_type", tool_block.get("type", None))
        conf = float(tool_block.get("confidence", 1.0))

        pose_block = tool_block.get("pose", tool_block)
        pos = pose_block.get("position", pose_block.get("p"))
        quat = pose_block.get("quaternion_wxyz", pose_block.get("q_wxyz"))

    pos3 = _coerce_vec3(pos)
    quat4 = _coerce_quat_wxyz(quat)

    tool = ToolState(
        tool_id=str(tool_id),
        tool_type=None if tool_type is None else str(tool_type),
        pose=Pose6D(position=pos3, quaternion_wxyz=quat4),
        confidence=conf,
    )

    # hands (optional)
    hands_out: Dict[str, HandState] = {}
    hands_block = d.get("hands", d.get("hand_states"))
    if isinstance(hands_block, dict):
        for side in ("left", "right"):
            hb = hands_block.get(side)
            if hb is None:
                continue
            joints = hb.get("joints", hb.get("keypoints", {}))
            if isinstance(joints, dict):
                joints3 = {str(k): _coerce_vec3(v) for k, v in joints.items()}
            else:
                # if it's a list, we just index them "j0", "j1", ...
                joints3 = {f"j{i}": _coerce_vec3(v) for i, v in enumerate(joints)}
            hconf = float(hb.get("confidence", 1.0))
            hands_out[side] = HandState(side=side, joints=joints3, confidence=hconf)

    meta = d.get("meta", {})
    if not isinstance(meta, dict):
        meta = {"meta": meta}

    return Frame(t=float(t), tool=tool, hands=hands_out, meta=meta)


def load_frames(input_path: str) -> List[Frame]:
    """
    Accepts:
      - .json  : either a list of frames OR {"frames": [...]}
      - .jsonl : one JSON dict per line
    """
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    if p.suffix.lower() == ".jsonl":
        frames_raw: List[Dict[str, Any]] = []
        for line_no, line in enumerate(p.read_text().splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            frames_raw.append(json.loads(line))
    elif p.suffix.lower() == ".json":
        obj = json.loads(p.read_text())
        if isinstance(obj, dict) and "frames" in obj:
            frames_raw = obj["frames"]
        elif isinstance(obj, list):
            frames_raw = obj
        else:
            raise ValueError("JSON must be a list of frames or a dict with key 'frames'.")
    else:
        raise ValueError(f"Unsupported input type: {p.suffix} (use .json or .jsonl)")

    frames = [_parse_frame(d, i) for i, d in enumerate(frames_raw)]
    frames.sort(key=lambda fr: fr.t)
    return frames


# ---------------------------
# Minimal analysis
# ---------------------------

def _ema(x: np.ndarray, alpha: float) -> np.ndarray:
    if x.size == 0:
        return x
    y = np.empty_like(x, dtype=float)
    y[0] = float(x[0])
    for i in range(1, len(x)):
        y[i] = alpha * float(x[i]) + (1.0 - alpha) * float(y[i - 1])
    return y


def _contiguous_true_regions(mask: np.ndarray) -> List[Tuple[int, int]]:
    """
    Returns inclusive start, inclusive end indices for each contiguous True run.
    """
    regions: List[Tuple[int, int]] = []
    if mask.size == 0:
        return regions

    in_run = False
    start = 0
    for i, v in enumerate(mask):
        if v and not in_run:
            in_run = True
            start = i
        elif not v and in_run:
            in_run = False
            regions.append((start, i - 1))
    if in_run:
        regions.append((start, len(mask) - 1))
    return regions


def run_analysis(
    input_path: str,
    output_dir: Optional[str] = None,
    config: Optional[AnalysisConfig] = None,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Minimal end-to-end run:
      - loads frames
      - computes tool speed
      - detects "tool_motion" events where speed > threshold
      - writes events.json + metrics.json
    """
    if config is None:
        config = load_config(config_path)

    out_dir = Path(output_dir or config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = load_frames(input_path)
    if len(frames) < 2:
        raise ValueError("Need at least 2 frames to compute motion.")

    t = np.asarray([fr.t for fr in frames], dtype=float)
    p = np.stack([fr.tool.pose.p() for fr in frames], axis=0)  # (N,3)

    dt = np.diff(t)
    dp = np.diff(p, axis=0)
    speed = np.zeros(len(frames), dtype=float)
    # speed[i] corresponds to frame i (use backward diff)
    safe_dt = np.where(dt <= 1e-9, np.nan, dt)
    inst = np.linalg.norm(dp, axis=1) / safe_dt
    inst = np.where(np.isfinite(inst), inst, 0.0)
    speed[1:] = inst

    speed_s = _ema(speed, alpha=config.ema_alpha)

    motion_mask = speed_s > float(config.motion_speed_threshold)
    regions = _contiguous_true_regions(motion_mask)

    events: List[Event] = []
    for (i0, i1) in regions:
        t0, t1 = float(t[i0]), float(t[i1])
        if (t1 - t0) < float(config.min_motion_event_duration_s):
            continue
        # confidence = clamp(mean normalized speed)
        mean_spd = float(np.mean(speed_s[i0:i1 + 1]))
        conf = float(np.clip(mean_spd / (config.motion_speed_threshold * 3.0), 0.2, 1.0))
        events.append(Event(
            event_type="tool_motion",
            t_start=t0,
            t_end=t1,
            confidence=conf,
            meta={"tool_id": frames[i0].tool.tool_id, "tool_type": frames[i0].tool.tool_type},
        ))

    total_dur = float(t[-1] - t[0])
    active_dur = float(sum(ev.t_end - ev.t_start for ev in events))
    metrics = {
        "total_duration_s": total_dur,
        "active_motion_duration_s": active_dur,
        "active_fraction": (active_dur / total_dur) if total_dur > 1e-9 else 0.0,
        "peak_speed": float(np.max(speed_s)),
        "mean_speed": float(np.mean(speed_s)),
        "motion_event_count": len(events),
    }

    # write outputs
    (out_dir / "events.json").write_text(json.dumps([e.to_dict() for e in events], indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    return {"events": [e.to_dict() for e in events], "metrics": metrics, "output_dir": str(out_dir)}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to perception frames (.json or .jsonl)")
    ap.add_argument("--out", default=None, help="Output directory (default from config)")
    ap.add_argument("--config", default=None, help="Optional JSON config path")
    args = ap.parse_args()

    result = run_analysis(input_path=args.input, output_dir=args.out, config_path=args.config)
    print(json.dumps({"output_dir": result["output_dir"], "metrics": result["metrics"]}, indent=2))
