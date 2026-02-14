"use client";
import type { ProcedureRun, DeviationReport, ObservedEvent, ProcedureNode, Procedure } from "@/lib/types";
import { ComplianceScore, VerdictBadge, DeviationTypeBadge, SafetyCriticalFlag } from "./badges";
import { cn, formatDuration } from "@/lib/utils";

interface Props {
  run: ProcedureRun;
  report: DeviationReport | null;
  events: ObservedEvent[];
  nodes: ProcedureNode[];
  procedure: Procedure | null;
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="gradient-border p-6 flex flex-col justify-center">
      <div className="text-sm text-zinc-500 uppercase tracking-wider font-medium">{label}</div>
      <div className="text-5xl font-bold text-white mt-2">{value}</div>
    </div>
  );
}

export function OverviewTab({ run, report, events, nodes, procedure }: Props) {
  if (!report) return <div className="text-zinc-500">No report available for this session.</div>;

  const topDeviations = report.adjudicated
    .filter(d => d.verdict === "confirmed")
    .slice(0, 5);

  return (
    <div className="grid grid-cols-12 gap-6 animate-fade-in">
      <div className="col-span-4 flex flex-col items-center gap-4 gradient-border p-6 glow-teal">
        <ComplianceScore score={report.compliance_score} />
        <div className="text-center">
          <div className="text-sm font-medium text-white">{procedure?.name}</div>
          <div className="text-xs text-zinc-500 mt-1">{run.surgeon_name} &middot; {formatDuration(run.started_at, run.ended_at)}</div>
        </div>
      </div>

      <div className="col-span-8 grid grid-cols-2 gap-4 stagger-children">
        <StatCard label="Steps Expected" value={report.total_expected} />
        <StatCard label="Steps Observed" value={report.total_observed} />
      </div>

      {procedure?.source_documents && procedure.source_documents.length > 0 && (
        <div className="col-span-12 gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-3 font-medium">Source Documents</div>
          <div className="flex flex-wrap gap-2">
            {procedure.source_documents.map((doc, i) => (
              <span key={i} className="px-3 py-1.5 bg-white/[0.03] border border-zinc-800/50 rounded-lg text-xs text-zinc-300 hover:bg-white/[0.05] transition-colors">{doc}</span>
            ))}
          </div>
        </div>
      )}

      {topDeviations.length > 0 && (
        <div className="col-span-12 gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-4 font-medium">Top Confirmed Deviations</div>
          <div className="space-y-2 stagger-children">
            {topDeviations.map((d, i) => (
              <div key={i} className="flex items-center justify-between bg-white/[0.02] hover:bg-white/[0.04] rounded-lg px-4 py-3 transition-all duration-200 border border-zinc-800/30">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-white">{d.node_name}</span>
                  <DeviationTypeBadge type={d.deviation_type} />
                  <SafetyCriticalFlag critical={d.original_safety_critical} />
                </div>
                <VerdictBadge verdict={d.verdict} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
