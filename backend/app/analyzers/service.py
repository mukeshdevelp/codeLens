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
    rule_based_pr_overview,
    summarize_discussion,
    summarize_file_changes,
    summarize_pr_overview,
)
from app.analyzers.types import AnalysisReport, FileChange, FileChangeSummary, FocusArea, ReviewActivity
from app.config import settings


async def analyze_pull_request(
    title: str,
    body: str | None,
    files: list[FileChange],
    use_ai: bool = True,
    pr_meta: dict | None = None,
    review_activity: list[dict] | None = None,
) -> AnalysisReport:
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
    exec_source = "rules"

    if use_ai and ai_is_configured():
        try:
            ai_summary, used_ai_exec = await summarize_with_cursor(title, body, risk_level_value, dimensions, focus_raw)
            summary = ai_summary
            if used_ai_exec:
                exec_source = "ai"
        except Exception:
            pass

    pr_overview = rule_based_pr_overview(title, body, files)
    discussion_summary = rule_based_discussion_summary(review_activity or [])
    file_change_dicts: list[dict] = []
    ai_file_count = 0

    if use_ai:
        pr_overview, _ = await summarize_pr_overview(title, body, files)
        file_change_dicts, ai_file_count = await summarize_file_changes(files)
        discussion_summary, _ = await summarize_discussion(review_activity or [])
    else:
        from app.analyzers.summarize import rule_based_file_summary

        file_change_dicts = [
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

    file_changes = [
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

    activity = review_activity or []
    review_items = [
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
        file_changes=file_changes,
        discussion_summary=discussion_summary,
        review_activity=review_items,
        ai_provider=settings.resolved_ai_provider() if ai_is_configured() else "",
        ai_summaries_used=ai_file_count + (1 if exec_source == "ai" else 0),
        executive_summary_source=exec_source,
    )
