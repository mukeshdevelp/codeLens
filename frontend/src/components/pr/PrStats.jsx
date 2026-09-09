export default function PrStats({ pr }) {
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
