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

function downloadStaticCSV(path: string, filename: string) {
  const a = document.createElement("a");
  a.href = path;
  a.download = filename;
  a.click();
}

async function downloadCentroidsAsCSV() {
  try {
    const resp = await fetch("/data/centroids.json");
    const raw = await resp.json();
    const keys = Object.keys(raw).sort();
    const rows = ["frame_idx,x,y"];
    for (let i = 0; i < keys.length; i++) {
      rows.push(`${i},${raw[keys[i]].x},${raw[keys[i]].y}`);
    }
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "blade_centroids.csv";
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    alert("Failed to export centroids");
  }
}

export function ReportTab({ report, events, nodes, run, procedure, runId }: Props) {
  const [fhirLoading, setFhirLoading] = useState(false);

  if (!report) return <div className="text-zinc-500">No data available.</div>;

  function buildFHIRBundle() {
    const patientId = run.patient_id || "PT-2026-04821";
    const encounterId = `encounter-${runId.slice(0, 8)}`;
    const procedureId = `procedure-${runId.slice(0, 8)}`;
    const now = new Date().toISOString();

    const entry: any[] = [];
    const ref = (type: string, id: string) => `${type}/${id}`;

    // Patient
    entry.push({ fullUrl: `urn:uuid:${patientId}`, resource: {
      resourceType: "Patient", id: patientId, identifier: [{ system: "urn:oid:viper", value: patientId }],
      name: [{ use: "official", text: "[Redacted]" }], gender: "female", birthDate: "1978-03-14",
    }, request: { method: "PUT", url: ref("Patient", patientId) } });

    // Encounter
    entry.push({ fullUrl: `urn:uuid:${encounterId}`, resource: {
      resourceType: "Encounter", id: encounterId, status: run.status === "completed" ? "finished" : "in-progress",
      class: { system: "http://terminology.hl7.org/CodeSystem/v3-ActCode", code: "AMB" },
      subject: { reference: ref("Patient", patientId) },
      period: { start: run.started_at, ...(run.ended_at ? { end: run.ended_at } : {}) },
    }, request: { method: "PUT", url: ref("Encounter", encounterId) } });

    // Procedure
    entry.push({ fullUrl: `urn:uuid:${procedureId}`, resource: {
      resourceType: "Procedure", id: procedureId, status: "completed",
      code: { text: procedure?.name || run.procedure_id },
      subject: { reference: ref("Patient", patientId) },
      encounter: { reference: ref("Encounter", encounterId) },
      performedPeriod: { start: run.started_at, ...(run.ended_at ? { end: run.ended_at } : {}) },
      performer: run.surgeon_name ? [{ actor: { display: run.surgeon_name } }] : [],
    }, request: { method: "PUT", url: ref("Procedure", procedureId) } });

    // Observations — one per event
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    for (const ev of events) {
      const obsId = `observation-event-${ev.id}`;
      const node = nodeMap.get(ev.node_id);
      entry.push({ fullUrl: `urn:uuid:${obsId}`, resource: {
        resourceType: "Observation", id: obsId, status: "final",
        code: { text: node?.name || ev.node_id },
        subject: { reference: ref("Patient", patientId) },
        encounter: { reference: ref("Encounter", encounterId) },
        effectiveDateTime: ev.timestamp,
        valueString: ev.metadata?.observation || node?.name || ev.node_id,
        component: (ev.metadata?.strokes || []).map(s => ({
          code: { text: `${s.stroke_type} (${s.instrument})` },
          valueString: `${s.timestamp_seconds}s–${s.end_seconds}s: ${s.description}`,
        })),
      }, request: { method: "PUT", url: ref("Observation", obsId) } });
    }

    // DetectedIssues — one per deviation
    if (report) {
      for (const [i, dev] of report.adjudicated.entries()) {
        const issueId = `detected-issue-${runId.slice(0, 8)}-${i}`;
        entry.push({ fullUrl: `urn:uuid:${issueId}`, resource: {
          resourceType: "DetectedIssue", id: issueId, status: "final",
          code: { text: dev.deviation_type },
          severity: dev.verdict === "confirmed" ? "high" : dev.verdict === "mitigated" ? "moderate" : "low",
          detail: `[${dev.verdict}] ${dev.node_name} (${dev.phase}): ${dev.evidence_summary}`,
          patient: { reference: ref("Patient", patientId) },
          implicated: [{ reference: ref("Procedure", procedureId) }],
          evidence: dev.citations.map(c => ({ detail: [{ text: c }] })),
        }, request: { method: "PUT", url: ref("DetectedIssue", issueId) } });
      }

      // Composition — summary report
      const compId = `composition-${runId.slice(0, 8)}`;
      entry.push({ fullUrl: `urn:uuid:${compId}`, resource: {
        resourceType: "Composition", id: compId, status: "final", type: { text: "Surgical Compliance Report" },
        date: now, title: `Compliance Report — ${procedure?.name || run.procedure_id}`,
        subject: { reference: ref("Patient", patientId) },
        section: [
          { title: "Score", text: { status: "generated", div: `<div>Compliance: ${report.compliance_score}% | Expected: ${report.total_expected} | Observed: ${report.total_observed} | Confirmed: ${report.confirmed_count} | Mitigated: ${report.mitigated_count} | Review: ${report.review_count}</div>` } },
          { title: "Narrative", text: { status: "generated", div: `<div>${report.report_text}</div>` } },
        ],
      }, request: { method: "PUT", url: ref("Composition", compId) } });
    }

    return { resourceType: "Bundle", type: "transaction", timestamp: now, entry };
  }

  function downloadFHIR() {
    setFhirLoading(true);
    try {
      const bundle = buildFHIRBundle();
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/fhir+json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fhir-bundle-${runId.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("FHIR export failed: " + (e as Error).message);
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
            title="Tweezer Tip Trajectories CSV"
            description="Per-frame (x0, y0, x1, y1) for both tweezer tips — 648 frames via optical flow tracking"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>}
            onClick={() => downloadStaticCSV("/data/tracked_tips_tweezer.csv", "tweezer_tips.csv")}
            accent
          />
          <ExportCard
            title="Blade Tip Trajectory CSV"
            description="Per-frame (x0, y0) blade tip position — 648 frames via optical flow tracking"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>}
            onClick={() => downloadStaticCSV("/data/tracked_tips_blade.csv", "blade_tips.csv")}
            accent
          />
          <ExportCard
            title="Blade Centroid (FoundationPose) CSV"
            description="Per-frame (x, y) blade body centroid from 6DoF pose estimation — 496 frames"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>}
            onClick={() => downloadCentroidsAsCSV()}
            accent
          />
          <ExportCard
            title="Kinematics Summary JSON"
            description="GOALS scores + per-instrument kinematic metrics (path length, smoothness, tremor, etc.)"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>}
            onClick={() => downloadStaticCSV("/data/kinematics.json", "kinematics.json")}
            accent
          />
          <ExportCard
            title="Hand Trajectories CSV (HaMeR 3D)"
            description="Per-frame (left_x, left_y, left_z, right_x, right_y, right_z) surgeon hand centroids from 3D mesh reconstruction — 496 frames"
            icon={<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11m0-5.5a1.5 1.5 0 013 0v3m0 0V11" /></svg>}
            onClick={() => downloadStaticCSV("/data/hand_trajectories.csv", "hand_trajectories.csv")}
            accent
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
