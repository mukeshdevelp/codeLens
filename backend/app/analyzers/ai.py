from __future__ import annotations

import json
import logging

import httpx

from app.analyzers.engine import compute_risk_score, rule_based_summary
from app.config import settings

logger = logging.getLogger(__name__)

# OpenAI-compatible chat completion endpoints
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "perplexity": {
        "base_url": "https://api.perplexity.ai",
        "model": "sonar",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
    },
}

_last_ai_error: str | None = None


def get_last_ai_error() -> str | None:
    return _last_ai_error


def ai_is_configured() -> bool:
    return bool(settings.resolved_ai_key())


def resolve_ai_config() -> tuple[str, str, str] | None:
    """Return (api_key, base_url, model) or None if no key configured."""
    api_key = settings.resolved_ai_key()
    if not api_key:
        return None

    provider = settings.resolved_ai_provider()
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai"])
    base_url = (settings.ai_base_url or preset["base_url"]).rstrip("/")
    model = settings.ai_model or settings.openai_model or preset["model"]
    return api_key, base_url, model


async def ai_complete(
    prompt: str,
    system: str = "You are a senior code reviewer.",
    max_tokens: int = 500,
) -> str | None:
    """Chat completion via configured provider (OpenAI-compatible APIs)."""
    global _last_ai_error

    config = resolve_ai_config()
    if not config:
        _last_ai_error = "No AI API key configured (set AI_API_KEY or OPENAI_API_KEY)"
        logger.warning(_last_ai_error)
        return None

    api_key, base_url, model = config
    url = f"{base_url}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            if res.status_code >= 400:
                _last_ai_error = f"AI API error ({settings.ai_provider or 'openai'}): {res.status_code} {res.text[:300]}"
                logger.warning(_last_ai_error)
                return None
            data = res.json()
            text = data["choices"][0]["message"]["content"].strip()
            if text:
                _last_ai_error = None
                return text
            _last_ai_error = "AI returned empty response"
            return None
    except Exception as exc:
        _last_ai_error = f"AI request failed ({settings.ai_provider or 'openai'}): {exc}"
        logger.warning(_last_ai_error)
        return None


async def summarize_with_cursor(
    title: str,
    body: str | None,
    risk_level_value: str,
    dimensions,
    focus_areas,
) -> tuple[str, bool]:
    fallback = rule_based_summary(risk_level_value, compute_risk_score(dimensions), dimensions, focus_areas)
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
    ai = await ai_complete(prompt)
    if ai:
        return ai, True

    if not settings.cursor_api_key:
        return fallback, False

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
            return fallback, False

        agent = create.json()
        agent_id = agent.get("id")
        if not agent_id:
            return fallback, False

        import asyncio

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
                    return text.strip(), True
                break
            if state in ("failed", "error", "cancelled"):
                break
            await asyncio.sleep(2)

    return fallback, False
