"use client";
import { useState } from "react";
import type { DeviationReport } from "@/lib/types";

interface Props {
  report: DeviationReport | null;
  runId: string;
}

export function ReportTab({ report, runId }: Props) {
  const [fhirLoading, setFhirLoading] = useState(false);

  if (!report) return <div className="text-zinc-500">No report available.</div>;

  function downloadText() {
    const blob = new Blob([report!.report_text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `compliance-report-${runId.slice(0, 8)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function downloadJSON() {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `compliance-report-${runId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadFHIR() {
    setFhirLoading(true);
    try {
      const fhirUrl = process.env.NEXT_PUBLIC_FHIR_API_URL || "http://localhost:8001";
      const resp = await fetch(`${fhirUrl}/fhir/from-pipeline/${runId}`, { method: "POST" });
      if (!resp.ok) throw new Error(`FHIR API error: ${resp.status}`);
      const bundle = await resp.json();
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/fhir+json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fhir-bundle-${runId.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("FHIR export failed. Make sure the FHIR service is running on port 8001.");
    } finally {
      setFhirLoading(false);
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-3">
        <button onClick={downloadText} className="px-4 py-2.5 bg-white/[0.03] hover:bg-white/[0.06] text-white text-sm rounded-xl border border-zinc-800/50 transition-all duration-200 hover:border-zinc-700">
          Download TXT
        </button>
        <button onClick={downloadJSON} className="px-4 py-2.5 bg-white/[0.03] hover:bg-white/[0.06] text-white text-sm rounded-xl border border-zinc-800/50 transition-all duration-200 hover:border-zinc-700">
          Download JSON
        </button>
        <button
          onClick={downloadFHIR}
          disabled={fhirLoading}
          className="px-4 py-2.5 bg-teal-500/10 hover:bg-teal-500/20 text-teal-400 text-sm rounded-xl border border-teal-500/20 transition-all duration-200 disabled:opacity-50 glow-teal"
        >
          {fhirLoading ? "Generating..." : "Export FHIR R4 Bundle"}
        </button>
      </div>

      <div className="gradient-border p-6">
        <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed overflow-x-auto">
          {report.report_text}
        </pre>
      </div>
    </div>
  );
}
