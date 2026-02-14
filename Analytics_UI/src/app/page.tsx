"use client";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { cn, scoreColor, formatDuration } from "@/lib/utils";
import type { ProcedureRun, DeviationReport, Procedure } from "@/lib/types";

interface SessionRow extends ProcedureRun {
  report?: DeviationReport;
  procedureName?: string;
}

export default function Dashboard() {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [runsRes, reportsRes, procsRes] = await Promise.all([
        supabase.from("procedure_runs").select("*").order("created_at", { ascending: false }),
        supabase.from("deviation_reports").select("*"),
        supabase.from("procedures").select("id, name"),
      ]);

      const procMap = new Map((procsRes.data || []).map((p: any) => [p.id, p.name]));
      const reportMap = new Map((reportsRes.data || []).map((r: any) => [r.procedure_run_id, r]));

      const rows: SessionRow[] = (runsRes.data || []).map((run: any) => ({
        ...run,
        report: reportMap.get(run.id),
        procedureName: procMap.get(run.procedure_id) || run.procedure_id,
      }));

      setSessions(rows);
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Surgery Sessions</h2>
        <p className="text-sm text-zinc-500 mt-1">Post-operative compliance analysis for all recorded procedures</p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 bg-zinc-900 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="border border-zinc-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/50">
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-4 py-3">Procedure</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-4 py-3">Surgeon</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-4 py-3">Date</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-4 py-3">Duration</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-4 py-3">Compliance</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-4 py-3">Deviations</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => {
                const score = s.report?.compliance_score;
                const totalDevs = (s.report?.confirmed_count || 0) + (s.report?.mitigated_count || 0) + (s.report?.review_count || 0);
                return (
                  <tr
                    key={s.id}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer transition-colors"
                    onClick={() => window.location.href = `/sessions/${s.id}`}
                  >
                    <td className="px-4 py-4">
                      <div className="font-medium text-white text-sm">{s.procedureName}</div>
                      <div className="text-xs text-zinc-500 font-mono mt-0.5">{s.id.slice(0, 8)}</div>
                    </td>
                    <td className="px-4 py-4 text-sm text-zinc-300">{s.surgeon_name || "—"}</td>
                    <td className="px-4 py-4 text-sm text-zinc-400">
                      {new Date(s.started_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td className="px-4 py-4 text-sm text-zinc-400">{formatDuration(s.started_at, s.ended_at)}</td>
                    <td className="px-4 py-4">
                      {score !== undefined ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 bg-zinc-800 rounded-full overflow-hidden">
                            <div
                              className={cn("h-full rounded-full", score >= 0.8 ? "bg-green-500" : score >= 0.5 ? "bg-yellow-500" : "bg-red-500")}
                              style={{ width: `${Math.round(score * 100)}%` }}
                            />
                          </div>
                          <span className={cn("text-sm font-medium", scoreColor(score))}>{Math.round(score * 100)}%</span>
                        </div>
                      ) : (
                        <span className="text-sm text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      {totalDevs > 0 ? (
                        <span className="text-sm text-red-400 font-medium">{totalDevs}</span>
                      ) : (
                        <span className="text-sm text-green-400">Clean</span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <span className={cn(
                        "px-2 py-0.5 rounded-full text-xs font-medium",
                        s.status === "completed" ? "bg-green-500/20 text-green-400" :
                        s.status === "in_progress" ? "bg-blue-500/20 text-blue-400" :
                        "bg-zinc-500/20 text-zinc-400"
                      )}>
                        {s.status.charAt(0).toUpperCase() + s.status.slice(1).replace(/_/g, " ")}
                        </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

