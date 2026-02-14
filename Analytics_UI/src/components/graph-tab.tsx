"use client";
import { useMemo, useState, useCallback } from "react";
import { ReactFlow, Background, Controls, type Node as FlowNode, type Edge as FlowEdge, Position, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ProcedureNode, ProcedureEdge, ObservedEvent, DeviationReport, AdjudicatedDeviation } from "@/lib/types";
import { PhaseBadge, SafetyCriticalFlag } from "./badges";

interface Props {
  nodes: ProcedureNode[];
  edges: ProcedureEdge[];
  events: ObservedEvent[];
  report: DeviationReport | null;
}

export function GraphTab({ nodes, edges, events, report }: Props) {
  const [selected, setSelected] = useState<ProcedureNode | null>(null);

  const observedIds = useMemo(() => new Set(events.map(e => e.node_id)), [events]);
  const deviationMap = useMemo(() => {
    const m = new Map<string, AdjudicatedDeviation>();
    if (report) {
      for (const d of report.adjudicated) m.set(d.node_id, d);
    }
    return m;
  }, [report]);

  // Topological layout: compute x/y positions
  const { flowNodes, flowEdges } = useMemo(() => {
    // Build adjacency for sequential edges
    const seqChildren = new Map<string, string[]>();
    const inDeg = new Map<string, number>();
    for (const n of nodes) {
      seqChildren.set(n.id, []);
      inDeg.set(n.id, 0);
    }
    for (const e of edges) {
      if (e.type === "sequential") {
        seqChildren.get(e.from_node)?.push(e.to_node);
        inDeg.set(e.to_node, (inDeg.get(e.to_node) || 0) + 1);
      }
    }

    // BFS for layers
    const layers: string[][] = [];
    let queue = nodes.filter(n => (inDeg.get(n.id) || 0) === 0).map(n => n.id);
    const visited = new Set<string>();
    while (queue.length > 0) {
      layers.push([...queue]);
      const next: string[] = [];
      for (const nid of queue) {
        visited.add(nid);
        for (const child of seqChildren.get(nid) || []) {
          const newDeg = (inDeg.get(child) || 1) - 1;
          inDeg.set(child, newDeg);
          if (newDeg === 0 && !visited.has(child)) next.push(child);
        }
      }
      queue = next;
    }
    // Add any remaining nodes not in sequential flow
    const unvisited = nodes.filter(n => !visited.has(n.id));
    if (unvisited.length > 0) layers.push(unvisited.map(n => n.id));

    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const flowNodes: FlowNode[] = [];

    for (let layerIdx = 0; layerIdx < layers.length; layerIdx++) {
      const layer = layers[layerIdx];
      for (let i = 0; i < layer.length; i++) {
        const nid = layer[i];
        const node = nodeMap.get(nid)!;
        const dev = deviationMap.get(nid);
        const observed = observedIds.has(nid);

        let bg = "#27272a"; // zinc-800 default
        let border = "#3f3f46"; // zinc-700
        let textColor = "#a1a1aa"; // zinc-400
        if (dev?.deviation_type === "skipped_safety" || dev?.deviation_type === "missing") {
          bg = "#450a0a"; border = "#dc2626"; textColor = "#fca5a5";
        } else if (dev?.deviation_type === "out_of_order") {
          bg = "#431407"; border = "#ea580c"; textColor = "#fdba74";
        } else if (observed) {
          bg = "#052e16"; border = "#16a34a"; textColor = "#86efac";
        }

        flowNodes.push({
          id: nid,
          position: { x: 80 + i * 220, y: 60 + layerIdx * 100 },
          data: {
            label: node.name,
          },
          sourcePosition: Position.Bottom,
          targetPosition: Position.Top,
          style: {
            background: bg,
            border: `1.5px solid ${border}`,
            color: textColor,
            borderRadius: "8px",
            padding: "8px 12px",
            fontSize: "11px",
            fontWeight: 500,
            width: 200,
            textAlign: "center" as const,
          },
        });
      }
    }

    const flowEdges: FlowEdge[] = edges.map((e, i) => ({
      id: `e-${i}`,
      source: e.from_node,
      target: e.to_node,
      type: "smoothstep",
      animated: e.type === "conditional",
      style: {
        stroke: e.type === "sequential" ? "#52525b" : "#3b82f680",
        strokeDasharray: e.type === "conditional" ? "5 5" : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: e.type === "sequential" ? "#52525b" : "#3b82f680" },
    }));

    return { flowNodes, flowEdges };
  }, [nodes, edges, observedIds, deviationMap]);

  const nodeMap = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes]);

  const onNodeClick = useCallback((_: unknown, node: FlowNode) => {
    setSelected(nodeMap.get(node.id) || null);
  }, [nodeMap]);

  return (
    <div className="grid grid-cols-12 gap-6">
      <div className={selected ? "col-span-8" : "col-span-12"}>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden" style={{ height: 600 }}>
          <ReactFlow
            nodes={flowNodes}
            edges={flowEdges}
            onNodeClick={onNodeClick}
            fitView
            minZoom={0.3}
            maxZoom={1.5}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#27272a" gap={20} />
            <Controls className="!bg-zinc-800 !border-zinc-700 !text-zinc-300 [&>button]:!bg-zinc-800 [&>button]:!border-zinc-700 [&>button]:!text-zinc-300 [&>button:hover]:!bg-zinc-700" />
          </ReactFlow>
        </div>
        <div className="flex items-center gap-4 mt-3 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-green-900 border border-green-600" /> Observed</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-red-950 border border-red-600" /> Missing/Skipped</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-orange-950 border border-orange-600" /> Out of Order</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-zinc-800 border border-zinc-700" /> Not Observed</span>
          <span className="flex items-center gap-1.5"><span className="w-6 border-t border-dashed border-blue-500" /> Conditional</span>
        </div>
      </div>

      {selected && (
        <div className="col-span-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 sticky top-8">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white">{selected.name}</h3>
              <button onClick={() => setSelected(null)} className="text-zinc-500 hover:text-white text-xs">Close</button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex items-center gap-2">
                <PhaseBadge phase={selected.phase} />
                <SafetyCriticalFlag critical={selected.safety_critical} />
                {selected.mandatory && <span className="text-xs text-yellow-400">Mandatory</span>}
              </div>
              <div>
                <div className="text-xs text-zinc-500 mb-1">Status</div>
                <div className="text-sm">
                  {observedIds.has(selected.id) ? (
                    <span className="text-green-400">Observed</span>
                  ) : (
                    <span className="text-red-400">Not observed</span>
                  )}
                  {deviationMap.has(selected.id) && (
                    <span className="ml-2 text-red-300">({deviationMap.get(selected.id)!.deviation_type})</span>
                  )}
                </div>
              </div>
              {selected.actors.length > 0 && (
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Actors</div>
                  <div className="flex flex-wrap gap-1">
                    {selected.actors.map(a => <span key={a} className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">{a}</span>)}
                  </div>
                </div>
              )}
              {selected.required_tools.length > 0 && (
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Required Tools</div>
                  <div className="flex flex-wrap gap-1">
                    {selected.required_tools.map(t => <span key={t} className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">{t.replace(/_/g, " ")}</span>)}
                  </div>
                </div>
              )}
              {selected.preconditions.length > 0 && (
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Preconditions</div>
                  <div className="flex flex-wrap gap-1">
                    {selected.preconditions.map(p => {
                      const pNode = nodeMap.get(p);
                      return <span key={p} className="px-2 py-0.5 bg-zinc-800 rounded text-xs text-zinc-300">{pNode?.name || p}</span>;
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

