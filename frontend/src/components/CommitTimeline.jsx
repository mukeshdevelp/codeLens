export default function CommitTimeline({ commits, htmlUrl }) {
  if (!commits?.length) {
    return <p className="muted">No commits found for this pull request.</p>;
  }

  return (
    <div className="commit-timeline">
      <div className="commit-timeline-header">
        <span className="muted">{commits.length} commit{commits.length !== 1 ? "s" : ""} on this branch</span>
        {htmlUrl && (
          <a href={`${htmlUrl}/commits`} target="_blank" rel="noreferrer" className="btn ghost btn-sm">
            View on GitHub
          </a>
        )}
      </div>
      <ol className="commit-list">
        {commits.map((commit, index) => {
          const shortSha = commit.sha?.slice(0, 7) || "???????";
          const firstLine = (commit.message || "").split("\n")[0];
          return (
            <li key={commit.sha || index} className="commit-card">
              <div className="commit-card-top">
                <span className="commit-index">#{index + 1}</span>
                {commit.htmlUrl ? (
                  <a href={commit.htmlUrl} target="_blank" rel="noreferrer" className="commit-sha">
                    {shortSha}
                  </a>
                ) : (
                  <code className="commit-sha">{shortSha}</code>
                )}
                <span className="commit-author">@{commit.author}</span>
                {commit.date && (
                  <time className="commit-date muted" dateTime={commit.date}>
                    {new Date(commit.date).toLocaleString()}
                  </time>
                )}
              </div>
              <p className="commit-message">{firstLine}</p>
              {(commit.additions > 0 || commit.deletions > 0) && (
                <div className="commit-stats">
                  {commit.additions > 0 && <span className="diff-stat-add">+{commit.additions}</span>}
                  {commit.deletions > 0 && <span className="diff-stat-del">-{commit.deletions}</span>}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
