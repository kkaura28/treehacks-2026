"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { cn, scoreColor, formatDuration } from "@/lib/utils";
import type { ProcedureRun, DeviationReport } from "@/lib/types";

interface SessionRow extends ProcedureRun {
  report?: DeviationReport;
}

export default function ProcedureSessions() {
  const params = useParams();
  const procedureId = params.id as string;

  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [procedureName, setProcedureName] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [procRes, runsRes, reportsRes] = await Promise.all([
        supabase.from("procedures").select("name").eq("id", procedureId).single(),
        supabase.from("procedure_runs").select("*").eq("procedure_id", procedureId).order("created_at", { ascending: false }),
        supabase.from("deviation_reports").select("*"),
      ]);

      setProcedureName(procRes.data?.name || procedureId);
      const reportMap = new Map((reportsRes.data || []).map((r: any) => [r.procedure_run_id, r]));

      const rows: SessionRow[] = (runsRes.data || []).map((run: any) => ({
        ...run,
        report: reportMap.get(run.id),
      }));

      setSessions(rows);
      setLoading(false);
    }
    load();
  }, [procedureId]);

  const avgCompliance = sessions.length > 0
    ? sessions.reduce((s, r) => s + (r.report?.compliance_score || 0), 0) / sessions.length
    : 0;
  const totalDevs = sessions.reduce((s, r) => s + (r.report?.confirmed_count || 0) + (r.report?.mitigated_count || 0) + (r.report?.review_count || 0), 0);

  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <a href="/" className="text-sm text-zinc-500 hover:text-teal-400 transition-colors duration-200">&larr; All procedures</a>
        <h2 className="text-3xl font-bold text-white mt-2 tracking-tight">{procedureName}</h2>
        <p className="text-sm text-zinc-400 mt-1">{sessions.length} session{sessions.length !== 1 ? "s" : ""} recorded</p>
      </div>

      {!loading && sessions.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-8 stagger-children">
          <div className="gradient-border p-4 glow-teal">
            <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Sessions</div>
            <div className="text-4xl font-bold bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent mt-1">{sessions.length}</div>
          </div>
          <div className="gradient-border p-4">
            <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Avg Compliance</div>
            <div className={cn("text-4xl font-bold mt-1", scoreColor(avgCompliance))}>{Math.round(avgCompliance * 100)}%</div>
          </div>
          <div className="gradient-border p-4">
            <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Total Deviations</div>
            <div className="text-4xl font-bold text-red-400 mt-1">{totalDevs}</div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="space-y-3 stagger-children">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-zinc-900/50 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="border border-zinc-800/50 rounded-xl overflow-hidden bg-zinc-900/30 backdrop-blur-sm animate-slide-up">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800/50">
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Session</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Surgeon</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Date</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Duration</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Compliance</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Deviations</th>
                <th className="text-left text-xs font-medium text-zinc-500 uppercase tracking-wider px-5 py-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="stagger-children">
              {sessions.map((s) => {
                const score = s.report?.compliance_score;
                const totalDevs = (s.report?.confirmed_count || 0) + (s.report?.mitigated_count || 0) + (s.report?.review_count || 0);
                return (
                  <tr
                    key={s.id}
                    className="border-b border-zinc-800/30 hover:bg-white/[0.02] cursor-pointer transition-all duration-200 group"
                    onClick={() => window.location.href = `/sessions/${s.id}`}
                  >
                    <td className="px-5 py-4">
                      <div className="font-medium text-white text-sm group-hover:text-teal-400 transition-colors">Session {s.id.slice(0, 8)}</div>
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-300">{s.surgeon_name || "—"}</td>
                    <td className="px-5 py-4 text-sm text-zinc-400">
                      {new Date(s.started_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td className="px-5 py-4 text-sm text-zinc-400">{formatDuration(s.started_at, s.ended_at)}</td>
                    <td className="px-5 py-4">
                      {score !== undefined ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-2 bg-zinc-800 rounded-full overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full transition-all duration-1000",
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
                    <td className="px-5 py-4">
                      {totalDevs > 0 ? (
                        <span className="text-sm text-red-400 font-medium">{totalDevs}</span>
                      ) : (
                        <span className="text-sm text-emerald-400">Clean</span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <span className={cn(
                        "px-2.5 py-1 rounded-full text-xs font-medium border",
                        s.status === "completed" ? "bg-teal-500/10 text-teal-400 border-teal-500/20" :
                        s.status === "in_progress" ? "bg-blue-500/10 text-blue-400 border-blue-500/20" :
                        "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
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

