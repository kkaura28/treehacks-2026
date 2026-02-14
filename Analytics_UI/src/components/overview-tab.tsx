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

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6 flex flex-col justify-center">
      <div className="text-sm text-zinc-500 uppercase tracking-wider">{label}</div>
      <div className="text-5xl font-bold text-white mt-2">{value}</div>
      {sub && <div className="text-sm text-zinc-500 mt-2">{sub}</div>}
    </div>
  );
}

export function OverviewTab({ run, report, events, nodes, procedure }: Props) {
  if (!report) return <div className="text-zinc-500">No report available for this session.</div>;

  const topDeviations = report.adjudicated
    .filter(d => d.verdict === "confirmed")
    .slice(0, 5);

  return (
    <div className="grid grid-cols-12 gap-6">
      <div className="col-span-4 flex flex-col items-center gap-4 bg-zinc-900 border border-zinc-800 rounded-lg p-6">
        <ComplianceScore score={report.compliance_score} />
        <div className="text-center">
          <div className="text-sm font-medium text-white">{procedure?.name}</div>
          <div className="text-xs text-zinc-500 mt-1">{run.surgeon_name} &middot; {formatDuration(run.started_at, run.ended_at)}</div>
        </div>
      </div>

      <div className="col-span-8 grid grid-cols-2 gap-4">
          <StatCard label="Steps Expected" value={report.total_expected} />
          <StatCard label="Steps Observed" value={report.total_observed} />

      </div>

      {procedure?.source_documents && procedure.source_documents.length > 0 && (
        <div className="col-span-12 bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Source Documents</div>
          <div className="flex flex-wrap gap-2">
            {procedure.source_documents.map((doc, i) => (
              <span key={i} className="px-2 py-1 bg-zinc-800 rounded text-xs text-zinc-300">{doc}</span>
            ))}
          </div>
        </div>
      )}

      {topDeviations.length > 0 && (
        <div className="col-span-12 bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <div className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Top Confirmed Deviations</div>
          <div className="space-y-3">
            {topDeviations.map((d, i) => (
              <div key={i} className="flex items-center justify-between bg-zinc-800/50 rounded-lg px-4 py-3">
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

