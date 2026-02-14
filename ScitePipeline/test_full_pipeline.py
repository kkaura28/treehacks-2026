"""
Full end-to-end pipeline test.

Supports three event sources:
  --mock       Use hardcoded mock events with deliberate deviations (default)
  --video FILE Use Gemini to interpret a surgical video
  --local      Skip Supabase, load graph from local JSON (always on for now)

Usage:
  python test_full_pipeline.py                              # mock events, lap chole
  python test_full_pipeline.py --video path/to/surgery.mp4  # Gemini video analysis
  python test_full_pipeline.py --video surgery.mp4 --procedure incision_drainage_abscess
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from models import (
    Node, Edge, ObservedEvent, RawDeviation, DeviationType,
    AdjudicatedDeviation, Verdict, ComplianceReport,
)
from adjudicator import adjudicate
from report import generate_report


# ── Argument parsing ───────────────────────────────────────

def _parse_args():
    args = {
        "source": "mock",
        "video_path": None,
        "procedure": "laparoscopic_cholecystectomy",
        "model": "gemini-2.5-pro",
    }
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--video" and i + 1 < len(argv):
            args["source"] = "video"
            args["video_path"] = argv[i + 1]
            i += 2
        elif argv[i] == "--mock":
            args["source"] = "mock"
            i += 1
        elif argv[i] == "--procedure" and i + 1 < len(argv):
            args["procedure"] = argv[i + 1]
            i += 2
        elif argv[i] == "--model" and i + 1 < len(argv):
            args["model"] = argv[i + 1]
            i += 2
        elif argv[i] == "--local":
            i += 1  # always local for now
        else:
            i += 1
    return args


# ── Graph loading ──────────────────────────────────────────

# Map procedure IDs to their JSON file paths
_PROCEDURE_JSON_MAP = {
    "laparoscopic_cholecystectomy": "SOP/data/lap_chole_data/laparoscopic_cholecystectomy.json",
    "cesarean_section": "SOP/data/c-section_data/cesarean_section.json",
    "laparoscopic_appendectomy": "SOP/data/appendectomy_data/laparoscopic_appendectomy.json",
    "incision_drainage_abscess": "SOP/data/abcess_data/incision_drainage_abscess.json",
}


def _load_graph(procedure_id: str) -> tuple[list[Node], list[Edge], str, list[dict]]:
    """
    Load procedure graph from local JSON.
    Returns (nodes, edges, procedure_name, raw_node_dicts).
    """
    rel_path = _PROCEDURE_JSON_MAP.get(procedure_id)
    if not rel_path:
        raise ValueError(
            f"Unknown procedure '{procedure_id}'. "
            f"Available: {list(_PROCEDURE_JSON_MAP.keys())}"
        )

    json_path = Path(__file__).parent.parent / rel_path
    if not json_path.exists():
        raise FileNotFoundError(f"Procedure JSON not found: {json_path}")

    with open(json_path) as f:
        data = json.load(f)

    procedure_name = data["procedure"]["name"]
    raw_nodes = data["nodes"]

    nodes = [
        Node(
            id=n["id"],
            procedure_id=procedure_id,
            name=n["name"],
            phase=n["phase"],
            mandatory=n["mandatory"],
            optional=n["optional"],
            safety_critical=n["safety_critical"],
            actors=n.get("actors", []),
            required_tools=n.get("required_tools", []),
            preconditions=n.get("preconditions", []),
        )
        for n in raw_nodes
    ]
    edges = [
        Edge(from_node=e["from"], to_node=e["to"], type=e["type"])
        for e in data["edges"]
    ]
    return nodes, edges, procedure_name, raw_nodes


# ── Event sources ──────────────────────────────────────────

MOCK_LAP_CHOLE_TIMELINE = [
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
    ("clip_cystic_duct", 30),  # OUT OF ORDER
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

MOCK_ABSCESS_TIMELINE = [
    ("patient_identification", 0),
    ("allergy_check", 1),
    ("equipment_preparation", 3),
    # MISSING: site_marking
    ("sterile_preparation", 5),
    ("local_anesthesia", 7),
    ("incision", 9),
    ("drainage_expression", 10),
    ("loculation_breakdown", 12),
    # MISSING: wound_irrigation
    ("wound_packing", 14),
    ("external_dressing", 15),
    ("discharge_instructions", 17),
]


def _get_mock_timeline(procedure_id: str) -> list[tuple[str, int]]:
    timelines = {
        "laparoscopic_cholecystectomy": MOCK_LAP_CHOLE_TIMELINE,
        "incision_drainage_abscess": MOCK_ABSCESS_TIMELINE,
    }
    if procedure_id not in timelines:
        raise ValueError(
            f"No mock timeline for '{procedure_id}'. "
            f"Use --video instead, or pick from: {list(timelines.keys())}"
        )
    return timelines[procedure_id]


def _generate_mock_events(procedure_id: str) -> list[ObservedEvent]:
    timeline = _get_mock_timeline(procedure_id)
    base = datetime.now(timezone.utc)
    return [
        ObservedEvent(
            node_id=node_id,
            timestamp=base + timedelta(minutes=offset),
            confidence=1.0,
            source="mock",
        )
        for node_id, offset in timeline
    ]


def _get_video_events(
    video_path: str,
    procedure_name: str,
    raw_nodes: list[dict],
    model_name: str,
) -> tuple[list[ObservedEvent], str]:
    from video_interpreter import interpret_video
    return interpret_video(
        video_path=video_path,
        procedure_name=procedure_name,
        nodes=raw_nodes,
        model_name=model_name,
    )


# ── Local comparator ──────────────────────────────────────

def _compare_local(
    nodes: list[Node],
    edges: list[Edge],
    observed: list[ObservedEvent],
) -> list[RawDeviation]:
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
                node_id=node.id, node_name=node.name, phase=node.phase,
                deviation_type=dev_type, mandatory=node.mandatory,
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
                        node_id=edge.to_node, node_name=node.name,
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
                    d.node_id == ev.node_id
                    and d.deviation_type == DeviationType.OUT_OF_ORDER
                    for d in deviations
                )
                if not already:
                    deviations.append(RawDeviation(
                        node_id=ev.node_id, node_name=node.name,
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


# ── Main ───────────────────────────────────────────────────

async def main():
    args = _parse_args()
    procedure_id = args["procedure"]
    source = args["source"]

    print("=" * 70)
    print(f"FULL PIPELINE TEST")
    print(f"  Source: {source.upper()}")
    print(f"  Procedure: {procedure_id}")
    if source == "video":
        print(f"  Video: {args['video_path']}")
        print(f"  Model: {args['model']}")
    print("=" * 70)
    print()

    # Step 1: Load graph
    print("[1/5] Loading gold-standard procedure graph...")
    nodes, edges, procedure_name, raw_nodes = _load_graph(procedure_id)
    mandatory_count = sum(1 for n in nodes if n.mandatory)
    print(f"  Procedure: {procedure_name}")
    print(f"  Nodes: {len(nodes)} ({mandatory_count} mandatory)")
    print(f"  Edges: {len(edges)}")
    print()

    # Step 2: Get observed events
    gemini_notes = ""
    if source == "video":
        video_path = args["video_path"]
        if not Path(video_path).exists():
            print(f"  ERROR: Video file not found: {video_path}")
            sys.exit(1)

        print(f"[2/5] Interpreting video with Gemini ({args['model']})...")
        print(f"  Uploading and processing video (may take 30-60s)...")
        observed, gemini_notes = _get_video_events(
            video_path=video_path,
            procedure_name=procedure_name,
            raw_nodes=raw_nodes,
            model_name=args["model"],
        )
        print(f"  Gemini detected {len(observed)} events:")
        for ev in observed:
            print(f"    - {ev.node_id} (confidence: {ev.confidence:.0%})")
        if gemini_notes:
            print(f"  Gemini notes: {gemini_notes[:200]}")
    else:
        print("[2/5] Generating mock observed events...")
        observed = _generate_mock_events(procedure_id)
        print(f"  Generated {len(observed)} mock events")

    print()

    # Step 3: Compare
    print("[3/5] Running graph comparison...")
    raw_deviations = _compare_local(nodes, edges, observed)
    print(f"  Found {len(raw_deviations)} deviations:")
    for d in raw_deviations:
        print(f"    - {d.node_id}: {d.deviation_type.value}")
    print()

    # Step 4: Adjudicate
    if raw_deviations:
        print("[4/5] Adjudicating deviations (scite API + DeBERTa NLI)...")
        print("  Loading NLI model (first time ~5s)...")
        adjudicated = await adjudicate(raw_deviations, procedure_name)
        print(f"  Adjudicated {len(adjudicated)} deviations:")
        for a in adjudicated:
            print(f"    - {a.node_id}: {a.verdict.value.upper()}")
    else:
        adjudicated = []
        print("[4/5] No deviations to adjudicate — full compliance!")
    print()

    # Step 5: Generate report
    print("[5/5] Generating compliance report...")
    run_id = f"{'video' if source == 'video' else 'mock'}-{procedure_id[:10]}-{datetime.now().strftime('%H%M%S')}"
    report = generate_report(
        procedure_run_id=run_id,
        procedure_id=procedure_id,
        procedure_name=procedure_name,
        adjudicated=adjudicated,
        total_expected=mandatory_count,
        total_observed=len(observed),
    )

    # Append Gemini notes to report if from video
    report_text = report.report_text
    if gemini_notes:
        report_text += f"\n\nGEMINI OBSERVATIONS:\n{gemini_notes}"

    print()
    print(report_text)

    # Save outputs
    out_dir = Path(__file__).parent
    txt_path = out_dir / f"report_{run_id}.txt"
    json_path = out_dir / f"report_{run_id}.json"

    txt_path.write_text(report_text)

    report_dict = report.model_dump()
    report_dict["source"] = source
    report_dict["gemini_notes"] = gemini_notes
    if source == "video":
        report_dict["video_path"] = args["video_path"]
        report_dict["gemini_model"] = args["model"]
    report_dict["detected_events"] = [
        {"node_id": ev.node_id, "confidence": ev.confidence, "source": ev.source}
        for ev in observed
    ]
    json_path.write_text(json.dumps(report_dict, indent=2, default=str))

    print(f"\nReport saved to: {txt_path}")
    print(f"JSON saved to: {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
