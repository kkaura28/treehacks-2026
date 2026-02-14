"""
scite.ai adjudicator.

Uses the scite Search API to fetch real citation snippets from surgical
literature, then scores each snippet using a zero-shot NLI model
(DeBERTa) to classify whether the deviation is clinically significant.

Pipeline per deviation:
  1. Build claim-specific search queries
  2. Fetch inline citation snippets from scite
  3. Score each snippet with DeBERTa zero-shot NLI (local, no API)
  4. Aggregate NLI scores + citation type counts → verdict
  5. Return evidence summary with real quotes + model confidence
"""

import re
import httpx
import logging
from typing import Any
from functools import lru_cache

from models import (
    RawDeviation, AdjudicatedDeviation, Verdict, DeviationType
)
from config import get_settings

logger = logging.getLogger(__name__)

SCITE_BASE = "https://api.scite.ai"

# NLI hypothesis labels — the model scores each snippet against these
_RISK_HYPOTHESIS = "Omitting or misordering this surgical step increases the risk of patient harm, injury, or complications."
_SAFE_HYPOTHESIS = "This surgical step can be safely omitted, reordered, or varied without increasing patient risk."


# ── NLI model (loaded once, cached) ───────────────────────

@lru_cache(maxsize=1)
def _get_nli_classifier():
    """
    Load the zero-shot NLI classifier. Cached after first call.
    Uses DeBERTa-v3-base trained on MNLI+FEVER+ANLI — strong on
    biomedical text without fine-tuning.
    """
    from transformers import pipeline
    logger.info("Loading NLI model (first call only)...")
    return pipeline(
        "zero-shot-classification",
        model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        device=-1,  # CPU (use 0 for GPU if available)
    )


def _score_snippet_nli(snippet: str) -> dict:
    """
    Score a single snippet using zero-shot NLI.

    Returns {
        "risk_score": float (0-1),
        "safe_score": float (0-1),
        "dominant": "risk" | "safe" | "neutral",
    }
    """
    classifier = _get_nli_classifier()

    # Truncate long snippets (model max ~512 tokens)
    text = snippet[:500]

    result = classifier(
        text,
        candidate_labels=[_RISK_HYPOTHESIS, _SAFE_HYPOTHESIS],
        multi_label=False,
    )

    scores = dict(zip(result["labels"], result["scores"]))
    risk = scores.get(_RISK_HYPOTHESIS, 0.0)
    safe = scores.get(_SAFE_HYPOTHESIS, 0.0)

    if risk > safe and risk > 0.5:
        dominant = "risk"
    elif safe > risk and safe > 0.5:
        dominant = "safe"
    else:
        dominant = "neutral"

    return {"risk_score": risk, "safe_score": safe, "dominant": dominant}


# ── Claim-specific query builders ──────────────────────────

def _build_search_queries(deviation: RawDeviation, procedure_name: str) -> list[str]:
    step = deviation.node_name
    proc = procedure_name

    if deviation.deviation_type == DeviationType.SKIPPED_SAFETY:
        return [
            f'"{step}" injury complication risk',
            f'"{step}" bile duct injury prevention',
        ]
    elif deviation.deviation_type == DeviationType.MISSING:
        return [
            f'"{step}" omission complication {proc}',
            f'without "{step}" outcome risk',
        ]
    elif deviation.deviation_type == DeviationType.OUT_OF_ORDER:
        terms = step.lower().replace("clip ", "").replace("divide ", "")
        return [
            f'"{terms}" order sequence technique {proc}',
            f'"{terms}" before after clipping',
        ]
    elif deviation.deviation_type == DeviationType.UNHANDLED_COMPLICATION:
        return [f'"{step}" uncontrolled complication outcome']

    return [f'"{step}" {proc} outcome risk']


