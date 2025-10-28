
import { supabase } from "../lib/supabaseClient";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:5000/api";



async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession();
  console.log("DEBUG session:", session);
  const headers = { "Content-Type": "application/json" };
 // If we have an access token, send it as Authorization
    if (session?.access_token) {
        console.log("DEBUG sending Authorization Bearer token");
        headers["Authorization"] = `Bearer ${session.access_token}`;
        return headers;
    }

    // DEV fallback: optionally send X-User-Id if you set VITE_DEV_USER_ID for local dev
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

export async function smartAnalyze({ resumeText, jobText, jobTitle }) {
  const r = await fetch(`${API_BASE}/smart/analyze`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({
      resume_text: resumeText,
      job_text: jobText,
      job_title: jobTitle
    })
  });
  let j;
  try { j = await r.json(); } catch { j = {}; }
  if (!r.ok) throw new Error(j.error || `Smart analysis failed (${r.status})`);
  return j;
}
export async function getMe() {
  const r = await fetch(`${API_BASE}/me`, { headers: await authHeaders() });
  if (!r.ok) return null;
  return r.json(); // { user_id, credits }
}

export async function createCheckoutSession() {
  const res = await fetch(`${API_BASE}/pay/checkout`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to start checkout");
  return res.json(); 
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
