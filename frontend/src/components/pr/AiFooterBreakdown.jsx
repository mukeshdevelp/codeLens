export default function AiFooterBreakdown({ report }) {
  if (!report?.aiProvider) return null;
  const b = report.aiSummaryBreakdown || {};
  const parts = [];
  if (b.executiveSummary === "ai") parts.push("executive");
  if (b.prOverview === "ai") parts.push("PR overview");
  if (b.discussionSummary === "ai") parts.push("discussion");
  if (b.fileChanges > 0) parts.push(`${b.fileChanges} file${b.fileChanges !== 1 ? "s" : ""}`);
  return (
    <>
      {" "}· AI ({report.aiProvider}): {parts.length ? parts.join(", ") : "none"}
      {" "}({report.aiSummariesUsed} total)
    </>
  );
}
