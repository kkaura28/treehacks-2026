"use client";
import { useEffect, useState } from "react";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";
import type { ObservedEvent } from "@/lib/types";

interface Props {
  events: ObservedEvent[];
  procedureId: string;
}

interface KinematicsData {
  fps: number;
  instruments: InstrumentData[];
  goals: { domain: string; score: number; max: number }[];
  overall_score: number;
}

interface InstrumentData {
  name: string;
  frames: number;
  duration_seconds: number;
  unit: string;            // "px" or "m"
  path_length: number;
  motion_economy: number;
  idle_fraction: number;
  movement_count: number;
  smoothness_sparc: number;
  tremor_index: number;
  mean_speed: number;
  max_speed: number;
  source: string;
  bimanual_correlation?: number;
  tip_spread_std?: number;
  hand_separation_std?: number;
  tip0?: InstrumentData;
  tip1?: InstrumentData;
}

type MetricDef = { key: keyof InstrumentData; label: string; unitLabel: (u: string) => string; description: string; lowerBetter: boolean };

const METRIC_KEYS: MetricDef[] = [
  { key: "path_length", label: "Path Length", unitLabel: u => u, description: "Total distance traveled by tracked point", lowerBetter: true },
  { key: "motion_economy", label: "Motion Economy", unitLabel: () => "ratio", description: "Straight-line / actual path (1.0 = perfect)", lowerBetter: false },
  { key: "idle_fraction", label: "Idle Time", unitLabel: () => "%", description: "Fraction of frames with negligible movement", lowerBetter: true },
  { key: "movement_count", label: "Movement Count", unitLabel: () => "moves", description: "Discrete movement segments detected", lowerBetter: true },
  { key: "smoothness_sparc", label: "Smoothness", unitLabel: () => "SPARC", description: "Spectral arc length — closer to 0 = smoother", lowerBetter: false },
  { key: "tremor_index", label: "Tremor Index", unitLabel: u => u, description: "RMS high-frequency oscillation amplitude", lowerBetter: true },
];

function statusForMetric(key: string, value: number, unit: string): "pass" | "marginal" | "fail" {
  if (unit === "m") {
    // 3D hand thresholds (meters)
    const t: Record<string, [number, number, boolean]> = {
      path_length:     [40, 70, true],
      motion_economy:  [0.03, 0.01, false],
      idle_fraction:   [0.2, 0.4, true],
      movement_count:  [20, 40, true],
      smoothness_sparc:[-100, -200, false],
      tremor_index:    [0.03, 0.06, true],
    };
    const th = t[key];
    if (!th) return "marginal";
    const [good, bad, lb] = th;
    if (lb) return value <= good ? "pass" : value <= bad ? "marginal" : "fail";
    return value >= good ? "pass" : value >= bad ? "marginal" : "fail";
  }
  // Pixel thresholds
  const t: Record<string, [number, number, boolean]> = {
    path_length:     [6000, 9000, true],
    motion_economy:  [0.03, 0.01, false],
    idle_fraction:   [0.45, 0.6, true],
    movement_count:  [80, 150, true],
    smoothness_sparc:[-200, -300, false],
    tremor_index:    [10, 15, true],
  };
  const th = t[key];
  if (!th) return "marginal";
  const [good, bad, lb] = th;
  if (lb) return value <= good ? "pass" : value <= bad ? "marginal" : "fail";
  return value >= good ? "pass" : value >= bad ? "marginal" : "fail";
}

function StatusDot({ status }: { status: "pass" | "marginal" | "fail" }) {
  return (
    <span className={cn(
      "w-2.5 h-2.5 rounded-full inline-block",
      status === "pass" ? "bg-emerald-500" : status === "marginal" ? "bg-amber-500" : "bg-red-500"
    )} />
  );
}

const SOURCE_BADGES: Record<string, string> = {
  optical_flow: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  foundation_pose: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  hamer: "text-pink-400 bg-pink-500/10 border-pink-500/20",
};

const SOURCE_LABELS: Record<string, string> = {
  optical_flow: "Optical Flow",
  foundation_pose: "FoundationPose",
  hamer: "HaMeR",
};

function formatVal(val: number, key: string, unit: string): string {
  if (key === "idle_fraction") return String(Math.round(val * 100));
  if (unit === "m") {
    if (key === "path_length") return val.toFixed(2);
    if (key === "tremor_index" || key === "mean_speed" || key === "max_speed") return val.toFixed(4);
  }
  if (typeof val === "number") return val > 100 ? String(Math.round(val)) : String(val);
  return String(val);
}

