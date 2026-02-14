"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { DeviationReport, ObservedEvent, ProcedureNode, ProcedureRun, Procedure } from "@/lib/types";

interface Props {
  report: DeviationReport | null;
  events: ObservedEvent[];
  nodes: ProcedureNode[];
  run: ProcedureRun;
  procedure: Procedure | null;
  runId: string;
}

function ExportCard({ title, description, icon, onClick, loading, accent, disabled }: {
  title: string; description: string; icon: React.ReactNode; onClick?: () => void; loading?: boolean; accent?: boolean; disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={cn(
        "gradient-border p-5 text-left hover:bg-white/[0.03] transition-all duration-200 group w-full disabled:opacity-40 disabled:cursor-not-allowed",
        accent && "glow-teal"
      )}
    >
      <div className="flex items-start gap-4">
        <div className={cn(
          "w-10 h-10 rounded-xl flex items-center justify-center shrink-0",
          accent ? "bg-teal-500/10 text-teal-400" : "bg-zinc-800 text-zinc-400"
        )}>
          {icon}
        </div>
        <div>
          <div className="text-sm font-medium text-white group-hover:text-teal-400 group-disabled:group-hover:text-white transition-colors flex items-center gap-2">
            {loading ? "Generating..." : title}
            {disabled && <span className="text-xs text-zinc-600 font-normal px-1.5 py-0.5 bg-zinc-800 rounded">Coming Soon</span>}
          </div>
          <p className="text-xs text-zinc-500 mt-1 leading-relaxed">{description}</p>
        </div>
      </div>
    </button>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium">{label}</div>
      <div className="text-sm text-white mt-0.5">{value}</div>
    </div>
  );
}

export function ReportTab({ report, events, nodes, run, procedure, runId }: Props) {
  const [fhirLoading, setFhirLoading] = useState(false);

  if (!report) return <div className="text-zinc-500">No data available.</div>;

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
    } catch {
      alert("FHIR export failed. Make sure the FHIR service is running on port 8001.");
    } finally {
      setFhirLoading(false);
    }
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {/* System Data */}
      <div>
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">System Data</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="gradient-border p-5 space-y-4">
            <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium border-b border-zinc-800/30 pb-2">Patient Information</div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Patient ID" value={run.patient_id || "PT-2026-04821"} />
              <Field label="MRN" value="MRN-00482193" />
              <Field label="Name" value="[Redacted]" />
              <Field label="DOB" value="1978-03-14" />
              <Field label="Sex" value="Female" />
              <Field label="Blood Type" value="O+" />
              <Field label="Allergies" value="Penicillin, Latex" />
              <Field label="BMI" value="26.4" />
            </div>
          </div>

          <div className="gradient-border p-5 space-y-4">
            <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium border-b border-zinc-800/30 pb-2">Surgery Details</div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Procedure" value={procedure?.name || run.procedure_id} />
              <Field label="Case ID" value={runId.slice(0, 8).toUpperCase()} />
              <Field label="Lead Surgeon" value={run.surgeon_name || "—"} />
              <Field label="Anesthesiologist" value="Dr. R. Patel" />
              <Field label="Scrub Nurse" value="RN M. Torres" />
              <Field label="OR Room" value="OR-7" />
              <Field label="Start Time" value={new Date(run.started_at).toLocaleString()} />
              <Field label="End Time" value={run.ended_at ? new Date(run.ended_at).toLocaleString() : "—"} />
            </div>
          </div>

          <div className="gradient-border p-5 space-y-4">
            <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium border-b border-zinc-800/30 pb-2">Pre-Operative</div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="ASA Class" value="II" />
              <Field label="Consent Signed" value="Yes — 2026-02-14 08:12" />
              <Field label="NPO Status" value="Confirmed (12h)" />
              <Field label="Antibiotic Prophylaxis" value="Cefazolin 2g IV" />
              <Field label="VTE Prophylaxis" value="SCDs applied" />
              <Field label="Site Marked" value="Yes — left lower quadrant" />
            </div>
          </div>

          <div className="gradient-border p-5 space-y-4">
            <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium border-b border-zinc-800/30 pb-2">Post-Operative</div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Estimated Blood Loss" value="15 mL" />
              <Field label="Specimens" value="Purulent fluid — sent to lab" />
              <Field label="Complications" value="None" />
              <Field label="Disposition" value="Discharged same day" />
              <Field label="Follow-Up" value="48h wound check" />
              <Field label="Discharge Rx" value="Augmentin 875mg BID x 7d" />
            </div>
          </div>
        </div>
      </div>

      {/* Tracking Data */}
      <div>
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">Tracking Data</h3>
        <div className="grid grid-cols-2 gap-4 stagger-children">
          <ExportCard
            title="Instrument Trajectories CSV"
            description="6DoF pose data for each tracked instrument (scalpel, hemostat, forceps) — position, rotation, velocity at each frame"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>}
            disabled
          />
          <ExportCard
            title="Hand Kinematics CSV"
            description="Surgeon hand position, orientation, and finger articulation data — left and right hand tracked independently"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11m0-5.5a1.5 1.5 0 013 0v3m0 0V11" /></svg>}
            disabled
          />
          <ExportCard
            title="Patient Anatomy CSV"
            description="Tracked anatomical landmarks and tissue deformation data — spatial reference points at each timestep"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>}
            disabled
          />
          <ExportCard
            title="Spatial Interactions CSV"
            description="Instrument-to-anatomy proximity, contact events, and safe zone boundary data over time"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" /></svg>}
            disabled
          />
        </div>
      </div>

      {/* EHR Interoperability */}
      <div>
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">EHR Interoperability</h3>
        <div className="grid grid-cols-2 gap-4">
          <ExportCard
            title="FHIR R4 Bundle"
            description="HL7 FHIR R4 transaction bundle — Patient, Encounter, Procedure, Observations, DetectedIssues, Composition"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>}
            onClick={downloadFHIR}
            loading={fhirLoading}
            accent
          />
        </div>
      </div>
    </div>
  );
}
