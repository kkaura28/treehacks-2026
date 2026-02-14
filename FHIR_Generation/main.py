"""
FHIR Generation service for the surgical compliance pipeline.

Converts live-video-derived surgical data into FHIR R4 Bundles that can
be submitted to hospital EHR/FHIR servers — eliminating the manual
operative-report backlog.

Endpoints:
  POST /fhir/generate              — convert a ComplianceReport payload to FHIR
  POST /fhir/from-pipeline/{id}    — fetch a stored report from Supabase → FHIR
  POST /fhir/from-video            — end-to-end: video → analysis → FHIR Bundle
"""

from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Allow importing ScitePipeline modules when running standalone
_SCITE_DIR = str(Path(__file__).resolve().parent.parent / "ScitePipeline")
if _SCITE_DIR not in sys.path:
    sys.path.insert(0, _SCITE_DIR)

from fhir_mapper import build_fhir_bundle

logger = logging.getLogger(__name__)

app = FastAPI(
    title="FHIR Generation Service",
    description="Converts surgical video analysis into FHIR R4 Bundles for EHR integration",
    version="0.1.0",
)


# ── Request / Response models ─────────────────────────────

class DeviationPayload(BaseModel):
    node_id: str
    node_name: str
    phase: str = ""
    deviation_type: str
    verdict: str = "confirmed"
    evidence_summary: str = ""
    citations: list[str] = []
    original_mandatory: bool = True
    original_safety_critical: bool = False


class CompliancePayload(BaseModel):
    """Mirrors ComplianceReport from the ScitePipeline."""
    procedure_run_id: str
    procedure_id: str
    procedure_name: str
    compliance_score: float = Field(ge=0, le=1)
    total_expected: int
    total_observed: int
    confirmed_count: int = 0
    mitigated_count: int = 0
    review_count: int = 0
    confirmed_deviations: list[DeviationPayload] = []
    mitigated_deviations: list[DeviationPayload] = []
    review_deviations: list[DeviationPayload] = []
    report_text: str = ""


class ObservedEventPayload(BaseModel):
    node_id: str
    timestamp: str = ""
    confidence: float = 1.0
    source: str = "gemini"


class FHIRGenerateRequest(BaseModel):
    compliance_report: CompliancePayload
    observed_events: list[ObservedEventPayload] = []
    video_url: str = ""
    patient_name: str = "Surgical Patient"
    surgeon_name: str = "Attending Surgeon"


class FHIRFromVideoRequest(BaseModel):
    procedure_json_path: str = Field(
        ..., description="Path to procedure SOP JSON (e.g. SOP/data/abcess_data/incision_drainage_abscess.json)"
    )
    video_path: str = Field(..., description="Path to surgical video file")
    patient_name: str = "Surgical Patient"
    surgeon_name: str = "Attending Surgeon"


# ── POST /fhir/generate ──────────────────────────────────

@app.post("/fhir/generate")
def generate_fhir(req: FHIRGenerateRequest):
    """
    Convert a compliance report + observed events into a FHIR R4 Bundle.

    Accepts the same data the ScitePipeline produces and returns a
    transaction Bundle ready for submission to any FHIR R4 server.
    """
    report_dict = req.compliance_report.model_dump()
    events = [ev.model_dump() for ev in req.observed_events]

    bundle = build_fhir_bundle(
        compliance_report=report_dict,
        observed_events=events if events else None,
        video_url=req.video_url,
        patient_name=req.patient_name,
        surgeon_name=req.surgeon_name,
    )
    return JSONResponse(content=bundle, media_type="application/fhir+json")


# ── POST /fhir/from-pipeline/{procedure_run_id} ──────────

