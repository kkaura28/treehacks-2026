"""
Mock event generator for demo purposes.

Creates a realistic lap chole event timeline with deliberate deviations:
  1. critical_view_of_safety — MISSING (hard safety violation)
  2. clip_cystic_duct before clip_cystic_artery — OUT OF ORDER
  3. who_time_out — happens but antibiotic given AFTER (timing issue)

When the CV model is ready, it just writes to the same observed_events table.
"""

from datetime import datetime, timedelta, timezone
from config import get_supabase


# ── Simulated lap chole timeline ───────────────────────────
# Each tuple: (node_id, minutes_offset_from_start)
# Deviations are commented inline.

MOCK_PROCEDURE_ID = "laparoscopic_cholecystectomy"

MOCK_TIMELINE: list[tuple[str, int]] = [
    ("who_sign_in",                         0),
    ("general_anesthesia",                   3),
    ("patient_positioning",                  8),
    ("who_time_out",                        12),
    # DEVIATION: antibiotic_prophylaxis is missing entirely (given in pre-op
    # but not recorded, or simply forgotten — system can't tell)
    ("establish_pneumoperitoneum",          14),
    ("trocar_placement",                    17),
    ("diagnostic_laparoscopy",              19),
    ("gallbladder_retraction",              21),
    ("calot_triangle_dissection",           24),
    # DEVIATION: critical_view_of_safety is SKIPPED — hard safety violation
    # Surgeon goes straight to clipping without documenting CVS.
    # DEVIATION: clip_cystic_duct BEFORE clip_cystic_artery (order swap)
    ("clip_cystic_duct",                    30),
    ("clip_cystic_artery",                  32),
    ("divide_cystic_duct",                  34),
    ("divide_cystic_artery",                35),
    ("gallbladder_dissection_from_liver_bed", 38),
    ("hemostasis_check",                    43),
    ("specimen_extraction",                 45),
    ("desufflation",                        47),
    ("port_site_closure",                   49),
    ("who_sign_out",                        52),
]


def generate_mock_events(
    supabase_client=None,
    surgeon_name: str = "Dr. Demo",
    base_time: datetime | None = None,
) -> dict:
    """
    Creates a procedure_run and inserts observed_events into Supabase.
    Returns {"procedure_run_id": ..., "event_count": ...}.
    """
    sb = supabase_client or get_supabase()
    base = base_time or datetime.now(timezone.utc)

    # 1. Create procedure run
    run = sb.table("procedure_runs").insert({
        "procedure_id": MOCK_PROCEDURE_ID,
        "surgeon_name": surgeon_name,
        "started_at": base.isoformat(),
        "ended_at": (base + timedelta(minutes=52)).isoformat(),
        "status": "completed",
    }).execute()

    run_id = run.data[0]["id"]

    # 2. Insert observed events
    events = []
    for node_id, offset_min in MOCK_TIMELINE:
        events.append({
            "procedure_run_id": run_id,
            "node_id": node_id,
            "timestamp": (base + timedelta(minutes=offset_min)).isoformat(),
            "confidence": 1.0,
            "source": "mock",
        })

    sb.table("observed_events").insert(events).execute()

    return {"procedure_run_id": run_id, "event_count": len(events)}


if __name__ == "__main__":
    result = generate_mock_events()
    print(f"Created procedure run: {result['procedure_run_id']}")
    print(f"Inserted {result['event_count']} mock events")
    print("\nDeliberate deviations baked in:")
    print("  1. critical_view_of_safety — MISSING")
    print("  2. clip_cystic_duct before clip_cystic_artery — OUT OF ORDER")
    print("  3. antibiotic_prophylaxis — MISSING (not recorded)")

