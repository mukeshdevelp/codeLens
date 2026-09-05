from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["high", "medium", "low", "info"]


@dataclass
class FileChange:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: str | None = None


@dataclass
class Finding:
    id: str
    category: str
    severity: Severity
    title: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionResult:
    name: str
    score: int
    summary: str
    findings: list[Finding] = field(default_factory=list)


@dataclass
class FocusArea:
    rank: int
    area: str
    reason: str
    severity: Severity
    files: list[str] = field(default_factory=list)


@dataclass
class AnalysisReport:
    pr: dict[str, str | None]
    risk_level: Severity
    risk_score: int
    executive_summary: str
    focus_areas: list[FocusArea]
    dimensions: list[DimensionResult]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr": self.pr,
            "riskLevel": self.risk_level,
            "riskScore": self.risk_score,
            "executiveSummary": self.executive_summary,
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
        }
