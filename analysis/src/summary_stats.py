# analysis/src/summary_stats.py
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from .data_types import Event


def compute_summary(
    t: np.ndarray,
    speed_smooth: np.ndarray,
    events: List[Event],
) -> Dict[str, Any]:
    """Compute summary metrics from the analysis run."""
    total_dur = float(t[-1] - t[0])
    active_dur = float(sum(ev.t_end - ev.t_start for ev in events))

    return {
        "total_duration_s": total_dur,
        "active_motion_duration_s": active_dur,
        "active_fraction": (active_dur / total_dur) if total_dur > 1e-9 else 0.0,
        "peak_speed": float(np.max(speed_smooth)),
        "mean_speed": float(np.mean(speed_smooth)),
        "motion_event_count": len(events),
    }
