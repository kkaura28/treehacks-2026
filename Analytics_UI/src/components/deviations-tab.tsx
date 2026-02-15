"use client";
import { useState, useMemo } from "react";
import type { DeviationReport, AdjudicatedDeviation } from "@/lib/types";
import { VerdictBadge, DeviationTypeBadge, PhaseBadge, SafetyCriticalFlag } from "./badges";
import { parseEvidenceSummary, cn } from "@/lib/utils";

interface Props {
  report: DeviationReport | null;
}

function SnippetCard({ text, confidence, source, doi, type }: { text: string; confidence: number; source: string; doi: string; type: "risk" | "safe" }) {
  return (
    <div className={cn(
      "border rounded-xl p-3.5",
      type === "risk" ? "border-red-500/15 bg-red-500/[0.03]" : "border-emerald-500/15 bg-emerald-500/[0.03]"
    )}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn(
          "text-xs font-medium px-2.5 py-0.5 rounded-full border",
          type === "risk" ? "bg-red-500/10 text-red-400 border-red-500/20" : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
        )}>
          {type === "risk" ? "Supports Risk" : "Supports Safety"}
        </span>
        <span className={cn(
          "text-xs font-mono font-semibold px-2 py-0.5 rounded-md",
          confidence >= 0.9 ? "text-red-400 bg-red-500/10" : confidence >= 0.7 ? "text-yellow-400 bg-yellow-500/10" : "text-zinc-400 bg-zinc-800"
        )}>
          {Math.round(confidence * 100)}% NLI
        </span>
      </div>
      <p className="text-xs text-zinc-300 leading-relaxed">&ldquo;{text.slice(0, 300)}{text.length > 300 ? "..." : ""}&rdquo;</p>
      <div className="mt-2 text-xs text-zinc-500">
        <span>{source.slice(0, 80)}</span>
        {doi && (
          <a href={`https://doi.org/${doi}`} target="_blank" rel="noopener noreferrer" className="ml-2 text-teal-400 hover:text-teal-300 transition-colors">
            DOI &rarr;
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
      "rounded-xl overflow-hidden transition-all duration-200",
      deviation.verdict === "confirmed" ? "gradient-border before:!bg-gradient-to-r before:!from-red-500/20 before:!via-red-500/5 before:!to-transparent" :
      deviation.verdict === "context_dependent" ? "gradient-border before:!bg-gradient-to-r before:!from-yellow-500/20 before:!via-yellow-500/5 before:!to-transparent" :
      "gradient-border before:!bg-gradient-to-r before:!from-emerald-500/20 before:!via-emerald-500/5 before:!to-transparent"
    )}>
      <div
        className="px-5 py-4 cursor-pointer hover:bg-white/[0.02] transition-all duration-200"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-white">{deviation.node_name}</span>
            <DeviationTypeBadge type={deviation.deviation_type} />
            {deviation.original_safety_critical && (
              <span className="text-[10px] text-red-400/70">⚠ Safety Critical</span>
            )}
          </div>
          <svg className={cn("w-4 h-4 text-zinc-500 transition-transform duration-200", expanded && "rotate-180")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-zinc-500 w-8">Risk</span>
          <div className="flex-1 h-3 bg-zinc-800/80 rounded-full overflow-hidden flex">
            <div className="bg-gradient-to-r from-red-500 to-red-400 h-full rounded-l-full transition-all duration-700" style={{ width: `${riskRatio * 100}%` }} />
            <div className="bg-gradient-to-r from-emerald-500 to-emerald-400 h-full rounded-r-full transition-all duration-700" style={{ width: `${(1 - riskRatio) * 100}%` }} />
          </div>
          <span className="text-xs text-zinc-500 w-8 text-right">Safe</span>
        </div>
      </div>

      {expanded && (
        <div className="px-5 py-5 border-t border-zinc-800/30 bg-white/[0.01] space-y-5 animate-fade-in">
          <div className="grid grid-cols-3 gap-3 text-center">
            {(() => {
              const total = evidence.citationLandscape.supporting + evidence.citationLandscape.contrasting;
              const supPct = total > 0 ? Math.round((evidence.citationLandscape.supporting / total) * 100) : 0;
              const conPct = total > 0 ? 100 - supPct : 0;
              return (<>
                <div className="gradient-border p-3">
                  <div className="text-xl font-bold text-red-400">{supPct}%</div>
                  <div className="text-xs text-zinc-500 mt-0.5">Supporting</div>
                </div>
                <div className="gradient-border p-3">
                  <div className="text-xl font-bold text-emerald-400">{conPct}%</div>
                  <div className="text-xs text-zinc-500 mt-0.5">Contrasting</div>
                </div>
              </>);
            })()}
            <div className="gradient-border p-3">
              <div className="text-xl font-bold text-white">{evidence.snippetsAnalyzed}</div>
              <div className="text-xs text-zinc-500 mt-0.5">Snippets Analyzed</div>
            </div>
          </div>

          {evidence.riskSnippets.length > 0 && (
            <div>
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2.5 font-medium">Evidence of Clinical Significance</div>
              <div className="space-y-2">
                {evidence.riskSnippets.map((s, i) => <SnippetCard key={i} {...s} />)}
              </div>
            </div>
          )}

          {evidence.safeSnippets.length > 0 && (
            <div>
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2.5 font-medium">Evidence Deviation May Be Acceptable</div>
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
    <div className="space-y-8 animate-fade-in">
      {confirmed.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-red-400 uppercase tracking-wider mb-4">
            Confirmed Deviations ({confirmed.length})
          </h3>
          <div className="space-y-3 stagger-children">
            {confirmed.map((d, i) => <DeviationCard key={i} deviation={d} />)}
          </div>
        </div>
      )}

      {review.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-yellow-400 uppercase tracking-wider mb-4">
            Needs Review ({review.length})
          </h3>
          <div className="space-y-3 stagger-children">
            {review.map((d, i) => <DeviationCard key={i} deviation={d} />)}
          </div>
        </div>
      )}

      {mitigated.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-4">
            Mitigated ({mitigated.length})
          </h3>
          <div className="space-y-3 stagger-children">
            {mitigated.map((d, i) => <DeviationCard key={i} deviation={d} />)}
          </div>
        </div>
      )}

      {report.adjudicated.length === 0 && (
        <div className="text-center py-16 animate-scale-in">
          <div className="text-5xl mb-4">✓</div>
          <div className="text-xl font-semibold bg-gradient-to-r from-teal-400 to-emerald-400 bg-clip-text text-transparent">Full Compliance</div>
          <div className="text-sm text-zinc-500 mt-1">No deviations detected</div>
        </div>
      )}
    </div>
  );
}
