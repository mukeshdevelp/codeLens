"""Shared datatypes for analyzer inputs, findings, and serialized PR reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["high", "medium", "low", "info"]


@dataclass
class FileChange:
    """One file entry from a GitHub pull request diff."""

    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None


@dataclass
class Finding:
    """A single explainable analyzer signal with severity and evidence."""

    id: str
    category: str
    severity: Severity
    title: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionResult:
    """Score and findings for one PRD analysis dimension."""

    name: str
    score: int
    summary: str
    findings: list[Finding] = field(default_factory=list)


@dataclass
class FocusArea:
    """Ranked area where reviewers should focus first."""

    rank: int
    area: str
    reason: str
    severity: Severity
    files: list[str] = field(default_factory=list)


@dataclass
class FileChangeSummary:
    filename: str
    status: str
    additions: int
    deletions: int
    summary: str
    patch: str = ""
    truncated: bool = False
    summary_source: str = "rules"
    summary_provider: str = ""
    summarized_at: str = ""


@dataclass
class CommitFileChange:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str = ""
    previous_filename: str = ""
    patch_unavailable: bool = False


@dataclass
class PrCommit:
    sha: str
    message: str
    author: str
    date: str
    html_url: str
    additions: int = 0
    deletions: int = 0
    files: list[CommitFileChange] = field(default_factory=list)


@dataclass
class ReviewActivity:
    type: str
    author: str
    body: str
    created_at: str
    state: str | None = None
    file: str | None = None
    line: int | None = None


@dataclass
class AnalysisReport:
    """Full PR analysis payload returned to the API and cached in SQLite."""

    pr: dict[str, Any]
    risk_level: Severity
    risk_score: int
    executive_summary: str
    focus_areas: list[FocusArea]
    dimensions: list[DimensionResult]
    generated_at: str
    pr_overview: str = ""
    file_changes: list[FileChangeSummary] = field(default_factory=list)
    discussion_summary: str = ""
    review_activity: list[ReviewActivity] = field(default_factory=list)
    commits: list[PrCommit] = field(default_factory=list)
    ai_provider: str = ""
    ai_summaries_used: int = 0
    executive_summary_source: str = "rules"
    pr_overview_source: str = "rules"
    discussion_summary_source: str = "rules"

    def to_dict(self) -> dict[str, Any]:
        """Serialize report for JSON API responses and ``pr_reports.report_json``."""
        return {
            "pr": self.pr,
            "riskLevel": self.risk_level,
            "riskScore": self.risk_score,
            "executiveSummary": self.executive_summary,
            "prOverview": self.pr_overview,
            "fileChanges": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "summary": f.summary,
                    "summarySource": f.summary_source,
                    "summaryProvider": f.summary_provider,
                    "summarizedAt": f.summarized_at,
                    "patch": f.patch,
                    "truncated": f.truncated,
                }
                for f in self.file_changes
            ],
            "discussionSummary": self.discussion_summary,
            "reviewActivity": [
                {
                    "type": a.type,
                    "author": a.author,
                    "body": a.body,
                    "createdAt": a.created_at,
                    "state": a.state,
                    "file": a.file,
                    "line": a.line,
                }
                for a in self.review_activity
            ],
            "commits": [
                {
                    "sha": c.sha,
                    "message": c.message,
                    "author": c.author,
                    "date": c.date,
                    "htmlUrl": c.html_url,
                    "additions": c.additions,
                    "deletions": c.deletions,
                    "files": [
                        {
                            "filename": f.filename,
                            "status": f.status,
                            "additions": f.additions,
                            "deletions": f.deletions,
                            "patch": f.patch,
                            "previousFilename": f.previous_filename,
                            "patchUnavailable": f.patch_unavailable,
                        }
                        for f in c.files
                    ],
                }
                for c in self.commits
            ],
            "focusAreas": [
                {
                    "rank": f.rank,
                    "area": f.area,
                    "reason": f.reason,
                    "severity": f.severity,
                    "files": f.files,
                }
                for f in self.focus_areas
            ],
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "summary": d.summary,
                    "findings": [
                        {
                            "id": f.id,
                            "category": f.category,
                            "severity": f.severity,
                            "title": f.title,
                            "description": f.description,
                            "evidence": f.evidence,
                        }
                        for f in d.findings
                    ],
                }
                for d in self.dimensions
            ],
            "generatedAt": self.generated_at,
            "aiProvider": self.ai_provider,
            "aiSummariesUsed": self.ai_summaries_used,
            "executiveSummarySource": self.executive_summary_source,
            "prOverviewSource": self.pr_overview_source,
            "discussionSummarySource": self.discussion_summary_source,
            "aiSummaryBreakdown": {
                "executiveSummary": self.executive_summary_source,
                "prOverview": self.pr_overview_source,
                "discussionSummary": self.discussion_summary_source,
                "fileChanges": sum(1 for f in self.file_changes if f.summary_source == "ai"),
            },
        }
