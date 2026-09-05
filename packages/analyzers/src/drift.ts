import type { DimensionResult, FileChange, Finding, PullRequestInput } from "./types.js";

const TITLE_KEYWORDS = /\b(fix|add|update|refactor|implement|remove|migrate|auth|login|payment|api|ui|bug)\b/gi;

function topLevelDirs(files: FileChange[]): string[] {
  const dirs = new Set<string>();
  for (const f of files) {
    const parts = f.filename.split("/");
    if (parts.length >= 2) dirs.add(parts.slice(0, 2).join("/"));
    else if (parts.length === 1) dirs.add("(root)");
    else dirs.add(parts[0]);
  }
  return [...dirs];
}

function extractKeywords(text: string): Set<string> {
  const words = new Set<string>();
  const matches = text.toLowerCase().match(/\b[a-z]{4,}\b/g) ?? [];
  for (const w of matches) words.add(w);
  return words;
}

export function detectScopeDrift(pr: PullRequestInput): DimensionResult {
  const findings: Finding[] = [];
  const dirs = topLevelDirs(pr.files);
  const titleWords = extractKeywords(pr.title);
  const bodyWords = extractKeywords(pr.body ?? "");

  if (dirs.length >= 4) {
    findings.push({
      id: "drift-many-modules",
      category: "drift",
      severity: "medium",
      title: "Changes span many modules",
      description: `PR touches ${dirs.length} top-level areas (${dirs.join(", ")}), which may be broader than a single focused change.`,
      evidence: { metric: dirs.join(", ") },
    });
  }

  const statedFocus = new Set([...titleWords, ...bodyWords]);
  const unrelatedDirs = dirs.filter((d) => {
    if (d === "(root)") return false;
    return ![...statedFocus].some((w) => d.toLowerCase().includes(w) || w.includes(d.toLowerCase()));
  });

  if (unrelatedDirs.length >= 2 && pr.title.length > 0) {
    findings.push({
      id: "drift-unrelated",
      category: "drift",
      severity: "medium",
      title: "Possible scope drift",
      description: `PR title/body focus may not cover all changed areas: ${unrelatedDirs.join(", ")}.`,
      evidence: { metric: `Title: "${pr.title}"` },
    });
  }

  const categories = clusterByDirectory(pr.files);
  if (categories.length >= 3) {
    findings.push({
      id: "drift-multi-feature",
      category: "drift",
      severity: "low",
      title: "Multiple functional areas changed",
      description: `Changes cluster into ${categories.length} areas: ${categories.map((c) => c.name).join(", ")}.`,
      evidence: { metric: categories.map((c) => `${c.name} (${c.files} files)`).join("; ") },
    });
  }

  const score = Math.min(findings.length * 15, 100);

  return {
    name: "Change & Drift",
    score,
    summary:
      findings.length === 0
        ? "Change scope appears aligned with stated purpose."
        : `${findings.length} scope signal(s) — verify the PR stays focused.`,
    findings,
  };
}

function clusterByDirectory(files: FileChange[]): Array<{ name: string; files: number }> {
  const map = new Map<string, number>();
  for (const f of files) {
    const parts = f.filename.split("/");
    const dir = parts.length >= 2 ? parts.slice(0, 2).join("/") : parts[0] ?? "(root)";
    map.set(dir, (map.get(dir) ?? 0) + 1);
  }
  return [...map.entries()]
    .map(([name, count]) => ({ name, files: count }))
    .sort((a, b) => b.files - a.files);
}

export function analyzeFunctionality(files: FileChange[]): DimensionResult {
  const clusters = clusterByDirectory(files);
  const findings: Finding[] = [];

  if (clusters.length === 1) {
    findings.push({
      id: "func-coherent",
      category: "functionality",
      severity: "info",
      title: "Coherent change",
      description: "All changes are within a single module/directory.",
      evidence: { metric: clusters[0].name },
    });
  } else if (clusters.length >= 3) {
    findings.push({
      id: "func-scattered",
      category: "functionality",
      severity: "medium",
      title: "Scattered functionality",
      description: "Changes spread across multiple modules — may bundle unrelated work.",
      evidence: { metric: clusters.map((c) => c.name).join(", ") },
    });
  }

  return {
    name: "Functionality",
    score: clusters.length >= 3 ? 40 : clusters.length === 2 ? 15 : 0,
    summary: `${clusters.length} functional area(s) affected.`,
    findings,
  };
}
