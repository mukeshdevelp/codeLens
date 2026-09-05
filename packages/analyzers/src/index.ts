import type { AnalysisReport, AnalyzeOptions, PullRequestInput } from "./types.js";
import { detectCriticalPaths } from "./critical-paths.js";
import { detectScopeDrift, analyzeFunctionality } from "./drift.js";
import { scanSecurity } from "./security.js";
import { checkTestCoverage } from "./tests.js";
import { analyzeVolume } from "./volume.js";
import {
  buildFocusAreas,
  computeRiskScore,
  riskLevelFromScore,
  ruleBasedSummary,
} from "./scorer.js";

export async function analyzePullRequest(
  pr: PullRequestInput,
  options: AnalyzeOptions = {}
): Promise<AnalysisReport> {
  const dimensions = [
    analyzeVolume(pr.files, options.repoAverageLines ?? 200),
    detectScopeDrift(pr),
    analyzeFunctionality(pr.files),
    detectCriticalPaths(pr.files),
    scanSecurity(pr.files),
    checkTestCoverage(pr.files),
  ];

  const allFindings = dimensions.flatMap((d) => d.findings);
  const riskScore = computeRiskScore(dimensions);
  const riskLevel = riskLevelFromScore(riskScore);
  const focusAreas = buildFocusAreas(allFindings);

  let executiveSummary = ruleBasedSummary(riskLevel, riskScore, dimensions, focusAreas);

  if (options.useAi && options.openAiApiKey) {
    try {
      executiveSummary = await aiSummarize(pr, dimensions, focusAreas, riskLevel, options);
    } catch {
      // fall back to rule-based summary
    }
  }

  return {
    pr: { title: pr.title, body: pr.body },
    riskLevel,
    riskScore,
    executiveSummary,
    focusAreas,
    dimensions,
    generatedAt: new Date().toISOString(),
  };
}

async function aiSummarize(
  pr: PullRequestInput,
  dimensions: AnalysisReport["dimensions"],
  focusAreas: AnalysisReport["focusAreas"],
  riskLevel: string,
  options: AnalyzeOptions
): Promise<string> {
  const model = options.openAiModel ?? "gpt-4o-mini";
  const structuredFindings = dimensions.map((d) => ({
    dimension: d.name,
    summary: d.summary,
    findings: d.findings.slice(0, 5).map((f) => ({
      severity: f.severity,
      title: f.title,
      file: f.evidence.file,
    })),
  }));

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${options.openAiApiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      temperature: 0.2,
      max_tokens: 300,
      messages: [
        {
          role: "system",
          content:
            "You summarize pull request analysis for code reviewers. Use ONLY the provided structured findings. Be concise (3-5 sentences). State risk level, what changed, and where to focus review. Do not invent issues not in the data.",
        },
        {
          role: "user",
          content: JSON.stringify({
            title: pr.title,
            body: pr.body?.slice(0, 500),
            riskLevel,
            focusAreas,
            dimensions: structuredFindings,
          }),
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(`OpenAI API error: ${response.status}`);
  }

  const data = (await response.json()) as {
    choices: Array<{ message: { content: string } }>;
  };

  return data.choices[0]?.message?.content?.trim() ?? ruleBasedSummary(
    riskLevel as "high" | "medium" | "low",
    computeRiskScore(dimensions),
    dimensions,
    focusAreas
  );
}

export * from "./types.js";
export { analyzeVolume, detectCriticalPaths, scanSecurity, checkTestCoverage, detectScopeDrift, analyzeFunctionality };
export { computeRiskScore, buildFocusAreas, ruleBasedSummary };
