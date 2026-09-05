import type { DimensionResult, FileChange, Finding } from "./types.js";

export function analyzeVolume(
  files: FileChange[],
  repoAverageLines = 200
): DimensionResult {
  const additions = files.reduce((s, f) => s + f.additions, 0);
  const deletions = files.reduce((s, f) => s + f.deletions, 0);
  const totalLines = additions + deletions;
  const fileCount = files.length;

  const findings: Finding[] = [];
  let score = 0;

  if (totalLines > repoAverageLines * 3) {
    score += 35;
    findings.push({
      id: "volume-large",
      category: "volume",
      severity: "high",
      title: "Large PR",
      description: `This PR changes ${totalLines} lines (${additions}+ / ${deletions}-), well above a typical ~${repoAverageLines} line change.`,
      evidence: { metric: `${totalLines} lines across ${fileCount} files` },
    });
  } else if (totalLines > repoAverageLines) {
    score += 15;
    findings.push({
      id: "volume-medium",
      category: "volume",
      severity: "medium",
      title: "Above-average PR size",
      description: `${totalLines} lines changed across ${fileCount} files.`,
      evidence: { metric: `${totalLines} lines` },
    });
  }

  const largeFiles = files
    .filter((f) => f.additions + f.deletions > 150)
    .sort((a, b) => b.additions + b.deletions - (a.additions + a.deletions));

  for (const f of largeFiles.slice(0, 3)) {
    score += 5;
    findings.push({
      id: `volume-file-${f.filename}`,
      category: "volume",
      severity: "medium",
      title: "Large file change",
      description: `${f.filename} has ${f.additions + f.deletions} line changes — consider reviewing in isolation.`,
      evidence: { file: f.filename, metric: `${f.additions}+ / ${f.deletions}-` },
    });
  }

  const summary =
    fileCount === 0
      ? "No file changes detected."
      : `${fileCount} files, ${additions} additions, ${deletions} deletions.`;

  return {
    name: "Code Volume",
    score: Math.min(score, 100),
    summary,
    findings,
  };
}
