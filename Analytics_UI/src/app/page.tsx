"use client";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { cn, scoreColor } from "@/lib/utils";

interface ProcedureSummary {
  id: string;
  name: string;
  sessionCount: number;
  avgCompliance: number;
  totalDeviations: number;
}

export default function Home() {
  const [procedures, setProcedures] = useState<ProcedureSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [procsRes, runsRes, reportsRes] = await Promise.all([
        supabase.from("procedures").select("id, name"),
        supabase.from("procedure_runs").select("id, procedure_id"),
        supabase.from("deviation_reports").select("procedure_run_id, compliance_score, confirmed_count, mitigated_count, review_count"),
      ]);

      const procs = procsRes.data || [];
      const runs = runsRes.data || [];
      const reports = reportsRes.data || [];

      const reportMap = new Map(reports.map((r: any) => [r.procedure_run_id, r]));

      const summaries: ProcedureSummary[] = procs.map((p: any) => {
        const procRuns = runs.filter((r: any) => r.procedure_id === p.id);
        const procReports = procRuns.map((r: any) => reportMap.get(r.id)).filter(Boolean);
        const avgScore = procReports.length > 0
          ? procReports.reduce((s: number, r: any) => s + (r.compliance_score || 0), 0) / procReports.length
          : 0;
        const totalDevs = procReports.reduce((s: number, r: any) => s + (r.confirmed_count || 0) + (r.mitigated_count || 0) + (r.review_count || 0), 0);

        return {
          id: p.id,
          name: p.name,
          sessionCount: procRuns.length,
          avgCompliance: avgScore,
          totalDeviations: totalDevs,
        };
      }).filter((p: ProcedureSummary) => p.sessionCount > 0);

      setProcedures(summaries);
      setLoading(false);
    }
    load();
  }, []);

  const totalSessions = procedures.reduce((s, p) => s + p.sessionCount, 0);
  const totalDevs = procedures.reduce((s, p) => s + p.totalDeviations, 0);
  const overallAvg = procedures.length > 0
    ? procedures.reduce((s, p) => s + p.avgCompliance * p.sessionCount, 0) / totalSessions
    : 0;

  return (
    <div className="animate-fade-in">
      {/* Hero */}
      <div className="relative mb-10 rounded-2xl overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-teal-500/10 via-cyan-500/5 to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(45,212,191,0.08),transparent_60%)]" />
        <div className="relative p-8">
          <h2 className="text-3xl font-bold text-white tracking-tight">Procedures</h2>
          <p className="text-sm text-zinc-400 mt-1">Select a procedure type to view surgery sessions and compliance analysis</p>

          {!loading && (
            <div className="grid grid-cols-3 gap-4 mt-6 stagger-children">
              <div className="gradient-border p-4 glow-teal">
                <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Total Sessions</div>
                <div className="text-4xl font-bold bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent mt-1">{totalSessions}</div>
              </div>
              <div className="gradient-border p-4">
                <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Avg Compliance</div>
                <div className={cn("text-4xl font-bold mt-1", scoreColor(overallAvg))}>{Math.round(overallAvg * 100)}%</div>
              </div>
              <div className="gradient-border p-4">
                <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Total Deviations</div>
                <div className="text-4xl font-bold text-red-400 mt-1">{totalDevs}</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Procedure Cards */}
      {loading ? (
        <div className="grid grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-40 bg-zinc-900/50 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 stagger-children">
          {procedures.map((p) => (
            <a
              key={p.id}
              href={`/procedures/${p.id}`}
              className="gradient-border p-6 hover:bg-white/[0.03] transition-all duration-200 group cursor-pointer"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-white group-hover:text-teal-400 transition-colors">{p.name}</h3>
                  <div className="text-sm text-zinc-500 mt-1">{p.sessionCount} session{p.sessionCount !== 1 ? "s" : ""} recorded</div>
                </div>
                <svg className="w-5 h-5 text-zinc-600 group-hover:text-teal-400 transition-colors mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>

              <div className="flex items-center gap-6 mt-5">
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Avg Compliance</div>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-2 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-1000",
                          p.avgCompliance >= 0.8 ? "bg-gradient-to-r from-green-500 to-emerald-400" :
                          p.avgCompliance >= 0.5 ? "bg-gradient-to-r from-yellow-500 to-amber-400" :
                          "bg-gradient-to-r from-red-500 to-rose-400"
                        )}
                        style={{ width: `${Math.round(p.avgCompliance * 100)}%` }}
                      />
                    </div>
                    <span className={cn("text-sm font-semibold tabular-nums", scoreColor(p.avgCompliance))}>{Math.round(p.avgCompliance * 100)}%</span>
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-500 mb-1">Deviations</div>
                  <span className="text-sm font-semibold text-red-400">{p.totalDeviations}</span>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
