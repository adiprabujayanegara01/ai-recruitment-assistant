const BASE = "/api/v1";
let token = localStorage.getItem("token");

export const setToken = (t) => { token = t; t ? localStorage.setItem("token", t) : localStorage.removeItem("token"); };
export const hasToken = () => !!token;

async function req(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.json) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  const res = await fetch(BASE + path, { ...opts, headers });
  if (res.status === 401 && token && !path.startsWith("/auth/login")) { setToken(null); window.location.href = "/login"; }
  if (!res.ok) {
    let msg = `Permintaan gagal (${res.status})`;
    try { const d = await res.json(); msg = typeof d.detail === "string" ? d.detail : d.detail?.[0]?.msg || msg; } catch {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return opts.blob ? res.blob() : res.json();
}

export const api = {
  login: (email, password) => req("/auth/login", { method: "POST", json: { email, password } }),
  me: () => req("/auth/me"),
  jobs: () => req("/jobs"),
  job: (id) => req(`/jobs/${id}`),
  createJob: (title, description) => req("/jobs", { method: "POST", json: { title, description } }),
  deleteJob: (id) => req(`/jobs/${id}`, { method: "DELETE" }),
  ranking: (id) => req(`/jobs/${id}/ranking`),
  candidates: (params = {}) => req("/candidates?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v))),
  candidate: (id) => req(`/candidates/${id}`),
  deleteCandidate: (id) => req(`/candidates/${id}`, { method: "DELETE" }),
  upload: (file, jobId) => {
    const f = new FormData(); f.append("file", file); if (jobId) f.append("job_id", jobId);
    return req("/candidates/upload", { method: "POST", body: f });
  },
  analyze: (candidate_id, job_id) => req("/matching/analyze", { method: "POST", json: { candidate_id, job_id } }),
  batch: (job_id) => req("/matching/batch", { method: "POST", json: { job_id } }),
  result: (id) => req(`/matching/${id}`),
  results: (params = {}) => req("/matching?" + new URLSearchParams(params)),
  report: (id) => req(`/reports/${id}`, { method: "POST", blob: true }),
  knowledge: () => req("/knowledge"),
  addKnowledge: (title, category, text) => {
    const f = new FormData(); f.append("title", title); f.append("category", category); f.append("text", text);
    return req("/knowledge", { method: "POST", body: f });
  },
  deleteKnowledge: (id) => req(`/knowledge/${id}`, { method: "DELETE" }),
  ask: (question) => req("/knowledge/ask", { method: "POST", json: { question } }),
  metrics: () => req("/admin/metrics"),
  audit: () => req("/admin/audit?limit=40"),
};