export function SkillsTab({ events, procedureId }: Props) {
  const [data, setData] = useState<KinematicsData | null>(null);

  useEffect(() => {
    fetch("/data/kinematics.json")
      .then(r => r.json())
      .then(setData)
      .catch(() => setData(null));
  }, []);

  if (!data) {
    return <div className="text-zinc-500">Loading kinematics data…</div>;
  }

  const { instruments, goals, overall_score } = data;
  const overallPass = overall_score >= 60;
  const radarData = goals.map(g => ({ domain: g.domain, score: g.score, fullMark: 5 }));

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Overall Assessment */}
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-4 gradient-border p-6 flex flex-col items-center justify-center glow-teal">
          <div className={cn(
            "text-6xl font-bold",
            overallPass
              ? "bg-gradient-to-b from-emerald-400 to-teal-400 bg-clip-text text-transparent"
              : "bg-gradient-to-b from-red-400 to-rose-400 bg-clip-text text-transparent"
          )}>
            {overall_score}
          </div>
          <div className="text-sm text-zinc-400 mt-1">GOALS Score</div>
          <div className={cn(
            "mt-3 px-4 py-1.5 rounded-full text-sm font-semibold border",
            overallPass
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              : "bg-red-500/10 text-red-400 border-red-500/20"
          )}>
            {overallPass ? "PASS" : "NEEDS IMPROVEMENT"}
          </div>
          <div className="text-xs text-zinc-600 mt-3 text-center">
            Based on GOALS/OSATS surgical skills framework
          </div>
        </div>

        {/* Radar Chart */}
        <div className="col-span-8 gradient-border p-5">
          <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-3">Skills Domain Assessment</div>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData} cx="50%" cy="50%">
              <PolarGrid stroke="#27272a" />
              <PolarAngleAxis dataKey="domain" tick={{ fill: "#a1a1aa", fontSize: 11, dy: -10 }} />
              <PolarRadiusAxis angle={90} domain={[0, 5]} tick={{ fill: "#52525b", fontSize: 10 }} axisLine={false} />
              <Radar name="Score" dataKey="score" stroke="#2dd4bf" fill="#2dd4bf" fillOpacity={0.15} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Domain Scores Detail */}
      <div className="gradient-border p-5">
        <div className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-4">Domain Scores</div>
        <div className="space-y-3 stagger-children">
          {goals.map((g) => {
            const pct = (g.score / g.max) * 100;
            const color = g.score >= 4 ? "from-emerald-500 to-teal-400" : g.score >= 3 ? "from-amber-500 to-yellow-400" : "from-red-500 to-rose-400";
            return (
              <div key={g.domain} className="flex items-center gap-4">
                <div className="w-44 shrink-0">
                  <div className="text-sm text-white font-medium">{g.domain}</div>
                </div>
                <div className="flex-1 h-3 bg-zinc-800/80 rounded-full overflow-hidden">
                  <div className={cn("h-full rounded-full bg-gradient-to-r transition-all duration-700", color)} style={{ width: `${pct}%` }} />
                </div>
                <div className="w-16 text-right">
                  <span className="text-sm font-semibold text-white tabular-nums">{g.score}</span>
                  <span className="text-xs text-zinc-600"> / 5</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Per-Instrument Kinematics */}
      {instruments.map((inst) => {
        const u = inst.unit;
        const metrics = METRIC_KEYS.map(m => ({
          ...m,
          value: inst[m.key] as number,
          displayUnit: m.key === "idle_fraction" ? "%" : m.unitLabel(u),
          status: statusForMetric(m.key as string, inst[m.key] as number, u),
        }));
        const passCount = metrics.filter(m => m.status === "pass").length;
        const marginalCount = metrics.filter(m => m.status === "marginal").length;

        return (
          <div key={inst.name}>
            <div className="flex items-center gap-4 mb-4">
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider">{inst.name}</h3>
              <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-medium border", SOURCE_BADGES[inst.source] || "text-zinc-400 bg-zinc-800 border-zinc-700")}>
                {SOURCE_LABELS[inst.source] || inst.source}
              </span>
              <span className="text-xs text-zinc-600">
                {inst.frames} frames · {inst.duration_seconds}s
                {u === "m" && " · 3D world coords"}
              </span>
              <div className="flex items-center gap-3 text-xs text-zinc-500 ml-auto">
                <span className="flex items-center gap-1"><StatusDot status="pass" /> {passCount}</span>
                <span className="flex items-center gap-1"><StatusDot status="marginal" /> {marginalCount}</span>
                <span className="flex items-center gap-1"><StatusDot status="fail" /> {metrics.length - passCount - marginalCount}</span>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 stagger-children">
              {metrics.map((m) => (
                <div key={m.key as string} className="gradient-border p-4 hover:bg-white/[0.02] transition-all duration-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-white">{m.label}</span>
                    <StatusDot status={m.status} />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className={cn(
                      "text-3xl font-bold tabular-nums",
                      m.status === "pass" ? "text-emerald-400" : m.status === "marginal" ? "text-amber-400" : "text-red-400"
                    )}>
                      {formatVal(m.value, m.key as string, u)}
                    </span>
                    <span className="text-sm text-zinc-500">{m.displayUnit}</span>
                  </div>
                  <p className="text-xs text-zinc-600 mt-1.5 leading-relaxed">{m.description}</p>
                </div>
              ))}

              {/* Bimanual extras for tweezer */}
              {inst.tip_spread_std !== undefined && (
                <>
                  <div className="gradient-border p-4 hover:bg-white/[0.02] transition-all duration-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">Bimanual Correlation</span>
                      <StatusDot status={inst.bimanual_correlation! > 0.5 ? "pass" : inst.bimanual_correlation! > 0.2 ? "marginal" : "fail"} />
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className={cn("text-3xl font-bold tabular-nums", inst.bimanual_correlation! > 0.5 ? "text-emerald-400" : "text-amber-400")}>
                        {inst.bimanual_correlation}
                      </span>
                      <span className="text-sm text-zinc-500">r</span>
                    </div>
                    <p className="text-xs text-zinc-600 mt-1.5 leading-relaxed">Velocity correlation between two tips (higher = more coordinated)</p>
                  </div>
                  <div className="gradient-border p-4 hover:bg-white/[0.02] transition-all duration-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">Tip Spread σ</span>
                      <StatusDot status={inst.tip_spread_std! < 15 ? "pass" : inst.tip_spread_std! < 30 ? "marginal" : "fail"} />
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className={cn("text-3xl font-bold tabular-nums", inst.tip_spread_std! < 15 ? "text-emerald-400" : "text-amber-400")}>
                        {inst.tip_spread_std}
                      </span>
                      <span className="text-sm text-zinc-500">px</span>
                    </div>
                    <p className="text-xs text-zinc-600 mt-1.5 leading-relaxed">Std deviation of inter-tip distance (lower = more consistent grip)</p>
                  </div>
                </>
              )}

              {/* Hand separation for HaMeR */}
              {inst.hand_separation_std !== undefined && (
                <>
                  <div className="gradient-border p-4 hover:bg-white/[0.02] transition-all duration-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">Hand Coordination</span>
                      <StatusDot status={inst.bimanual_correlation! > 0.3 ? "pass" : inst.bimanual_correlation! > 0.1 ? "marginal" : "fail"} />
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className={cn("text-3xl font-bold tabular-nums", inst.bimanual_correlation! > 0.3 ? "text-emerald-400" : inst.bimanual_correlation! > 0.1 ? "text-amber-400" : "text-red-400")}>
                        {inst.bimanual_correlation}
                      </span>
                      <span className="text-sm text-zinc-500">r</span>
                    </div>
                    <p className="text-xs text-zinc-600 mt-1.5 leading-relaxed">3D velocity correlation between left and right hands</p>
                  </div>
                  <div className="gradient-border p-4 hover:bg-white/[0.02] transition-all duration-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">Hand Separation σ</span>
                      <StatusDot status={inst.hand_separation_std! < 0.03 ? "pass" : inst.hand_separation_std! < 0.06 ? "marginal" : "fail"} />
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className={cn("text-3xl font-bold tabular-nums", inst.hand_separation_std! < 0.03 ? "text-emerald-400" : inst.hand_separation_std! < 0.06 ? "text-amber-400" : "text-red-400")}>
                        {inst.hand_separation_std}
                      </span>
                      <span className="text-sm text-zinc-500">m</span>
                    </div>
                    <p className="text-xs text-zinc-600 mt-1.5 leading-relaxed">Std of inter-hand distance in 3D (lower = more consistent spatial coordination)</p>
                  </div>
                </>
              )}
            </div>
          </div>
        );
      })}

      {/* Data Source Note */}
      <div className="gradient-border p-4 flex items-start gap-3">
        <svg className="w-5 h-5 text-teal-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <div className="text-sm text-white font-medium">Computed from Real Tracking Data</div>
          <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
            Kinematic metrics are computed from per-frame trajectories —
            {instruments.some(i => i.source === "optical_flow") && ` optical flow tip tracking (${instruments.filter(i => i.source === "optical_flow").length} instruments)`}
            {instruments.some(i => i.source === "foundation_pose") && `, FoundationPose 6DoF centroid (${instruments.filter(i => i.source === "foundation_pose").length} instrument)`}
            {instruments.some(i => i.source === "hamer") && `, HaMeR 3D hand mesh reconstruction (${instruments.filter(i => i.source === "hamer").length} hands)`}.
            {" "}GOALS domain scores combine instrument kinematics with 3D hand data for depth perception and bimanual assessment.
          </p>
        </div>
      </div>
    </div>
  );
}
