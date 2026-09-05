import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import AiSourceBadge, { PanelHeading } from "../components/AiSourceBadge";
import FileWalkthrough from "../components/FileWalkthrough";
import Layout from "../components/Layout";
import ReviewDiscussion from "../components/ReviewDiscussion";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "changes", label: "Changes" },
  { id: "discussion", label: "Discussion" },
  { id: "analysis", label: "Risk analysis" },
];

function RiskBadge({ level, score }) {
  return (
    <div className={`risk-banner risk-${level}`}>
      <span>{level.toUpperCase()} RISK</span>
      <strong>{score}/100</strong>
    </div>
  );
}

function AiFooterBreakdown({ report }) {
  if (!report?.aiProvider) return null;
  const b = report.aiSummaryBreakdown || {};
  const parts = [];
  if (b.executiveSummary === "ai") parts.push("executive");
  if (b.prOverview === "ai") parts.push("PR overview");
  if (b.discussionSummary === "ai") parts.push("discussion");
  if (b.fileChanges > 0) parts.push(`${b.fileChanges} file${b.fileChanges !== 1 ? "s" : ""}`);
  return (
    <>
      {" "}· AI ({report.aiProvider}): {parts.length ? parts.join(", ") : "none"}
      {" "}({report.aiSummariesUsed} total)
    </>
  );
}

function PrStats({ pr }) {
  if (!pr) return null;
  return (
    <div className="pr-stats">
      {pr.author && <span>by @{pr.author}</span>}
      {pr.changedFiles != null && <span>{pr.changedFiles} files</span>}
      {pr.commitCount != null && pr.commitCount > 0 && (
        <span>{pr.commitCount} commit{pr.commitCount !== 1 ? "s" : ""}</span>
      )}
      {pr.additions != null && <span className="diff-stat-add">+{pr.additions}</span>}
      {pr.deletions != null && <span className="diff-stat-del">-{pr.deletions}</span>}
      {pr.htmlUrl && (
        <a href={pr.htmlUrl} target="_blank" rel="noreferrer" className="btn ghost btn-sm">View on GitHub</a>
      )}
    </div>
  );
}

