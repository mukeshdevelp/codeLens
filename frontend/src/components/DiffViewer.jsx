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

export default function DiffViewer({ patch, maxLines = 400 }) {
  if (!patch) {
    return <p className="muted diff-empty">Diff too large to display (GitHub omits patches over 1 MB).</p>;
  }

  const lines = patch.split("\n");
  const truncated = lines.length > maxLines;
  const visible = truncated ? lines.slice(0, maxLines) : lines;

  return (
    <div className="diff-viewer">
      <pre className="diff-pre">
        {visible.map((line, i) => (
          <DiffLine key={`${i}-${line.slice(0, 20)}`} line={line} />
        ))}
      </pre>
      {truncated && (
        <p className="muted diff-truncated">
          Showing first {maxLines} of {lines.length} diff lines. Open on GitHub for the full diff.
        </p>
      )}
    </div>
  );
}
