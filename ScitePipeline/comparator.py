"""
Graph comparison engine.

Diffs observed events against the gold-standard procedure graph from Supabase.
Produces a list of RawDeviation objects.
"""

from models import Node, Edge, ObservedEvent, RawDeviation, DeviationType
from config import get_supabase


def load_gold_standard(procedure_id: str) -> tuple[list[Node], list[Edge]]:
    """Fetch the expected nodes and edges for a procedure from Supabase."""
    sb = get_supabase()

    nodes_resp = sb.table("nodes").select("*").eq("procedure_id", procedure_id).execute()
    edges_resp = sb.table("edges").select("*").eq("procedure_id", procedure_id).execute()

    nodes = [Node(**row) for row in nodes_resp.data]
    edges = [Edge(**row) for row in edges_resp.data]
    return nodes, edges


def load_observed_events(procedure_run_id: str) -> list[ObservedEvent]:
    """Fetch observed events for a procedure run, ordered by timestamp."""
    sb = get_supabase()

    resp = (
        sb.table("observed_events")
        .select("*")
        .eq("procedure_run_id", procedure_run_id)
        .order("timestamp")
        .execute()
    )
    return [ObservedEvent(**row) for row in resp.data]


def _topological_order(nodes: list[Node], edges: list[Edge]) -> list[str]:
    """
    Compute a topological ordering of sequential edges.
    Used to determine expected step ordering.
    """
    seq_edges = [e for e in edges if e.type == "sequential"]
    adjacency: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {}

    all_ids = {n.id for n in nodes}
    for nid in all_ids:
        adjacency[nid] = []
        in_degree[nid] = 0

    for e in seq_edges:
        adjacency[e.from_node].append(e.to_node)
        in_degree[e.to_node] = in_degree.get(e.to_node, 0) + 1

    # Kahn's algorithm
    queue = [nid for nid in all_ids if in_degree.get(nid, 0) == 0]
    order = []
    while queue:
        queue.sort()  # deterministic tie-breaking
        node = queue.pop(0)
        order.append(node)
        for neighbor in adjacency.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order


def compare(
    procedure_id: str,
    procedure_run_id: str,
) -> list[RawDeviation]:
    """
    Main comparison function.

    Returns a list of deviations found between the observed events
    and the gold-standard procedure graph.
    """
    nodes, edges = load_gold_standard(procedure_id)
    observed = load_observed_events(procedure_run_id)

    node_map = {n.id: n for n in nodes}
    observed_ids = {ev.node_id for ev in observed}
    observed_order = [ev.node_id for ev in observed]
    topo_order = _topological_order(nodes, edges)
    topo_index = {nid: i for i, nid in enumerate(topo_order)}

    deviations: list[RawDeviation] = []

    # ── 1. Missing mandatory steps ─────────────────────────
    for node in nodes:
        if node.mandatory and node.id not in observed_ids:
            dev_type = (
                DeviationType.SKIPPED_SAFETY
                if node.safety_critical
                else DeviationType.MISSING
            )
            deviations.append(RawDeviation(
                node_id=node.id,
                node_name=node.name,
                phase=node.phase,
                deviation_type=dev_type,
                mandatory=node.mandatory,
                safety_critical=node.safety_critical,
                context=f"Mandatory step '{node.name}' was not observed during the procedure.",
            ))

    # ── 2. Out-of-order steps ──────────────────────────────
    # Check sequential edges: if A→B is sequential, A must appear before B
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

    # ── 3. Precondition violations ─────────────────────────
    # If a node was observed but its preconditions were NOT observed
    for ev in observed:
        node = node_map.get(ev.node_id)
        if not node or not node.preconditions:
            continue
        for pre_id in node.preconditions:
            pre_node = node_map.get(pre_id)
            if pre_node and pre_node.mandatory and pre_id not in observed_ids:
                # Only flag if not already captured as a missing step
                already_flagged = any(
                    d.node_id == ev.node_id
                    and d.deviation_type == DeviationType.OUT_OF_ORDER
                    for d in deviations
                )
                if not already_flagged:
                    deviations.append(RawDeviation(
                        node_id=ev.node_id,
                        node_name=node.name,
                        phase=node.phase,
                        deviation_type=DeviationType.OUT_OF_ORDER,
                        mandatory=node.mandatory,
                        safety_critical=node.safety_critical,
                        context=(
                            f"'{node.name}' was performed but its required "
                            f"precondition '{pre_node.name}' was not observed."
                        ),
                    ))

    # Deduplicate by (node_id, deviation_type)
    seen = set()
    unique: list[RawDeviation] = []
    for d in deviations:
        key = (d.node_id, d.deviation_type)
        if key not in seen:
            seen.add(key)
            unique.append(d)

    return unique

