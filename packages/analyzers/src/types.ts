export type Severity = "high" | "medium" | "low" | "info";

export interface FileChange {
  filename: string;
  status: "added" | "modified" | "removed" | "renamed";
  additions: number;
  deletions: number;
  patch?: string;
}

export interface Finding {
  id: string;
  category: string;
  severity: Severity;
  title: string;
  description: string;
  evidence: {
    file?: string;
    line?: number;
    snippet?: string;
    metric?: string;
  };
}

export interface DimensionResult {
  name: string;
  score: number;
  summary: string;
  findings: Finding[];
}

export interface PullRequestInput {
  title: string;
  body?: string;
  baseBranch?: string;
  headBranch?: string;
  files: FileChange[];
}

export interface AnalysisReport {
  pr: {
    title: string;
    body?: string;
  };
  riskLevel: Severity;
  riskScore: number;
  executiveSummary: string;
  focusAreas: Array<{
    rank: number;
    area: string;
    reason: string;
    severity: Severity;
    files: string[];
  }>;
  dimensions: DimensionResult[];
  generatedAt: string;
}

export interface AnalyzeOptions {
  repoAverageLines?: number;
  useAi?: boolean;
  openAiApiKey?: string;
  openAiModel?: string;
}
