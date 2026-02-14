"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { PATIENT_PROFILES, formatPatientContext } from "@/lib/patient-data";
import type { PatientProfile } from "@/lib/patient-data";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function BriefingChat() {
  const { id } = useParams() as { id: string };
  const patient = PATIENT_PROFILES[id] || null;

  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [procedureName, setProcedureName] = useState("");
  const [autoSpeak, setAutoSpeak] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const greeted = useRef(false);

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

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Auto-greet on mount (ref guard prevents Strict Mode double-fire)
  useEffect(() => {
    if (patient && !greeted.current) {
      greeted.current = true;
      sendMessage("Brief me on this patient.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient]);

  const speakText = useCallback((text: string) => {
    if (!autoSpeak || typeof window === "undefined") return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1;
    utterance.pitch = 1;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }, [autoSpeak]);

  const sendMessage = useCallback(async (text: string) => {
    if (!patient || !text.trim()) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...messages, userMsg].map((m) => ({ role: m.role, content: m.content })),
          patientContext: formatPatientContext(patient),
        }),
      });

      const data = await res.json();
      const assistantMsg: Message = { role: "assistant", content: data.content || data.error || "Error" };
      setMessages((prev) => [...prev, assistantMsg]);
      speakText(assistantMsg.content);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Failed to reach the AI. Please try again." }]);
    } finally {
      setLoading(false);
    }
  }, [patient, messages, speakText]);

  // Voice recognition
  const toggleListening = useCallback(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition not supported in this browser. Use Chrome.");
      return;
    }

    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      setListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setListening(false);
      sendMessage(transcript);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }, [listening, sendMessage]);

  const stopSpeaking = () => {
    window.speechSynthesis.cancel();
    setSpeaking(false);
  };

  if (!patient) {
    return <div className="text-zinc-500">Patient not found for this session.</div>;
  }

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

        {/* Chat area */}
        <div className="col-span-8 flex flex-col" style={{ height: "calc(100vh - 140px)" }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white">Pre-Op Briefing</h2>
            <div className="flex items-center gap-3">
              {speaking && (
                <button
                  onClick={stopSpeaking}
                  className="text-xs text-zinc-400 hover:text-red-400 transition-colors flex items-center gap-1"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Stop speaking
                </button>
              )}
              <button
                onClick={() => { setAutoSpeak(!autoSpeak); if (speaking) stopSpeaking(); }}
                className={cn(
                  "text-xs flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-colors",
                  autoSpeak
                    ? "text-violet-400 border-violet-500/30 bg-violet-500/10"
                    : "text-zinc-500 border-zinc-700 bg-zinc-800/50"
                )}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
                </svg>
                Auto-speak {autoSpeak ? "on" : "off"}
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-4 pr-2 mb-4">
            {messages.map((m, i) => (
              <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cn(
                  "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
                  m.role === "user"
                    ? "bg-violet-500/20 text-violet-100 border border-violet-500/20"
                    : "bg-zinc-800/80 text-zinc-200 border border-zinc-700/50"
                )}>
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-zinc-800/80 border border-zinc-700/50 rounded-2xl px-4 py-3">
                  <div className="flex gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce [animation-delay:0ms]" />
                    <div className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce [animation-delay:150ms]" />
                    <div className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Mic button */}
          <div className="flex flex-col items-center gap-2">
            <button
              onClick={toggleListening}
              disabled={loading}
              className={cn(
                "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-200 border-2",
                listening
                  ? "bg-red-500/20 border-red-500 text-red-400 shadow-[0_0_30px_rgba(239,68,68,0.3)] animate-pulse"
                  : "bg-violet-500/10 border-violet-500/30 text-violet-400 hover:bg-violet-500/20 hover:border-violet-500/50 hover:shadow-[0_0_20px_rgba(139,92,246,0.2)]",
                loading && "opacity-50 cursor-not-allowed"
              )}
            >
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
              </svg>
            </button>
            <span className="text-[10px] text-zinc-600">
              {listening ? "Listening…" : loading ? "Thinking…" : "Tap to ask"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

