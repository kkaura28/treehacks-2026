"""
FastAPI orchestrator for the post-op compliance analysis pipeline.

Endpoints:
  POST /mock          — generate mock events for a demo run
  POST /analyze/{id}  — run full analysis on a completed procedure run
  GET  /report/{id}   — retrieve a stored report
"""

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from config import get_supabase
from mock_events import generate_mock_events
from comparator import compare
from adjudicator import adjudicate
from report import generate_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify Supabase connection
    sb = get_supabase()
    yield


app = FastAPI(
    title="Surgical Compliance Pipeline",
    description="Post-op analysis: graph comparison + OpenEvidence adjudication",
    version="0.1.0",
    lifespan=lifespan,
)


# ── POST /mock ─────────────────────────────────────────────

@app.post("/mock")
def create_mock_run():
    """Generate a mock procedure run with deliberate deviations."""
    result = generate_mock_events()
    return {
        "status": "created",
        "procedure_run_id": result["procedure_run_id"],
        "event_count": result["event_count"],
        "deviations_baked_in": [
            "critical_view_of_safety — MISSING",
            "clip_cystic_duct before clip_cystic_artery — OUT OF ORDER",
            "antibiotic_prophylaxis — MISSING",
        ],
    }


# ── POST /analyze/{procedure_run_id} ──────────────────────

@app.post("/analyze/{procedure_run_id}")
async def analyze_procedure(procedure_run_id: str):
    """
    Run the full post-op analysis pipeline:
      1. Load observed events from Supabase
      2. Compare against gold-standard graph
      3. Adjudicate deviations via OpenEvidence
      4. Generate and store compliance report
    """
    sb = get_supabase()

    # Fetch the procedure run
    run_resp = (
        sb.table("procedure_runs")
        .select("*")
        .eq("id", procedure_run_id)
        .execute()
    )
    if not run_resp.data:
        raise HTTPException(404, f"Procedure run {procedure_run_id} not found")

    run = run_resp.data[0]
    procedure_id = run["procedure_id"]

    # Get procedure metadata
    proc_resp = (
        sb.table("procedures")
        .select("*")
        .eq("id", procedure_id)
        .execute()
    )
    if not proc_resp.data:
        raise HTTPException(404, f"Procedure {procedure_id} not found")

    procedure_name = proc_resp.data[0]["name"]

    # Count expected mandatory nodes
    nodes_resp = (
        sb.table("nodes")
        .select("id")
        .eq("procedure_id", procedure_id)
        .eq("mandatory", True)
        .execute()
    )
    total_expected = len(nodes_resp.data)

    # Count observed events
    events_resp = (
        sb.table("observed_events")
        .select("id")
        .eq("procedure_run_id", procedure_run_id)
        .execute()
    )
    total_observed = len(events_resp.data)

    # ── Step 1: Compare ────────────────────────────────────
    raw_deviations = compare(procedure_id, procedure_run_id)

    # ── Step 2: Adjudicate via OpenEvidence ────────────────
    adjudicated = await adjudicate(raw_deviations, procedure_name)

    # ── Step 3: Generate report ────────────────────────────
    compliance_report = generate_report(
        procedure_run_id=procedure_run_id,
        procedure_id=procedure_id,
        procedure_name=procedure_name,
        adjudicated=adjudicated,
        total_expected=total_expected,
        total_observed=total_observed,
    )

    # ── Step 4: Store in Supabase ──────────────────────────
    sb.table("deviation_reports").upsert({
        "procedure_run_id": procedure_run_id,
        "compliance_score": compliance_report.compliance_score,
        "total_expected": compliance_report.total_expected,
        "total_observed": compliance_report.total_observed,
        "confirmed_count": compliance_report.confirmed_count,
        "mitigated_count": compliance_report.mitigated_count,
        "review_count": compliance_report.review_count,
        "raw_deviations": [d.model_dump() for d in raw_deviations],
        "adjudicated": [d.model_dump() for d in adjudicated],
        "report_text": compliance_report.report_text,
    }).execute()

    return compliance_report.model_dump()


# ── GET /report/{procedure_run_id} ─────────────────────────

@app.get("/report/{procedure_run_id}")
def get_report(procedure_run_id: str):
    """Retrieve a stored compliance report."""
    sb = get_supabase()
    resp = (
        sb.table("deviation_reports")
        .select("*")
        .eq("procedure_run_id", procedure_run_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Report not found. Run /analyze first.")
    return resp.data[0]


# ── GET /report/{procedure_run_id}/text ────────────────────

@app.get("/report/{procedure_run_id}/text")
def get_report_text(procedure_run_id: str):
    """Retrieve just the human-readable report text."""
    sb = get_supabase()
    resp = (
        sb.table("deviation_reports")
        .select("report_text")
        .eq("procedure_run_id", procedure_run_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(404, "Report not found. Run /analyze first.")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(resp.data[0]["report_text"])


# ── Run server ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

