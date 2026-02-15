# analysis/src/analysis_pipeline.py
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Allow running directly: python analysis_pipeline.py
if __name__ == "__main__" and not __package__:
    _root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(_root))
    __package__ = "analysis.src"

from .analysis_config import AnalysisConfig, load_config
from .frame_loader import load_frames
from .motion_metrics import compute_speed
from .signal_processing import ema
from .event_detector import detect_motion_events
from .summary_stats import compute_summary
from .output_writer import write_results


def run_analysis(
    input_path: str,
    output_dir: Optional[str] = None,
    config: Optional[AnalysisConfig] = None,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    End-to-end run:
      - loads frames
      - computes tool speed
      - smooths with EMA
      - detects tool_motion events
      - computes summary metrics
      - writes events.json + metrics.json
    """
    if config is None:
        config = load_config(config_path)

    out_dir = Path(output_dir or config.output_dir)

    frames = load_frames(input_path)
    if len(frames) < 2:
        raise ValueError("Need at least 2 frames to compute motion.")

    t, speed = compute_speed(frames)
    speed_smooth = ema(speed, alpha=config.ema_alpha)
    events = detect_motion_events(t, speed_smooth, frames, config)
    metrics = compute_summary(t, speed_smooth, events)

    write_results(out_dir, events, metrics)

    return {"events": [e.to_dict() for e in events], "metrics": metrics, "output_dir": str(out_dir)}


if __name__ == "__main__":
    # Argument parsing
    # import argparse

    # ap = argparse.ArgumentParser()
    # ap.add_argument("--input", required=True, help="Path to perception frames (.json or .jsonl)")
    # ap.add_argument("--out", default=None, help="Output directory (default from config)")
    # ap.add_argument("--config", default=None, help="Optional JSON config path")
    # args = ap.parse_args()

    # result = run_analysis(input_path=args.input, output_dir=args.out, config_path=args.config)
    # print(json.dumps({"output_dir": result["output_dir"], "metrics": result["metrics"]}, indent=2))

    # Hyperparameters (paths relative to repo root)
    REPO_ROOT   = str(_root)
    INPUT_PATH  = str(_root / "analysis/data/samples/synth_run_0001/frames.json")
    OUTPUT_DIR  = str(_root / "analysis/outputs/synth_run_0001")
    CONFIG_PATH = None  # set to a JSON path to override defaults

    result = run_analysis(input_path=INPUT_PATH, output_dir=OUTPUT_DIR, config_path=CONFIG_PATH)
    print(json.dumps({"output_dir": result["output_dir"], "metrics": result["metrics"]}, indent=2))
