"""
Gemini video interpreter.

Sends a surgical video to Gemini 2.5 Pro, which watches it and returns
structured events mapped to the procedure graph's node IDs.

Educational mode — not for clinical decision-making.
"""

import json
import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google import genai
from google.genai import types

from config import get_settings
from models import ObservedEvent

logger = logging.getLogger(__name__)


# ── Prompt ─────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a surgical education assistant analyzing a video of a medical procedure.

Procedure type: {procedure_name}

The following are the expected steps for this procedure. Each has a unique ID you MUST use:

{node_list}

Watch the video carefully from start to finish. For each step you can identify:
1. Map it to the closest node ID from the list above (use the EXACT id string)
2. Note the timestamp in seconds from video start
3. Rate your confidence (0.0 to 1.0)

Return ONLY valid JSON — no markdown, no commentary:
{{
  "detected_events": [
    {{
      "node_id": "exact_id_from_list",
      "timestamp_seconds": 32,
      "confidence": 0.85,
      "observation": "Brief description of what you see"
    }}
  ],
  "notes": "Any overall observations about the procedure"
}}

Rules:
- ONLY use node IDs from the list above. Do NOT invent new IDs.
- Only include steps you actually observe in the video.
- If a step is not visible or you cannot identify it, do NOT include it.
- Order events by timestamp.
- Be conservative with confidence — if unsure, use a lower score.
"""


def _build_node_list(nodes: list[dict]) -> str:
    """Format node IDs + names for the prompt."""
    lines = []
    for n in nodes:
        marker = " [SAFETY-CRITICAL]" if n.get("safety_critical") else ""
        mandatory = " (mandatory)" if n.get("mandatory") else " (optional)"
        lines.append(f"  - {n['id']}: {n['name']}{mandatory}{marker}")
    return "\n".join(lines)


def _parse_gemini_response(text: str) -> dict:
    """Extract JSON from Gemini response, handling markdown fences."""
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0]
    return json.loads(cleaned.strip())


# ── Public API ─────────────────────────────────────────────

def interpret_video(
    video_path: str,
    procedure_name: str,
    nodes: list[dict],
    model_name: str = "gemini-2.5-pro",
) -> tuple[list[ObservedEvent], str]:
    """
    Send a video to Gemini and get back structured surgical events.

    Args:
        video_path: Path to video file (mp4, mov, etc.)
        procedure_name: e.g. "Incision and Drainage of Abscess"
        nodes: List of node dicts with id, name, safety_critical, mandatory
        model_name: Gemini model to use

    Returns:
        Tuple of (list of ObservedEvent, notes string from Gemini)
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")

    client = genai.Client(api_key=settings.gemini_api_key)

    # Upload video
    logger.info(f"Uploading video: {video_path}")
    video_file = client.files.upload(file=video_path)

    # Wait for processing
    logger.info("Waiting for Gemini to process video...")
    while video_file.state == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state == "FAILED":
        raise RuntimeError(f"Gemini video processing failed: {video_file.state}")

    logger.info(f"Video ready: {video_file.uri}")

    # Build prompt
    node_list = _build_node_list(nodes)
    prompt = _SYSTEM_PROMPT.format(
        procedure_name=procedure_name,
        node_list=node_list,
    )

    # Query Gemini
    logger.info(f"Querying {model_name}...")
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

    # Parse response
    raw_text = response.text
    logger.info(f"Gemini response length: {len(raw_text)} chars")

    data = _parse_gemini_response(raw_text)
    notes = data.get("notes", "")

    # Convert to ObservedEvent objects
    valid_ids = {n["id"] for n in nodes}
    base_time = datetime.now(timezone.utc)
    events = []

    for item in data.get("detected_events", []):
        node_id = item.get("node_id", "")
        if node_id not in valid_ids:
            logger.warning(f"Gemini returned unknown node_id '{node_id}' — skipping")
            continue

        events.append(ObservedEvent(
            node_id=node_id,
            timestamp=base_time + timedelta(seconds=item.get("timestamp_seconds", 0)),
            confidence=item.get("confidence", 0.5),
            source="gemini",
        ))

    # Clean up uploaded file
    try:
        client.files.delete(name=video_file.name)
    except Exception:
        pass

    logger.info(f"Detected {len(events)} events from video")
    return events, notes


def interpret_video_from_json(nodes_json_path: str, video_path: str, **kwargs) -> tuple[list[ObservedEvent], str]:
    """
    Convenience: load nodes from a procedure JSON file and interpret video.
    """
    with open(nodes_json_path) as f:
        data = json.load(f)

    procedure_name = data["procedure"]["name"]
    nodes = data["nodes"]

    return interpret_video(
        video_path=video_path,
        procedure_name=procedure_name,
        nodes=nodes,
        **kwargs,
    )

