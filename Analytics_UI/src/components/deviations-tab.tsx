"use client";
import { useState, useMemo } from "react";
import type { DeviationReport, AdjudicatedDeviation } from "@/lib/types";
import { VerdictBadge, DeviationTypeBadge, PhaseBadge, SafetyCriticalFlag, ConfidenceBar } from "./badges";
import { parseEvidenceSummary, cn } from "@/lib/utils";

interface Props {
  report: DeviationReport | null;
}

function SnippetCard({ text, confidence, source, doi, type }: { text: string; confidence: number; source: string; doi: string; type: "risk" | "safe" }) {
  return (
    <div className={cn(
      "border rounded-lg p-3",
      type === "risk" ? "border-red-500/20 bg-red-500/5" : "border-green-500/20 bg-green-500/5"
    )}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn(
          "text-xs font-medium px-2 py-0.5 rounded-full",
          type === "risk" ? "bg-red-500/20 text-red-400" : "bg-green-500/20 text-green-400"
        )}>
          {type === "risk" ? "Supports Risk" : "Supports Safety"}
        </span>
        <span className={cn(
          "text-xs font-mono font-medium",
          confidence >= 0.9 ? "text-red-400" : confidence >= 0.7 ? "text-yellow-400" : "text-zinc-400"
        )}>
          {Math.round(confidence * 100)}% NLI
        </span>
      </div>
      <p className="text-xs text-zinc-300 leading-relaxed">&ldquo;{text.slice(0, 300)}{text.length > 300 ? "..." : ""}&rdquo;</p>
      <div className="mt-2 text-xs text-zinc-500">
        <span>{source.slice(0, 80)}</span>
        {doi && (
          <a href={`https://doi.org/${doi}`} target="_blank" rel="noopener noreferrer" className="ml-2 text-blue-400 hover:underline">
            DOI
          </a>
        )}
      </div>
    </div>
  );
}

function DeviationCard({ deviation }: { deviation: AdjudicatedDeviation }) {
  const [expanded, setExpanded] = useState(false);
  const evidence = useMemo(() => parseEvidenceSummary(deviation.evidence_summary), [deviation.evidence_summary]);

  const totalSnippets = evidence.riskSnippets.length + evidence.safeSnippets.length;
  const riskRatio = totalSnippets > 0
    ? evidence.riskSnippets.reduce((s, sn) => s + sn.confidence, 0) /
      (evidence.riskSnippets.reduce((s, sn) => s + sn.confidence, 0) + evidence.safeSnippets.reduce((s, sn) => s + sn.confidence, 0))
    : 0.5;

  return (
    <div className={cn(
      "border rounded-lg overflow-hidden",
      deviation.verdict === "confirmed" ? "border-red-500/30" :
      deviation.verdict === "context_dependent" ? "border-yellow-500/30" :
      "border-green-500/30"
    )}>
      <div
        className={cn(
          "px-4 py-3 cursor-pointer hover:bg-zinc-800/50 transition-colors",
          deviation.verdict === "confirmed" ? "bg-red-500/5" :
          deviation.verdict === "context_dependent" ? "bg-yellow-500/5" :
          "bg-green-500/5"
        )}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-white">{deviation.node_name}</span>
            <DeviationTypeBadge type={deviation.deviation_type} />
            <PhaseBadge phase={deviation.phase} />
            <SafetyCriticalFlag critical={deviation.original_safety_critical} />
          </div>
          <div className="flex items-center gap-2">
            <VerdictBadge verdict={deviation.verdict} />
            <svg className={cn("w-4 h-4 text-zinc-500 transition-transform", expanded && "rotate-180")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        {/* NLI score bar */}
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-zinc-500 w-8">Risk</span>
          <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden flex">
            <div className="bg-red-500/70 h-full rounded-l-full" style={{ width: `${riskRatio * 100}%` }} />
            <div className="bg-green-500/70 h-full rounded-r-full" style={{ width: `${(1 - riskRatio) * 100}%` }} />
          </div>
          <span className="text-xs text-zinc-500 w-8 text-right">Safe</span>
        </div>
      </div>

      {expanded && (
        <div className="px-4 py-4 border-t border-zinc-800/50 bg-zinc-900/50 space-y-4">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-zinc-800/50 rounded-lg p-2">
              <div className="text-lg font-bold text-white">{evidence.citationLandscape.supporting.toLocaleString()}</div>
              <div className="text-xs text-zinc-500">Supporting</div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-2">
              <div className="text-lg font-bold text-white">{evidence.citationLandscape.contrasting.toLocaleString()}</div>
              <div className="text-xs text-zinc-500">Contrasting</div>
            </div>
            <div className="bg-zinc-800/50 rounded-lg p-2">
              <div className="text-lg font-bold text-white">{evidence.snippetsAnalyzed}</div>
              <div className="text-xs text-zinc-500">Snippets Analyzed</div>
            </div>
          </div>

          {evidence.riskSnippets.length > 0 && (
            <div>
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Evidence of Clinical Significance</div>
              <div className="space-y-2">
                {evidence.riskSnippets.map((s, i) => <SnippetCard key={i} {...s} />)}
              </div>
            </div>
          )}

          {evidence.safeSnippets.length > 0 && (
            <div>
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Evidence Deviation May Be Acceptable</div>
              <div className="space-y-2">
                {evidence.safeSnippets.map((s, i) => <SnippetCard key={i} {...s} />)}
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}

export function DeviationsTab({ report }: Props) {
  if (!report) return <div className="text-zinc-500">No report available.</div>;

  const confirmed = report.adjudicated.filter(d => d.verdict === "confirmed");
  const review = report.adjudicated.filter(d => d.verdict === "context_dependent");
  const mitigated = report.adjudicated.filter(d => d.verdict === "mitigated");

  return (
    <div className="space-y-6">
      {confirmed.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-red-400 uppercase tracking-wider mb-3">
            Confirmed Deviations ({confirmed.length})
          </h3>
          <div className="space-y-3">
            {confirmed.map((d, i) => <DeviationCard key={i} deviation={d} />)}
          </div>
        </div>
      )}

      {review.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-yellow-400 uppercase tracking-wider mb-3">
            Needs Review ({review.length})
          </h3>
          <div className="space-y-3">
            {review.map((d, i) => <DeviationCard key={i} deviation={d} />)}
          </div>
        </div>
      )}

      {mitigated.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-green-400 uppercase tracking-wider mb-3">
            Mitigated ({mitigated.length})
          </h3>
          <div className="space-y-3">
            {mitigated.map((d, i) => <DeviationCard key={i} deviation={d} />)}
          </div>
        </div>
      )}

      {report.adjudicated.length === 0 && (
        <div className="text-center py-12">
          <div className="text-4xl mb-3">✓</div>
          <div className="text-lg text-green-400 font-medium">Full Compliance</div>
          <div className="text-sm text-zinc-500">No deviations detected</div>
        </div>
      )}
    </div>
  );
}

