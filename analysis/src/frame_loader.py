# analysis/src/frame_loader.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .data_types import Pose6D, HandState, ToolState, Frame


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
    t = d.get("t", d.get("timestamp", d.get("time_s")))
    if t is None:
        raise ValueError(f"Frame[{idx}] missing timestamp field (t/timestamp/time_s).")

    tool_block = d.get("tool", None)
    if tool_block is None:
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
