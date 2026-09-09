"""Orchestrates rule-based analyzers and optional AI summaries into an AnalysisReport."""

from __future__ import annotations

from datetime import datetime, timezone

from app.analyzers.ai import ai_is_configured, summarize_with_cursor
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
from app.analyzers.summarize import (
    rule_based_discussion_summary,
    rule_based_file_summary,
    rule_based_pr_overview,
    summarize_discussion,
    summarize_file_changes,
    summarize_pr_overview,
)
from app.analyzers.types import (
    AnalysisReport,
    CommitFileChange,
    FileChange,
    FileChangeSummary,
    FocusArea,
    PrCommit,
    ReviewActivity,
)
from app.config import settings


def _run_dimensions(title: str, body: str | None, files: list[FileChange]):
    return [
        analyze_volume(files),
        detect_scope_drift(title, body, files),
        analyze_functionality(files),
        detect_critical_paths(files),
        scan_security(files),
        check_test_coverage(files),
    ]


def _rule_based_file_dicts(files: list[FileChange]) -> list[dict]:
    return [
        {
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "summary": rule_based_file_summary(f),
            "summarySource": "rules",
            "patch": f.patch or "",
            "truncated": bool(f.patch and len(f.patch.splitlines()) > 500),
        }
        for f in files
    ]


async def _maybe_ai_executive_summary(
    title: str,
    body: str | None,
    risk_level_value: str,
    dimensions,
    focus_raw: list[dict],
    default_summary: str,
) -> tuple[str, str]:
    if not ai_is_configured():
        return default_summary, "rules"
    try:
        ai_summary, used_ai_exec = await summarize_with_cursor(
            title, body, risk_level_value, dimensions, focus_raw
        )
        return ai_summary, "ai" if used_ai_exec else "rules"
    except Exception:
        return default_summary, "rules"


async def _enrich_with_ai_summaries(
    title: str,
    body: str | None,
    files: list[FileChange],
    activity: list[dict],
    exec_source: str,
) -> tuple[str, str, str, str, list[dict], int]:
    pr_overview = rule_based_pr_overview(title, body, files)
    discussion_summary = rule_based_discussion_summary(activity)
    pr_overview_source = "rules"
    discussion_source = "rules"
    ai_total_count = 1 if exec_source == "ai" else 0

    pr_overview, used_pr = await summarize_pr_overview(title, body, files)
    if used_pr:
        pr_overview_source = "ai"
        ai_total_count += 1

    file_change_dicts, ai_file_count = await summarize_file_changes(files)
    ai_total_count += ai_file_count

    discussion_summary, used_disc = await summarize_discussion(activity)
    if used_disc:
        discussion_source = "ai"
        ai_total_count += 1

    return pr_overview, pr_overview_source, discussion_summary, discussion_source, file_change_dicts, ai_total_count


def _to_file_changes(file_change_dicts: list[dict]) -> list[FileChangeSummary]:
    return [
        FileChangeSummary(
            filename=fc["filename"],
            status=fc["status"],
            additions=fc["additions"],
            deletions=fc["deletions"],
            summary=fc["summary"],
            patch=fc.get("patch", ""),
            truncated=fc.get("truncated", False),
            summary_source=fc.get("summarySource", "rules"),
            summary_provider=fc.get("summaryProvider", ""),
            summarized_at=fc.get("summarizedAt", ""),
        )
        for fc in file_change_dicts
    ]


def _to_review_activity(activity: list[dict]) -> list[ReviewActivity]:
    return [
        ReviewActivity(
            type=a.get("type", "comment"),
            author=a.get("author", "unknown"),
            body=a.get("body", ""),
            created_at=a.get("createdAt", ""),
            state=a.get("state"),
            file=a.get("file"),
            line=a.get("line"),
        )
        for a in activity
    ]


def _to_commits(commits: list[dict] | None) -> list[PrCommit]:
    return [
        PrCommit(
            sha=c.get("sha", ""),
            message=c.get("message", ""),
            author=c.get("author", "unknown"),
            date=c.get("date", ""),
            html_url=c.get("htmlUrl", ""),
            additions=c.get("additions", 0),
            deletions=c.get("deletions", 0),
            files=[
                CommitFileChange(
                    filename=f.get("filename", ""),
                    status=f.get("status", "modified"),
                    additions=f.get("additions", 0),
                    deletions=f.get("deletions", 0),
                    patch=f.get("patch", ""),
                    previous_filename=f.get("previousFilename", ""),
                    patch_unavailable=bool(f.get("patchUnavailable")),
                )
                for f in c.get("files", [])
            ],
        )
        for c in (commits or [])
    ]


async def analyze_pull_request(
    title: str,
    body: str | None,
    files: list[FileChange],
    use_ai: bool = True,
    pr_meta: dict | None = None,
    review_activity: list[dict] | None = None,
    commits: list[dict] | None = None,
) -> AnalysisReport:
    """Run all PRD dimensions, build focus areas, and optionally enrich with AI summaries."""
    dimensions = _run_dimensions(title, body, files)
    all_findings = [f for d in dimensions for f in d.findings]
    risk_score = compute_risk_score(dimensions)
    risk_level_value = risk_level(risk_score)
    focus_raw = build_focus_areas(all_findings)
    focus_areas = [FocusArea(**f) for f in focus_raw]

    summary = rule_based_summary(risk_level_value, risk_score, dimensions, focus_raw)
    exec_source = "rules"
    if use_ai and ai_is_configured():
        summary, exec_source = await _maybe_ai_executive_summary(
            title, body, risk_level_value, dimensions, focus_raw, summary
        )

    activity = review_activity or []
    pr_overview_source = "rules"
    discussion_source = "rules"
    ai_total_count = 1 if exec_source == "ai" else 0

    if use_ai:
        pr_overview, pr_overview_source, discussion_summary, discussion_source, file_change_dicts, ai_total_count = await _enrich_with_ai_summaries(
            title, body, files, activity, exec_source
        )
    else:
        pr_overview = rule_based_pr_overview(title, body, files)
        discussion_summary = rule_based_discussion_summary(activity)
        file_change_dicts = _rule_based_file_dicts(files)

    pr_data: dict = {"title": title, "body": body}
    if pr_meta:
        pr_data.update(pr_meta)

    return AnalysisReport(
        pr=pr_data,
        risk_level=risk_level_value,  # type: ignore[arg-type]
        risk_score=risk_score,
        executive_summary=summary,
        focus_areas=focus_areas,
        dimensions=dimensions,
        generated_at=datetime.now(timezone.utc).isoformat(),
        pr_overview=pr_overview,
        file_changes=_to_file_changes(file_change_dicts),
        discussion_summary=discussion_summary,
        review_activity=_to_review_activity(activity),
        commits=_to_commits(commits),
        ai_provider=settings.resolved_ai_provider() if ai_is_configured() else "",
        ai_summaries_used=ai_total_count,
        executive_summary_source=exec_source,
        pr_overview_source=pr_overview_source,
        discussion_summary_source=discussion_source,
    )
