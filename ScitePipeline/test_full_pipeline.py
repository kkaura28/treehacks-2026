"""
Full end-to-end pipeline test.

Runs the entire flow:
  1. Load gold-standard graph (from Supabase or local JSON fallback)
  2. Generate mock observed events with deliberate deviations
  3. Compare observed vs. expected → raw deviations
  4. Adjudicate each deviation via scite + DeBERTa NLI
  5. Generate compliance report

Usage:
  python test_full_pipeline.py              # tries Supabase, falls back to local
  python test_full_pipeline.py --local      # skip Supabase, use local JSON
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from models import (
    Node, Edge, ObservedEvent, RawDeviation, DeviationType,
    AdjudicatedDeviation, Verdict, ComplianceReport,
)
from adjudicator import adjudicate
from report import generate_report


# ── Gold standard graph (local fallback) ───────────────────

def _load_local_graph() -> tuple[list[Node], list[Edge]]:
    """Load the lap chole graph from the local JSON file."""
    json_path = Path(__file__).parent.parent / "SOP" / "data" / "lap_chole_data" / "laparoscopic_cholecystectomy.json"
    with open(json_path) as f:
        data = json.load(f)

    nodes = [
        Node(
            id=n["id"],
            procedure_id="laparoscopic_cholecystectomy",
            name=n["name"],
            phase=n["phase"],
            mandatory=n["mandatory"],
            optional=n["optional"],
            safety_critical=n["safety_critical"],
            actors=n.get("actors", []),
            required_tools=n.get("required_tools", []),
            preconditions=n.get("preconditions", []),
        )
        for n in data["nodes"]
    ]
    edges = [
        Edge(from_node=e["from"], to_node=e["to"], type=e["type"])
        for e in data["edges"]
    ]
    return nodes, edges


def _load_supabase_graph() -> tuple[list[Node], list[Edge]] | None:
    """Try loading from Supabase. Returns None if not configured."""
    try:
        from config import get_supabase, get_settings
        settings = get_settings()
        if not settings.supabase_url or "your-project" in settings.supabase_url:
            return None

        sb = get_supabase()
        nodes_resp = sb.table("nodes").select("*").eq("procedure_id", "laparoscopic_cholecystectomy").execute()
        edges_resp = sb.table("edges").select("*").eq("procedure_id", "laparoscopic_cholecystectomy").execute()

        if not nodes_resp.data:
            return None

        nodes = [Node(**row) for row in nodes_resp.data]
        edges = [Edge(**row) for row in edges_resp.data]
        return nodes, edges
    except Exception as e:
        print(f"  Supabase not available: {e}")
        return None


# ── Mock events (same as mock_events.py but in-memory) ─────

MOCK_TIMELINE = [
    ("who_sign_in", 0),
    ("general_anesthesia", 3),
    ("patient_positioning", 8),
    ("who_time_out", 12),
    # MISSING: antibiotic_prophylaxis
    ("establish_pneumoperitoneum", 14),
    ("trocar_placement", 17),
    ("diagnostic_laparoscopy", 19),
    ("gallbladder_retraction", 21),
    ("calot_triangle_dissection", 24),
    # MISSING: critical_view_of_safety
    ("clip_cystic_duct", 30),        # OUT OF ORDER (should be after clip_cystic_artery)
    ("clip_cystic_artery", 32),
    ("divide_cystic_duct", 34),
    ("divide_cystic_artery", 35),
    ("gallbladder_dissection_from_liver_bed", 38),
    ("hemostasis_check", 43),
    ("specimen_extraction", 45),
    ("desufflation", 47),
    ("port_site_closure", 49),
    ("who_sign_out", 52),
]


def _generate_mock_events() -> list[ObservedEvent]:
    base = datetime.now(timezone.utc)
    return [
        ObservedEvent(
            node_id=node_id,
            timestamp=base + timedelta(minutes=offset),
            confidence=1.0,
            source="mock",
        )
        for node_id, offset in MOCK_TIMELINE
    ]


# ── Local comparator (no Supabase dependency) ──────────────

def _compare_local(
    nodes: list[Node],
    edges: list[Edge],
    observed: list[ObservedEvent],
) -> list[RawDeviation]:
    """Graph comparison engine — runs entirely in memory."""
    node_map = {n.id: n for n in nodes}
    observed_ids = {ev.node_id for ev in observed}
    observed_order = [ev.node_id for ev in observed]

    deviations: list[RawDeviation] = []

    # 1. Missing mandatory steps
    for node in nodes:
        if node.mandatory and node.id not in observed_ids:
            dev_type = (
                DeviationType.SKIPPED_SAFETY if node.safety_critical
                else DeviationType.MISSING
            )
            deviations.append(RawDeviation(
                node_id=node.id,
                node_name=node.name,
                phase=node.phase,
                deviation_type=dev_type,
                mandatory=node.mandatory,
                safety_critical=node.safety_critical,
                context=f"Mandatory step '{node.name}' was not observed.",
            ))

    # 2. Out-of-order (sequential edge violations)
    seq_edges = [e for e in edges if e.type == "sequential"]
    for edge in seq_edges:
        if edge.from_node in observed_ids and edge.to_node in observed_ids:
            from_idx = observed_order.index(edge.from_node)
            to_idx = observed_order.index(edge.to_node)
            if from_idx > to_idx:
                node = node_map.get(edge.to_node)
                if node:
                    deviations.append(RawDeviation(
                        node_id=edge.to_node,
                        node_name=node.name,
                        phase=node.phase,
                        deviation_type=DeviationType.OUT_OF_ORDER,
                        mandatory=node.mandatory,
                        safety_critical=node.safety_critical,
                        context=(
                            f"'{node.name}' was observed before "
                            f"'{node_map[edge.from_node].name}', "
                            f"violating expected sequential order."
                        ),
                    ))

    # 3. Precondition violations
    for ev in observed:
        node = node_map.get(ev.node_id)
        if not node or not node.preconditions:
            continue
        for pre_id in node.preconditions:
            pre_node = node_map.get(pre_id)
            if pre_node and pre_node.mandatory and pre_id not in observed_ids:
                already = any(
                    d.node_id == ev.node_id and d.deviation_type == DeviationType.OUT_OF_ORDER
                    for d in deviations
                )
                if not already:
                    deviations.append(RawDeviation(
                        node_id=ev.node_id,
                        node_name=node.name,
                        phase=node.phase,
                        deviation_type=DeviationType.OUT_OF_ORDER,
                        mandatory=node.mandatory,
                        safety_critical=node.safety_critical,
                        context=(
                            f"'{node.name}' was performed but precondition "
                            f"'{pre_node.name}' was not observed."
                        ),
                    ))

    # Deduplicate
    seen = set()
    unique = []
    for d in deviations:
        key = (d.node_id, d.deviation_type)
        if key not in seen:
            seen.add(key)
            unique.append(d)

    return unique


# ── Main test ──────────────────────────────────────────────

async def main():
    use_local = "--local" in sys.argv

    print("=" * 70)
    print("FULL PIPELINE TEST — Laparoscopic Cholecystectomy")
    print("=" * 70)
    print()

    # Step 1: Load graph
    print("[1/5] Loading gold-standard procedure graph...")
    graph = None
    if not use_local:
        graph = _load_supabase_graph()
        if graph:
            print("  ✓ Loaded from Supabase")

    if not graph:
        graph = _load_local_graph()
        print("  ✓ Loaded from local JSON")

    nodes, edges = graph
    mandatory_count = sum(1 for n in nodes if n.mandatory)
    print(f"  Nodes: {len(nodes)} ({mandatory_count} mandatory)")
    print(f"  Edges: {len(edges)}")
    print()

    # Step 2: Generate mock events
    print("[2/5] Generating mock observed events...")
    observed = _generate_mock_events()
    print(f"  ✓ Generated {len(observed)} events")
    print("  Deliberate deviations:")
    print("    - critical_view_of_safety: MISSING")
    print("    - antibiotic_prophylaxis: MISSING")
    print("    - clip_cystic_duct before clip_cystic_artery: OUT OF ORDER")
    print()

    # Step 3: Compare
    print("[3/5] Running graph comparison...")
    raw_deviations = _compare_local(nodes, edges, observed)
    print(f"  ✓ Found {len(raw_deviations)} deviations:")
    for d in raw_deviations:
        print(f"    - {d.node_id}: {d.deviation_type.value}")
    print()

    # Step 4: Adjudicate via scite + NLI
    print("[4/5] Adjudicating deviations (scite API + DeBERTa NLI)...")
    print("  Loading NLI model (first time may take ~5s)...")
    adjudicated = await adjudicate(raw_deviations, "Laparoscopic Cholecystectomy")
    print(f"  ✓ Adjudicated {len(adjudicated)} deviations:")
    for a in adjudicated:
        print(f"    - {a.node_id}: {a.verdict.value.upper()}")
    print()

    # Step 5: Generate report
    print("[5/5] Generating compliance report...")
    report = generate_report(
        procedure_run_id="test-run-001",
        procedure_id="laparoscopic_cholecystectomy",
        procedure_name="Laparoscopic Cholecystectomy",
        adjudicated=adjudicated,
        total_expected=mandatory_count,
        total_observed=len(observed),
    )
    print()
    print(report.report_text)

    # Save report to file
    report_path = Path(__file__).parent / "test_report_output.txt"
    report_path.write_text(report.report_text)
    print(f"\nReport saved to: {report_path}")

    # Also save JSON
    json_path = Path(__file__).parent / "test_report_output.json"
    json_path.write_text(json.dumps(report.model_dump(), indent=2, default=str))
    print(f"JSON saved to: {json_path}")


if __name__ == "__main__":
    asyncio.run(main())

