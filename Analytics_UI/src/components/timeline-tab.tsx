"use client";
import { useRef, useMemo, useState } from "react";
import type { ObservedEvent, ProcedureNode, DeviationReport, StrokeSegment } from "@/lib/types";
import { cn, formatTimestamp, formatTimestampPrecise } from "@/lib/utils";
import { PhaseBadge } from "./badges";

interface Props {
  events: ObservedEvent[];
  nodes: ProcedureNode[];
  report: DeviationReport | null;
}

const STROKE_COLORS: Record<string, string> = {
  cut: "text-red-400 bg-red-500/10 border-red-500/20",
  spread: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  grasp: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  retract: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  cauterize: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  suture: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  irrigate: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  dissect: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  other: "text-zinc-400 bg-zinc-500/10 border-zinc-500/20",
};


export function TimelineTab({ events, nodes, report }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const tipVideoRef = useRef<HTMLVideoElement>(null);
  const [expandedEvents, setExpandedEvents] = useState<Set<number>>(new Set());

  const nodeMap = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes]);
  const deviationNodeIds = useMemo(() => {
    if (!report) return new Set<string>();
    return new Set(report.adjudicated.map(d => d.node_id));
  }, [report]);

  const videoPath = events[0]?.metadata?.video_path;
  const hasVideo = !!videoPath;
  const hasTipVideo = videoPath === "surgery_video.mp4";

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

  const missingNodes = useMemo(() => {
    const observed = new Set(events.map(e => e.node_id));
    return nodes.filter(n => n.mandatory && !observed.has(n.id));
  }, [events, nodes]);

  function seekTo(seconds: number) {
    if (videoRef.current) videoRef.current.currentTime = seconds;
    if (tipVideoRef.current) tipVideoRef.current.currentTime = seconds;
  }

  function toggleExpand(eventId: number) {
    setExpandedEvents(prev => {
      const next = new Set(prev);
      if (next.has(eventId)) next.delete(eventId);
      else next.add(eventId);
      return next;
    });
  }

  return (
    <div className="grid grid-cols-12 gap-6 animate-fade-in">
      {hasVideo && (
        <div className="col-span-5">
          <div className="sticky top-8 space-y-3">
            <div className="gradient-border overflow-hidden glow-teal">
              <div className="px-3 pt-2 pb-1 text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Surgery Feed</div>
              <video
                ref={videoRef}
                controls
                className="w-full aspect-video bg-black"
                src={`/videos/${videoPath}`}
              >
                <source src={`/videos/${videoPath}`} type="video/mp4" />
              </video>
            </div>
            {hasTipVideo && (<>
              <div className="gradient-border overflow-hidden">
                <div className="px-3 pt-2 pb-1 text-[10px] font-medium text-zinc-500 uppercase tracking-wider">Instrument Tip Tracking</div>
                <video
                  ref={tipVideoRef}
                  controls
                  className="w-full aspect-video bg-black"
                  src="/videos/surgery_video_tip.mp4"
                >
                  <source src="/videos/surgery_video_tip.mp4" type="video/mp4" />
                </video>
              </div>
              <div className="gradient-border overflow-hidden">
                <div className="px-3 pt-2 pb-1 text-[10px] font-medium text-zinc-500 uppercase tracking-wider">SAM 2 Segmentation Mask</div>
                <video
                  controls
                  className="w-full aspect-video bg-black"
                  src="/videos/surgery_video_mask.mp4"
                >
                  <source src="/videos/surgery_video_mask.mp4" type="video/mp4" />
                </video>
              </div>
            </>)}
            <div className="text-xs text-zinc-500 px-1">
              Click events to seek video to that timestamp
            </div>
          </div>
        </div>
      )}

      <div className={cn(hasVideo ? "col-span-7" : "col-span-12")}>
        {!hasVideo && (
          <div className="gradient-border px-4 py-3 mb-6 flex items-center gap-3 bg-zinc-900/50">
            <svg className="w-4 h-4 text-zinc-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
            <span className="text-xs text-zinc-500">No video available for this session — timestamps below are relative to procedure start</span>
          </div>
        )}
        <div className="space-y-6 stagger-children">
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
                  const strokes = ev.metadata?.strokes;
                  const hasStrokes = strokes && strokes.length > 0;
                  const isExpanded = expandedEvents.has(ev.id);

                  return (
                    <div key={ev.id || i}>
                    <div
                      onClick={() => seekTo(ts)}
                      className={cn(
                        "gradient-border px-4 py-3 cursor-pointer hover:bg-white/[0.03] transition-all duration-200 group",
                        hasDeviation && "!border-red-500/30 before:!bg-gradient-to-r before:!from-red-500/20 before:!to-transparent"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono text-teal-400/70 w-12">{formatTimestamp(ts)}</span>
                          <span className="text-sm font-medium text-white group-hover:text-teal-400 transition-colors">{node?.name || ev.node_id}</span>
                          {hasDeviation && (
                            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                          )}
                        </div>
                          {hasStrokes && (
                            <button
                              onClick={(e) => { e.stopPropagation(); toggleExpand(ev.id); }}
                              className={cn(
                                "flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium border transition-all",
                                isExpanded
                                  ? "bg-teal-500/10 text-teal-400 border-teal-500/20"
                                  : "bg-white/[0.03] text-zinc-500 border-zinc-800/50 hover:text-teal-400 hover:border-teal-500/20"
                              )}
                            >
                              <svg className={cn("w-3 h-3 transition-transform", isExpanded && "rotate-180")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                              {strokes!.length} strokes
                            </button>
                          )}
                      </div>
                      {observation && (
                        <p className="text-xs text-zinc-500 mt-2 italic leading-relaxed">{observation}</p>
                        )}
                      </div>

                      {/* Stroke sub-items */}
                      {hasStrokes && isExpanded && (
                        <div className="ml-6 mt-1 mb-2 border-l-2 border-zinc-800/50 pl-4 space-y-1.5 animate-fade-in">
                          {strokes!.map((stroke, si) => (
                            <div
                              key={si}
                              onClick={() => seekTo(stroke.timestamp_seconds)}
                              className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] cursor-pointer transition-all group/stroke"
                            >
                              <span className="text-[10px] font-mono text-zinc-600 w-20 shrink-0">
                                {formatTimestampPrecise(stroke.timestamp_seconds)}–{formatTimestampPrecise(stroke.end_seconds)}
                              </span>
                              <span className="text-[10px] text-zinc-600 font-mono capitalize shrink-0 w-14">{stroke.instrument}</span>
                              <span className={cn(
                                "px-1.5 py-0.5 rounded text-[10px] font-medium border capitalize shrink-0",
                                STROKE_COLORS[stroke.stroke_type] || STROKE_COLORS.other
                              )}>
                                {stroke.stroke_type}
                              </span>
                              <span className="text-xs text-zinc-400 group-hover/stroke:text-zinc-300 transition-colors truncate">
                                {stroke.description}
                              </span>
                            </div>
                          ))}
                        </div>
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
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/15 text-red-400 border border-red-500/20">Missing</span>
                <span className="text-xs text-zinc-500">{missingNodes.length} expected steps not observed</span>
              </div>
              <div className="space-y-2">
                {missingNodes.map((node) => (
                  <div key={node.id} className="gradient-border px-4 py-3 opacity-50">
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