def _clean_html(text: str) -> str:
    text = re.sub(r"<cite[^>]*>.*?</cite>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


# ── scite API ──────────────────────────────────────────────

async def _search_with_snippets(term: str, limit: int = 5) -> list[dict]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{SCITE_BASE}/search/v2",
                params={"term": term, "mode": "citations", "limit": limit},
                headers={"Authorization": f"Bearer {settings.scite_api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

            snippets = []
            for hit in data.get("hits", []):
                doi = hit.get("doi", "")
                title = _clean_html(hit.get("title", ""))
                for cite in hit.get("citations", []):
                    raw = cite.get("snippet", "")
                    if not raw:
                        continue
                    snippet = _clean_html(raw)
                    if len(snippet) < 30:
                        continue
                    snippets.append({
                        "snippet": snippet,
                        "doi": doi,
                        "title": title,
                        "section": cite.get("section", ""),
                        "cite_type": cite.get("type", "mentioning"),
                    })
            return snippets
    except Exception as e:
        logger.error(f"scite search error: {e}")
        return []


async def _count_by_citation_type(term: str, citation_type: str) -> int:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{SCITE_BASE}/search/v2",
                params={"term": term, "mode": "citations", "limit": 1, "citation_types": citation_type},
                headers={"Authorization": f"Bearer {settings.scite_api_key}"},
            )
            resp.raise_for_status()
            return resp.json().get("count", 0)
    except Exception as e:
        logger.error(f"scite count error ({citation_type}): {e}")
        return 0


# ── Verdict classification (NLI-based) ─────────────────────

def _classify_from_evidence(
    scored_snippets: list[dict],
    sup_count: int,
    con_count: int,
    deviation: RawDeviation,
) -> Verdict:
    """
    Classify verdict using NLI model scores on snippets (primary)
    and scite citation type counts (secondary).
    """
    if not scored_snippets:
        # No snippet evidence → precautionary principle
        return Verdict.CONFIRMED if deviation.safety_critical else Verdict.CONTEXT_DEPENDENT

    # Aggregate NLI scores across all snippets
    total_risk = sum(s["nli"]["risk_score"] for s in scored_snippets)
    total_safe = sum(s["nli"]["safe_score"] for s in scored_snippets)

    # Secondary signal from citation type counts (capped at 2 pts per side)
    if sup_count + con_count > 0:
        ratio = sup_count / (sup_count + con_count)
        total_risk += ratio * 2
        total_safe += (1 - ratio) * 2

    total = total_risk + total_safe
    if total == 0:
        return Verdict.CONFIRMED if deviation.safety_critical else Verdict.CONTEXT_DEPENDENT

    risk_ratio = total_risk / total

    # Safety-critical: lower threshold to confirm, higher to mitigate
    if deviation.safety_critical:
        if risk_ratio >= 0.55:
            return Verdict.CONFIRMED
        elif risk_ratio < 0.3:
            return Verdict.MITIGATED
        return Verdict.CONTEXT_DEPENDENT
    else:
        if risk_ratio >= 0.6:
            return Verdict.CONFIRMED
        elif risk_ratio < 0.35:
            return Verdict.MITIGATED
        return Verdict.CONTEXT_DEPENDENT


# ── Report builders ────────────────────────────────────────

def _build_evidence_summary(
    scored_snippets: list[dict],
    sup_count: int,
    con_count: int,
    deviation: RawDeviation,
) -> str:
    lines = [
        f"Evidence analysis for: '{deviation.node_name}' ({deviation.deviation_type.value})",
        f"  Citation landscape: {sup_count} supporting, {con_count} contrasting",
        f"  Snippets analyzed by NLI model: {len(scored_snippets)}",
        "",
    ]

    risk_items = [s for s in scored_snippets if s["nli"]["dominant"] == "risk"]
    safe_items = [s for s in scored_snippets if s["nli"]["dominant"] == "safe"]

    # Sort by confidence
    risk_items.sort(key=lambda s: s["nli"]["risk_score"], reverse=True)
    safe_items.sort(key=lambda s: s["nli"]["safe_score"], reverse=True)

    if risk_items:
        lines.append("Evidence this deviation is clinically significant:")
        for item in risk_items[:3]:
            conf = item["nli"]["risk_score"]
            lines.append(f'  - [NLI confidence: {conf:.0%}] "{item["snippet"][:280]}"')
            lines.append(f"    Source: {item['title'][:80]} (DOI: {item['doi']})")

    if safe_items:
        lines.append("")
        lines.append("Evidence this deviation may be acceptable:")
        for item in safe_items[:2]:
            conf = item["nli"]["safe_score"]
            lines.append(f'  - [NLI confidence: {conf:.0%}] "{item["snippet"][:280]}"')
            lines.append(f"    Source: {item['title'][:80]} (DOI: {item['doi']})")

    neutral = [s for s in scored_snippets if s["nli"]["dominant"] == "neutral"]
    if not risk_items and not safe_items and neutral:
        lines.append("Snippets found but NLI model was inconclusive:")
        for item in neutral[:2]:
            lines.append(f'  - "{item["snippet"][:200]}"')

    if not scored_snippets:
        lines.append("No relevant citation snippets found for this deviation.")

    return "\n".join(lines)


def _extract_citations(scored_snippets: list[dict], sup_count: int, con_count: int) -> list[str]:
    cites = [f"[scite: {sup_count} supporting, {con_count} contrasting]"]
    seen = set()
    for item in scored_snippets:
        doi = item.get("doi", "")
        if doi and doi not in seen:
            seen.add(doi)
            cites.append(f"{item.get('title', '')[:80]} (DOI: {doi})")
        if len(cites) >= 7:
            break
    return cites


# ── Public API ─────────────────────────────────────────────

async def adjudicate(
    deviations: list[RawDeviation],
    procedure_name: str,
) -> list[AdjudicatedDeviation]:
    """
    Adjudicate deviations using scite snippets + DeBERTa NLI scoring.

    For each deviation:
      1. Build claim-specific search queries
      2. Fetch real citation snippets from scite
      3. Score each snippet with DeBERTa zero-shot NLI
      4. Aggregate NLI scores + citation counts → verdict
      5. Return evidence with real quotes + model confidence
    """
    results: list[AdjudicatedDeviation] = []
    settings = get_settings()

    if not settings.scite_api_key:
        logger.warning("No scite API key — marking all for review")
        for dev in deviations:
            results.append(AdjudicatedDeviation(
                node_id=dev.node_id, node_name=dev.node_name,
                phase=dev.phase, deviation_type=dev.deviation_type,
                verdict=Verdict.CONTEXT_DEPENDENT,
                evidence_summary="scite API key not configured.",
                citations=[], original_mandatory=dev.mandatory,
                original_safety_critical=dev.safety_critical,
            ))
        return results

    # Pre-warm the NLI model (first call loads it, ~5s)
    _get_nli_classifier()

    for dev in deviations:
        queries = _build_search_queries(dev, procedure_name)

        # Collect snippets from all queries (deduplicated)
        all_snippets: list[dict] = []
        seen_keys: set[str] = set()

        for query in queries:
            snippets = await _search_with_snippets(query, limit=5)
            for s in snippets:
                key = f"{s['doi']}:{s['snippet'][:50]}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_snippets.append(s)

        # Score each snippet with NLI model
        scored: list[dict] = []
        for s in all_snippets:
            nli_result = _score_snippet_nli(s["snippet"])
            scored.append({**s, "nli": nli_result})

        # Citation type counts as secondary signal
        primary_q = queries[0]
        sup_count = await _count_by_citation_type(primary_q, "supporting")
        con_count = await _count_by_citation_type(primary_q, "contrasting")

        verdict = _classify_from_evidence(scored, sup_count, con_count, dev)
        summary = _build_evidence_summary(scored, sup_count, con_count, dev)
        citations = _extract_citations(scored, sup_count, con_count)

        results.append(AdjudicatedDeviation(
            node_id=dev.node_id, node_name=dev.node_name,
            phase=dev.phase, deviation_type=dev.deviation_type,
            verdict=verdict, evidence_summary=summary,
            citations=citations, original_mandatory=dev.mandatory,
            original_safety_critical=dev.safety_critical,
        ))

    return results
