# analysis/src/output_writer.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .data_types import Event


def write_results(
    out_dir: Path,
    events: List[Event],
    metrics: Dict[str, Any],
) -> None:
    """Write events.json and metrics.json to the output directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "events.json").write_text(json.dumps([e.to_dict() for e in events], indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
