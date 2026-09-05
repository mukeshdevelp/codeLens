#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import {
  analyzePullRequest,
  analyzeVolume,
  detectCriticalPaths,
  scanSecurity,
  checkTestCoverage,
  detectScopeDrift,
  type FileChange,
} from "@codelens/analyzers";

const fileChangeSchema = z.object({
  filename: z.string(),
  status: z.enum(["added", "modified", "removed", "renamed"]),
  additions: z.number(),
  deletions: z.number(),
  patch: z.string().optional(),
});

const server = new McpServer({
  name: "codelens",
  version: "1.0.0",
});

server.tool(
  "analyze_pull_request",
  "Full PR analysis: volume, drift, critical paths, security, tests, risk score, and AI summary.",
  {
    title: z.string().describe("PR title"),
    body: z.string().optional().describe("PR description"),
    files: z.array(fileChangeSchema).describe("Changed files with optional patch diffs"),
    useAi: z.boolean().optional().describe("Use OpenAI for executive summary (needs OPENAI_API_KEY)"),
  },
  async ({ title, body, files, useAi }) => {
    const report = await analyzePullRequest(
      { title, body, files: files as FileChange[] },
      {
        useAi: useAi ?? Boolean(process.env.OPENAI_API_KEY),
        openAiApiKey: process.env.OPENAI_API_KEY,
        openAiModel: process.env.OPENAI_MODEL,
      }
    );
    return {
      content: [{ type: "text", text: JSON.stringify(report, null, 2) }],
    };
  }
);

server.tool(
  "analyze_diff_volume",
  "Measure PR size: files changed, lines added/removed, large file flags.",
  { files: z.array(fileChangeSchema) },
  async ({ files }) => {
    const result = analyzeVolume(files as FileChange[]);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "detect_critical_paths",
  "Flag changes touching auth, payments, permissions, data, infra, or API surfaces.",
  { files: z.array(fileChangeSchema) },
  async ({ files }) => {
    const result = detectCriticalPaths(files as FileChange[]);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "scan_security_patterns",
  "Scan added diff lines for secrets, eval, SQL injection patterns, and other unsafe code.",
  { files: z.array(fileChangeSchema) },
  async ({ files }) => {
    const result = scanSecurity(files as FileChange[]);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "check_test_coverage_gaps",
  "Find source files changed without corresponding test file updates.",
  { files: z.array(fileChangeSchema) },
  async ({ files }) => {
    const result = checkTestCoverage(files as FileChange[]);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "detect_scope_drift",
  "Check if PR changes are broader than the stated title/description.",
  {
    title: z.string(),
    body: z.string().optional(),
    files: z.array(fileChangeSchema),
  },
  async ({ title, body, files }) => {
    const result = detectScopeDrift({ title, body, files: files as FileChange[] });
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("CodeLens MCP server running on stdio");
}

main().catch((err) => {
  console.error("MCP server failed:", err);
  process.exit(1);
});
