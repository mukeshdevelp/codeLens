import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
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

function PrStats({ pr }) {
  if (!pr) return null;
  return (
    <div className="pr-stats">
      {pr.author && <span>by @{pr.author}</span>}
      {pr.changedFiles != null && <span>{pr.changedFiles} files</span>}
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
    if (data.fileChanges?.some((f) => !("summarySource" in f))) return true;
    // Groq configured but cache has no AI file summaries — run analyze once and save to DB
    if (status?.configured) {
      const hasAiFileSummary = data.fileChanges?.some((f) => f.summarySource === "ai");
      if (!hasAiFileSummary || !data.aiSummariesUsed) return true;
      // Old Groq cache before per-file timestamp — re-run once and save fresh summaries
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
            <>
              <section className="panel">
                <h3>PR summary</h3>
                <p className="pr-overview">{report.prOverview || report.executiveSummary}</p>
              </section>

              <section className="panel">
                <h3>Executive summary</h3>
                <p>{report.executiveSummary}</p>
              </section>

              <section className="panel">
                <h3>Where to focus first</h3>
                <ol className="focus-list">
                  {report.focusAreas.map((area) => (
                    <li key={area.rank} className={`focus-${area.severity}`}>
                      <strong>#{area.rank} {area.area}</strong>
                      <span>{area.reason}</span>
                      {area.files.length > 0 && <code>{area.files.join(", ")}</code>}
                    </li>
                  ))}
                </ol>
              </section>
            </>
          )}

          {tab === "changes" && (
            <section className="panel">
              <h3>Walkthrough</h3>
              <p className="muted panel-intro">
                File-by-file summary with diffs — like CodeRabbit. Expand any file to see what changed.
              </p>
              <FileWalkthrough files={report.fileChanges || []} aiProvider={report.aiProvider} />
            </section>
          )}

          {tab === "discussion" && (
            <section className="panel">
              <h3>Review discussion</h3>
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
              <h3>Analysis breakdown</h3>
              <div className="dimensions">
                {report.dimensions.map((dim) => (
                  <details key={dim.name} className="dimension" open={dim.score >= 25}>
                    <summary>
                      <span>{dim.name}</span>
                      <span className="dim-score">{dim.score}</span>
                    </summary>
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
            {report.aiProvider && (
              <> · AI: {report.aiProvider} ({report.aiSummariesUsed} AI summaries)</>
            )}
          </p>
        </div>
      )}
    </Layout>
  );
}