export default function PrReport() {
  const { owner, repo, number } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");
  const [aiStatus, setAiStatus] = useState(null);
  const prNumber = Number(number);

  const isStaleReport = (data, status) => {
    if (!data) return true;
    if (!data.fileChanges?.length && (data.pr?.changedFiles ?? 0) > 0) return true;
    if (!("aiProvider" in data)) return true;
    if (!("commits" in data)) return true;
    if (!("discussionSummarySource" in data)) return true;
    if (!("prOverviewSource" in data)) return true;
    if (data.fileChanges?.some((f) => !("summarySource" in f))) return true;
    if (status?.configured) {
      const hasAiFileSummary = data.fileChanges?.some((f) => f.summarySource === "ai");
      if (!hasAiFileSummary || !data.aiSummariesUsed) return true;
      if (data.fileChanges?.some((f) => f.summarySource === "ai" && !f.summarizedAt)) return true;
    }
    return false;
  };

  const runAnalyze = async () => {
    setAnalyzing(true);
    setError("");
    try {
      setReport(await api.analyze(owner, repo, prNumber));
      api.aiStatus().then(setAiStatus).catch(() => {});
    } catch (e) {
      setError(e.message);
    } finally {
      setAnalyzing(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    api.aiStatus().then(setAiStatus).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const status = await api.aiStatus().catch(() => null);
      if (cancelled) return;
      setAiStatus(status);

      try {
        const data = await api.report(owner, repo, prNumber);
        if (cancelled) return;
        if (isStaleReport(data, status)) {
          await runAnalyze();
          return;
        }
        setReport(data);
      } catch {
        if (!cancelled) await runAnalyze();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [owner, repo, number]);

  return (
    <Layout title={`PR #${number}`}>
      <div className="breadcrumb">
        <Link to="/dashboard">Repositories</Link>
        <span>/</span>
        <Link to={`/repos/${owner}/${repo}`}>{owner}/{repo}</Link>
        <span>/</span>
        <span>#{number}</span>
      </div>

      <div className="report-header">
        <div>
          <h2>{report?.pr?.title || `Pull Request #${number}`}</h2>
          <p className="muted">{owner}/{repo}</p>
          <PrStats pr={report?.pr} />
        </div>
        <button type="button" className="btn primary" onClick={runAnalyze} disabled={analyzing}>
          {analyzing ? "Analyzing…" : "Re-analyze"}
        </button>
      </div>

      {(loading || analyzing) && <div className="page-center"><div className="spinner" /></div>}
      {error && <div className="error-banner">{error}</div>}
      {aiStatus?.configured && report && report.aiSummariesUsed === 0 && !analyzing && (
        <div className="error-banner">
          AI provider ({aiStatus.provider}) is configured but summaries fell back to rules.
          {aiStatus.lastError && <> Error: {aiStatus.lastError}</>}
          {" "}Click <strong>Re-analyze</strong> after restarting the backend. If it persists, run{" "}
          <code>curl http://localhost:8000/api/ai/test</code>.
        </div>
      )}

      {report && !analyzing && (
        <div className="report">
          <RiskBadge level={report.riskLevel} score={report.riskScore} />

          <nav className="report-tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`report-tab ${tab === t.id ? "active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
                {t.id === "changes" && report.fileChanges?.length > 0 && (
                  <span className="tab-count">{report.fileChanges.length}</span>
                )}
                {t.id === "discussion" && report.reviewActivity?.length > 0 && (
                  <span className="tab-count">{report.reviewActivity.length}</span>
                )}
              </button>
            ))}
          </nav>

          {tab === "overview" && (
            <div className="overview-section">
              <section className="panel overview-panel">
                <PanelHeading
                  title="PR summary"
                  source={report.prOverviewSource}
                  provider={report.aiProvider}
                />
                <div className="overview-highlight">
                  <p className="pr-overview">{report.prOverview || report.executiveSummary}</p>
                </div>
              </section>

              <section className="panel overview-panel">
                <PanelHeading
                  title="Executive summary"
                  source={report.executiveSummarySource}
                  provider={report.aiProvider}
                />
                <div className="overview-highlight overview-highlight-exec">
                  <p className="overview-exec-text">{report.executiveSummary}</p>
                </div>
              </section>

              <section className="panel overview-panel">
                <div className="panel-heading">
                  <h3>Where to focus first</h3>
                  <AiSourceBadge source="rules" />
                </div>
                <ol className="focus-list">
                  {report.focusAreas.map((area) => (
                    <li key={area.rank} className={`focus-card focus-${area.severity}`}>
                      <div className="focus-card-header">
                        <span className={`badge badge-${area.severity}`}>{area.severity}</span>
                        <strong className="focus-card-title">#{area.rank} {area.area}</strong>
                      </div>
                      <p className="focus-card-reason">{area.reason}</p>
                      {area.files.length > 0 && (
                        <div className="focus-card-files">
                          <span className="focus-file-label">Files</span>
                          <code>{area.files.join(", ")}</code>
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              </section>
            </div>
          )}

          {tab === "changes" && (
            <section className="panel">
              <div className="panel-heading">
                <h3>Walkthrough</h3>
                {report.fileChanges?.some((f) => f.summarySource === "ai") && (
                  <AiSourceBadge source="ai" provider={report.aiProvider} />
                )}
              </div>
              <p className="muted panel-intro">
                File-by-file summary with diffs — like CodeRabbit. Expand any file to see what changed.
              </p>
              <FileWalkthrough
                files={report.fileChanges || []}
                aiProvider={report.aiProvider}
                commits={report.commits || []}
                prHtmlUrl={report.pr?.htmlUrl}
              />
            </section>
          )}

          {tab === "discussion" && (
            <section className="panel">
              <PanelHeading
                title="Review discussion"
                source={report.discussionSummarySource}
                provider={report.aiProvider}
              />
              <p className="muted panel-intro">
                Summarized review comments, feedback, and conversation on this PR.
              </p>
              <ReviewDiscussion
                summary={report.discussionSummary}
                activity={report.reviewActivity}
              />
            </section>
          )}

          {tab === "analysis" && (
            <section className="panel">
              <div className="panel-heading">
                <h3>Analysis breakdown</h3>
                <AiSourceBadge source="rules" />
              </div>
              <p className="muted panel-intro">Risk dimensions and findings are generated by rule-based analyzers.</p>
              <div className="dimensions">
                {report.dimensions.map((dim) => (
                  <details key={dim.name} className="dimension" open={dim.score >= 25}>
                    <summary>
                      <span>{dim.name}</span>
                      <span className="dim-score">{dim.score}</span>
                    </summary>
                    <p className="dim-summary-row">
                      <AiSourceBadge source="rules" />
                    </p>
                    <p className="dim-summary">{dim.summary}</p>
                    <ul className="finding-list">
                      {dim.findings.length === 0 && <li className="finding-empty muted">No findings</li>}
                      {dim.findings.map((f) => (
                        <li key={f.id} className={`finding-card sev-${f.severity}`}>
                          <div className="finding-header">
                            <span className={`badge badge-${f.severity}`}>{f.severity}</span>
                            <strong className="finding-title">{f.title}</strong>
                          </div>
                          <p className="finding-desc">{f.description}</p>
                          {f.evidence?.file && (
                            <div className="finding-file">
                              <span className="finding-file-label">File</span>
                              <code>{f.evidence.file}</code>
                            </div>
                          )}
                          {f.evidence?.metric && !f.evidence?.file && (
                            <div className="finding-metric muted">{f.evidence.metric}</div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </details>
                ))}
              </div>
            </section>
          )}

          <p className="muted footer-note">
            Generated {new Date(report.generatedAt).toLocaleString()}
            <AiFooterBreakdown report={report} />
          </p>
        </div>
      )}
    </Layout>
  );
}
