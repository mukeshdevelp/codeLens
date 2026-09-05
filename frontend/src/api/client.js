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
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  me: () => request("/auth/me"),
  logout: () => request("/auth/logout", { method: "POST" }),
  repos: () => request("/api/repos"),
  pulls: (owner, repo) => request(`/api/repos/${owner}/${repo}/pulls`),
  analyze: (owner, repo, number) =>
    request(`/api/repos/${owner}/${repo}/pulls/${number}/analyze`, { method: "POST" }),
  report: (owner, repo, number) =>
    request(`/api/repos/${owner}/${repo}/pulls/${number}/report`),
};

export function loginUrl() {
  return "/auth/github";
}
