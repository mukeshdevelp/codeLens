import type { DimensionResult, FileChange, Finding } from "./types.js";

const SOURCE_EXT = /\.(ts|tsx|js|jsx|py|go|rs|java)$/i;
const TEST_PATTERNS = [
  /\/tests?\//i,
  /\.test\./i,
  /\.spec\./i,
  /_test\./i,
  /test_/i,
];

function isTestFile(path: string): boolean {
  return TEST_PATTERNS.some((p) => p.test(path));
}

function isSourceFile(path: string): boolean {
  return SOURCE_EXT.test(path) && !isTestFile(path);
}

function expectedTestPaths(sourcePath: string): string[] {
  const base = sourcePath.replace(SOURCE_EXT, "");
  const ext = sourcePath.match(SOURCE_EXT)?.[0] ?? ".ts";
  return [
    `${base}.test${ext}`,
    `${base}.spec${ext}`,
    sourcePath.replace("/src/", "/tests/").replace(SOURCE_EXT, `.test${ext}`),
    `tests/${sourcePath.split("/").pop()?.replace(SOURCE_EXT, `.test${ext}`) ?? ""}`,
  ];
}

export function checkTestCoverage(files: FileChange[]): DimensionResult {
  const changedPaths = new Set(files.map((f) => f.filename));
  const sourceFiles = files.filter((f) => isSourceFile(f.filename) && f.status !== "removed");
  const testFilesChanged = files.filter((f) => isTestFile(f.filename));

  const findings: Finding[] = [];

  for (const src of sourceFiles) {
    const candidates = expectedTestPaths(src.filename);
    const hasMatchingTestChange = candidates.some((c) => changedPaths.has(c));
    const anyTestChanged = testFilesChanged.length > 0;

    if (!hasMatchingTestChange && !anyTestChanged) {
      findings.push({
        id: `test-gap-${src.filename}`,
        category: "tests",
        severity: src.additions > 20 ? "high" : "medium",
        title: "Source changed without matching test update",
        description: `${src.filename} was modified but no corresponding test file appears in this PR.`,
        evidence: { file: src.filename, metric: `${src.additions}+ lines` },
      });
    }
  }

  if (sourceFiles.length > 0 && testFilesChanged.length === 0) {
    findings.push({
      id: "test-none",
      category: "tests",
      severity: "medium",
      title: "No test files in PR",
      description: "This PR modifies source code but includes no test file changes.",
      evidence: { metric: `${sourceFiles.length} source files changed` },
    });
  }

  const score = Math.min(findings.length * 18, 100);

  return {
    name: "Test Coverage",
    score,
    summary:
      testFilesChanged.length > 0
        ? `${testFilesChanged.length} test file(s) updated alongside source changes.`
        : "No test file changes detected.",
    findings,
  };
}
