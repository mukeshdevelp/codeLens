import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import AiSourceBadge, { PanelHeading } from "../components/AiSourceBadge";
import CommitWalkthrough from "../components/CommitWalkthrough";
import FileWalkthrough from "../components/FileWalkthrough";
import Layout from "../components/Layout";
import ReviewDiscussion from "../components/ReviewDiscussion";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "changes", label: "Changes" },
  { id: "commits", label: "Commits" },
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
  const [ghStatus, setGhStatus] = useState(null);
  const [posting, setPosting] = useState(false);
  const [prActions, setPrActions] = useState(null);
  const [approving, setApproving] = useState(false);
  const [merging, setMerging] = useState(false);
  const [showMergeConfirm, setShowMergeConfirm] = useState(false);
  const [mergeMethod, setMergeMethod] = useState("merge");
  const [successMsg, setSuccessMsg] = useState("");
  const prNumber = Number(number);

  const isStaleReport = (data, status) => {
    if (!data) return true;
    if (!data.fileChanges?.length && (data.pr?.changedFiles ?? 0) > 0) return true;
    if (!("aiProvider" in data)) return true;
    if (!("commits" in data)) return true;
    if (data.commits?.length > 0 && !("files" in data.commits[0])) return true;
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

  const runAnalyze = async (opts = {}) => {
    setAnalyzing(true);
    setError("");
    try {
      setReport(await api.analyze(owner, repo, prNumber, opts));
      api.aiStatus().then(setAiStatus).catch(() => {});
    } catch (e) {
      setError(e.message);
    } finally {
      setAnalyzing(false);
      setLoading(false);
    }
  };

  const postToGithub = async () => {
    setPosting(true);
    setError("");
    try {
      const res = await api.postSummaryToGithub(owner, repo, prNumber, false);
      if (res.skipped) {
        setError("Summary already posted to GitHub. Use force from API to post again.");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setPosting(false);
    }
  };

  const refreshPrActions = async () => {
    try {
      setPrActions(await api.prActions(owner, repo, prNumber));
    } catch {
      setPrActions(null);
    }
  };

  const approvePr = async () => {
    setApproving(true);
    setError("");
    setSuccessMsg("");
    try {
      await api.approvePr(owner, repo, prNumber);
      setSuccessMsg("Pull request approved on GitHub.");
      await refreshPrActions();
    } catch (e) {
      setError(e.message);
    } finally {
      setApproving(false);
    }
  };

  const mergePr = async (method = mergeMethod) => {
    setMerging(true);
    setError("");
    setSuccessMsg("");
    setShowMergeConfirm(false);
    try {
      const res = await api.mergePr(owner, repo, prNumber, method);
      setSuccessMsg(`Merged into ${res.baseRef || prActions?.baseRef || "base branch"}.`);
      await refreshPrActions();
    } catch (e) {
      setError(e.message);
    } finally {
      setMerging(false);
    }
  };

  const approveAndMerge = async () => {
    setMerging(true);
    setError("");
    setSuccessMsg("");
    setShowMergeConfirm(false);
    try {
      if (prActions?.canApprove && !prActions?.userApproved) {
        await api.approvePr(owner, repo, prNumber);
      }
      const res = await api.mergePr(owner, repo, prNumber, mergeMethod);
      const prefix = prActions?.canApprove ? "Approved and merged" : "Merged";
      setSuccessMsg(`${prefix} into ${res.baseRef || prActions?.baseRef || "base branch"}.`);
      await refreshPrActions();
    } catch (e) {
      setError(e.message);
    } finally {
      setMerging(false);
    }
  };

  const prIsOpen = prActions?.state === "open" && !prActions?.merged;
  const canMerge = prIsOpen && prActions?.mergeable !== false;
  const mergeBlockedReason = prActions?.mergeableState === "dirty"
    ? "Merge conflicts must be resolved on GitHub first."
    : prActions?.mergeableState === "blocked"
      ? "Required checks or reviews are blocking merge."
      : prActions?.mergeable === null
        ? "GitHub is still computing merge status — try again shortly."
        : "";

  useEffect(() => {
    api.aiStatus().then(setAiStatus).catch(() => {});
    api.githubStatus().then(setGhStatus).catch(() => {});
  }, []);

  useEffect(() => {
    refreshPrActions();
  }, [owner, repo, number]);

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
        <div className="report-header-actions">
          {prActions?.merged && (
            <span className="pr-status-badge merged">Merged</span>
          )}
          {prActions && prActions.state === "closed" && !prActions.merged && (
            <span className="pr-status-badge closed">Closed</span>
          )}
          {prIsOpen && (
            <>
              {prActions.canApprove && (
                <button
                  type="button"
                  className="btn ghost"
                  onClick={approvePr}
                  disabled={approving || merging || prActions.userApproved}
                  title={prActions.userApproved ? "You already approved this PR" : "Submit an APPROVE review on GitHub"}
                >
                  {approving ? "Approving…" : prActions.userApproved ? "Approved" : "Approve PR"}
                </button>
              )}
              <button
                type="button"
                className="btn success"
                onClick={() => setShowMergeConfirm(true)}
                disabled={merging || approving || !canMerge}
                title={mergeBlockedReason || `Merge into ${prActions.baseRef || "base branch"}`}
              >
                {merging ? "Merging…" : `Merge into ${prActions.baseRef || "base"}`}
              </button>
            </>
          )}
          {ghStatus?.prCommentsEnabled && (
            <button type="button" className="btn ghost" onClick={postToGithub} disabled={posting || !report}>
              {posting ? "Posting…" : "Post to GitHub"}
            </button>
          )}
          {ghStatus?.checksEnabled && ghStatus?.appConfigured && (
            <button
              type="button"
              className="btn ghost"
              onClick={() => runAnalyze({ syncGithubCheck: true })}
              disabled={analyzing}
            >
              Sync GitHub Check
            </button>
          )}
          <button type="button" className="btn primary" onClick={() => runAnalyze()} disabled={analyzing}>
            {analyzing ? "Analyzing…" : "Re-analyze"}
          </button>
        </div>
      </div>

      {ghStatus?.appConfigured && (
        <p className="muted github-integration-note">
          GitHub App connected — webhooks auto-analyze PRs; Checks appear on github.com when enabled.
          {ghStatus.installUrl && (
            <> <a href={ghStatus.installUrl} target="_blank" rel="noreferrer">Install app</a></>
          )}
        </p>
      )}
      {(loading || analyzing) && <div className="page-center"><div className="spinner" /></div>}
      {error && <div className="error-banner">{error}</div>}
      {successMsg && <div className="success-banner">{successMsg}</div>}
      {prIsOpen && mergeBlockedReason && !error && (
        <p className="muted merge-hint">{mergeBlockedReason}</p>
      )}
      {prIsOpen && prActions?.isAuthor && (
        <p className="muted merge-hint">
          You opened this PR — GitHub does not allow self-approval. Use <strong>Merge</strong> if you have permission.
        </p>
      )}
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
                {t.id === "commits" && report.commits?.length > 0 && (
                  <span className="tab-count">{report.commits.length}</span>
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
                <p className="muted panel-intro">
                  Rule-based risk signals from analyzers — not AI. Docs (.md) are excluded from auth/security keyword scans.
                </p>
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
                File-by-file summary with diffs. Expand any file to see what changed.
              </p>
              <FileWalkthrough
                files={report.fileChanges || []}
                aiProvider={report.aiProvider}
                prHtmlUrl={report.pr?.htmlUrl}
              />
            </section>
          )}

          {tab === "commits" && (
            <section className="panel">
              <h3>Commit history</h3>
              <p className="muted panel-intro">
                All commits on this branch with per-file diffs — green for additions, red for deletions.
              </p>
              <CommitWalkthrough
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

      {showMergeConfirm && prActions && (
        <div className="modal-backdrop" onClick={() => !merging && setShowMergeConfirm(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <h3>Merge pull request?</h3>
            <p className="muted">
              This will merge <strong>#{number}</strong> into <code>{prActions.baseRef}</code> on GitHub.
              {report?.riskLevel === "high" && (
                <> This PR is flagged as <strong>high risk</strong> — confirm you have reviewed the changes.</>
              )}
            </p>
            <label className="merge-method-label">
              Merge method
              <select
                value={mergeMethod}
                onChange={(e) => setMergeMethod(e.target.value)}
                disabled={merging}
              >
                <option value="merge">Create a merge commit</option>
                <option value="squash">Squash and merge</option>
                <option value="rebase">Rebase and merge</option>
              </select>
            </label>
            <div className="modal-actions">
              <button type="button" className="btn ghost" onClick={() => setShowMergeConfirm(false)} disabled={merging}>
                Cancel
              </button>
              {!prActions.userApproved && prActions.canApprove && (
                <button type="button" className="btn ghost" onClick={approveAndMerge} disabled={merging}>
                  {merging ? "Working…" : "Approve & merge"}
                </button>
              )}
              <button type="button" className="btn success" onClick={() => mergePr()} disabled={merging}>
                {merging ? "Merging…" : "Merge"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
