"use client";
import { cn, verdictColor, phaseColor, deviationTypeLabel } from "@/lib/utils";

export function VerdictBadge({ verdict }: { verdict: string }) {
  const label = verdict === "context_dependent" ? "Needs Review" : verdict.charAt(0).toUpperCase() + verdict.slice(1);
  return (
    <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border", verdictColor(verdict))}>
      {label}
    </span>
  );
}

export function PhaseBadge({ phase }: { phase: string }) {
  return (
    <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", phaseColor(phase))}>
      {phase.charAt(0).toUpperCase() + phase.slice(1)}
    </span>
  );
}

export function DeviationTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    missing: "bg-red-500/20 text-red-400",
    out_of_order: "bg-orange-500/20 text-orange-400",
    skipped_safety: "bg-rose-500/20 text-rose-300",
    unhandled_complication: "bg-pink-500/20 text-pink-400",
  };
  return (
    <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", colors[type] || "bg-zinc-500/20 text-zinc-400")}>
      {deviationTypeLabel(type)}
    </span>
  );
}

export function SafetyCriticalFlag({ critical }: { critical: boolean }) {
  if (!critical) return null;
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-600/30 text-red-300 border border-red-500/30 flex items-center gap-1">
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
      Safety Critical
    </span>
  );
}

export function ConfidenceBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      {label && <span className="text-xs text-zinc-500 w-20 shrink-0">{label}</span>}
      <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-zinc-400 w-10 text-right">{pct}%</span>
    </div>
  );
}

export function ComplianceScore({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "text-green-400" : score >= 0.5 ? "text-yellow-400" : "text-red-400";
  const ringColor = score >= 0.8 ? "stroke-green-500" : score >= 0.5 ? "stroke-yellow-500" : "stroke-red-500";
  const circumference = 2 * Math.PI * 45;
  const offset = circumference - score * circumference;

  return (
    <div className="relative w-32 h-32 flex items-center justify-center">
      <svg className="w-32 h-32 -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="45" fill="none" stroke="hsl(var(--border))" strokeWidth="8" />
        <circle
          cx="50" cy="50" r="45" fill="none"
          className={ringColor}
          strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-3xl font-bold", color)}>{pct}%</span>
        <span className="text-xs text-zinc-500">compliance</span>
      </div>
    </div>
  );
}

