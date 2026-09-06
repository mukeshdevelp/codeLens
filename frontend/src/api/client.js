/** HTTP client for CodeLens backend API (proxied via Vite or nginx). */

/**
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function request(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const d = err.detail;
    let message = "Request failed";
    if (typeof d === "string") message = d;
    else if (Array.isArray(d)) {
      message = d.map((x) => (typeof x === "string" ? x : x.msg || JSON.stringify(x))).join("; ");
    } else if (d && typeof d === "object" && d.message) {
      message = d.errors?.length ? `${d.message}: ${d.errors.join("; ")}` : d.message;
    } else if (d) message = JSON.stringify(d);
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  repos: () => request("/api/repos"),
  pulls: (owner, repo) => request(`/api/repos/${owner}/${repo}/pulls`),
  analyze: (owner, repo, number, opts = {}) => {
    const params = new URLSearchParams();
    if (opts.postGithubComment) params.set("post_github_comment", "true");
    if (opts.syncGithubCheck) params.set("sync_github_check", "true");
    const qs = params.toString();
    return request(
      `/api/repos/${owner}/${repo}/pulls/${number}/analyze${qs ? `?${qs}` : ""}`,
      { method: "POST" }
    );
  },
  report: (owner, repo, number) =>
    request(`/api/repos/${owner}/${repo}/pulls/${number}/report`),
  aiStatus: () => request("/api/ai/status"),
  githubStatus: () => request("/api/github/status"),
  postSummaryToGithub: (owner, repo, number, force = false) =>
    request(
      `/api/github/repos/${owner}/${repo}/pulls/${number}/post-summary?force=${force}`,
      { method: "POST" }
    ),
  embedReport: (owner, repo, number, token) =>
    request(`/api/github/embed/${owner}/${repo}/pulls/${number}/report?token=${encodeURIComponent(token)}`),
  prActions: (owner, repo, number) =>
    request(`/api/repos/${owner}/${repo}/pulls/${number}/actions`),
  approvePr: (owner, repo, number) =>
    request(`/api/repos/${owner}/${repo}/pulls/${number}/approve`, { method: "POST" }),
  mergePr: (owner, repo, number, mergeMethod = "merge") =>
    request(
      `/api/repos/${owner}/${repo}/pulls/${number}/merge?merge_method=${encodeURIComponent(mergeMethod)}`,
      { method: "POST" }
    ),
};

/** URL to start GitHub OAuth login flow. */
export function loginUrl() {
  return "/auth/github";
}
