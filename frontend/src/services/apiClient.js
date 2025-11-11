
import { supabase } from "../lib/supabaseClient";

// Prefer localhost to keep auth/session cookies on the same site as frontend
export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000/api";



export async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession();
  console.log("DEBUG session:", session);
  const headers = { "Content-Type": "application/json" };
  // If we have an access token, send it as Authorization
  if (session?.access_token) {
    console.log("DEBUG sending Authorization Bearer token");
    headers["Authorization"] = `Bearer ${session.access_token}`;
    return headers;
  }
  const devUid = import.meta.env.VITE_DEV_USER_ID;
  if (devUid) {
    console.log("DEBUG using dev X-User-Id:", devUid);
    headers["X-User-Id"] = devUid;
    return headers;
  }

  console.warn("DEBUG no session found; calling API without auth headers");
  return headers;
}

export async function scoreResume(resumeText, jobText, jobTitle = "") {
  const res = await fetch(`${API_BASE}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resumeText, jobText, jobTitle })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data === "object" ? JSON.stringify(data) : String(data);
    throw new Error(msg || "Score request failed");
  }


  if (typeof data.score === "number") {
    return data;
  }

  const similarity = typeof data.similarity === "number" ? data.similarity : 0;
  return {
    score: Math.round(similarity * 100),
    matches: data.matches ?? [],
    missing_keywords: data.missing_keywords ?? [],
    denominator: data.denominator ?? undefined,
  };
}

// ...existing code...
export async function smartAnalyze({ resumeText, jobText, jobTitle }) {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/smart/analyze`, {
    method: "POST",
    headers,
    body: JSON.stringify({ resume_text: resumeText, job_text: jobText, job_title: jobTitle })
  });

  let analysis;
  try {
    analysis = await res.json();
  } catch {
    analysis = null;
  }
  if (!res.ok) throw new Error((analysis && (analysis.error || analysis.message)) || `Smart analysis failed (${res.status})`);

  const payload = (analysis && (analysis.data || analysis.result || analysis.analysis)) || analysis || null;

  // best-effort refresh of profile so caller can update UI immediately
  let profile = null;
  try {
    profile = await getMe();
  } catch (e) {
    console.debug("getMe after analyze failed", e);
  }

  return { analysis: payload, profile };
}
// ...existing code...


export async function getMe() {
  const headers = await authHeaders();
  const r = await fetch(`${API_BASE}/me`, { method: "GET", headers });
  if (!r.ok) return null;
  return await r.json().catch(() => null);
}

export async function updateProfile(fields) {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/profile`, {
    method: "POST",
    headers,
    body: JSON.stringify(fields || {})
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.error || data?.message || `Update failed (${res.status})`);
  return data;
}

export async function createCheckoutSession({ packId, credits } = {}) {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/payments/checkout`, {
    method: "POST",
    headers,
    body: JSON.stringify({ packId, credits }),
  });
  const text = await res.text();
  let json = {};
  try { json = text ? JSON.parse(text) : {}; } catch (e) { throw new Error("Invalid JSON from checkout"); }
  if (!res.ok) throw new Error(json?.message || json?.error || `Checkout failed (${res.status})`);
  return json; // { url }
}
export async function getProfile() {
  return getMe();
}
export async function scoreResumeFile({ file, job_text, job_title = null, isPro = false }) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("job_text", job_text);
  if (job_title) fd.append("job_title", job_title);
  fd.append("isPro", String(isPro));
  const res = await fetch(`${API_BASE}/extract`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function extractTextFromFileAPI(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/extract`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.text ?? "";
}
