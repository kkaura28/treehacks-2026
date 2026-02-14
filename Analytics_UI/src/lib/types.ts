// ── Supabase table types ──────────────────────────────────

export interface Procedure {
  id: string;
  name: string;
  version: string;
  source_documents: string[];
  created_at: string;
}

export interface ProcedureNode {
  id: string;
  procedure_id: string;
  name: string;
  phase: string;
  mandatory: boolean;
  optional: boolean;
  safety_critical: boolean;
  actors: string[];
  required_tools: string[];
  preconditions: string[];
}

export interface ProcedureEdge {
  id: number;
  procedure_id: string;
  from_node: string;
  to_node: string;
  type: "sequential" | "conditional";
}

export interface ProcedureRun {
  id: string;
  procedure_id: string;
  surgeon_name: string | null;
  patient_id: string | null;
  started_at: string;
  ended_at: string | null;
  status: "in_progress" | "completed" | "cancelled";
  created_at: string;
}

export interface ObservedEvent {
  id: number;
  procedure_run_id: string;
  node_id: string;
  timestamp: string;
  confidence: number;
  source: string;
  metadata: {
    timestamp_seconds?: number;
    observation?: string;
    original_source?: string;
    video_path?: string;
  };
  created_at: string;
}

export interface AdjudicatedDeviation {
  node_id: string;
  node_name: string;
  phase: string;
  deviation_type: "missing" | "out_of_order" | "skipped_safety" | "unhandled_complication";
  verdict: "confirmed" | "mitigated" | "context_dependent";
  evidence_summary: string;
  citations: string[];
  original_mandatory: boolean;
  original_safety_critical: boolean;
}

export interface DeviationReport {
  id: string;
  procedure_run_id: string;
  compliance_score: number;
  total_expected: number;
  total_observed: number;
  confirmed_count: number;
  mitigated_count: number;
  review_count: number;
  raw_deviations: AdjudicatedDeviation[];
  adjudicated: AdjudicatedDeviation[];
  report_text: string;
  created_at: string;
}

// ── Joined types for the UI ──────────────────────────────

export interface SessionListItem extends ProcedureRun {
  procedure_name?: string;
  compliance_score?: number;
  confirmed_count?: number;
  total_deviations?: number;
}

// ── Evidence parsing helpers ─────────────────────────────

export interface ParsedSnippet {
  text: string;
  confidence: number;
  source: string;
  doi: string;
  type: "risk" | "safe";
}

export interface ParsedEvidence {
  citationLandscape: { supporting: number; contrasting: number };
  snippetsAnalyzed: number;
  riskSnippets: ParsedSnippet[];
  safeSnippets: ParsedSnippet[];
}

