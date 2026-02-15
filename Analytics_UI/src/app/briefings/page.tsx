"use client";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { PATIENT_PROFILES } from "@/lib/patient-data";
import type { ProcedureRun } from "@/lib/types";

export default function Briefings() {
  const [runs, setRuns] = useState<(ProcedureRun & { procedure_name?: string })[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [runsRes, procsRes] = await Promise.all([
        supabase.from("procedure_runs").select("*").order("created_at", { ascending: false }),
        supabase.from("procedures").select("id, name"),
      ]);

      const procMap = new Map((procsRes.data || []).map((p: any) => [p.id, p.name]));
      const rows = (runsRes.data || [])
        .filter((r: any) => PATIENT_PROFILES[r.id])
        .map((r: any) => ({ ...r, procedure_name: procMap.get(r.procedure_id) }));

      setRuns(rows);
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="relative mb-10 rounded-2xl overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-violet-500/10 via-indigo-500/5 to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(139,92,246,0.08),transparent_60%)]" />
        <div className="relative p-8">
          <h2 className="text-3xl font-bold text-white tracking-tight">Pre-Op Briefings</h2>
          <p className="text-sm text-zinc-400 mt-1">Voice-powered patient briefing — ask about your patient before scrubbing in</p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-zinc-900/50 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3 stagger-children">
          {runs.map((r) => {
            const patient = PATIENT_PROFILES[r.id];
            if (!patient) return null;
            const hasAllergy = patient.allergies.length > 0;
            const hasCriticalLab = patient.lab_results?.some((l) => l.flag === "critical");

            return (
              <a
                key={r.id}
                href={`/briefings/${r.id}`}
                className="gradient-border p-5 flex items-center gap-5 hover:bg-white/[0.03] transition-all duration-200 group cursor-pointer"
              >
                <div className="w-12 h-12 rounded-full bg-violet-500/10 border border-violet-500/20 flex items-center justify-center shrink-0">
                  <svg className="w-6 h-6 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-white group-hover:text-violet-400 transition-colors">
                      {patient.name}
                    </h3>
                    <span className="text-xs text-zinc-500">{patient.age}{patient.sex}</span>
                    {hasAllergy && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                        ALLERGY
                      </span>
                    )}
                    {hasCriticalLab && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        CRITICAL LAB
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400 mt-0.5 truncate">{patient.chief_complaint}</p>
                  <p className="text-xs text-zinc-600 mt-0.5">{r.procedure_name}</p>
                </div>
                <svg className="w-5 h-5 text-zinc-600 group-hover:text-violet-400 transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}

