import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { analyzePullRequest } from "@codelens/analyzers";
import { renderMarkdownReport } from "@codelens/reporter";

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(__dirname, "../fixtures/demo-pr.json");

const pr = JSON.parse(readFileSync(fixturePath, "utf-8"));

const report = await analyzePullRequest(pr, {
  useAi: Boolean(process.env.OPENAI_API_KEY),
  openAiApiKey: process.env.OPENAI_API_KEY,
  openAiModel: process.env.OPENAI_MODEL,
});

console.log("\n" + "=".repeat(60));
console.log("CODELENS DEMO — PR ANALYSIS OUTPUT");
console.log("=".repeat(60));
console.log(renderMarkdownReport(report));
console.log("\nJSON report saved to .reports/demo-output.json");

mkdirSync(join(__dirname, "../.reports"), { recursive: true });
mkdirSync(join(__dirname, "../apps/api/.reports"), { recursive: true });
writeFileSync(join(__dirname, "../.reports/demo-output.json"), JSON.stringify(report, null, 2));
writeFileSync(join(__dirname, "../apps/api/.reports/demo-1.json"), JSON.stringify(report, null, 2));
