import { useState } from "react";
import { smartAnalyze } from "../services/apiClient";

export default function SmartSuggestions({ resumeText, jobText, jobTitle }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  const run = async () => {
    if (!resumeText || !jobText) {
      setErr("Please provide resume text and job description first.");
      setOpen(true);
      return;
    }
    setErr(null);
    setOpen(true);
    setLoading(true);
    try {
      const res = await smartAnalyze({ resumeText, jobText, jobTitle });
      setData(res);
    } catch (e) {
      setErr(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full flex flex-col items-center mt-4">
      <button
        onClick={run}
        className="block mx-auto px-4 py-2 rounded-xl bg-indigo-600 text-white hover:opacity-90 disabled:opacity-50"
        disabled={loading}
      >
        {loading ? "Generating…" : "AI suggestions"}
      </button>

      {open && (
        <div className="relative mx-auto mt-4 w-full max-w-3xl rounded-2xl border bg-white/60 backdrop-blur p-6 shadow-sm">
          <h3 className="text-center font-semibold">Smart Suggestions</h3>
          <button
            onClick={() => setOpen(false)}
            className="absolute right-4 top-4 text-sm px-2 py-1 rounded-md border hover:bg-gray-50"
          >
            Close
          </button>

          {err && <p className="text-rose-600 text-sm mt-3 text-center">{err}</p>}

          {!err && loading && (
            <div className="animate-pulse text-sm opacity-70 mt-3 text-center">
              Analyzing your resume against the job description…
            </div>
          )}

          {data && (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60">Fit Estimate</div>
                <div className="text-3xl font-bold">{data.fit_estimate}%</div>
                <div className="text-xs opacity-60">
                  Heuristic only — not an ATS guarantee.
                </div>
              </div>

              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Top Critical Gaps</div>
                <div className="flex flex-wrap gap-2">
                  {data.critical_gaps?.map((k) => (
                    <span key={k} className="px-2 py-1 text-xs border rounded-full bg-amber-50">
                      {k}
                    </span>
                  ))}
                </div>
              </div>

              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Matched (Expanded)</div>
                <div className="flex flex-wrap gap-2">
                  {data.present_skills?.map((k) => (
                    <span key={k} className="px-2 py-1 text-xs border rounded-full bg-emerald-50">
                      {k}
                    </span>
                  ))}
                </div>
              </div>

              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Missing (Smart)</div>
                <div className="flex flex-wrap gap-2">
                  {data.missing_skills?.map((k) => (
                    <span key={k} className="px-2 py-1 text-xs border rounded-full bg-rose-50">
                      {k}
                    </span>
                  ))}
                </div>
              </div>

              <div className="md:col-span-2 p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Personal Suggestions</div>
                <ul className="list-disc pl-5 text-sm space-y-1">
                  {Object.entries(data.section_suggestions || {}).flatMap(
                    ([sec, arr]) => (arr || []).map((s, i) => (
                      <li key={sec + i}>
                        <b>{sec}:</b> {s}
                      </li>
                    ))
                  )}
                </ul>
              </div>

              <div className="md:col-span-2 p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Ready-to-use Bullets</div>
                <ul className="list-disc pl-5 text-sm space-y-1">
                  {(data.ready_bullets || []).map((b, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span>{b}</span>
                      <button
                        className="ml-auto text-xs px-2 py-0.5 rounded border hover:bg-gray-50"
                        onClick={() => navigator.clipboard.writeText(b)}
                        title="Copy"
                      >
                        Copy
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="md:col-span-2 p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Rewrite Hints</div>
                <ul className="list-disc pl-5 text-sm space-y-1">
                  {(data.rewrite_hints || []).map((h, i) => (
                    <li key={i}>{h}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
