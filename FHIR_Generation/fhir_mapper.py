"""
FHIR R4 mapper for surgical compliance pipeline.

Converts live-video-derived surgical data (observed events, deviations,
compliance reports) into a FHIR R4 Bundle that can be submitted directly
to hospital EHR systems — eliminating the manual operative-report backlog.

FHIR resources generated:
  Patient, Practitioner, Encounter, Procedure, Observation (per step),
  DetectedIssue (per deviation), Composition (operative note), Media (video ref)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

# ── SNOMED / LOINC codes for common surgical procedures ───

PROCEDURE_SNOMED: dict[str, dict] = {
    "laparoscopic_cholecystectomy":   {"code": "45595009",  "display": "Laparoscopic cholecystectomy"},
    "incision_drainage_abscess":      {"code": "36164003",  "display": "Incision and drainage of abscess"},
    "laparoscopic_appendectomy":      {"code": "6025007",   "display": "Laparoscopic appendectomy"},
    "cesarean_section":               {"code": "11466000",  "display": "Cesarean section"},
}

# Deviation type → FHIR DetectedIssue code
_DEVIATION_CODE_MAP = {
    "missing":                  ("missing-step",       "Mandatory step not observed"),
    "out_of_order":             ("out-of-order",       "Steps performed out of expected sequence"),
    "skipped_safety":           ("skipped-safety",     "Safety-critical step was skipped"),
    "unhandled_complication":   ("unhandled-complication", "Complication arose without documented management"),
}

# Verdict → FHIR severity
_VERDICT_SEVERITY = {
    "confirmed":         "high",
    "context_dependent": "moderate",
    "mitigated":         "low",
}


def _uid() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Individual resource builders ──────────────────────────

def _patient(patient_id: str = "patient-1", name: str = "Surgical Patient") -> dict:
    return {
        "fullUrl": f"urn:uuid:{patient_id}",
        "resource": {
            "resourceType": "Patient",
            "id": patient_id,
            "name": [{"use": "usual", "text": name}],
            "active": True,
        },
        "request": {"method": "POST", "url": "Patient"},
    }


def _practitioner(pract_id: str = "practitioner-1", name: str = "Attending Surgeon") -> dict:
    return {
        "fullUrl": f"urn:uuid:{pract_id}",
        "resource": {
            "resourceType": "Practitioner",
            "id": pract_id,
            "name": [{"use": "usual", "text": name}],
            "qualification": [{
                "code": {
                    "coding": [{"system": "http://snomed.info/sct", "code": "304292004", "display": "Surgeon"}],
                },
            }],
        },
        "request": {"method": "POST", "url": "Practitioner"},
    }


def _encounter(enc_id: str, patient_ref: str, run_id: str) -> dict:
    return {
        "fullUrl": f"urn:uuid:{enc_id}",
        "resource": {
            "resourceType": "Encounter",
            "id": enc_id,
            "status": "finished",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "IMP",
                "display": "inpatient encounter",
            },
            "subject": {"reference": f"urn:uuid:{patient_ref}"},
            "identifier": [{"system": "urn:surgical-pipeline", "value": run_id}],
        },
        "request": {"method": "POST", "url": "Encounter"},
    }


def _procedure(
    proc_id: str,
    patient_ref: str,
    encounter_ref: str,
    practitioner_ref: str,
    procedure_name: str,
    procedure_code_id: str,
    compliance_score: float,
    total_observed: int,
    total_expected: int,
    run_id: str,
) -> dict:
    snomed = PROCEDURE_SNOMED.get(procedure_code_id, {"code": "71388002", "display": procedure_name})
    return {
        "fullUrl": f"urn:uuid:{proc_id}",
        "resource": {
            "resourceType": "Procedure",
            "id": proc_id,
            "status": "completed",
            "code": {
                "coding": [{"system": "http://snomed.info/sct", **snomed}],
                "text": procedure_name,
            },
            "subject": {"reference": f"urn:uuid:{patient_ref}"},
            "encounter": {"reference": f"urn:uuid:{encounter_ref}"},
            "performer": [{"actor": {"reference": f"urn:uuid:{practitioner_ref}"}}],
            "identifier": [{"system": "urn:surgical-pipeline:run", "value": run_id}],
            "extension": [
                {
                    "url": "urn:surgical-pipeline:compliance-score",
                    "valueDecimal": compliance_score,
                },
                {
                    "url": "urn:surgical-pipeline:steps-observed",
                    "valueInteger": total_observed,
                },
                {
                    "url": "urn:surgical-pipeline:steps-expected",
                    "valueInteger": total_expected,
                },
            ],
        },
        "request": {"method": "POST", "url": "Procedure"},
    }


def _observation_from_event(
    event: dict,
    patient_ref: str,
    encounter_ref: str,
    procedure_ref: str,
    node_lookup: dict[str, dict] | None = None,
) -> dict:
    """Map a single ObservedEvent (from video analysis) to a FHIR Observation."""
    obs_id = f"obs-{event['node_id']}-{_uid()[:8]}"
    node_info = (node_lookup or {}).get(event["node_id"], {})
    display = node_info.get("name", event["node_id"])
    phase = node_info.get("phase", "unknown")

    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "procedure",
                "display": "Procedure",
            }],
        }],
        "code": {
            "coding": [{
                "system": "urn:surgical-pipeline:step",
                "code": event["node_id"],
                "display": display,
            }],
            "text": f"Surgical step: {display}",
        },
        "subject": {"reference": f"urn:uuid:{patient_ref}"},
        "encounter": {"reference": f"urn:uuid:{encounter_ref}"},
        "partOf": [{"reference": f"urn:uuid:{procedure_ref}"}],
        "effectiveDateTime": event.get("timestamp", _now_iso()),
        "method": {
            "coding": [{
                "system": "urn:surgical-pipeline:detection-method",
                "code": event.get("source", "gemini"),
                "display": f"AI video analysis ({event.get('source', 'gemini')})",
            }],
        },
        "component": [
            {
                "code": {"text": "confidence"},
                "valueQuantity": {
                    "value": round(event.get("confidence", 1.0) * 100, 1),
                    "unit": "%",
                    "system": "http://unitsofmeasure.org",
                    "code": "%",
                },
            },
            {
                "code": {"text": "surgical-phase"},
                "valueString": phase,
            },
        ],
    }

    return {
        "fullUrl": f"urn:uuid:{obs_id}",
        "resource": resource,
        "request": {"method": "POST", "url": "Observation"},
    }


def _detected_issue_from_deviation(
    dev: dict,
    patient_ref: str,
    procedure_ref: str,
) -> dict:
    """Map an AdjudicatedDeviation to a FHIR DetectedIssue."""
    issue_id = f"issue-{dev['node_id']}-{_uid()[:8]}"
    dev_type = dev.get("deviation_type", "missing")
    verdict = dev.get("verdict", "confirmed")
    code_info = _DEVIATION_CODE_MAP.get(dev_type, ("other", "Other deviation"))
    severity = _VERDICT_SEVERITY.get(verdict, "moderate")

    evidence_entries = []
    for cite in dev.get("citations", [])[:5]:
        evidence_entries.append({"detail": [{"display": cite}]})

    resource: dict[str, Any] = {
        "resourceType": "DetectedIssue",
        "id": issue_id,
        "status": "final",
        "severity": severity,
        "code": {
            "coding": [{
                "system": "urn:surgical-pipeline:deviation-type",
                "code": code_info[0],
                "display": code_info[1],
            }],
            "text": f"{dev.get('node_name', dev['node_id'])}: {code_info[1]}",
        },
        "patient": {"reference": f"urn:uuid:{patient_ref}"},
        "implicated": [{"reference": f"urn:uuid:{procedure_ref}"}],
        "detail": dev.get("evidence_summary", "")[:2000],
        "extension": [
            {
                "url": "urn:surgical-pipeline:safety-critical",
                "valueBoolean": dev.get("original_safety_critical", False),
            },
            {
                "url": "urn:surgical-pipeline:surgical-phase",
                "valueString": dev.get("phase", ""),
            },
        ],
    }
    if evidence_entries:
        resource["evidence"] = evidence_entries

    return {
        "fullUrl": f"urn:uuid:{issue_id}",
        "resource": resource,
        "request": {"method": "POST", "url": "DetectedIssue"},
    }


def _media_video(
    media_id: str,
    patient_ref: str,
    procedure_ref: str,
    video_url: str = "",
    video_name: str = "surgical-video.mp4",
) -> dict:
    resource: dict[str, Any] = {
        "resourceType": "Media",
        "id": media_id,
        "status": "completed",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/media-type",
                "code": "video",
                "display": "Video",
            }],
        },
        "subject": {"reference": f"urn:uuid:{patient_ref}"},
        "partOf": [{"reference": f"urn:uuid:{procedure_ref}"}],
        "content": {
            "contentType": "video/mp4",
            "title": video_name,
        },
    }
    if video_url:
        resource["content"]["url"] = video_url

    return {
        "fullUrl": f"urn:uuid:{media_id}",
        "resource": resource,
        "request": {"method": "POST", "url": "Media"},
    }


def _composition(
    comp_id: str,
    patient_ref: str,
    encounter_ref: str,
    practitioner_ref: str,
    procedure_ref: str,
    issue_ids: list[str],
    observation_ids: list[str],
    report_text: str,
    procedure_name: str,
    compliance_score: float,
    summary: dict,
) -> dict:
    """Build a FHIR Composition — the machine-readable operative note."""
    sections = [
        {
            "title": "Procedure Summary",
            "code": {"coding": [{"system": "http://loinc.org", "code": "8648-8", "display": "Hospital course Narrative"}]},
            "text": {
                "status": "generated",
                "div": (
                    f'<div xmlns="http://www.w3.org/1999/xhtml">'
                    f"<p><b>Procedure:</b> {procedure_name}</p>"
                    f"<p><b>Compliance Score:</b> {compliance_score:.0%}</p>"
                    f"<p><b>Steps observed:</b> {summary.get('total_observed', 0)} / {summary.get('total_expected', 0)}</p>"
                    f"<p><b>Deviations:</b> {summary.get('confirmed', 0)} confirmed, "
                    f"{summary.get('mitigated', 0)} mitigated, {summary.get('review', 0)} review needed</p>"
                    f"</div>"
                ),
            },
        },
    ]

    if observation_ids:
        sections.append({
            "title": "Observed Surgical Steps (AI Video Analysis)",
            "code": {"coding": [{"system": "http://loinc.org", "code": "29554-3", "display": "Procedure Narrative"}]},
            "entry": [{"reference": f"urn:uuid:{oid}"} for oid in observation_ids],
        })

    if issue_ids:
        sections.append({
            "title": "Detected Deviations from Standard Operating Procedure",
            "code": {"coding": [{"system": "http://loinc.org", "code": "55112-7", "display": "Document summary"}]},
            "entry": [{"reference": f"urn:uuid:{iid}"} for iid in issue_ids],
        })

    if report_text:
        # Truncate to keep FHIR payload reasonable
        trimmed = report_text[:5000]
        sections.append({
            "title": "Full Compliance Report",
            "code": {"coding": [{"system": "http://loinc.org", "code": "11504-8", "display": "Surgical operation note"}]},
            "text": {
                "status": "generated",
                "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><pre>{trimmed}</pre></div>',
            },
        })

    return {
        "fullUrl": f"urn:uuid:{comp_id}",
        "resource": {
            "resourceType": "Composition",
            "id": comp_id,
            "status": "final",
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "11504-8",
                    "display": "Surgical operation note",
                }],
            },
            "subject": {"reference": f"urn:uuid:{patient_ref}"},
            "encounter": {"reference": f"urn:uuid:{encounter_ref}"},
            "date": _now_iso(),
            "author": [{"reference": f"urn:uuid:{practitioner_ref}"}],
            "title": f"Post-Operative Compliance Report — {procedure_name}",
            "section": sections,
        },
        "request": {"method": "POST", "url": "Composition"},
    }


# ── Public API ────────────────────────────────────────────

def build_fhir_bundle(
    compliance_report: dict,
    observed_events: list[dict] | None = None,
    node_lookup: dict[str, dict] | None = None,
    video_url: str = "",
    patient_name: str = "Surgical Patient",
    surgeon_name: str = "Attending Surgeon",
) -> dict:
    """
    Convert surgical pipeline output into a complete FHIR R4 transaction Bundle.

    Args:
        compliance_report: ComplianceReport.model_dump() dict from the pipeline
        observed_events:   List of ObservedEvent dicts (from video interpreter)
        node_lookup:       {node_id: {name, phase, ...}} for enriching Observations
        video_url:         URL of the surgical video (optional)
        patient_name:      Patient name placeholder
        surgeon_name:      Surgeon name placeholder

    Returns:
        FHIR R4 Bundle dict ready for JSON serialization / EHR submission
    """
    # Stable ref IDs
    patient_id      = "patient-1"
    practitioner_id = "practitioner-1"
    encounter_id    = f"enc-{compliance_report['procedure_run_id']}"
    procedure_id    = f"proc-{compliance_report['procedure_run_id']}"
    media_id        = f"media-{compliance_report['procedure_run_id']}"
    comp_id         = f"comp-{compliance_report['procedure_run_id']}"

    entries: list[dict] = []

    # Core resources
    entries.append(_patient(patient_id, patient_name))
    entries.append(_practitioner(practitioner_id, surgeon_name))
    entries.append(_encounter(encounter_id, patient_id, compliance_report["procedure_run_id"]))
    entries.append(_procedure(
        proc_id=procedure_id,
        patient_ref=patient_id,
        encounter_ref=encounter_id,
        practitioner_ref=practitioner_id,
        procedure_name=compliance_report["procedure_name"],
        procedure_code_id=compliance_report.get("procedure_id", ""),
        compliance_score=compliance_report["compliance_score"],
        total_observed=compliance_report["total_observed"],
        total_expected=compliance_report["total_expected"],
        run_id=compliance_report["procedure_run_id"],
    ))

    # Video reference
    if video_url:
        entries.append(_media_video(media_id, patient_id, procedure_id, video_url))

    # Observations from video-detected events
    observation_ids: list[str] = []
    for ev in (observed_events or []):
        obs_entry = _observation_from_event(ev, patient_id, encounter_id, procedure_id, node_lookup)
        observation_ids.append(obs_entry["resource"]["id"])
        entries.append(obs_entry)

    # DetectedIssues from deviations
    issue_ids: list[str] = []
    all_devs = (
        compliance_report.get("confirmed_deviations", [])
        + compliance_report.get("review_deviations", [])
        + compliance_report.get("mitigated_deviations", [])
    )
    for dev in all_devs:
        issue_entry = _detected_issue_from_deviation(dev, patient_id, procedure_id)
        issue_ids.append(issue_entry["resource"]["id"])
        entries.append(issue_entry)

    # Composition (operative note)
    summary = {
        "total_observed": compliance_report["total_observed"],
        "total_expected": compliance_report["total_expected"],
        "confirmed":      compliance_report.get("confirmed_count", 0),
        "mitigated":      compliance_report.get("mitigated_count", 0),
        "review":         compliance_report.get("review_count", 0),
    }
    entries.append(_composition(
        comp_id=comp_id,
        patient_ref=patient_id,
        encounter_ref=encounter_id,
        practitioner_ref=practitioner_id,
        procedure_ref=procedure_id,
        issue_ids=issue_ids,
        observation_ids=observation_ids,
        report_text=compliance_report.get("report_text", ""),
        procedure_name=compliance_report["procedure_name"],
        compliance_score=compliance_report["compliance_score"],
        summary=summary,
    ))

    return {
        "resourceType": "Bundle",
        "id": f"bundle-{compliance_report['procedure_run_id']}",
        "type": "transaction",
        "timestamp": _now_iso(),
        "entry": entries,
    }