@app.post("/fhir/from-pipeline/{procedure_run_id}")
def fhir_from_pipeline(procedure_run_id: str, video_url: str = ""):
    """
    Fetch a stored compliance report from Supabase and convert it to FHIR.
    Requires ScitePipeline's Supabase config (.env in ScitePipeline/).
    """
    try:
        from config import get_supabase
    except Exception:
        raise HTTPException(500, "Supabase config not available. Ensure .env is set up in ScitePipeline/.")

    sb = get_supabase()

    # Fetch stored report
    resp = (
        sb.table("deviation_reports")
        .select("*")
        .eq("procedure_run_id", procedure_run_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, f"No report found for run {procedure_run_id}. Run /analyze first.")

    stored = resp.data[0]

    # Fetch procedure metadata
    run_resp = sb.table("procedure_runs").select("procedure_id").eq("id", procedure_run_id).execute()
    procedure_id = run_resp.data[0]["procedure_id"] if run_resp.data else ""
    proc_resp = sb.table("procedures").select("name").eq("id", procedure_id).execute()
    procedure_name = proc_resp.data[0]["name"] if proc_resp.data else "Unknown Procedure"

    # Fetch observed events for richer FHIR Observations
    events_resp = (
        sb.table("observed_events")
        .select("*")
        .eq("procedure_run_id", procedure_run_id)
        .order("timestamp")
        .execute()
    )
    observed_events = events_resp.data or []

    # Build node lookup for step names
    node_lookup: dict[str, dict] = {}
    if procedure_id:
        nodes_resp = sb.table("nodes").select("id, name, phase").eq("procedure_id", procedure_id).execute()
        node_lookup = {n["id"]: n for n in (nodes_resp.data or [])}

    report_dict = {
        "procedure_run_id": procedure_run_id,
        "procedure_id": procedure_id,
        "procedure_name": procedure_name,
        "compliance_score": stored.get("compliance_score", 0),
        "total_expected": stored.get("total_expected", 0),
        "total_observed": stored.get("total_observed", 0),
        "confirmed_count": stored.get("confirmed_count", 0),
        "mitigated_count": stored.get("mitigated_count", 0),
        "review_count": stored.get("review_count", 0),
        "confirmed_deviations": [d for d in stored.get("adjudicated", []) if d.get("verdict") == "confirmed"],
        "mitigated_deviations": [d for d in stored.get("adjudicated", []) if d.get("verdict") == "mitigated"],
        "review_deviations": [d for d in stored.get("adjudicated", []) if d.get("verdict") == "context_dependent"],
        "report_text": stored.get("report_text", ""),
    }

    bundle = build_fhir_bundle(
        compliance_report=report_dict,
        observed_events=observed_events,
        node_lookup=node_lookup,
        video_url=video_url,
    )
    return JSONResponse(content=bundle, media_type="application/fhir+json")


# ── POST /fhir/from-video — end-to-end pipeline ──────────

@app.post("/fhir/from-video")
async def fhir_from_video(req: FHIRFromVideoRequest):
    """
    End-to-end: interpret a surgical video → compare against SOP →
    adjudicate deviations → generate FHIR Bundle.

    This is the single-call endpoint that turns a live-stream recording
    into a standards-compliant operative report with zero manual effort.
    """
    try:
        from video_interpreter import interpret_video_from_json
        from comparator import compare, load_gold_standard
        from adjudicator import adjudicate
        from report import generate_report
        from config import get_supabase
    except ImportError as e:
        raise HTTPException(500, f"ScitePipeline modules not available: {e}")

    sop_path = Path(req.procedure_json_path)
    vid_path = Path(req.video_path)
    if not sop_path.exists():
        raise HTTPException(400, f"SOP JSON not found: {sop_path}")
    if not vid_path.exists():
        raise HTTPException(400, f"Video not found: {vid_path}")

    # Load SOP
    with open(sop_path) as f:
        sop = json.load(f)
    procedure_name = sop["procedure"]["name"]
    procedure_id = sop["procedure"]["id"]
    nodes = sop["nodes"]
    node_lookup = {n["id"]: n for n in nodes}

    # Step 1: Video → events
    logger.info("Interpreting surgical video with Gemini…")
    events, notes = interpret_video_from_json(str(sop_path), str(vid_path))

    # Step 2: Store events and compare (requires Supabase run)
    sb = get_supabase()

    run_id = f"fhir-auto-{datetime.now(timezone.utc).strftime('%y%m%d-%H%M%S')}"
    sb.table("procedure_runs").insert({
        "id": run_id,
        "procedure_id": procedure_id,
        "status": "completed",
    }).execute()

    for ev in events:
        sb.table("observed_events").insert({
            "procedure_run_id": run_id,
            "node_id": ev.node_id,
            "timestamp": ev.timestamp.isoformat(),
            "confidence": ev.confidence,
            "source": ev.source,
        }).execute()

    # Step 3: Compare
    raw_deviations = compare(procedure_id, run_id)

    # Step 4: Adjudicate
    adjudicated = await adjudicate(raw_deviations, procedure_name)

    # Step 5: Generate compliance report
    total_mandatory = sum(1 for n in nodes if n.get("mandatory"))
    compliance = generate_report(
        procedure_run_id=run_id,
        procedure_id=procedure_id,
        procedure_name=procedure_name,
        adjudicated=adjudicated,
        total_expected=total_mandatory,
        total_observed=len(events),
    )

    # Step 6: Convert to FHIR
    report_dict = compliance.model_dump()
    # Serialize datetimes for JSON
    report_dict["created_at"] = str(report_dict.get("created_at", ""))
    for key in ("confirmed_deviations", "mitigated_deviations", "review_deviations"):
        for d in report_dict.get(key, []):
            d["deviation_type"] = d["deviation_type"].value if hasattr(d["deviation_type"], "value") else d["deviation_type"]
            d["verdict"] = d["verdict"].value if hasattr(d["verdict"], "value") else d["verdict"]

    event_dicts = [
        {"node_id": ev.node_id, "timestamp": ev.timestamp.isoformat(), "confidence": ev.confidence, "source": ev.source}
        for ev in events
    ]

    bundle = build_fhir_bundle(
        compliance_report=report_dict,
        observed_events=event_dicts,
        node_lookup=node_lookup,
        patient_name=req.patient_name,
        surgeon_name=req.surgeon_name,
    )

    return JSONResponse(content=bundle, media_type="application/fhir+json")


# ── CLI helper: convert a local JSON report to FHIR ──────

def convert_report_file(report_path: str, output_path: str | None = None) -> dict:
    """
    Standalone utility: load a ComplianceReport JSON file and produce
    a FHIR Bundle. Useful for batch conversion of backlogged reports.
    """
    with open(report_path) as f:
        report_dict = json.load(f)

    bundle = build_fhir_bundle(compliance_report=report_dict)

    out = output_path or report_path.replace(".json", "_fhir.json")
    with open(out, "w") as f:
        json.dump(bundle, f, indent=2)
    print(f"FHIR Bundle written to {out}")
    return bundle


# ── Run server ────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FHIR Generation Service")
    parser.add_argument("--serve", action="store_true", help="Run FastAPI server")
    parser.add_argument("--convert", type=str, help="Convert a local report JSON to FHIR")
    parser.add_argument("--output", type=str, help="Output path for converted FHIR JSON")
    parser.add_argument("--port", type=int, default=8001, help="Server port (default 8001)")
    args = parser.parse_args()

    if args.convert:
        convert_report_file(args.convert, args.output)
    elif args.serve:
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=args.port, reload=True)
    else:
        # Default: run server
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=args.port, reload=True)

