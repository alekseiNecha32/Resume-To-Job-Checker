const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:5000/api"; // add /api only if your backend uses it

export async function scoreResume(payload) {
  const res = await fetch(`${API_BASE}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
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

/** 🔹 Extract just the text from an uploaded file. Backend should return { text: "<plain text>" } */
export async function extractTextFromFileAPI(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/extract`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.text ?? "";
}
