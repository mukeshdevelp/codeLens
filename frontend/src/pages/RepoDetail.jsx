import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import Layout from "../components/Layout";

export default function RepoDetail() {
  const { owner, repo } = useParams();
  const [pulls, setPulls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.pulls(owner, repo)
      .then(setPulls)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [owner, repo]);

  return (
    <Layout title={`${owner}/${repo}`}>
      <div className="breadcrumb">
        <Link to="/dashboard">Repositories</Link>
        <span>/</span>
        <span>{owner}/{repo}</span>
      </div>

      <section className="hero compact">
        <h2>Open pull requests</h2>
        <p>Analyze a PR to get risk signals, focus areas, and an executive summary.</p>
      </section>

      {loading && <div className="page-center"><div className="spinner" /></div>}
      {error && <div className="error-banner">{error}</div>}

      {!loading && !error && (
        <div className="pr-list">
          {pulls.length === 0 && <p className="muted">No open pull requests.</p>}
          {pulls.map((pr) => (
            <div key={pr.number} className="pr-row">
              <div>
                <h3>#{pr.number} {pr.title}</h3>
                <p className="muted">by {pr.author} · updated {new Date(pr.updatedAt).toLocaleDateString()}</p>
              </div>
              <div className="pr-actions">
                <a href={pr.htmlUrl} target="_blank" rel="noreferrer" className="btn ghost">GitHub</a>
                <Link to={`/repos/${owner}/${repo}/pulls/${pr.number}`} className="btn primary">Analyze</Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  );
}
