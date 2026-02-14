# analysis/src/event_detector.py
from __future__ import annotations

from typing import List, Tuple

import numpy as np

from .data_types import Frame, Event
from .analysis_config import AnalysisConfig


def _contiguous_true_regions(mask: np.ndarray) -> List[Tuple[int, int]]:
    """Returns (inclusive start, inclusive end) index pairs for each contiguous True run."""
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


def detect_motion_events(
    t: np.ndarray,
    speed_smooth: np.ndarray,
    frames: List[Frame],
    config: AnalysisConfig,
) -> List[Event]:
    """Detect tool_motion events where smoothed speed exceeds the threshold."""
    motion_mask = speed_smooth > float(config.motion_speed_threshold)
    regions = _contiguous_true_regions(motion_mask)

    events: List[Event] = []
    for (i0, i1) in regions:
        t0, t1 = float(t[i0]), float(t[i1])
        if (t1 - t0) < float(config.min_motion_event_duration_s):
            continue
        mean_spd = float(np.mean(speed_smooth[i0:i1 + 1]))
        conf = float(np.clip(mean_spd / (config.motion_speed_threshold * 3.0), 0.2, 1.0))
        events.append(Event(
            event_type="tool_motion",
            t_start=t0,
            t_end=t1,
            confidence=conf,
            meta={"tool_id": frames[i0].tool.tool_id, "tool_type": frames[i0].tool.tool_type},
        ))

    return events
