import express, { type Request } from "express";
import { createHash, timingSafeEqual } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { analyzePullRequest, type FileChange } from "@codelens/analyzers";
import { renderMarkdownReport, renderCheckSummary } from "@codelens/reporter";
import { createAppOctokit, fetchPullRequestFiles } from "./github.js";

type RawBodyRequest = Request & { rawBody?: Buffer };

const app = express();
const PORT = Number(process.env.PORT ?? 3001);
const WEB_URL = process.env.WEB_URL ?? "http://localhost:3000";
const REPORTS_DIR = join(process.cwd(), ".reports");

app.use(express.json({ verify: (req, _res, buf) => { (req as RawBodyRequest).rawBody = buf; } }));

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "codelens-api" });
});

app.post("/webhooks/github", async (req, res) => {
  const signature = req.headers["x-hub-signature-256"] as string | undefined;
  if (process.env.GITHUB_WEBHOOK_SECRET && !verifySignature((req as RawBodyRequest).rawBody, signature)) {
    res.status(401).send("Invalid signature");
    return;
  }

  const event = req.headers["x-github-event"] as string;
  if (event !== "pull_request") {
    res.status(200).send("Ignored");
    return;
  }

  const action = req.body.action;
  if (!["opened", "synchronize", "reopened"].includes(action)) {
    res.status(200).send("Ignored action");
    return;
  }

  res.status(202).json({ message: "Analysis queued" });

  const pr = req.body.pull_request;
  const repo = req.body.repository;

  processPullRequest({
    owner: repo.owner.login,
    repo: repo.name,
    number: pr.number,
    title: pr.title,
    body: pr.body ?? "",
    htmlUrl: pr.html_url,
  }).catch((err) => console.error("PR analysis failed:", err));
});

app.post("/api/analyze", async (req, res) => {
  try {
    const { title, body, files } = req.body as {
      title: string;
      body?: string;
      files: FileChange[];
    };
    const report = await analyzePullRequest(
      { title, body, files },
      {
        useAi: Boolean(process.env.OPENAI_API_KEY),
        openAiApiKey: process.env.OPENAI_API_KEY,
        openAiModel: process.env.OPENAI_MODEL,
      }
    );
    saveReport("local", 0, report);
    res.json(report);
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.get("/api/reports/:owner/:repo/:number", (req, res) => {
  const report = loadReport(req.params.owner, Number(req.params.number));
  if (!report) {
    res.status(404).json({ error: "Report not found" });
    return;
  }
  res.json(report);
});

async function processPullRequest(input: {
  owner: string;
  repo: string;
  number: number;
  title: string;
  body: string;
  htmlUrl: string;
}) {
  let files: FileChange[] = [];

  if (process.env.GITHUB_APP_ID && process.env.GITHUB_PRIVATE_KEY) {
    const octokit = await createAppOctokit(input.owner);
    files = await fetchPullRequestFiles(octokit, input.owner, input.repo, input.number);
  }

  const report = await analyzePullRequest(
    { title: input.title, body: input.body, files },
    {
      useAi: Boolean(process.env.OPENAI_API_KEY),
      openAiApiKey: process.env.OPENAI_API_KEY,
      openAiModel: process.env.OPENAI_MODEL,
    }
  );

  saveReport(input.owner, input.number, report);

  const reportUrl = `${WEB_URL}/report/${input.owner}/${input.repo}/${input.number}`;
  const markdown = renderMarkdownReport(report, reportUrl);

  if (process.env.GITHUB_APP_ID && process.env.GITHUB_PRIVATE_KEY) {
    const octokit = await createAppOctokit(input.owner);
    await postPrComment(octokit, input.owner, input.repo, input.number, markdown);
    await postCheckRun(octokit, input.owner, input.repo, input.number, report);
  }

  console.log(`Analysis complete for ${input.owner}/${input.repo}#${input.number} — ${report.riskLevel} risk`);
}

async function postPrComment(
  octokit: Awaited<ReturnType<typeof createAppOctokit>>,
  owner: string,
  repo: string,
  number: number,
  body: string
) {
  const marker = "<!-- codelens-report -->";
  const { data: comments } = await octokit.rest.issues.listComments({ owner, repo, issue_number: number });

  const existing = comments.find((c) => c.body?.includes(marker));
  const fullBody = `${marker}\n${body}`;

  if (existing) {
    await octokit.rest.issues.updateComment({
      owner,
      repo,
      comment_id: existing.id,
      body: fullBody,
    });
  } else {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number: number,
      body: fullBody,
    });
  }
}

async function postCheckRun(
  octokit: Awaited<ReturnType<typeof createAppOctokit>>,
  owner: string,
  repo: string,
  number: number,
  report: Awaited<ReturnType<typeof analyzePullRequest>>
) {
  const { data: pr } = await octokit.rest.pulls.get({ owner, repo, pull_number: number });

  await octokit.rest.checks.create({
    owner,
    repo,
    name: "CodeLens",
    head_sha: pr.head.sha,
    status: "completed",
    conclusion: report.riskLevel === "high" ? "neutral" : "success",
    output: {
      title: renderCheckSummary(report),
      summary: report.executiveSummary,
    },
  });
}

function saveReport(owner: string, number: number, report: unknown) {
  mkdirSync(REPORTS_DIR, { recursive: true });
  writeFileSync(join(REPORTS_DIR, `${owner}-${number}.json`), JSON.stringify(report, null, 2));
}

function loadReport(owner: string, number: number) {
  const path = join(REPORTS_DIR, `${owner}-${number}.json`);
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf-8"));
}

function verifySignature(rawBody: Buffer | undefined, signature: string | undefined): boolean {
  if (!rawBody || !signature?.startsWith("sha256=")) return false;
  const expected = "sha256=" + createHash("sha256").update(rawBody).digest("hex");
  try {
    return timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  } catch {
    return false;
  }
}

app.listen(PORT, () => {
  console.log(`CodeLens API listening on http://localhost:${PORT}`);
});
