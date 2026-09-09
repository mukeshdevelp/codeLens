/** Shared file status labels and CSS classes for walkthrough components. */

export const STATUS_LABEL = {
  added: "A",
  removed: "D",
  modified: "M",
  renamed: "R",
  changed: "C",
};

export function statusClass(status) {
  return `file-status file-status-${status || "modified"}`;
}
