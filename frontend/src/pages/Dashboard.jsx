import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Layout from "../components/Layout";

export default function Dashboard() {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.repos()
      .then(setRepos)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Layout title="Your repositories">
      <section className="hero">
        <h2>Where do you want to start?</h2>
        <p>Select a repository to view open pull requests and run CodeLens analysis.</p>
      </section>

      {loading && <div className="page-center"><div className="spinner" /></div>}
      {error && <div className="error-banner">{error}</div>}

      {!loading && !error && (
        <div className="repo-grid">
          {repos.map((repo) => (
            <Link key={repo.id} to={`/repos/${repo.owner}/${repo.name}`} className="repo-card">
              <div className="repo-card-top">
                <h3>{repo.fullName}</h3>
                {repo.private && <span className="pill">Private</span>}
              </div>
              <p>{repo.description || "No description"}</p>
              <div className="repo-meta">
                <span>{repo.openIssues} open issues</span>
                <span>Updated {new Date(repo.updatedAt).toLocaleDateString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </Layout>
  );
}
