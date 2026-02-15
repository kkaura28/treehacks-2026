"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { useConversation } from "@elevenlabs/react";
import { supabase } from "@/lib/supabase";
import { PATIENT_PROFILES, formatPatientContext, type PatientProfile } from "@/lib/patient-data";
import { cn } from "@/lib/utils";

const AGENT_ID = "agent_3301kh6y1pc6eag8659yq8za4vd5";

function buildSessionConfig() {
  return {
    agentId: AGENT_ID,
    connectionType: "webrtc" as const,
  };
}

export default function BriefingChat() {
  const { id } = useParams() as { id: string };
  const patient = PATIENT_PROFILES[id] || null;

  const [procedureName, setProcedureName] = useState("");
  const [error, setError] = useState("");
  const started = useRef(false);
  const patientRef = useRef(patient);
  patientRef.current = patient;

  const conversation = useConversation({
    onConnect: () => {
      // Inject patient context as a user message after a short delay
      setTimeout(() => {
        if (patientRef.current) {
          const ctx = formatPatientContext(patientRef.current);
          conversation.sendContextualUpdate(ctx);
          // Also send as a user text message so the agent definitely sees it
          conversation.sendUserMessage(
            `Here is the patient I am operating on today:\n\n${ctx}\n\nBrief me.`
          );
        }
      }, 1500);
    },
    onError: (e: any) => {
      console.error("ElevenLabs error:", e);
      setError(typeof e === "string" ? e : e?.message || "Connection error");
    },
  });

  // Load procedure name
  useEffect(() => {
    async function load() {
      const runRes = await supabase.from("procedure_runs").select("procedure_id").eq("id", id).single();
      if (runRes.data) {
        const procRes = await supabase.from("procedures").select("name").eq("id", runRes.data.procedure_id).single();
        setProcedureName(procRes.data?.name || "");
      }
    }
    load();
  }, [id]);

  // Auto-start conversation
  useEffect(() => {
    if (patient && !started.current && conversation.status === "disconnected") {
      started.current = true;
      conversation.startSession(buildSessionConfig()).catch((e) => {
        console.error("Failed to start session:", e);
        started.current = false;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (conversation.status === "connected") {
        conversation.endSession();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleConversation = useCallback(async () => {
    if (!patient) return;
    if (conversation.status === "connected") {
      await conversation.endSession();
      started.current = false;
    } else {
      started.current = true;
      await conversation.startSession(buildSessionConfig());
    }
  }, [patient, conversation]);

  if (!patient) {
    return <div className="text-zinc-500">Patient not found for this session.</div>;
  }

  const isConnected = conversation.status === "connected";
  const isConnecting = conversation.status === "connecting";

  return (
    <div className="animate-fade-in">
      <a href="/briefings" className="text-sm text-zinc-500 hover:text-violet-400 transition-colors">&larr; All briefings</a>

      <div className="grid grid-cols-12 gap-6 mt-4">
        {/* Patient sidebar */}
        <div className="col-span-4">
          <div className="gradient-border p-5 sticky top-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">{patient.name}</h3>
                <span className="text-xs text-zinc-500">{patient.age}{patient.sex} · {patient.vitals.weight}</span>
              </div>
            </div>

            {procedureName && (
              <div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Procedure</div>
                <div className="text-xs text-zinc-300">{procedureName}</div>
              </div>
            )}

            <div>
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Chief Complaint</div>
              <div className="text-xs text-zinc-300">{patient.chief_complaint}</div>
            </div>

            {patient.allergies.length > 0 && (
              <div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Allergies</div>
                {patient.allergies.map((a) => (
                  <div key={a.substance} className="flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                    <span className="text-xs text-red-400 font-medium">{a.substance}</span>
                    <span className="text-xs text-zinc-500">— {a.reaction}</span>
                  </div>
                ))}
              </div>
            )}

            {patient.medications.length > 0 && (
              <div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Medications</div>
                {patient.medications.map((m) => (
                  <div key={m.name} className="text-xs text-zinc-400 mt-1">
                    <span className="text-zinc-300 font-medium">{m.name}</span> {m.dose}
                  </div>
                ))}
              </div>
            )}

            <div>
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Vitals</div>
              <div className="grid grid-cols-2 gap-1.5 text-xs">
                <span className="text-zinc-400">BP <span className="text-zinc-300">{patient.vitals.bp}</span></span>
                <span className="text-zinc-400">HR <span className="text-zinc-300">{patient.vitals.hr}</span></span>
                <span className="text-zinc-400">Temp <span className="text-zinc-300">{patient.vitals.temp}</span></span>
                <span className="text-zinc-400">SpO2 <span className="text-zinc-300">{patient.vitals.spo2}%</span></span>
              </div>
            </div>

            {patient.lab_results && patient.lab_results.length > 0 && (
              <div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium mb-1">Labs</div>
                {patient.lab_results.map((l) => (
                  <div key={l.name} className="flex items-center justify-between text-xs mt-1">
                    <span className="text-zinc-400">{l.name}</span>
                    <span className={cn(
                      "font-mono",
                      l.flag === "critical" ? "text-red-400 font-bold" :
                      l.flag === "high" ? "text-amber-400" :
                      l.flag === "low" ? "text-blue-400" : "text-zinc-300"
                    )}>
                      {l.value} {l.flag && <span className="text-[9px] uppercase">({l.flag})</span>}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Voice area */}
        <div className="col-span-8 flex flex-col items-center justify-center" style={{ height: "calc(100vh - 140px)" }}>
          <h2 className="text-xl font-bold text-white mb-2">Pre-Op Briefing</h2>
          <p className="text-sm text-zinc-500 mb-12">Voice conversation with AI about your patient</p>

          {/* Pulsing orb */}
          <div className="relative mb-8">
            <div className={cn(
              "absolute inset-0 rounded-full transition-all duration-500",
              isConnected && conversation.isSpeaking
                ? "bg-violet-500/20 scale-150 animate-pulse"
                : isConnected
                  ? "bg-violet-500/10 scale-125"
                  : "bg-transparent scale-100"
            )} />
            <button
              onClick={toggleConversation}
              disabled={isConnecting}
              className={cn(
                "relative w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 border-2",
                isConnected
                  ? "bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30 shadow-[0_0_40px_rgba(239,68,68,0.2)]"
                  : isConnecting
                    ? "bg-violet-500/10 border-violet-500/30 text-violet-400 opacity-60 cursor-wait"
                    : "bg-violet-500/10 border-violet-500/30 text-violet-400 hover:bg-violet-500/20 hover:border-violet-500/50 hover:shadow-[0_0_40px_rgba(139,92,246,0.2)]"
              )}
            >
              {isConnected ? (
                <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              ) : (
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                </svg>
              )}
            </button>
          </div>

          <span className="text-sm text-zinc-500">
            {isConnecting ? "Connecting…" :
             isConnected && conversation.isSpeaking ? "Agent speaking…" :
             isConnected ? "Listening — ask a question" :
             "Tap to start briefing"}
          </span>

          {error && (
            <div className="mt-4 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 max-w-md text-center">
              {error}
            </div>
          )}

          {isConnected && (
            <button
              onClick={() => conversation.endSession()}
              className="mt-6 text-xs text-zinc-600 hover:text-red-400 transition-colors"
            >
              End conversation
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
