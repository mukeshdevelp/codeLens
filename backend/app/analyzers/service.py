from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from app.analyzers.ai import summarize_with_cursor
from app.analyzers.engine import (
    analyze_functionality,
    analyze_volume,
    build_focus_areas,
    check_test_coverage,
    compute_risk_score,
    detect_critical_paths,
    detect_scope_drift,
    risk_level,
    rule_based_summary,
    scan_security,
)
from app.analyzers.types import AnalysisReport, FileChange, FocusArea
from app.config import settings


async def analyze_pull_request(title: str, body: str | None, files: list[FileChange], use_ai: bool = True) -> AnalysisReport:
    dimensions = [
        analyze_volume(files),
        detect_scope_drift(title, body, files),
        analyze_functionality(files),
        detect_critical_paths(files),
        scan_security(files),
        check_test_coverage(files),
    ]
    all_findings = [f for d in dimensions for f in d.findings]
    risk_score = compute_risk_score(dimensions)
    risk_level_value = risk_level(risk_score)
    focus_raw = build_focus_areas(all_findings)
    focus_areas = [FocusArea(**f) for f in focus_raw]
    summary = rule_based_summary(risk_level_value, risk_score, dimensions, focus_raw)

    if use_ai:
        try:
            if settings.cursor_api_key:
                summary = await summarize_with_cursor(title, body, risk_level_value, dimensions, focus_raw)
            elif settings.openai_api_key:
                summary = await _openai_summarize(title, body, risk_level_value, dimensions, focus_raw)
        except Exception:
            pass

    return AnalysisReport(
        pr={"title": title, "body": body},
        risk_level=risk_level_value,  # type: ignore[arg-type]
        risk_score=risk_score,
        executive_summary=summary,
        focus_areas=focus_areas,
        dimensions=dimensions,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


async def _openai_summarize(title: str, body: str | None, risk_level_value: str, dimensions, focus_areas) -> str:
    payload = {
        "title": title,
        "body": (body or "")[:500],
        "riskLevel": risk_level_value,
        "focusAreas": focus_areas,
        "dimensions": [
            {
                "dimension": d.name,
                "summary": d.summary,
                "findings": [{"severity": f.severity, "title": f.title, "file": f.evidence.get("file")} for f in d.findings[:5]],
            }
            for d in dimensions
        ],
    }
    prompt = (
        "Summarize this pull request analysis for a code reviewer in 3-5 sentences. "
        "Use ONLY the JSON data. State risk, what changed, and where to focus. Do not invent issues.\n\n"
        + json.dumps(payload, indent=2)
    )
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_model,
                "temperature": 0.2,
                "max_tokens": 300,
                "messages": [
                    {"role": "system", "content": "You summarize PR analysis for reviewers."},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()
