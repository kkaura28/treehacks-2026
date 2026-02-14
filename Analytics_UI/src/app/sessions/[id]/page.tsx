"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { cn } from "@/lib/utils";
import type { ProcedureRun, DeviationReport, ObservedEvent, ProcedureNode, ProcedureEdge, Procedure } from "@/lib/types";
import { OverviewTab } from "@/components/overview-tab";
import { TimelineTab } from "@/components/timeline-tab";
import { GraphTab } from "@/components/graph-tab";
import { DeviationsTab } from "@/components/deviations-tab";
import { ReportTab } from "@/components/report-tab";

const TABS = ["Overview", "Video & Timeline", "Procedure Graph", "Deviation Analysis", "Report"] as const;
type Tab = typeof TABS[number];

export default function SessionDetail() {
  const params = useParams();
  const id = params.id as string;

  const [tab, setTab] = useState<Tab>("Overview");
  const [loading, setLoading] = useState(true);
  const [run, setRun] = useState<ProcedureRun | null>(null);
  const [procedure, setProcedure] = useState<Procedure | null>(null);
  const [report, setReport] = useState<DeviationReport | null>(null);
  const [events, setEvents] = useState<ObservedEvent[]>([]);
  const [nodes, setNodes] = useState<ProcedureNode[]>([]);
  const [edges, setEdges] = useState<ProcedureEdge[]>([]);

  useEffect(() => {
    async function load() {
      const runRes = await supabase.from("procedure_runs").select("*").eq("id", id).single();
      if (!runRes.data) return;
      setRun(runRes.data);

      const [procRes, reportRes, eventsRes, nodesRes, edgesRes] = await Promise.all([
        supabase.from("procedures").select("*").eq("id", runRes.data.procedure_id).single(),
        supabase.from("deviation_reports").select("*").eq("procedure_run_id", id).single(),
        supabase.from("observed_events").select("*").eq("procedure_run_id", id).order("timestamp"),
        supabase.from("nodes").select("*").eq("procedure_id", runRes.data.procedure_id),
        supabase.from("edges").select("*").eq("procedure_id", runRes.data.procedure_id),
      ]);

      setProcedure(procRes.data);
      setReport(reportRes.data);
      setEvents(eventsRes.data || []);
      setNodes(nodesRes.data || []);
      setEdges(edgesRes.data || []);
      setLoading(false);
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-zinc-800 rounded animate-pulse" />
        <div className="h-12 bg-zinc-800 rounded animate-pulse" />
        <div className="h-96 bg-zinc-800 rounded animate-pulse" />
      </div>
    );
  }

  if (!run) {
    return <div className="text-zinc-500">Session not found.</div>;
  }

  return (
    <div>
      <div className="mb-6">
        <a href="/" className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">&larr; Back to sessions</a>
        <h2 className="text-2xl font-bold text-white mt-2">{procedure?.name || run.procedure_id}</h2>
        <div className="flex items-center gap-4 mt-1 text-sm text-zinc-500">
          {run.surgeon_name && <span>{run.surgeon_name}</span>}
          <span>{new Date(run.started_at).toLocaleString()}</span>
          <span className="font-mono text-xs">{run.id.slice(0, 8)}</span>
        </div>
      </div>

      <div className="flex gap-1 border-b border-zinc-800 mb-6">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-[1px]",
              tab === t
                ? "text-white border-green-500"
                : "text-zinc-500 border-transparent hover:text-zinc-300"
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && <OverviewTab run={run} report={report} events={events} nodes={nodes} procedure={procedure} />}
      {tab === "Video & Timeline" && <TimelineTab events={events} nodes={nodes} report={report} />}
      {tab === "Procedure Graph" && <GraphTab nodes={nodes} edges={edges} events={events} report={report} />}
      {tab === "Deviation Analysis" && <DeviationsTab report={report} />}
      {tab === "Report" && <ReportTab report={report} runId={run.id} />}
    </div>
  );
}

