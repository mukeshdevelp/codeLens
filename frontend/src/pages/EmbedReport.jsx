import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import "../styles.css";

/**
 * Minimal PR report for embedding inside github.com (Check Run details / sidebar).
 * Loaded via signed token — no OAuth session required.
 */
export default function EmbedReport() {
  const { owner, repo, number } = useParams();
  const [search] = useSearchParams();
  const token = search.get("token") || "";
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setError("Missing embed token");
      setLoading(false);
      return;
    }
    api
      .embedReport(owner, repo, Number(number), token)
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [owner, repo, number, token]);

  if (loading) {
    return <div className="embed-page"><div className="spinner" /></div>;
  }

  if (error || !report) {
    return (
      <div className="embed-page">
        <p className="error-banner">{error || "Report not found"}</p>
      </div>
    );
  }

  return (
    <div className="embed-page">
      <header className="embed-header">
        <strong>CodeLens</strong>
        <span className={`risk-pill risk-${report.riskLevel}`}>{report.riskLevel} · {report.riskScore}/100</span>
        <Link
          to={`/repos/${owner}/${repo}/pulls/${number}`}
          className="btn ghost btn-sm"
          target="_blank"
          rel="noreferrer"
        >
          Open full app
        </Link>
      </header>

      <section className="embed-section">
        <h3>Summary</h3>
        <p>{report.executiveSummary || report.prOverview}</p>
      </section>

      {report.focusAreas?.length > 0 && (
        <section className="embed-section">
          <h3>Focus</h3>
          <ul className="embed-focus">
            {report.focusAreas.map((a) => (
              <li key={a.rank}>
                <span className={`badge badge-${a.severity}`}>{a.severity}</span>
                <strong>#{a.rank} {a.area}</strong> — {a.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="muted embed-footer">
        Embedded from GitHub · {report.pr?.changedFiles} files · {report.pr?.commitCount || 0} commits
      </p>
    </div>
  );
}
