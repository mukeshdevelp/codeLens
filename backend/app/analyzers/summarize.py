from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.analyzers.ai import ai_complete, ai_is_configured
from app.analyzers.types import FileChange

STATUS_VERB = {
    "added": "Adds",
    "removed": "Removes",
    "modified": "Updates",
    "renamed": "Renames",
    "changed": "Changes",
    "copied": "Copies",
}

REVIEW_STATE_LABEL = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "requested changes",
    "COMMENTED": "left review comments",
    "DISMISSED": "dismissed a review",
    "PENDING": "has a pending review",
}

MAX_AI_FILE_SUMMARIES = 20


def _patch_preview(patch: str | None, max_lines: int = 40) -> str:
    if not patch:
        return ""
    lines = patch.splitlines()
    if len(lines) <= max_lines:
        return patch
    return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"


def rule_based_file_summary(f: FileChange) -> str:
    verb = STATUS_VERB.get(f.status, "Changes")
    parts = [f"{verb} `{f.filename}`"]
    if f.additions or f.deletions:
        parts.append(f"({f.additions}+ / {f.deletions}-)")
    if f.patch:
        added = [ln[1:].strip() for ln in f.patch.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        removed = [ln[1:].strip() for ln in f.patch.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        hints: list[str] = []
        for line in (added + removed)[:6]:
            clean = re.sub(r"\s+", " ", line)[:80]
            if clean and not clean.startswith(("@@", "{", "}")):
                hints.append(clean)
                break
        if hints:
            parts.append(f"— e.g. `{hints[0][:60]}`")
    return " ".join(parts)


def rule_based_pr_overview(title: str, body: str | None, files: list[FileChange]) -> str:
    total_add = sum(f.additions for f in files)
    total_del = sum(f.deletions for f in files)
    dirs = sorted({f.filename.split("/")[0] for f in files if "/" in f.filename})[:4]
    scope = f" across {', '.join(dirs)}" if dirs else ""
    desc = (body or "").strip().split("\n")[0][:200] if body else ""
    if desc:
        return f"{title} — {desc} ({len(files)} files, {total_add}+ / {total_del}-{scope})."
    return f"{title} — changes {len(files)} files ({total_add}+ / {total_del}-){scope}."


def rule_based_discussion_summary(activity: list[dict[str, Any]]) -> str:
    if not activity:
        return "No review comments or discussion yet on this pull request."
    reviewers = {a["author"] for a in activity if a.get("author")}
    reviews = [a for a in activity if a.get("type") == "review"]
    comments = [a for a in activity if a.get("type") in ("comment", "review_comment")]
    parts: list[str] = []
    if reviews:
        states = [f"{r['author']} {REVIEW_STATE_LABEL.get(r.get('state', ''), 'reviewed')}" for r in reviews[:3]]
        parts.append("Reviews: " + "; ".join(states) + ".")
    if comments:
        parts.append(f"{len(comments)} inline or general comment{'s' if len(comments) != 1 else ''} from {', '.join(sorted(reviewers)[:4])}.")
        snippet = next((c["body"][:120] for c in comments if c.get("body")), None)
        if snippet:
            parts.append(f'Latest: "{snippet}{"…" if len(snippet) == 120 else ""}"')
    return " ".join(parts)


async def _ai_file_summary(f: FileChange) -> str | None:
    preview = _patch_preview(f.patch, max_lines=35)
    prompt = (
        f"You are CodeLens, a PR review assistant. Summarize what this file change does.\n"
        f"Rules:\n"
        f"- Exactly 1-2 sentences, plain text\n"
        f"- Start with the filename: {f.filename}\n"
        f"- Name specific tech/tools from the diff (e.g. kubeadm, Tailscale, Calico)\n"
        f"- Do NOT use generic phrases like 'comprehensive guide', 'step-by-step instructions', "
        f"or 'this document provides'\n"
        f"- Write as a code reviewer, not as GitHub Copilot\n\n"
        f"Change type: {f.status} | Lines: +{f.additions} / -{f.deletions}\n\n"
    )
    if preview:
        prompt += f"Diff excerpt:\n{preview[:2500]}"
    else:
        prompt += "No diff available — infer from filename and change stats."
    return await ai_complete(
        prompt,
        system="CodeLens file-change summarizer. Concise, technical, distinct per file.",
        max_tokens=200,
    )


async def _ai_summarize_all_files(files: list[FileChange]) -> dict[str, str]:
    """One Groq call for all files — faster and more distinct summaries."""
    if not ai_is_configured() or not files:
        return {}

    items = []
    for f in sorted(files, key=lambda x: x.additions + x.deletions, reverse=True)[:MAX_AI_FILE_SUMMARIES]:
        preview = _patch_preview(f.patch, max_lines=20)
        items.append({
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "diffExcerpt": preview[:1200] if preview else "",
        })

    prompt = (
        "For each file below, write a UNIQUE 1-2 sentence summary of what that file adds or changes. "
        "Each summary must be different — focus on that file's specific purpose. "
        "Return ONLY valid JSON: {\"summaries\": [{\"filename\": \"...\", \"summary\": \"...\"}]}\n\n"
        + json.dumps({"files": items}, indent=2)
    )
    raw = await ai_complete(
        prompt,
        system="You return JSON only. Summarize each changed file distinctly for a PR walkthrough.",
        max_tokens=1200,
    )
    if not raw:
        return {}

    try:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        rows = data.get("summaries") or data.get("files") or []
        return {r["filename"]: r["summary"] for r in rows if r.get("filename") and r.get("summary")}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


async def summarize_pr_overview(title: str, body: str | None, files: list[FileChange]) -> tuple[str, bool]:
    fallback = rule_based_pr_overview(title, body, files)
    if not ai_is_configured():
        return fallback, False
    file_list = [
        {"file": f.filename, "status": f.status, "additions": f.additions, "deletions": f.deletions}
        for f in sorted(files, key=lambda x: x.additions + x.deletions, reverse=True)[:20]
    ]
    prompt = (
        "Write a concise 2-4 sentence overview of this pull request for a reviewer. "
        "Explain WHAT the PR does and WHY, in plain English. Do not list every file. "
        "Use only the data provided.\n\n"
        + json.dumps({"title": title, "description": (body or "")[:800], "files": file_list}, indent=2)
    )
    ai = await ai_complete(prompt, system="You write clear PR summaries like CodeRabbit.", max_tokens=250)
    return (ai or fallback), bool(ai)


async def summarize_file_changes(files: list[FileChange]) -> tuple[list[dict[str, Any]], int]:
    """Per-file walkthrough summaries with diff patches. Calls Groq once per file, then caches in DB via analyze."""
    from datetime import datetime, timezone

    from app.config import settings

    ranked = sorted(files, key=lambda f: f.additions + f.deletions, reverse=True)
    results: list[dict[str, Any]] = []
    ai_count = 0
    provider = settings.resolved_ai_provider() if ai_is_configured() else ""
    now = datetime.now(timezone.utc).isoformat()

    # Parallel Groq calls — one per file (reliable; batch JSON often fails on reasoning models)
    ai_map: dict[str, str] = {}
    if ai_is_configured():
        targets = ranked[:MAX_AI_FILE_SUMMARIES]

        async def _summarize_one(file_change: FileChange) -> tuple[str, str | None]:
            text = await _ai_file_summary(file_change)
            return file_change.filename, text

        pairs = await asyncio.gather(*[_summarize_one(f) for f in targets])
        ai_map = {name: text for name, text in pairs if text}

    for f in ranked:
        summary = rule_based_file_summary(f)
        used_ai = False
        summarized_at = ""

        if f.filename in ai_map:
            summary = ai_map[f.filename]
            used_ai = True
            summarized_at = now
            ai_count += 1

        results.append(
            {
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "summary": summary,
                "summarySource": "ai" if used_ai else "rules",
                "summaryProvider": provider if used_ai else "",
                "summarizedAt": summarized_at,
                "patch": f.patch or "",
                "truncated": bool(f.patch and len(f.patch.splitlines()) > 500),
            }
        )

    return results, ai_count


async def summarize_discussion(activity: list[dict[str, Any]]) -> tuple[str, bool]:
    fallback = rule_based_discussion_summary(activity)
    if not activity or not ai_is_configured():
        return fallback, False
    compact = [
        {
            "type": a.get("type"),
            "author": a.get("author"),
            "state": a.get("state"),
            "body": (a.get("body") or "")[:400],
            "file": a.get("file"),
        }
        for a in activity[:30]
    ]
    prompt = (
        "Summarize the review discussion on this pull request in 3-5 sentences. "
        "Cover: who reviewed, what feedback was given, whether concerns were addressed, "
        "and the overall review sentiment. Use ONLY the data below.\n\n"
        + json.dumps(compact, indent=2)
    )
    ai = await ai_complete(prompt, system="You summarize PR review threads like CodeRabbit.", max_tokens=300)
    return (ai or fallback), bool(ai)
