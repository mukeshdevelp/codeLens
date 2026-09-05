import type { DimensionResult, FileChange, Finding } from "./types.js";

const CRITICAL_PATTERNS: Array<{
  id: string;
  label: string;
  severity: "high" | "medium";
  patterns: RegExp[];
}> = [
  {
    id: "auth",
    label: "Authentication",
    severity: "high",
    patterns: [/auth/i, /login/i, /session/i, /jwt/i, /oauth/i, /password/i, /token/i],
  },
  {
    id: "payments",
    label: "Payments & Billing",
    severity: "high",
    patterns: [/payment/i, /billing/i, /stripe/i, /checkout/i, /invoice/i, /subscription/i],
  },
  {
    id: "permissions",
    label: "Permissions & Access Control",
    severity: "high",
    patterns: [/permission/i, /rbac/i, /acl/i, /authorize/i, /role/i, /policy/i],
  },
  {
    id: "data",
    label: "Data Handling",
    severity: "medium",
    patterns: [/database/i, /migration/i, /schema/i, /sql/i, /encrypt/i, /pii/i],
  },
  {
    id: "infra",
    label: "Infrastructure & Config",
    severity: "medium",
    patterns: [/docker/i, /kubernetes/i, /terraform/i, /deploy/i, /\.env/i, /config/i],
  },
  {
    id: "api",
    label: "Public API Surface",
    severity: "medium",
    patterns: [/routes?\//i, /controller/i, /middleware/i, /endpoint/i, /graphql/i],
  },
];

export function detectCriticalPaths(files: FileChange[]): DimensionResult {
  const findings: Finding[] = [];
  const hitAreas = new Set<string>();

  for (const file of files) {
    const path = file.filename;
    const content = `${path}\n${file.patch ?? ""}`;

    for (const area of CRITICAL_PATTERNS) {
      if (area.patterns.some((p) => p.test(content))) {
        hitAreas.add(area.label);
        findings.push({
          id: `critical-${area.id}-${path}`,
          category: "critical",
          severity: area.severity,
          title: `${area.label} area touched`,
          description: `Changes may affect ${area.label.toLowerCase()} — review carefully.`,
          evidence: { file: path },
        });
      }
    }
  }

  const uniqueLabels = [...hitAreas];
  const score = Math.min(findings.length * 12, 100);

  return {
    name: "Critical Functionality",
    score,
    summary:
      uniqueLabels.length === 0
        ? "No critical-path areas detected in changed files."
        : `Touches: ${uniqueLabels.join(", ")}.`,
    findings: dedupeByFile(findings),
  };
}

function dedupeByFile(findings: Finding[]): Finding[] {
  const seen = new Set<string>();
  return findings.filter((f) => {
    const key = `${f.title}:${f.evidence.file}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
