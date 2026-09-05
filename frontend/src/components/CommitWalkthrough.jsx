import { useState } from "react";
import DiffViewer from "./DiffViewer";

const STATUS_LABEL = {
  added: "A",
  removed: "D",
  modified: "M",
  renamed: "R",
  changed: "C",
};

function statusClass(status) {
  return `file-status file-status-${status || "modified"}`;
}

function CommitFileCard({ file, commitUrl }) {
  const [open, setOpen] = useState(false);
  const label = file.previousFilename
    ? `${file.previousFilename} → ${file.filename}`
    : file.filename;

  return (
    <div className={`commit-file-card ${open ? "open" : ""}`}>
      <button type="button" className="commit-file-header" onClick={() => setOpen(!open)}>
        <span className={statusClass(file.status)}>{STATUS_LABEL[file.status] || "M"}</span>
        <span className="commit-file-name">{label}</span>
        <span className="file-stats">
          {file.additions > 0 && <span className="diff-stat-add">+{file.additions}</span>}
          {file.deletions > 0 && <span className="diff-stat-del">-{file.deletions}</span>}
        </span>
        <span className="file-chevron">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="commit-file-body">
          <p className="muted commit-diff-label">
            Changes in this commit (parent → {file.filename})
          </p>
          <DiffViewer
            patch={file.patch}
            githubUrl={commitUrl}
            defaultExpanded
            unavailable={file.patchUnavailable}
          />
        </div>
      )}
    </div>
  );
}

export default function CommitWalkthrough({ commits, prHtmlUrl }) {
  const [openCommits, setOpenCommits] = useState(() => new Set(commits?.length ? [commits[0].sha] : []));

  if (!commits?.length) {
    return <p className="muted">No commits found for this pull request.</p>;
  }

  const toggleCommit = (sha) => {
    setOpenCommits((prev) => {
      const next = new Set(prev);
      if (next.has(sha)) next.delete(sha);
      else next.add(sha);
      return next;
    });
  };

  const expandAll = () => setOpenCommits(new Set(commits.map((c) => c.sha)));
  const collapseAll = () => setOpenCommits(new Set());

  const totalAdd = commits.reduce((s, c) => s + (c.additions || 0), 0);
  const totalDel = commits.reduce((s, c) => s + (c.deletions || 0), 0);

  return (
    <div className="commit-walkthrough">
      <div className="walkthrough-toolbar">
        <span className="muted">
          {commits.length} commit{commits.length !== 1 ? "s" : ""}{" "}
          · <span className="diff-stat-add">+{totalAdd}</span>{" "}
          <span className="diff-stat-del">-{totalDel}</span>
        </span>
        <div className="commit-toolbar-actions">
          <button type="button" className="btn ghost btn-sm" onClick={expandAll}>Expand all</button>
          <button type="button" className="btn ghost btn-sm" onClick={collapseAll}>Collapse all</button>
          {prHtmlUrl && (
            <a href={`${prHtmlUrl}/commits`} target="_blank" rel="noreferrer" className="btn ghost btn-sm">
              View on GitHub
            </a>
          )}
        </div>
      </div>

      <p className="muted walkthrough-note">
        Each commit shows files changed with a before → after diff.{" "}
        <span className="diff-stat-add">Green</span> = added lines,{" "}
        <span className="diff-stat-del">red</span> = removed lines.
      </p>

      <ol className="commit-walkthrough-list">
        {commits.map((commit, index) => {
          const isOpen = openCommits.has(commit.sha);
          const shortSha = commit.sha?.slice(0, 7) || "???????";
          const firstLine = (commit.message || "").split("\n")[0];
          const restMessage = (commit.message || "").split("\n").slice(1).join("\n").trim();

          return (
            <li key={commit.sha || index} className={`commit-walkthrough-card ${isOpen ? "open" : ""}`}>
              <button type="button" className="commit-walkthrough-header" onClick={() => toggleCommit(commit.sha)}>
                <span className="commit-index">#{index + 1}</span>
                <div className="commit-walkthrough-meta">
                  <div className="commit-walkthrough-title-row">
                    {commit.htmlUrl ? (
                      <a
                        href={commit.htmlUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="commit-sha"
                        onClick={(e) => e.stopPropagation()}
                      >
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
                </div>
                <div className="commit-walkthrough-stats">
                  {commit.additions > 0 && <span className="diff-stat-add">+{commit.additions}</span>}
                  {commit.deletions > 0 && <span className="diff-stat-del">-{commit.deletions}</span>}
                  <span className="commit-file-count muted">
                    {commit.files?.length || 0} file{(commit.files?.length || 0) !== 1 ? "s" : ""}
                  </span>
                </div>
                <span className="file-chevron">{isOpen ? "▾" : "▸"}</span>
              </button>

              {isOpen && (
                <div className="commit-walkthrough-body">
                  {restMessage && <pre className="commit-message-full muted">{restMessage}</pre>}
                  {!commit.files?.length ? (
                    <p className="muted">No file changes in this commit.</p>
                  ) : (
                    <div className="commit-files-list">
                      {commit.files.map((file) => (
                        <CommitFileCard
                          key={`${commit.sha}-${file.filename}`}
                          file={file}
                          commitUrl={commit.htmlUrl}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
