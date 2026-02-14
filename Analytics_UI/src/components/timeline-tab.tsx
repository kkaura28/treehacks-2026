"use client";
import { useRef, useMemo } from "react";
import type { ObservedEvent, ProcedureNode, DeviationReport } from "@/lib/types";
import { cn, formatTimestamp, phaseColor } from "@/lib/utils";
import { ConfidenceBar, PhaseBadge } from "./badges";

interface Props {
  events: ObservedEvent[];
  nodes: ProcedureNode[];
  report: DeviationReport | null;
}

export function TimelineTab({ events, nodes, report }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  const nodeMap = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes]);
  const deviationNodeIds = useMemo(() => {
    if (!report) return new Set<string>();
    return new Set(report.adjudicated.map(d => d.node_id));
  }, [report]);

  const videoPath = events[0]?.metadata?.video_path;
  const hasVideo = !!videoPath;

  // Group events by phase
  const grouped = useMemo(() => {
    const groups: Record<string, ObservedEvent[]> = {};
    for (const ev of events) {
      const node = nodeMap.get(ev.node_id);
      const phase = node?.phase || "unknown";
      if (!groups[phase]) groups[phase] = [];
      groups[phase].push(ev);
    }
    return groups;
  }, [events, nodeMap]);

  // Missing expected nodes
  const missingNodes = useMemo(() => {
    const observed = new Set(events.map(e => e.node_id));
    return nodes.filter(n => n.mandatory && !observed.has(n.id));
  }, [events, nodes]);

  function seekTo(seconds: number) {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play();
    }
  }

  return (
    <div className="grid grid-cols-12 gap-6">
      {hasVideo && (
        <div className="col-span-5">
          <div className="sticky top-8 bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
            <video
              ref={videoRef}
              controls
              className="w-full aspect-video bg-black"
              src={`/videos/${videoPath}`}
            >
              <source src={`/videos/${videoPath}`} type="video/mp4" />
            </video>
            <div className="p-3 text-xs text-zinc-500">
              Click events to seek video to that timestamp
            </div>
          </div>
        </div>
      )}

      <div className={cn(hasVideo ? "col-span-7" : "col-span-12")}>
        <div className="space-y-6">
          {Object.entries(grouped).map(([phase, phaseEvents]) => (
            <div key={phase}>
              <div className="flex items-center gap-2 mb-3">
                <PhaseBadge phase={phase} />
                <span className="text-xs text-zinc-500">{phaseEvents.length} events</span>
              </div>
              <div className="space-y-2">
                {phaseEvents.map((ev, i) => {
                  const node = nodeMap.get(ev.node_id);
                  const ts = ev.metadata?.timestamp_seconds ?? 0;
                  const hasDeviation = deviationNodeIds.has(ev.node_id);
                  const observation = ev.metadata?.observation;

                  return (
                    <div
                      key={ev.id || i}
                      onClick={() => seekTo(ts)}
                      className={cn(
                        "bg-zinc-900 border rounded-lg px-4 py-3 cursor-pointer hover:bg-zinc-800/70 transition-colors",
                        hasDeviation ? "border-red-500/30" : "border-zinc-800"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono text-zinc-500 w-12">{formatTimestamp(ts)}</span>
                          <span className="text-sm font-medium text-white">{node?.name || ev.node_id}</span>
                          {hasDeviation && (
                            <span className="w-2 h-2 rounded-full bg-red-500" />
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "px-1.5 py-0.5 rounded text-xs",
                            ev.source === "mock" ? "bg-zinc-700 text-zinc-400" : "bg-blue-500/20 text-blue-400"
                          )}>
                            {ev.metadata?.original_source || ev.source}
                          </span>
                        </div>
                      </div>
                      <div className="mt-2">
                        <ConfidenceBar value={ev.confidence} label="Confidence" />
                      </div>
                      {observation && (
                        <p className="text-xs text-zinc-500 mt-2 italic">{observation}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {missingNodes.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/20 text-red-400">Missing</span>
                <span className="text-xs text-zinc-500">{missingNodes.length} expected steps not observed</span>
              </div>
              <div className="space-y-2">
                {missingNodes.map((node) => (
                  <div key={node.id} className="bg-zinc-900 border border-red-500/20 rounded-lg px-4 py-3 opacity-60">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-zinc-600 w-12">--:--</span>
                      <span className="text-sm text-zinc-500 line-through">{node.name}</span>
                      <PhaseBadge phase={node.phase} />
                      {node.safety_critical && (
                        <span className="text-xs text-red-400">safety critical</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

