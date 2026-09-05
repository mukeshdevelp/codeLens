from __future__ import annotations

import json

import httpx

from app.analyzers.engine import compute_risk_score, rule_based_summary
from app.config import settings


async def summarize_with_cursor(
    title: str,
    body: str | None,
    risk_level_value: str,
    dimensions,
    focus_areas,
) -> str:
    fallback = rule_based_summary(risk_level_value, compute_risk_score(dimensions), dimensions, focus_areas)
    if not settings.cursor_api_key:
        return fallback

    payload = {
        "title": title,
        "body": (body or "")[:500],
        "riskLevel": risk_level_value,
        "focusAreas": focus_areas,
        "dimensions": [
            {
                "dimension": d.name,
                "summary": d.summary,
                "findings": [
                    {"severity": f.severity, "title": f.title, "file": f.evidence.get("file")}
                    for f in d.findings[:5]
                ],
            }
            for d in dimensions
        ],
    }
    prompt = (
        "Summarize this pull request analysis for a code reviewer in 3-5 sentences. "
        "Use ONLY the JSON data. State risk, what changed, and where to focus. Do not invent issues.\n\n"
        + json.dumps(payload, indent=2)
    )

    # Cursor Cloud Agents API
    async with httpx.AsyncClient(timeout=90) as client:
        create = await client.post(
            "https://api.cursor.com/v0/agents",
            headers={
                "Authorization": f"Bearer {settings.cursor_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": {"text": prompt},
                "model": settings.cursor_model,
                "source": {"repository": "https://github.com/octocat/Hello-World"},
            },
        )
        if create.status_code >= 400:
            return fallback

        agent = create.json()
        agent_id = agent.get("id")
        if not agent_id:
            return fallback

        # Poll for completion
        for _ in range(30):
            status_res = await client.get(
                f"https://api.cursor.com/v0/agents/{agent_id}",
                headers={"Authorization": f"Bearer {settings.cursor_api_key}"},
            )
            if status_res.status_code >= 400:
                break
            data = status_res.json()
            state = data.get("status") or data.get("state")
            if state in ("completed", "finished", "done"):
                text = data.get("result") or data.get("output") or data.get("summary") or ""
                if isinstance(text, str) and len(text.strip()) > 20:
                    return text.strip()
                break
            if state in ("failed", "error", "cancelled"):
                break
            import asyncio
            await asyncio.sleep(2)

    return fallback
