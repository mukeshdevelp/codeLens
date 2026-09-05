import { useState } from "react";

function DiffLine({ line }) {
  if (line.startsWith("@@")) {
    return <div className="diff-line diff-hunk">{line}</div>;
  }
  if (line.startsWith("+") && !line.startsWith("+++")) {
    return <div className="diff-line diff-add">{line}</div>;
  }
  if (line.startsWith("-") && !line.startsWith("---")) {
    return <div className="diff-line diff-del">{line}</div>;
  }
  return <div className="diff-line">{line || " "}</div>;
}

const PREVIEW_LINES = 200;

export default function DiffViewer({ patch, githubUrl }) {
  const [expanded, setExpanded] = useState(true);

  if (!patch) {
    return (
      <div className="diff-empty-wrap">
        <p className="muted diff-empty">Diff too large to display (GitHub omits patches over 1 MB).</p>
        {githubUrl && (
          <a href={githubUrl} target="_blank" rel="noreferrer" className="btn ghost btn-sm">
            View full diff on GitHub
          </a>
        )}
      </div>
    );
  }

  const lines = patch.split("\n");
  const isLarge = lines.length > PREVIEW_LINES;
  const showAll = expanded || !isLarge;
  const visible = showAll ? lines : lines.slice(0, PREVIEW_LINES);
  const hiddenCount = lines.length - PREVIEW_LINES;

  return (
    <div className={`diff-viewer ${showAll ? "diff-viewer-full" : ""}`}>
      <pre className="diff-pre">
        {visible.map((line, i) => (
          <DiffLine key={`${i}-${line.slice(0, 20)}`} line={line} />
        ))}
      </pre>
      {isLarge && (
        <div className="diff-footer">
          {!showAll ? (
            <button type="button" className="btn ghost btn-sm" onClick={() => setExpanded(true)}>
              Show all {lines.length} lines ({hiddenCount} more hidden)
            </button>
          ) : (
            <button type="button" className="btn ghost btn-sm" onClick={() => setExpanded(false)}>
              Collapse diff
            </button>
          )}
          {githubUrl && (
            <a href={githubUrl} target="_blank" rel="noreferrer" className="btn ghost btn-sm">
              Open on GitHub
            </a>
          )}
        </div>
      )}
      {!isLarge && githubUrl && (
        <div className="diff-footer">
          <span className="muted diff-line-count">{lines.length} lines</span>
          <a href={githubUrl} target="_blank" rel="noreferrer" className="btn ghost btn-sm">
            Open on GitHub
          </a>
        </div>
      )}
    </div>
  );
}
