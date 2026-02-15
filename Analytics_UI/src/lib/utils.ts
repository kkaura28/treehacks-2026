import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { ParsedEvidence, ParsedSnippet } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function scoreColor(score: number): string {
  if (score >= 0.8) return "text-green-400";
  if (score >= 0.5) return "text-yellow-400";
  return "text-red-400";
}

export function scoreBgColor(score: number): string {
  if (score >= 0.8) return "bg-green-500/20 border-green-500/30";
  if (score >= 0.5) return "bg-yellow-500/20 border-yellow-500/30";
  return "bg-red-500/20 border-red-500/30";
}

export function verdictColor(verdict: string): string {
  switch (verdict) {
    case "confirmed": return "bg-red-500/20 text-red-400 border-red-500/30";
    case "mitigated": return "bg-green-500/20 text-green-400 border-green-500/30";
    case "context_dependent": return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
    default: return "bg-zinc-500/20 text-zinc-400 border-zinc-500/30";
  }
}

export function deviationTypeLabel(type: string): string {
  switch (type) {
    case "missing": return "Missing Step";
    case "out_of_order": return "Out of Order";
    case "skipped_safety": return "Skipped Safety";
    case "unhandled_complication": return "Unhandled Complication";
    default: return type;
  }
}

export function phaseColor(phase: string): string {
  switch (phase) {
    case "checklist": return "bg-blue-500/20 text-blue-400";
    case "setup": return "bg-purple-500/20 text-purple-400";
    case "exposure": return "bg-orange-500/20 text-orange-400";
    case "safety": return "bg-red-500/20 text-red-400";
    case "division": return "bg-amber-500/20 text-amber-400";
    case "closure": return "bg-teal-500/20 text-teal-400";
    case "complication": return "bg-rose-500/20 text-rose-400";
    default: return "bg-zinc-500/20 text-zinc-400";
  }
}

export function formatDuration(startedAt: string, endedAt: string | null): string {
  if (!endedAt) return "In progress";
  const ms = new Date(endedAt).getTime() - new Date(startedAt).getTime();
  const min = Math.round(ms / 60000);
  if (min < 60) return `${min}m`;
  return `${Math.floor(min / 60)}h ${min % 60}m`;
}

export function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function formatTimestampPrecise(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

export function parseEvidenceSummary(summary: string): ParsedEvidence {
  const result: ParsedEvidence = {
    citationLandscape: { supporting: 0, contrasting: 0 },
    snippetsAnalyzed: 0,
    riskSnippets: [],
    safeSnippets: [],
  };

  const landscapeMatch = summary.match(/(\d+)\s+supporting,\s+(\d+)\s+contrasting/);
  if (landscapeMatch) {
    result.citationLandscape.supporting = parseInt(landscapeMatch[1]);
    result.citationLandscape.contrasting = parseInt(landscapeMatch[2]);
  }

  const snippetsMatch = summary.match(/Snippets analyzed by NLI model:\s+(\d+)/);
  if (snippetsMatch) {
    result.snippetsAnalyzed = parseInt(snippetsMatch[1]);
  }

  const snippetRegex = /\[NLI confidence:\s+(\d+)%\]\s+"([^"]+)"\s+Source:\s+(.+?)\s+\(DOI:\s+([^)]+)\)/g;
  let match;
  let inRisk = true;

  if (summary.includes("Evidence this deviation may be acceptable:")) {
    const parts = summary.split("Evidence this deviation may be acceptable:");
    const riskPart = parts[0];
    const safePart = parts[1] || "";

    let riskMatch;
    while ((riskMatch = snippetRegex.exec(riskPart)) !== null) {
      result.riskSnippets.push({
        text: riskMatch[2],
        confidence: parseInt(riskMatch[1]) / 100,
        source: riskMatch[3].trim(),
        doi: riskMatch[4].trim(),
        type: "risk",
      });
    }

    const safeRegex = /\[NLI confidence:\s+(\d+)%\]\s+"([^"]+)"\s+Source:\s+(.+?)\s+\(DOI:\s+([^)]+)\)/g;
    let safeMatch;
    while ((safeMatch = safeRegex.exec(safePart)) !== null) {
      result.safeSnippets.push({
        text: safeMatch[2],
        confidence: parseInt(safeMatch[1]) / 100,
        source: safeMatch[3].trim(),
        doi: safeMatch[4].trim(),
        type: "safe",
      });
    }
  } else {
    while ((match = snippetRegex.exec(summary)) !== null) {
      result.riskSnippets.push({
        text: match[2],
        confidence: parseInt(match[1]) / 100,
        source: match[3].trim(),
        doi: match[4].trim(),
        type: "risk",
      });
    }
  }

  return result;
}

