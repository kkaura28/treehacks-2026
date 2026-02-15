"""
Report generator.

Takes adjudicated deviations and produces a ComplianceReport with:
  - Weighted compliance score
  - Deviations grouped by verdict
  - Human-readable report text
"""

from datetime import datetime, timezone
from models import (
    AdjudicatedDeviation, ComplianceReport, Verdict, DeviationType
)


def _severity_label(dev: AdjudicatedDeviation) -> str:
    """Return a human-readable severity icon/label."""
    if dev.verdict == Verdict.CONFIRMED:
        return "CONFIRMED"
    elif dev.verdict == Verdict.MITIGATED:
        return "MITIGATED"
    return "REVIEW NEEDED"


def _format_deviation_block(dev: AdjudicatedDeviation) -> str:
    """Format a single deviation for the text report."""
    lines = [
        f"  [{_severity_label(dev)}] {dev.node_name}",
        f"    Type: {dev.deviation_type.value}",
        f"    Phase: {dev.phase}",
        f"    Safety-critical: {dev.original_safety_critical}",
    ]
    if dev.evidence_summary:
        # Truncate to keep report readable
        summary = dev.evidence_summary[:300]
        if len(dev.evidence_summary) > 300:
            summary += "..."
        lines.append(f"    Evidence: {summary}")
    if dev.citations:
        lines.append(f"    Citations: {', '.join(dev.citations[:5])}")
    return "\n".join(lines)


def compute_score(
    adjudicated: list[AdjudicatedDeviation],
    total_mandatory: int,
) -> float:
    """
    Compute weighted compliance score.

    - confirmed deviations: full penalty (1.0 each)
    - context_dependent: partial penalty (0.25 each)
    - mitigated: no penalty
    """
    if total_mandatory == 0:
        return 1.0

    confirmed = sum(1 for d in adjudicated if d.verdict == Verdict.CONFIRMED)
    review = sum(1 for d in adjudicated if d.verdict == Verdict.CONTEXT_DEPENDENT)

    penalty = confirmed + (0.25 * review)
    score = max(0.0, (total_mandatory - penalty) / total_mandatory)
    return round(score, 4)


def generate_report(
    procedure_run_id: str,
    procedure_id: str,
    procedure_name: str,
    adjudicated: list[AdjudicatedDeviation],
    total_expected: int,
    total_observed: int,
) -> ComplianceReport:
    """Build the full compliance report."""

    confirmed = [d for d in adjudicated if d.verdict == Verdict.CONFIRMED]
    mitigated = [d for d in adjudicated if d.verdict == Verdict.MITIGATED]
    review = [d for d in adjudicated if d.verdict == Verdict.CONTEXT_DEPENDENT]

    total_mandatory = total_expected  # simplification: use total expected nodes
    score = compute_score(adjudicated, total_mandatory)

    # ── Build text report ──────────────────────────────────
    divider = "=" * 60
    lines = [
        divider,
        "POST-OPERATIVE COMPLIANCE REPORT",
        f"Procedure: {procedure_name}",
        f"Run ID: {procedure_run_id}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Compliance Score: {score:.0%}",
        divider,
        "",
        f"Steps expected: {total_expected}",
        f"Steps observed: {total_observed}",
        f"Deviations found: {len(adjudicated)}",
        f"  Confirmed: {len(confirmed)}",
        f"  Mitigated: {len(mitigated)}",
        f"  Needs review: {len(review)}",
        "",
    ]

    if confirmed:
        lines.append("-" * 60)
        lines.append("CONFIRMED DEVIATIONS")
        lines.append("-" * 60)
        for dev in confirmed:
            lines.append(_format_deviation_block(dev))
            lines.append("")

    if review:
        lines.append("-" * 60)
        lines.append("DEVIATIONS PENDING REVIEW")
        lines.append("-" * 60)
        for dev in review:
            lines.append(_format_deviation_block(dev))
            lines.append("")

    if mitigated:
        lines.append("-" * 60)
        lines.append("MITIGATED DEVIATIONS (no score penalty)")
        lines.append("-" * 60)
        for dev in mitigated:
            lines.append(_format_deviation_block(dev))
            lines.append("")

    if not adjudicated:
        lines.append("No deviations detected. Full compliance.")

    lines.append(divider)
    report_text = "\n".join(lines)

    return ComplianceReport(
        procedure_run_id=procedure_run_id,
        procedure_id=procedure_id,
        procedure_name=procedure_name,
        compliance_score=score,
        total_expected=total_expected,
        total_observed=total_observed,
        confirmed_count=len(confirmed),
        mitigated_count=len(mitigated),
        review_count=len(review),
        confirmed_deviations=confirmed,
        mitigated_deviations=mitigated,
        review_deviations=review,
        report_text=report_text,
    )

