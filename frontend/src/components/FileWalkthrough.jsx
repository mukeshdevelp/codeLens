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

export default function FileWalkthrough({ files }) {
  const [openFiles, setOpenFiles] = useState(() => new Set(files.slice(0, 2).map((f) => f.filename)));
  const [expandAll, setExpandAll] = useState(false);

  const toggle = (filename) => {
    setOpenFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const handleExpandAll = () => {
    if (expandAll) {
      setOpenFiles(new Set());
      setExpandAll(false);
    } else {
      setOpenFiles(new Set(files.map((f) => f.filename)));
      setExpandAll(true);
    }
  };

  if (!files?.length) {
    return <p className="muted">No file changes found.</p>;
  }

  const totalAdd = files.reduce((s, f) => s + (f.additions || 0), 0);
  const totalDel = files.reduce((s, f) => s + (f.deletions || 0), 0);

  return (
    <div className="walkthrough">
      <div className="walkthrough-toolbar">
        <span className="muted">{files.length} files · <span className="diff-stat-add">+{totalAdd}</span> <span className="diff-stat-del">-{totalDel}</span></span>
        <button type="button" className="btn ghost btn-sm" onClick={handleExpandAll}>
          {expandAll ? "Collapse all" : "Expand all"}
        </button>
      </div>

      <div className="file-list">
        {files.map((file) => {
          const isOpen = openFiles.has(file.filename);
          return (
            <div key={file.filename} className={`file-card ${isOpen ? "open" : ""}`}>
              <button type="button" className="file-card-header" onClick={() => toggle(file.filename)}>
                <span className={statusClass(file.status)}>{STATUS_LABEL[file.status] || "M"}</span>
                <span className="file-name">{file.filename}</span>
                <span className="file-stats">
                  {file.additions > 0 && <span className="diff-stat-add">+{file.additions}</span>}
                  {file.deletions > 0 && <span className="diff-stat-del">-{file.deletions}</span>}
                </span>
                <span className="file-chevron">{isOpen ? "▾" : "▸"}</span>
              </button>

              {isOpen && (
                <div className="file-card-body">
                  <p className="file-summary">{file.summary}</p>
                  <DiffViewer patch={file.patch} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
