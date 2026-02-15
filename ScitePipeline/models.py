from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ── Graph models (read from Supabase) ──────────────────────

class Node(BaseModel):
    id: str
    procedure_id: str
    name: str
    phase: str
    mandatory: bool
    optional: bool
    safety_critical: bool
    actors: list[str] = []
    required_tools: list[str] = []
    preconditions: list[str] = []


class Edge(BaseModel):
    from_node: str
    to_node: str
    type: str  # "sequential" | "conditional"


# ── Observed event (written by CV model or mock) ───────────

class ObservedEvent(BaseModel):
    node_id: str
    timestamp: datetime
    confidence: float = 1.0
    source: str = "mock"


# ── Deviation types ────────────────────────────────────────

class DeviationType(str, Enum):
    MISSING = "missing"
    OUT_OF_ORDER = "out_of_order"
    SKIPPED_SAFETY = "skipped_safety"
    UNHANDLED_COMPLICATION = "unhandled_complication"


class RawDeviation(BaseModel):
    node_id: str
    node_name: str
    phase: str
    deviation_type: DeviationType
    mandatory: bool
    safety_critical: bool
    context: str = ""


# ── Adjudication verdicts ──────────────────────────────────

class Verdict(str, Enum):
    CONFIRMED = "confirmed"
    MITIGATED = "mitigated"
    CONTEXT_DEPENDENT = "context_dependent"


class AdjudicatedDeviation(BaseModel):
    node_id: str
    node_name: str
    phase: str
    deviation_type: DeviationType
    verdict: Verdict
    evidence_summary: str = ""
    citations: list[str] = []
    original_mandatory: bool = True
    original_safety_critical: bool = False


# ── Final report ───────────────────────────────────────────

class ComplianceReport(BaseModel):
    procedure_run_id: str
    procedure_id: str
    procedure_name: str
    compliance_score: float = Field(ge=0, le=1)
    total_expected: int
    total_observed: int
    confirmed_count: int = 0
    mitigated_count: int = 0
    review_count: int = 0
    confirmed_deviations: list[AdjudicatedDeviation] = []
    mitigated_deviations: list[AdjudicatedDeviation] = []
    review_deviations: list[AdjudicatedDeviation] = []
    report_text: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

