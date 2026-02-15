"use client";
import { useEffect, useState } from "react";
import { cn, verdictColor, phaseColor, deviationTypeLabel } from "@/lib/utils";

export function VerdictBadge({ verdict }: { verdict: string }) {
  const label = verdict === "context_dependent" ? "Needs Review" : verdict.charAt(0).toUpperCase() + verdict.slice(1);
  return (
    <span className={cn("px-2.5 py-0.5 rounded-full text-xs font-medium border", verdictColor(verdict))}>
      {label}
    </span>
  );
}

export function PhaseBadge({ phase }: { phase: string }) {
  return (
    <span className={cn("px-2.5 py-0.5 rounded-full text-xs font-medium", phaseColor(phase))}>
      {phase.charAt(0).toUpperCase() + phase.slice(1)}
    </span>
  );
}

export function DeviationTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    missing: "bg-red-500/15 text-red-400 border border-red-500/20",
    out_of_order: "bg-orange-500/15 text-orange-400 border border-orange-500/20",
    skipped_safety: "bg-rose-500/15 text-rose-300 border border-rose-500/20",
    unhandled_complication: "bg-pink-500/15 text-pink-400 border border-pink-500/20",
  };
  return (
    <span className={cn("px-2.5 py-0.5 rounded-full text-xs font-medium", colors[type] || "bg-zinc-500/15 text-zinc-400 border border-zinc-500/20")}>
      {deviationTypeLabel(type)}
    </span>
  );
}

export function SafetyCriticalFlag({ critical }: { critical: boolean }) {
  if (!critical) return null;
  return (
    <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-600/20 text-red-300 border border-red-500/25 flex items-center gap-1">
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
      Safety Critical
    </span>
  );
}

export function ConfidenceBar({ value, label }: { value: number; label?: string }) {
  const [width, setWidth] = useState(0);
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "bg-gradient-to-r from-green-500 to-emerald-400" : pct >= 50 ? "bg-gradient-to-r from-yellow-500 to-amber-400" : "bg-gradient-to-r from-red-500 to-rose-400";

  useEffect(() => {
    const t = setTimeout(() => setWidth(pct), 100);
    return () => clearTimeout(t);
  }, [pct]);

  return (
    <div className="flex items-center gap-2">
      {label && <span className="text-xs text-zinc-500 w-20 shrink-0">{label}</span>}
      <div className="flex-1 h-2 bg-zinc-800/80 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-700 ease-out", color)} style={{ width: `${width}%` }} />
      </div>
      <span className="text-xs text-zinc-400 w-10 text-right font-mono">{pct}%</span>
    </div>
  );
}

export function ComplianceScore({ score }: { score: number }) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const pct = Math.round(score * 100);

  useEffect(() => {
    const duration = 1200;
    const steps = 60;
    const increment = score / steps;
    let current = 0;
    const interval = setInterval(() => {
      current += increment;
      if (current >= score) {
        setAnimatedScore(score);
        clearInterval(interval);
      } else {
        setAnimatedScore(current);
      }
    }, duration / steps);
    return () => clearInterval(interval);
  }, [score]);

  const displayPct = Math.round(animatedScore * 100);
  const color = score >= 0.8 ? "from-green-400 to-emerald-300" : score >= 0.5 ? "from-yellow-400 to-amber-300" : "from-red-400 to-rose-300";
  const ringColor = score >= 0.8 ? "stroke-green-500" : score >= 0.5 ? "stroke-yellow-500" : "stroke-red-500";
  const glowColor = score >= 0.8 ? "drop-shadow(0 0 8px rgba(34,197,94,0.3))" : score >= 0.5 ? "drop-shadow(0 0 8px rgba(234,179,8,0.3))" : "drop-shadow(0 0 8px rgba(239,68,68,0.3))";
  const circumference = 2 * Math.PI * 45;
  const offset = circumference - animatedScore * circumference;

  return (
    <div className="relative w-36 h-36 flex items-center justify-center">
      <svg className="w-36 h-36 -rotate-90" viewBox="0 0 100 100" style={{ filter: glowColor }}>
        <circle cx="50" cy="50" r="45" fill="none" stroke="hsl(var(--border))" strokeWidth="6" opacity="0.5" />
        <circle
          cx="50" cy="50" r="45" fill="none"
          className={ringColor}
          strokeWidth="7" strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-4xl font-bold bg-gradient-to-b bg-clip-text text-transparent", color)}>{displayPct}%</span>
        <span className="text-xs text-zinc-500 mt-0.5">compliance</span>
      </div>
    </div>
  );
}
