"use client";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { cn, scoreColor } from "@/lib/utils";

interface SurgeonSummary {
  name: string;
  sessionCount: number;
  avgCompliance: number;
  totalDeviations: number;
  latestSession: string;
  trend: number; // positive = improving
}

export default function Surgeons() {
  const [surgeons, setSurgeons] = useState<SurgeonSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [runsRes, reportsRes] = await Promise.all([
        supabase.from("procedure_runs").select("id, surgeon_name, started_at").order("started_at"),
        supabase.from("deviation_reports").select("procedure_run_id, compliance_score, confirmed_count, mitigated_count, review_count"),
      ]);

      const runs = runsRes.data || [];
      const reports = reportsRes.data || [];
      const reportMap = new Map(reports.map((r: any) => [r.procedure_run_id, r]));

      // Group by surgeon
      const byName = new Map<string, typeof runs>();
      for (const run of runs) {
        if (!run.surgeon_name) continue;
        const arr = byName.get(run.surgeon_name) || [];
        arr.push(run);
        byName.set(run.surgeon_name, arr);
      }

      const summaries: SurgeonSummary[] = [];
      for (const [name, sRuns] of byName) {
        const withReports = sRuns.map((r: any) => ({ ...r, report: reportMap.get(r.id) })).filter((r: any) => r.report);
        if (withReports.length === 0) continue;

        const scores = withReports.map((r: any) => r.report.compliance_score as number);
        const avg = scores.reduce((a: number, b: number) => a + b, 0) / scores.length;
        const totalDevs = withReports.reduce((s: number, r: any) => s + (r.report.confirmed_count || 0) + (r.report.mitigated_count || 0) + (r.report.review_count || 0), 0);

        // Trend: compare last half avg to first half avg
        let trend = 0;
        if (scores.length >= 2) {
          const mid = Math.floor(scores.length / 2);
          const firstHalf = scores.slice(0, mid).reduce((a: number, b: number) => a + b, 0) / mid;
          const secondHalf = scores.slice(mid).reduce((a: number, b: number) => a + b, 0) / (scores.length - mid);
          trend = secondHalf - firstHalf;
        }

        summaries.push({
          name,
          sessionCount: withReports.length,
          avgCompliance: avg,
          totalDeviations: totalDevs,
          latestSession: sRuns[sRuns.length - 1].started_at,
          trend,
        });
      }

      summaries.sort((a, b) => b.sessionCount - a.sessionCount);
      setSurgeons(summaries);
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="relative mb-10 rounded-2xl overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-indigo-500/5 to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(59,130,246,0.08),transparent_60%)]" />
        <div className="relative p-8">
          <h2 className="text-3xl font-bold text-white tracking-tight">Surgeon Performance</h2>
          <p className="text-sm text-zinc-400 mt-1">Track compliance trends and skill progression across sessions</p>

        </div>
      </div>

      {loading ? (
        <div className="space-y-3 stagger-children">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-zinc-900/50 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : surgeons.length === 0 ? (
        <div className="text-zinc-500 text-center py-20">No surgeon data found.</div>
      ) : (
        <div className="space-y-3 stagger-children">
          {surgeons.map((s) => (
            <a
              key={s.name}
              href={`/surgeons/${encodeURIComponent(s.name)}`}
              className="gradient-border p-5 flex items-center gap-5 hover:bg-white/[0.03] transition-all duration-200 group cursor-pointer"
            >
              <div className="w-12 h-12 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
                <span className="text-lg font-bold text-blue-400">{s.name.charAt(0).toUpperCase()}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-semibold text-white group-hover:text-blue-400 transition-colors">{s.name}</h3>
                  {s.trend > 0.02 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>
                      IMPROVING
                    </span>
                  )}
                  {s.trend < -0.02 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-500/10 text-red-400 border border-red-500/20 flex items-center gap-1">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>
                      DECLINING
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 mt-1.5">
                  <span className="text-xs text-zinc-500">{s.sessionCount} session{s.sessionCount !== 1 ? "s" : ""}</span>
                  <span className="text-xs text-zinc-600">·</span>
                  <span className="text-xs text-zinc-500">{s.totalDeviations} deviation{s.totalDeviations !== 1 ? "s" : ""}</span>
                  <span className="text-xs text-zinc-600">·</span>
                  <span className="text-xs text-zinc-500">Last: {new Date(s.latestSession).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <div className="text-right">
                  <div className={cn("text-lg font-bold tabular-nums", scoreColor(s.avgCompliance))}>{Math.round(s.avgCompliance * 100)}%</div>
                  <div className="text-[10px] text-zinc-600 uppercase">avg compliance</div>
                </div>
                <svg className="w-5 h-5 text-zinc-600 group-hover:text-blue-400 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

