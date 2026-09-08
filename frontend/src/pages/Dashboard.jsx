import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Layout from "../components/Layout";

function matchesRepoSearch(repo, query) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    repo.fullName,
    repo.name,
    repo.owner,
    repo.description,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return q.split(/\s+/).every((term) => haystack.includes(term));
}

export default function Dashboard() {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.repos()
      .then(setRepos)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredRepos = useMemo(
    () => repos.filter((repo) => matchesRepoSearch(repo, search)),
    [repos, search]
  );

  return (
    <Layout title="Your repositories">
      <section className="hero">
        <h2>Where do you want to start?</h2>
        <p>Select a repository to view open pull requests and run CodeLens analysis.</p>
      </section>

      {!loading && !error && repos.length > 0 && (
        <div className="repo-search-bar">
          <label className="repo-search-label" htmlFor="repo-search">
            Search repositories
          </label>
          <input
            id="repo-search"
            type="search"
            className="repo-search-input"
            placeholder="Search by name, owner, or description…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoComplete="off"
          />
          {search.trim() && (
            <p className="repo-search-meta muted">
              Showing {filteredRepos.length} of {repos.length} repositories
            </p>
          )}
        </div>
      )}

      {loading && <div className="page-center"><div className="spinner" /></div>}
      {error && <div className="error-banner">{error}</div>}

      {!loading && !error && filteredRepos.length > 0 && (
        <div className="repo-grid">
          {filteredRepos.map((repo) => (
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

      {!loading && !error && repos.length > 0 && filteredRepos.length === 0 && (
        <div className="panel repo-search-empty">
          <p>No repositories match &quot;{search.trim()}&quot;.</p>
          <button type="button" className="btn ghost" onClick={() => setSearch("")}>
            Clear search
          </button>
        </div>
      )}

      {!loading && !error && repos.length === 0 && (
        <div className="panel">
          <p className="muted">No repositories found for your GitHub account.</p>
        </div>
      )}
    </Layout>
  );
}
