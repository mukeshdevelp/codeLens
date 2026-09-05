import type { AnalysisReport, DimensionResult, Finding, Severity } from "./types.js";

const WEIGHTS: Record<string, number> = {
  Security: 3,
  "Critical Functionality": 3,
  "Test Coverage": 2,
  "Change & Drift": 1.5,
  "Code Volume": 1,
  Functionality: 1,
};

export function computeRiskScore(dimensions: DimensionResult[]): number {
  let weighted = 0;
  let totalWeight = 0;

  for (const dim of dimensions) {
    const w = WEIGHTS[dim.name] ?? 1;
    weighted += dim.score * w;
    totalWeight += w;
  }

  return Math.round(Math.min(weighted / totalWeight, 100));
}

export function riskLevelFromScore(score: number): Severity {
  if (score >= 55) return "high";
  if (score >= 25) return "medium";
  return "low";
}

export function buildFocusAreas(allFindings: Finding[]): AnalysisReport["focusAreas"] {
  const severityOrder: Record<Severity, number> = { high: 0, medium: 1, low: 2, info: 3 };

  const ranked = [...allFindings]
    .filter((f) => f.severity !== "info")
    .sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

  const areas = new Map<string, { reason: string; severity: Severity; files: Set<string> }>();

  for (const f of ranked) {
    const area = f.evidence.file ?? f.category;
    const existing = areas.get(area);
    if (existing) {
      if (severityOrder[f.severity] < severityOrder[existing.severity]) {
        existing.severity = f.severity;
        existing.reason = f.title;
      }
      if (f.evidence.file) existing.files.add(f.evidence.file);
    } else {
      areas.set(area, {
        reason: f.title,
        severity: f.severity,
        files: new Set(f.evidence.file ? [f.evidence.file] : []),
      });
    }
  }

  return [...areas.entries()].slice(0, 5).map(([area, data], i) => ({
    rank: i + 1,
    area,
    reason: data.reason,
    severity: data.severity,
    files: [...data.files],
  }));
}

export function ruleBasedSummary(
  riskLevel: Severity,
  riskScore: number,
  dimensions: DimensionResult[],
  focusAreas: AnalysisReport["focusAreas"]
): string {
  const highlights = dimensions
    .filter((d) => d.findings.some((f) => f.severity === "high" || f.severity === "medium"))
    .map((d) => d.name);

  const focus =
    focusAreas.length > 0
      ? ` Start with: ${focusAreas.slice(0, 3).map((f) => f.area).join(", ")}.`
      : "";

  if (riskLevel === "high") {
    return `High-risk PR (score ${riskScore}/100). Key concerns: ${highlights.join(", ") || "multiple signals"}.${focus}`;
  }
  if (riskLevel === "medium") {
    return `Medium-risk PR (score ${riskScore}/100). Review ${highlights.join(", ") || "changed areas"} before approving.${focus}`;
  }
  return `Low-risk PR (score ${riskScore}/100). Focused change with no major red flags.${focus}`;
}
