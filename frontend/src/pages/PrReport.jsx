import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import Layout from "../components/Layout";

function RiskBadge({ level, score }) {
  return (
    <div className={`risk-banner risk-${level}`}>
      <span>{level.toUpperCase()} RISK</span>
      <strong>{score}/100</strong>
    </div>
  );
}

export default function PrReport() {
  const { owner, repo, number } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const prNumber = Number(number);

  const runAnalyze = async () => {
    setAnalyzing(true);
    setError("");
    try {
      setReport(await api.analyze(owner, repo, prNumber));
    } catch (e) {
      setError(e.message);
    } finally {
      setAnalyzing(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    api.report(owner, repo, prNumber)
      .then(setReport)
      .catch(() => runAnalyze())
      .finally(() => setLoading(false));
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
        </div>
        <button type="button" className="btn primary" onClick={runAnalyze} disabled={analyzing}>
          {analyzing ? "Analyzing…" : "Re-analyze"}
        </button>
      </div>

      {(loading || analyzing) && <div className="page-center"><div className="spinner" /></div>}
      {error && <div className="error-banner">{error}</div>}

      {report && !analyzing && (
        <div className="report">
          <RiskBadge level={report.riskLevel} score={report.riskScore} />

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

          <section className="panel">
            <h3>Analysis breakdown</h3>
            <div className="dimensions">
              {report.dimensions.map((dim) => (
                <details key={dim.name} className="dimension" open={dim.score >= 25}>
                  <summary>
                    <span>{dim.name}</span>
                    <span className="dim-score">{dim.score}</span>
                  </summary>
                  <p className="muted">{dim.summary}</p>
                  <ul>
                    {dim.findings.length === 0 && <li className="muted">No findings</li>}
                    {dim.findings.map((f) => (
                      <li key={f.id} className={`finding sev-${f.severity}`}>
                        <span className="badge">{f.severity}</span>
                        <strong>{f.title}</strong>
                        <span>{f.description}</span>
                        {f.evidence?.file && <code>{f.evidence.file}</code>}
                      </li>
                    ))}
                  </ul>
                </details>
              ))}
            </div>
          </section>

          <p className="muted footer-note">Generated {new Date(report.generatedAt).toLocaleString()}</p>
        </div>
      )}
    </Layout>
  );
}
