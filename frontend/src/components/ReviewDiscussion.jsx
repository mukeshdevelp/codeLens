const REVIEW_STATE_STYLE = {
  APPROVED: "review-approved",
  CHANGES_REQUESTED: "review-changes",
  COMMENTED: "review-commented",
};

function formatState(state) {
  if (!state) return null;
  return state.replace(/_/g, " ").toLowerCase();
}

export default function ReviewDiscussion({ summary, activity }) {
  if (!summary && (!activity || activity.length === 0)) {
    return <p className="muted">No review discussion yet.</p>;
  }

  return (
    <div className="discussion">
      {summary && (
        <div className="discussion-summary">
          <p>{summary}</p>
        </div>
      )}

      {activity?.length > 0 && (
        <div className="discussion-thread">
          <h4>Review timeline</h4>
          {activity.map((item, i) => (
            <div key={`${item.createdAt}-${i}`} className={`discussion-item discussion-${item.type}`}>
              <div className="discussion-meta">
                <strong>@{item.author}</strong>
                {item.state && (
                  <span className={`review-state ${REVIEW_STATE_STYLE[item.state] || ""}`}>
                    {formatState(item.state)}
                  </span>
                )}
                {item.file && (
                  <code className="discussion-file">{item.file}{item.line ? `:${item.line}` : ""}</code>
                )}
                <span className="muted discussion-time">
                  {item.createdAt ? new Date(item.createdAt).toLocaleString() : ""}
                </span>
              </div>
              {item.body && <p className="discussion-body">{item.body}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
