/** Client-side checks for cached report schema freshness. */

export function isStaleReport(data, aiStatus) {
  if (!data) return true;
  if (!data.fileChanges?.length && (data.pr?.changedFiles ?? 0) > 0) return true;
  if (!("aiProvider" in data)) return true;
  if (!("commits" in data)) return true;
  if (data.commits?.length > 0 && !("files" in data.commits[0])) return true;
  if (!("discussionSummarySource" in data)) return true;
  if (!("prOverviewSource" in data)) return true;
  if (data.fileChanges?.some((f) => !("summarySource" in f))) return true;
  if (aiStatus?.configured) {
    const hasAiFileSummary = data.fileChanges?.some((f) => f.summarySource === "ai");
    if (!hasAiFileSummary || !data.aiSummariesUsed) return true;
    if (data.fileChanges?.some((f) => f.summarySource === "ai" && !f.summarizedAt)) return true;
  }
  return false;
}
