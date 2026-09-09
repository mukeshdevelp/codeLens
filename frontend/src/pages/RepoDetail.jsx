import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import Layout from "../components/Layout";
import Breadcrumb from "../components/ui/Breadcrumb";
import ErrorBanner from "../components/ui/ErrorBanner";
import LoadingSpinner from "../components/ui/LoadingSpinner";

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
      <Breadcrumb
        items={[
          { label: "Repositories", to: "/dashboard" },
          { label: `${owner}/${repo}` },
        ]}
      />

      <section className="hero compact">
        <h2>Open pull requests</h2>
        <p>Analyze a PR to get risk signals, focus areas, and an executive summary.</p>
      </section>

      {loading && <LoadingSpinner />}
      <ErrorBanner message={error} />

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
