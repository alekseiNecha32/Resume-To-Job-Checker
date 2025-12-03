
import { supabase } from "../lib/supabaseClient";

const DEFAULT_BACKEND = "https://resume-tojob.onrender.com/api";
export const API_BASE = (import.meta.env.VITE_API_URL?.startsWith("http") ? import.meta.env.VITE_API_URL : DEFAULT_BACKEND);


export async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession();
  const headers = {};
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }
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

  let profile = null;
  try {
    profile = await getMe();
  } catch (e) {
    console.debug("getMe after analyze failed", e);
  }

  return { analysis: payload, profile };
}


export async function getMe() {
  const headers = await authHeaders();
  const r = await fetch(`${API_BASE}/me`, { headers });
  if (r.status === 404) return null; // tolerate missing during deploy
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await r.json() : {};
  if (!r.ok) throw new Error(data?.error || `me failed (${r.status})`);
  return data;
}


export async function updateProfile({ avatarFile } = {}) {
  const headers = await authHeaders();
  const fd = new FormData();
  if (avatarFile) fd.append("avatar", avatarFile);

  const res = await fetch(`${API_BASE}/profile`, {
    method: "POST",
    headers, // no Content-Type; let browser set multipart/form-data
    body: fd
  });

  const text = await res.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(data?.error || `Update failed (${res.status})`);
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
  return json;
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


export async function apiCall(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  console.log(`📡 Calling: ${url}`);
  return fetch(url, options);
}

export async function apiCallWithAuth(endpoint, token, options = {}) {
  return apiCall(endpoint, {
    ...options,
    headers: {
      ...options.headers,
      "Authorization": `Bearer ${token}`
    }
  });
}