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
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={downloadText} className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white text-sm rounded-lg border border-zinc-700 transition-colors">
          Download TXT
        </button>
        <button onClick={downloadJSON} className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white text-sm rounded-lg border border-zinc-700 transition-colors">
          Download JSON
        </button>
        <button
          onClick={downloadFHIR}
          disabled={fhirLoading}
          className="px-4 py-2 bg-green-600/20 hover:bg-green-600/30 text-green-400 text-sm rounded-lg border border-green-600/30 transition-colors disabled:opacity-50"
        >
          {fhirLoading ? "Generating..." : "Export FHIR R4 Bundle"}
        </button>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
        <pre className="text-sm text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed overflow-x-auto">
          {report.report_text}
        </pre>
      </div>
    </div>
  );
}

