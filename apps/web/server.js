import express from "express";
import { readFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = Number(process.env.PORT ?? 3000);
const API_URL = process.env.API_URL ?? "http://localhost:3001";
const REPORTS_DIR = join(__dirname, "../../api/.reports");

app.use(express.static(join(__dirname, "public")));

app.get("/report/:owner/:repo/:number", async (req, res) => {
  const { owner, repo, number } = req.params;
  let report = null;

  const localPath = join(REPORTS_DIR, `${owner}-${number}.json`);
  if (existsSync(localPath)) {
    report = JSON.parse(readFileSync(localPath, "utf-8"));
  } else {
    try {
      const r = await fetch(`${API_URL}/api/reports/${owner}/${repo}/${number}`);
      if (r.ok) report = await r.json();
    } catch {
      /* ignore */
    }
  }

  res.send(renderPage(owner, repo, number, report));
});

function renderPage(owner, repo, number, report) {
  if (!report) {
    return `<!DOCTYPE html><html><head><title>CodeLens</title><link rel="stylesheet" href="/styles.css"></head>
    <body><main><h1>CodeLens</h1><p>No report found for ${owner}/${repo}#${number}. Run analysis first.</p></main></body></html>`;
  }

  const riskClass = report.riskLevel;
  const focusHtml = report.focusAreas
    .map(
      (a) =>
        `<li class="focus-${a.severity}"><strong>#${a.rank} ${esc(a.area)}</strong> — ${esc(a.reason)}<br><small>${esc(a.files.join(", "))}</small></li>`
    )
    .join("");

  const dimsHtml = report.dimensions
    .map((d) => {
      const findings = d.findings
        .map(
          (f) =>
            `<li class="sev-${f.severity}"><span class="badge">${f.severity}</span> ${esc(f.title)} ${f.evidence.file ? `<code>${esc(f.evidence.file)}</code>` : ""}</li>`
        )
        .join("");
      return `<section class="dimension"><h3>${esc(d.name)} <span class="score">${d.score}</span></h3><p>${esc(d.summary)}</p><ul>${findings || "<li>No findings</li>"}</ul></section>`;
    })
    .join("");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CodeLens — ${esc(owner)}/${esc(repo)}#${number}</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">CodeLens PR Brief</p>
      <h1>${esc(report.pr.title)}</h1>
      <p class="meta">${esc(owner)}/${esc(repo)}#${number}</p>
    </header>
    <div class="risk-banner risk-${riskClass}">
      <span class="risk-label">${report.riskLevel.toUpperCase()} RISK</span>
      <span class="risk-score">${report.riskScore}/100</span>
    </div>
    <section class="summary"><h2>Executive Summary</h2><p>${esc(report.executiveSummary)}</p></section>
    <section><h2>Where to focus first</h2><ol class="focus-list">${focusHtml}</ol></section>
    <section><h2>Analysis breakdown</h2>${dimsHtml}</section>
    <footer><small>Generated ${new Date(report.generatedAt).toLocaleString()}</small></footer>
  </main>
</body>
</html>`;
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

app.listen(PORT, () => console.log(`CodeLens dashboard http://localhost:${PORT}`));
