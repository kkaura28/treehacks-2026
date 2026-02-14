# analysis/src/motion_metrics.py
from __future__ import annotations

from typing import List

import numpy as np

from .data_types import Frame


def compute_speed(frames: List[Frame]) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (t, speed) arrays from a sorted list of frames.
    speed[i] is the backward-difference instantaneous speed at frame i.
    """
    t = np.asarray([fr.t for fr in frames], dtype=float)
    p = np.stack([fr.tool.pose.p() for fr in frames], axis=0)

    dt = np.diff(t)
    dp = np.diff(p, axis=0)
    speed = np.zeros(len(frames), dtype=float)
    safe_dt = np.where(dt <= 1e-9, np.nan, dt)
    inst = np.linalg.norm(dp, axis=1) / safe_dt
    inst = np.where(np.isfinite(inst), inst, 0.0)
    speed[1:] = inst

    return t, speed
