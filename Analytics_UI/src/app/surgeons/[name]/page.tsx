"use client";
import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { cn, scoreColor, formatDuration } from "@/lib/utils";
import type { ProcedureRun, DeviationReport, AdjudicatedDeviation } from "@/lib/types";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
  BarChart, Bar, Cell, PieChart, Pie,
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";

interface KinematicsData {
  fps: number;
  instruments: { name: string; frames: number; duration_seconds: number; unit: string; path_length: number; motion_economy: number; idle_fraction: number; movement_count: number; smoothness_sparc: number; tremor_index: number; mean_speed: number; max_speed: number; source: string; bimanual_correlation?: number }[];
  goals: { domain: string; score: number; max: number }[];
  overall_score: number;
}

interface SessionRow extends ProcedureRun {
  report?: DeviationReport;
  procedure_name?: string;
}

export default function SurgeonDetail() {
  const params = useParams();
  const name = decodeURIComponent(params.name as string);

  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [kinematics, setKinematics] = useState<KinematicsData | null>(null);

  useEffect(() => {
    fetch("/data/kinematics.json").then(r => r.json()).then(setKinematics).catch(() => {});
  }, []);

  useEffect(() => {
    async function load() {
      const [runsRes, reportsRes, procsRes] = await Promise.all([
        supabase.from("procedure_runs").select("*").eq("surgeon_name", name).order("started_at"),
        supabase.from("deviation_reports").select("*"),
        supabase.from("procedures").select("id, name"),
      ]);

      const reportMap = new Map((reportsRes.data || []).map((r: any) => [r.procedure_run_id, r]));
      const procMap = new Map((procsRes.data || []).map((p: any) => [p.id, p.name]));

      const rows: SessionRow[] = (runsRes.data || []).map((run: any) => ({
        ...run,
        report: reportMap.get(run.id),
        procedure_name: procMap.get(run.procedure_id),
      }));

      setSessions(rows);
      setLoading(false);
    }
    load();
  }, [name]);

  // Compute analytics
  const analytics = useMemo(() => {
    const withReports = sessions.filter((s) => s.report);
    if (withReports.length === 0) return null;

    const scores = withReports.map((s) => s.report!.compliance_score);
    const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
    const best = Math.max(...scores);
    const latest = scores[scores.length - 1];

    // Trend line data
    const trendData = withReports.map((s, i) => ({
      session: i + 1,
      date: new Date(s.started_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      compliance: Math.round(s.report!.compliance_score * 100),
      procedure: s.procedure_name || s.procedure_id,
    }));

    // Improvement: linear regression slope
    const n = scores.length;
    const xMean = (n - 1) / 2;
    const yMean = scores.reduce((a, b) => a + b, 0) / n;
    const slope = n > 1
      ? scores.reduce((s, y, i) => s + (i - xMean) * (y - yMean), 0) / scores.reduce((s, _, i) => s + (i - xMean) ** 2, 0)
      : 0;

    // Deviation type breakdown
    const devCounts: Record<string, number> = {};
    for (const s of withReports) {
      for (const d of (s.report!.adjudicated as AdjudicatedDeviation[])) {
        devCounts[d.deviation_type] = (devCounts[d.deviation_type] || 0) + 1;
      }
    }
    const devBreakdown = Object.entries(devCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([type, count]) => ({ type: type.replace(/_/g, " "), count }));

    // Most common deviation nodes
    const nodeCounts: Record<string, number> = {};
    for (const s of withReports) {
      for (const d of (s.report!.adjudicated as AdjudicatedDeviation[])) {
        if (d.verdict === "confirmed") {
          nodeCounts[d.node_name] = (nodeCounts[d.node_name] || 0) + 1;
        }
      }
    }
    const topNodes = Object.entries(nodeCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([node, count]) => ({ node, count }));

    // Verdict distribution
    const verdictCounts = { confirmed: 0, mitigated: 0, context_dependent: 0 };
    for (const s of withReports) {
      for (const d of (s.report!.adjudicated as AdjudicatedDeviation[])) {
        verdictCounts[d.verdict] = (verdictCounts[d.verdict] || 0) + 1;
      }
    }

    const totalDevs = Object.values(verdictCounts).reduce((a, b) => a + b, 0);

    return { avg, best, latest, slope, trendData, devBreakdown, topNodes, verdictCounts, totalDevs, sessionCount: withReports.length };
  }, [sessions]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-zinc-800 rounded animate-pulse" />
        <div className="h-12 bg-zinc-800 rounded animate-pulse" />
        <div className="h-96 bg-zinc-800 rounded animate-pulse" />
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="animate-fade-in">
        <a href="/surgeons" className="text-sm text-zinc-500 hover:text-blue-400 transition-colors">&larr; All surgeons</a>
        <h2 className="text-3xl font-bold text-white mt-2">{name}</h2>
        <div className="text-zinc-500 mt-8">No session data with reports found for this surgeon.</div>
      </div>
    );
  }

  const DEV_COLORS: Record<string, string> = {
    missing: "#ef4444",
    "out of order": "#f59e0b",
    "skipped safety": "#dc2626",
    "unhandled complication": "#a855f7",
  };

  const VERDICT_COLORS = { confirmed: "#ef4444", mitigated: "#22c55e", context_dependent: "#f59e0b" };

  const improvementPct = Math.round(analytics.slope * analytics.sessionCount * 100);

  return (
    <div className="animate-fade-in">
      <a href="/surgeons" className="text-sm text-zinc-500 hover:text-blue-400 transition-colors">&larr; All surgeons</a>
      <h2 className="text-3xl font-bold text-white mt-2 tracking-tight">{name}</h2>
      <p className="text-sm text-zinc-400 mt-1">{analytics.sessionCount} session{analytics.sessionCount !== 1 ? "s" : ""} analyzed</p>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4 mt-6 stagger-children">
        <div className="gradient-border p-5 glow-teal">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Avg Compliance</div>
          <div className={cn("text-4xl font-bold mt-2 tabular-nums", scoreColor(analytics.avg))}>{Math.round(analytics.avg * 100)}%</div>
        </div>
        <div className="gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Best Score</div>
          <div className={cn("text-4xl font-bold mt-2 tabular-nums", scoreColor(analytics.best))}>{Math.round(analytics.best * 100)}%</div>
        </div>
        <div className="gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Latest Score</div>
          <div className={cn("text-4xl font-bold mt-2 tabular-nums", scoreColor(analytics.latest))}>{Math.round(analytics.latest * 100)}%</div>
        </div>
        <div className="gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Improvement</div>
          <div className={cn(
            "text-4xl font-bold mt-2 tabular-nums",
            improvementPct > 0 ? "text-emerald-400" : improvementPct < 0 ? "text-red-400" : "text-zinc-400"
          )}>
            {improvementPct > 0 ? "+" : ""}{improvementPct}%
          </div>
        </div>
      </div>

      {/* Compliance Trend Chart */}
      <div className="gradient-border p-6 mt-6">
        <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-4">Compliance Over Time</div>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={analytics.trendData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="date" tick={{ fill: "#71717a", fontSize: 11 }} axisLine={{ stroke: "#27272a" }} />
            <YAxis domain={[0, 100]} tick={{ fill: "#71717a", fontSize: 11 }} axisLine={{ stroke: "#27272a" }} tickFormatter={(v) => `${v}%`} />
            <ReferenceLine y={80} stroke="#22c55e" strokeDasharray="6 4" strokeOpacity={0.4} label={{ value: "Target 80%", fill: "#22c55e", fontSize: 10, position: "right" }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#a1a1aa" }}
              formatter={(value, _name, entry: any) => [`${value}%`, entry?.payload?.procedure]}
            />
            <Line
              type="monotone"
              dataKey="compliance"
              stroke="#3b82f6"
              strokeWidth={2.5}
              dot={{ fill: "#3b82f6", r: 4, stroke: "#18181b", strokeWidth: 2 }}
              activeDot={{ r: 6, stroke: "#3b82f6", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Deviation Analysis Row */}
      <div className="grid grid-cols-12 gap-6 mt-6">
        {/* Deviation Type Breakdown */}
        <div className="col-span-4 gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-4">Deviation Types</div>
          {analytics.devBreakdown.length > 0 ? (
            <div className="space-y-3">
              {analytics.devBreakdown.map((d) => {
                const pct = analytics.totalDevs > 0 ? (d.count / analytics.totalDevs) * 100 : 0;
                return (
                  <div key={d.type}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-zinc-300 capitalize">{d.type}</span>
                      <span className="text-xs text-zinc-500 tabular-nums">{d.count}</span>
                    </div>
                    <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, backgroundColor: DEV_COLORS[d.type] || "#6b7280" }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-zinc-600">No deviations recorded</div>
          )}

          {/* Verdict mini-summary */}
          {analytics.totalDevs > 0 && (
            <div className="mt-6 pt-4 border-t border-zinc-800/50">
              <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-3">Verdict Breakdown</div>
              <div className="flex gap-4">
                {(Object.entries(analytics.verdictCounts) as [string, number][]).filter(([,c]) => c > 0).map(([v, c]) => (
                  <div key={v} className="text-center">
                    <div className="text-lg font-bold tabular-nums" style={{ color: VERDICT_COLORS[v as keyof typeof VERDICT_COLORS] }}>{c}</div>
                    <div className="text-[10px] text-zinc-600 capitalize">{v.replace(/_/g, " ")}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Top Repeated Deviations */}
        <div className="col-span-8 gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-4">Most Frequent Confirmed Deviations</div>
          {analytics.topNodes.length > 0 ? (
            <div className="space-y-2 stagger-children">
              {analytics.topNodes.map((d, i) => (
                <div key={d.node} className="flex items-center gap-4 bg-white/[0.02] hover:bg-white/[0.04] rounded-lg px-4 py-3 transition-all border border-zinc-800/30">
                  <span className="w-6 h-6 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center text-xs font-bold text-red-400 shrink-0">
                    {i + 1}
                  </span>
                  <span className="text-sm text-white font-medium flex-1">{d.node}</span>
                  <span className="text-sm text-red-400 font-semibold tabular-nums">{d.count}×</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-zinc-600">No confirmed deviations — excellent compliance!</div>
          )}

          {analytics.topNodes.length > 0 && (
            <div className="mt-4 p-3 rounded-lg bg-blue-500/5 border border-blue-500/10">
              <p className="text-xs text-blue-300/80 leading-relaxed">
                <span className="font-medium text-blue-400">Training Focus:</span> These steps are repeatedly flagged across sessions. Targeted practice on <span className="text-white font-medium">{analytics.topNodes[0].node}</span> could have the highest impact on compliance scores.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Motion Analytics */}
      {kinematics && (
        <div className="mt-6">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-4">Motion Analytics</div>
          <div className="grid grid-cols-12 gap-6">
            {/* GOALS Radar */}
            <div className="col-span-5 gradient-border p-5">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">GOALS Assessment</div>
                <div className={cn(
                  "px-3 py-1 rounded-full text-xs font-semibold border",
                  kinematics.overall_score >= 60
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-red-500/10 text-red-400 border-red-500/20"
                )}>
                  {kinematics.overall_score}/100
                </div>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <RadarChart data={kinematics.goals.map(g => ({ domain: g.domain, score: g.score, fullMark: 5 }))} cx="50%" cy="50%">
                  <PolarGrid stroke="#27272a" />
                  <PolarAngleAxis dataKey="domain" tick={{ fill: "#a1a1aa", fontSize: 10, dy: -6 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 5]} tick={{ fill: "#52525b", fontSize: 9 }} axisLine={false} />
                  <Radar name="Score" dataKey="score" stroke="#2dd4bf" fill="#2dd4bf" fillOpacity={0.15} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Per-instrument summary cards */}
            <div className="col-span-7 space-y-3">
              {kinematics.instruments.map((inst) => {
                const srcColor = inst.source === "hamer" ? "text-pink-400 bg-pink-500/10 border-pink-500/20"
                  : inst.source === "foundation_pose" ? "text-violet-400 bg-violet-500/10 border-violet-500/20"
                  : "text-blue-400 bg-blue-500/10 border-blue-500/20";
                const srcLabel = inst.source === "hamer" ? "HaMeR" : inst.source === "foundation_pose" ? "FoundationPose" : "Optical Flow";
                const idle = Math.round(inst.idle_fraction * 100);
                return (
                  <div key={inst.name} className="gradient-border px-5 py-3.5 hover:bg-white/[0.02] transition-all">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-sm font-medium text-white">{inst.name}</span>
                      <span className={cn("px-1.5 py-0.5 rounded-full text-[9px] font-medium border", srcColor)}>{srcLabel}</span>
                      <span className="text-[10px] text-zinc-600 ml-auto">{inst.frames} frames · {inst.duration_seconds}s</span>
                    </div>
                    <div className="grid grid-cols-5 gap-3">
                      <div>
                        <div className="text-[10px] text-zinc-600">Path Length</div>
                        <div className="text-sm font-semibold text-white tabular-nums">
                          {inst.unit === "m" ? inst.path_length.toFixed(1) : Math.round(inst.path_length)}
                          <span className="text-[10px] text-zinc-600 ml-0.5">{inst.unit}</span>
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-zinc-600">Idle</div>
                        <div className={cn("text-sm font-semibold tabular-nums", idle > 50 ? "text-amber-400" : "text-emerald-400")}>{idle}%</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-zinc-600">Moves</div>
                        <div className="text-sm font-semibold text-white tabular-nums">{inst.movement_count}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-zinc-600">Smoothness</div>
                        <div className="text-sm font-semibold text-white tabular-nums">{Math.round(inst.smoothness_sparc)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-zinc-600">Tremor</div>
                        <div className={cn("text-sm font-semibold tabular-nums",
                          inst.unit === "m" ? (inst.tremor_index < 0.03 ? "text-emerald-400" : "text-amber-400") : (inst.tremor_index < 10 ? "text-emerald-400" : "text-amber-400")
                        )}>
                          {inst.unit === "m" ? inst.tremor_index.toFixed(3) : inst.tremor_index.toFixed(1)}
                          <span className="text-[10px] text-zinc-600 ml-0.5">{inst.unit}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Session History Table */}
      <div className="mt-6">
        <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-4">Session History</div>
        <div className="border border-zinc-800/50 rounded-xl overflow-hidden bg-zinc-900/30 backdrop-blur-sm">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800/50">
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">#</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Date</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Procedure</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Duration</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Compliance</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Deviations</th>
              </tr>
            </thead>
            <tbody className="stagger-children">
              {[...sessions].reverse().map((s, i) => {
                const score = s.report?.compliance_score;
                const devs = (s.report?.confirmed_count || 0) + (s.report?.mitigated_count || 0) + (s.report?.review_count || 0);
                return (
                  <tr
                    key={s.id}
                    className="border-b border-zinc-800/30 hover:bg-white/[0.02] cursor-pointer transition-all group"
                    onClick={() => window.location.href = `/sessions/${s.id}`}
                  >
                    <td className="px-5 py-3.5 text-sm text-zinc-500 tabular-nums">{sessions.length - i}</td>
                    <td className="px-5 py-3.5 text-sm text-zinc-300">
                      {new Date(s.started_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-white font-medium group-hover:text-blue-400 transition-colors">{s.procedure_name || s.procedure_id}</td>
                    <td className="px-5 py-3.5 text-sm text-zinc-400">{formatDuration(s.started_at, s.ended_at)}</td>
                    <td className="px-5 py-3.5">
                      {score !== undefined ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 bg-zinc-800 rounded-full overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                score >= 0.8 ? "bg-gradient-to-r from-green-500 to-emerald-400" :
                                score >= 0.5 ? "bg-gradient-to-r from-yellow-500 to-amber-400" :
                                "bg-gradient-to-r from-red-500 to-rose-400"
                              )}
                              style={{ width: `${Math.round(score * 100)}%` }}
                            />
                          </div>
                          <span className={cn("text-sm font-semibold tabular-nums", scoreColor(score))}>{Math.round(score * 100)}%</span>
                        </div>
                      ) : (
                        <span className="text-sm text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {devs > 0 ? (
                        <span className="text-sm text-red-400 font-medium">{devs}</span>
                      ) : (
                        <span className="text-sm text-emerald-400">Clean</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

