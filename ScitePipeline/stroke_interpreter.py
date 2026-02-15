"""
Stroke-level segmentation for surgical steps.

Given a video and a detected step (with timestamp), sends a focused Gemini call
to identify individual instrument strokes/sub-movements within that step.

This adds granularity below the SOP node level — useful for skills assessment
and training feedback.
"""

import json
import time
import logging
from pathlib import Path

from google import genai
from google.genai import types

from config import get_settings

logger = logging.getLogger(__name__)


_STROKE_PROMPT = """You are analyzing a surgical video at a specific timestamp range.

Procedure: {procedure_name}
Current step: {step_name} (starts at ~{start_seconds}s)
Look at the video from {start_seconds}s to {end_seconds}s.

Identify each distinct instrument stroke or sub-movement within this step. A "stroke" is a single continuous instrument action — e.g. one cut, one spread, one grasp, one cautery application.

Return ONLY valid JSON:
{{
  "strokes": [
    {{
      "timestamp_seconds": 28.4,
      "end_seconds": 31.2,
      "description": "Brief description of the sub-movement",
      "stroke_type": "cut|spread|grasp|retract|cauterize|suture|irrigate|dissect|other",
      "instrument": "scalpel|forceps|hemostat|scissors|cautery|needle_driver|other"
    }}
  ]
}}

Rules:
- Only include strokes you can clearly observe in the video.
- Order by timestamp.
- Be VERY precise with timestamps — use DECIMAL seconds to the nearest tenth (e.g. 28.3, not just 28). Watch frame by frame.
- CRITICAL: Each stroke is ONE single motion of the instrument. Every time the blade moves through tissue, every time forceps open and close, every time the hemostat spreads — that is its own stroke. Do NOT group or summarize multiple motions into one stroke.
- Count carefully. Watch the full time window multiple times if needed. Report exactly what you see — no more, no less.
- Duration matters: a single scalpel cut typically lasts 0.3–1.0 seconds. A hemostat spread is 0.5–1.5 seconds. A grasp is 0.3–1.0 seconds. If your stroke duration is longer than ~2 seconds, you are probably grouping multiple motions — split them.
- stroke_type should be ONE of: cut, spread, grasp, retract, cauterize, suture, irrigate, dissect, other.
- Keep descriptions under 15 words but be specific about what you see (direction, depth, tissue layer, e.g. "Third cut deepening into subcutaneous fat").
"""


def segment_strokes(
    video_path: str,
    procedure_name: str,
    step_name: str,
    start_seconds: int,
    end_seconds: int,
    model_name: str = "gemini-3-pro-preview",
) -> list[dict]:
    """
    Analyze a video segment for individual instrument strokes.

    Args:
        video_path: Path to video file
        procedure_name: e.g. "Incision and Drainage of Abscess"
        step_name: e.g. "Incision Over Abscess (Along Skin Lines)"
        start_seconds: Start of the step in the video
        end_seconds: End of the step (or start of next step)
        model_name: Gemini model (flash is fine for this)

    Returns:
        List of stroke dicts with timestamp, description, type, instrument
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=settings.gemini_api_key)

    # Upload video
    logger.info(f"Uploading video for stroke segmentation: {video_path}")
    video_file = client.files.upload(file=video_path)

    while video_file.state == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state == "FAILED":
        raise RuntimeError("Video processing failed")

    prompt = _STROKE_PROMPT.format(
        procedure_name=procedure_name,
        step_name=step_name,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(
                        file_uri=video_file.uri,
                        mime_type=video_file.mime_type,
                    ),
                    types.Part.from_text(text=prompt),
                ],
            ),
        ],
    )

    # Parse
    raw = response.text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0]
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0]

    data = json.loads(raw.strip())
    strokes = data.get("strokes", [])

    # Cleanup
    try:
        client.files.delete(name=video_file.name)
    except Exception:
        pass

    logger.info(f"Detected {len(strokes)} strokes in '{step_name}'")
    return strokes

