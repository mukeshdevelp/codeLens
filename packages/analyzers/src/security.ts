import type { DimensionResult, FileChange, Finding } from "./types.js";

const SECRET_PATTERNS: Array<{ id: string; pattern: RegExp; label: string }> = [
  { id: "aws-key", pattern: /AKIA[0-9A-Z]{16}/, label: "AWS access key" },
  { id: "github-token", pattern: /ghp_[a-zA-Z0-9]{36}/, label: "GitHub token" },
  { id: "private-key", pattern: /-----BEGIN (RSA |EC )?PRIVATE KEY-----/, label: "Private key" },
  { id: "api-key-assign", pattern: /(?:api[_-]?key|secret|password|token)\s*[=:]\s*['"][^'"]{8,}['"]/i, label: "Hardcoded credential" },
  { id: "hardcoded-fallback", pattern: /\|\|\s*['"][^'"]{12,}['"]/, label: "Hardcoded fallback secret" },
];

const UNSAFE_PATTERNS: Array<{ id: string; pattern: RegExp; label: string; severity: "high" | "medium" }> = [
  { id: "eval", pattern: /\beval\s*\(/, label: "eval() usage", severity: "high" },
  { id: "exec", pattern: /child_process\.(exec|execSync)/, label: "Shell command execution", severity: "high" },
  { id: "sql-concat", pattern: /(?:query|execute)\s*\(\s*[`'"].*\$\{/, label: "Possible SQL injection (string interpolation)", severity: "high" },
  { id: "innerhtml", pattern: /\.innerHTML\s*=/, label: "Direct innerHTML assignment (XSS risk)", severity: "medium" },
  { id: "disable-ssl", pattern: /rejectUnauthorized\s*:\s*false/, label: "TLS verification disabled", severity: "high" },
];

export function scanSecurity(files: FileChange[]): DimensionResult {
  const findings: Finding[] = [];

  for (const file of files) {
    const patch = file.patch ?? "";
    const lines = patch.split("\n");

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!line.startsWith("+") || line.startsWith("+++")) continue;
      const added = line.slice(1);

      for (const rule of SECRET_PATTERNS) {
        if (rule.pattern.test(added)) {
          findings.push({
            id: `sec-${rule.id}-${file.filename}-${i}`,
            category: "security",
            severity: "high",
            title: `Possible secret: ${rule.label}`,
            description: "Added line may contain a credential or secret.",
            evidence: { file: file.filename, line: i, snippet: redact(added.trim()) },
          });
        }
      }

      for (const rule of UNSAFE_PATTERNS) {
        if (rule.pattern.test(added)) {
          findings.push({
            id: `sec-${rule.id}-${file.filename}-${i}`,
            category: "security",
            severity: rule.severity,
            title: `Unsafe pattern: ${rule.label}`,
            description: `Added code matches a known risky pattern.`,
            evidence: { file: file.filename, line: i, snippet: added.trim().slice(0, 120) },
          });
        }
      }
    }
  }

  const score = Math.min(findings.filter((f) => f.severity === "high").length * 25 + findings.length * 8, 100);

  return {
    name: "Security",
    score,
    summary:
      findings.length === 0
        ? "No obvious secrets or unsafe patterns in added lines."
        : `${findings.length} potential security concern(s) in the diff.`,
    findings,
  };
}

function redact(s: string): string {
  return s.replace(/(['"])[^'"]{4,}\1/g, "$1***REDACTED***$1");
}
