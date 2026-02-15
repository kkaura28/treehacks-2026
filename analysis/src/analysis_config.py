# analysis/src/analysis_config.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
import json
from pathlib import Path


@dataclass(frozen=True)
class AnalysisConfig:
    # Smoothing
    ema_alpha: float = 0.35

    # Minimal event detection
    motion_speed_threshold: float = 0.08   # units/sec (depends on your pose units)
    min_motion_event_duration_s: float = 0.25

    # IO
    output_dir: str = "analysis/outputs"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_config(path: Optional[str]) -> AnalysisConfig:
    """
    Minimal loader: JSON only. If path is None, returns defaults.
    Expected JSON keys match AnalysisConfig fields.
    """
    if path is None:
        return AnalysisConfig()

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    data = json.loads(p.read_text())
    return AnalysisConfig(**data)
