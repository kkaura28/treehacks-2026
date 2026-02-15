"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { supabase } from "@/lib/supabase";
import { cn } from "@/lib/utils";
import type { ProcedureRun, ProcedureNode, ObservedEvent } from "@/lib/types";

// ── Types ──────────────────────────────────────────────────

interface LiveRun extends ProcedureRun {
  procedure_name: string;
  totalSteps: number;
  completedSteps: number;
  currentStep: string | null;
  currentPhase: string | null;
  events: ObservedEvent[];
  nodes: ProcedureNode[];
  elapsedMs: number;
}

// ── Helpers ────────────────────────────────────────────────

function elapsed(startedAt: string): number {
  return Date.now() - new Date(startedAt).getTime();
}

function fmtElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}m ${String(sec).padStart(2, "0")}s`;
}

function assignOR(index: number): string {
  const rooms = ["OR-1", "OR-2", "OR-3", "OR-4", "OR-5", "OR-6"];
  return rooms[index % rooms.length];
}

// ── Component ──────────────────────────────────────────────

export default function CommandCenter() {
  const [liveRuns, setLiveRuns] = useState<LiveRun[]>([]);
  const [recentRuns, setRecentRuns] = useState<LiveRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now());
  const runsRef = useRef<LiveRun[]>([]);

  // Tick every second for elapsed time
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  // ── Build a LiveRun from raw data ──────────────────────

  const buildLiveRun = useCallback(
    (run: ProcedureRun, procName: string, nodes: ProcedureNode[], events: ObservedEvent[]): LiveRun => {
      const mandatoryNodes = nodes.filter((n) => n.mandatory);
      const completedNodeIds = new Set(events.map((e) => e.node_id));
      const completedSteps = mandatoryNodes.filter((n) => completedNodeIds.has(n.id)).length;
      const lastEvent = events.length > 0 ? events[events.length - 1] : null;
      const lastNode = lastEvent ? nodes.find((n) => n.id === lastEvent.node_id) : null;

      return {
        ...run,
        procedure_name: procName,
        totalSteps: mandatoryNodes.length,
        completedSteps,
        currentStep: lastNode?.name || null,
        currentPhase: lastNode?.phase || null,
        events,
        nodes,
        elapsedMs: elapsed(run.started_at),
      };
    },
    []
  );

  // ── Initial load ───────────────────────────────────────

  const loadRuns = useCallback(async () => {
    const [runsRes, procsRes] = await Promise.all([
      supabase.from("procedure_runs").select("*").order("started_at", { ascending: false }),
      supabase.from("procedures").select("id, name"),
    ]);

    const runs: ProcedureRun[] = runsRes.data || [];
    const procMap = new Map<string, string>((procsRes.data || []).map((p: any) => [p.id, p.name]));

    // Get unique procedure IDs
    const procIds = [...new Set(runs.map((r) => r.procedure_id))];

    // Batch load nodes for all procedures
    const nodesRes = await supabase.from("nodes").select("*").in("procedure_id", procIds);
    const allNodes: ProcedureNode[] = nodesRes.data || [];
    const nodesByProc = new Map<string, ProcedureNode[]>();
    for (const n of allNodes) {
      const arr = nodesByProc.get(n.procedure_id) || [];
      arr.push(n);
      nodesByProc.set(n.procedure_id, arr);
    }

    // Batch load events for all runs
    const runIds = runs.map((r) => r.id);
    const eventsRes = await supabase.from("observed_events").select("*").in("procedure_run_id", runIds).order("timestamp");
    const allEvents: ObservedEvent[] = eventsRes.data || [];
    const eventsByRun = new Map<string, ObservedEvent[]>();
    for (const e of allEvents) {
      const arr = eventsByRun.get(e.procedure_run_id) || [];
      arr.push(e);
      eventsByRun.set(e.procedure_run_id, arr);
    }

    const liveRunsList: LiveRun[] = [];
    const recentRunsList: LiveRun[] = [];

    for (const run of runs) {
      const lr = buildLiveRun(
        run,
        procMap.get(run.procedure_id) || run.procedure_id,
        nodesByProc.get(run.procedure_id) || [],
        eventsByRun.get(run.id) || []
      );
      if (run.status === "in_progress") liveRunsList.push(lr);
      else recentRunsList.push(lr);
    }

    setLiveRuns(liveRunsList);
    setRecentRuns(recentRunsList.slice(0, 8));
    runsRef.current = liveRunsList;
    setLoading(false);
  }, [buildLiveRun]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // ── Supabase Realtime subscriptions ────────────────────

  useEffect(() => {
    // Listen for new events on in-progress runs
    const eventsChannel = supabase
      .channel("command-center-events")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "observed_events" },
        () => {
          // Reload when new events come in
          loadRuns();
        }
      )
      .subscribe();

    // Listen for run status changes
    const runsChannel = supabase
      .channel("command-center-runs")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "procedure_runs" },
        () => {
          loadRuns();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(eventsChannel);
      supabase.removeChannel(runsChannel);
    };
  }, [loadRuns]);

  // ── Render ─────────────────────────────────────────────

  const currentTime = new Date(now).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <div className="animate-fade-in -m-8 min-h-screen bg-[#0a0a0f]">
      {/* Header */}
      <div className="border-b border-zinc-800/50 bg-zinc-950/80 backdrop-blur-xl px-8 py-4 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={cn(
              "w-2.5 h-2.5 rounded-full",
              liveRuns.length > 0 ? "bg-emerald-500 animate-pulse" : "bg-zinc-600"
            )} />
            <h1 className="text-lg font-bold text-white tracking-tight">OR Command Center</h1>
          </div>
          <span className="text-xs text-zinc-600 font-mono">{liveRuns.length} active</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-zinc-500 font-mono tabular-nums">{currentTime}</span>
          <button
            onClick={loadRuns}
            className="text-xs text-zinc-500 hover:text-teal-400 transition-colors px-2 py-1 rounded border border-zinc-800 hover:border-teal-500/30"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="p-8">
        {loading ? (
          <div className="grid grid-cols-2 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-48 bg-zinc-900/50 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {/* Live Procedures */}
            {liveRuns.length > 0 ? (
              <div className="mb-10">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Live Procedures</h2>
                </div>
                <div className="grid grid-cols-2 gap-4 stagger-children">
                  {liveRuns.map((run, i) => (
                    <LiveRunCard key={run.id} run={run} orRoom={assignOR(i)} now={now} />
                  ))}
                </div>
              </div>
            ) : (
              <div className="mb-10">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-2 h-2 rounded-full bg-zinc-600" />
                  <h2 className="text-sm font-semibold text-white uppercase tracking-wider">Live Procedures</h2>
                </div>
                <div className="border border-dashed border-zinc-800 rounded-xl p-12 text-center">
                  <svg className="w-12 h-12 text-zinc-700 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-zinc-600 text-sm">No procedures in progress</p>
                  <p className="text-zinc-700 text-xs mt-1">New procedures will appear here in real-time via streaming</p>
                </div>
              </div>
            )}

            {/* Recent Completed */}
            {recentRuns.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-4">Recent Completed</h2>
                <div className="border border-zinc-800/50 rounded-xl overflow-hidden bg-zinc-900/20">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-zinc-800/50">
                        <th className="text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-5 py-3">OR</th>
                        <th className="text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-5 py-3">Procedure</th>
                        <th className="text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-5 py-3">Surgeon</th>
                        <th className="text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-5 py-3">Steps</th>
                        <th className="text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-5 py-3">Completed</th>
                        <th className="text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-5 py-3">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentRuns.map((run, i) => (
                        <tr
                          key={run.id}
                          className="border-b border-zinc-800/20 hover:bg-white/[0.02] cursor-pointer transition-all"
                          onClick={() => window.location.href = `/sessions/${run.id}`}
                        >
                          <td className="px-5 py-3 text-xs text-zinc-500 font-mono">{assignOR(liveRuns.length + i)}</td>
                          <td className="px-5 py-3 text-sm text-zinc-300 font-medium">{run.procedure_name}</td>
                          <td className="px-5 py-3 text-sm text-zinc-400">{run.surgeon_name || "—"}</td>
                          <td className="px-5 py-3 text-xs text-zinc-500 tabular-nums">{run.completedSteps}/{run.totalSteps}</td>
                          <td className="px-5 py-3 text-xs text-zinc-500">
                            {new Date(run.started_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                          </td>
                          <td className="px-5 py-3">
                            <span className={cn(
                              "px-2 py-0.5 rounded-full text-[10px] font-medium border",
                              run.status === "completed"
                                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                : "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                            )}>
                              {run.status === "completed" ? "DONE" : run.status.toUpperCase()}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Live Run Card ──────────────────────────────────────────

function LiveRunCard({ run, orRoom, now }: { run: LiveRun; orRoom: string; now: number }) {
  const pct = run.totalSteps > 0 ? Math.round((run.completedSteps / run.totalSteps) * 100) : 0;
  const elapsedMs = now - new Date(run.started_at).getTime();

  // Build step indicator dots
  const mandatoryNodes = run.nodes.filter((n) => n.mandatory);
  const completedIds = new Set(run.events.map((e) => e.node_id));

  // Find the index of the current step
  const currentNodeId = run.events.length > 0 ? run.events[run.events.length - 1].node_id : null;

  return (
    <div className="relative border border-emerald-500/20 rounded-xl bg-gradient-to-br from-zinc-900/80 to-zinc-950 overflow-hidden group hover:border-emerald-500/40 transition-all duration-300">
      {/* Glow */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/[0.03] to-transparent pointer-events-none" />

      {/* Progress bar at top */}
      <div className="h-1 bg-zinc-800">
        <div
          className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-1000"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="relative p-5">
        {/* Header row */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                {orRoom}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[10px] text-emerald-400 font-medium uppercase tracking-wider">Live</span>
              </span>
            </div>
            <h3 className="text-base font-semibold text-white">{run.procedure_name}</h3>
            <p className="text-xs text-zinc-500 mt-0.5">{run.surgeon_name || "Unknown Surgeon"}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-white tabular-nums">{pct}%</div>
            <div className="text-[10px] text-zinc-600 uppercase">complete</div>
          </div>
        </div>

        {/* Current step */}
        {run.currentStep && (
          <div className="mb-4 px-3 py-2 rounded-lg bg-white/[0.03] border border-zinc-800/50">
            <div className="text-[10px] text-zinc-600 uppercase tracking-wider mb-0.5">Current Step</div>
            <div className="text-sm text-white font-medium">{run.currentStep}</div>
          </div>
        )}

        {/* Step dots */}
        <div className="flex gap-1 mb-4 flex-wrap">
          {mandatoryNodes.map((node) => {
            const isDone = completedIds.has(node.id);
            const isCurrent = node.id === currentNodeId;
            return (
              <div
                key={node.id}
                title={node.name}
                className={cn(
                  "h-2 rounded-full transition-all duration-500",
                  mandatoryNodes.length <= 12 ? "flex-1" : "w-2",
                  isDone
                    ? "bg-emerald-500"
                    : isCurrent
                      ? "bg-teal-400 animate-pulse"
                      : "bg-zinc-800"
                )}
              />
            );
          })}
        </div>

        {/* Footer stats */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            <span className="text-zinc-500">
              <span className="text-zinc-300 font-medium tabular-nums">{run.completedSteps}</span>/{run.totalSteps} steps
            </span>
            <span className="text-zinc-500 font-mono tabular-nums">{fmtElapsed(elapsedMs)}</span>
          </div>
          <button
            onClick={() => window.location.href = `/sessions/${run.id}`}
            className="text-zinc-600 hover:text-teal-400 transition-colors"
          >
            View details →
          </button>
        </div>
      </div>
    </div>
  );
}

