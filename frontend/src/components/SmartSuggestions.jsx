import { useState } from "react";
import { smartAnalyze, getMe, createCheckoutSession } from "../services/apiClient";
import AuthBox from "./AuthBox";

export default function SmartSuggestions({ resumeText, jobText, jobTitle }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [needAuth, setNeedAuth] = useState(false);

  const run = async () => {
    if (loading) return; 
    if (!resumeText || !jobText) {
      setOpen(true);
      setErr("Please provide resume text and job description first.");
      setData(null);
      return;
    }

    setOpen(true);
    setErr(null);
    setData(null);
    setLoading(true);

    try {
      // auth check
      const me = await getMe();
      if (!me) {
        setNeedAuth(true);
        setLoading(false);
        return;
      }

      // call analysis
      const res = await smartAnalyze({ resumeText, jobText, jobTitle });
      setData(res);
    } catch (e) {
      const msg = String(e?.message || "Something went wrong");

      if (msg.toLowerCase().includes("sign in")) {
        setNeedAuth(true);
        setData(null);
      } else if (
        msg.toLowerCase().includes("no credits") ||
        msg.toLowerCase().includes("insufficient")
      ) {
        setErr("You’re out of credits.");
        setData(null);
      } else {
        setErr(msg);
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const onBuyClick = async () => {
    try {
      const { url } = await createCheckoutSession();
      if (url) window.location.href = url;
    } catch (e) {
      alert(e?.message || "Checkout failed");
    }
  };

  const closePanel = () => {
    setOpen(false);
    setErr(null);
    // keep data to let users copy bullets after close/open if you prefer:
    // setData(null);
    setNeedAuth(false);
  };

  return (
    <div className="w-full flex flex-col items-center mt-6">
      {/* Centered trigger */}
      <button
        onClick={run}
        disabled={loading}
        className={`px-4 py-2 rounded-xl bg-indigo-600 text-white hover:opacity-90 disabled:opacity-50`}
      >
        {loading ? "Generating…" : "AI suggestions"}
      </button>

      {/* Panel */}
      {open && (
        <div className="relative mx-auto mt-4 w-full max-w-4xl rounded-2xl border bg-white/70 backdrop-blur p-6 shadow-sm">
          <h3 className="text-center font-semibold">Smart Suggestions</h3>
          <button
            onClick={closePanel}
            className="absolute right-4 top-4 text-sm px-2 py-1 rounded-md border hover:bg-gray-50"
          >
            Close
          </button>

          {/* States */}
          {err && (
            <div className="mt-4 text-center">
              <p className="text-rose-600 text-sm">{err}</p>

              {err.includes("credits") && (
                <button
                  onClick={onBuyClick}
                  className="mt-3 inline-flex px-3 py-2 rounded-lg bg-indigo-600 text-white"
                >
                  Buy 7 Smart Analyses — $7
                </button>
              )}
            </div>
          )}

          {!err && loading && (
            <div className="mt-4 text-center animate-pulse text-sm opacity-70">
              Analyzing your resume against the job description…
            </div>
          )}

          {needAuth && (
            <div className="mt-4">
              <AuthBox
                onDone={async () => {
                  setNeedAuth(false);
                  const me = await getMe();
                  if (me) await run();
                }}
              />
            </div>
          )}

          {/* Results */}
          {data && !needAuth && !loading && (
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {/* Fit */}
              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60">Fit Estimate</div>
                <div className="text-3xl font-bold">{data.fit_estimate}%</div>
                <div className="text-xs opacity-60">
                  Heuristic only — not an ATS guarantee.
                </div>
              </div>

              {/* Critical gaps */}
              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Top Critical Gaps</div>
                <div className="flex flex-wrap gap-2">
                  {(data.critical_gaps || []).map((k) => (
                    <span
                      key={`cg-${k}`}
                      className="px-2 py-1 text-xs border rounded-full bg-amber-50"
                    >
                      {k}
                    </span>
                  ))}
                </div>
              </div>

              {/* Present */}
              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Matched (Expanded)</div>
                <div className="flex flex-wrap gap-2">
                  {(data.present_skills || []).map((k) => (
                    <span
                      key={`ps-${k}`}
                      className="px-2 py-1 text-xs border rounded-full bg-emerald-50"
                    >
                      {k}
                    </span>
                  ))}
                </div>
              </div>

              {/* Missing */}
              <div className="p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Missing (Smart)</div>
                <div className="flex flex-wrap gap-2">
                  {(data.missing_skills || []).map((k) => (
                    <span
                      key={`ms-${k}`}
                      className="px-2 py-1 text-xs border rounded-full bg-rose-50"
                    >
                      {k}
                    </span>
                  ))}
                </div>
              </div>

              {/* Section suggestions */}
              <div className="md:col-span-2 p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Personal Suggestions</div>
                <ul className="list-disc pl-5 text-sm space-y-1">
                  {Object.entries(data.section_suggestions || {}).flatMap(
                    ([sec, arr]) =>
                      (arr || []).map((s, i) => (
                        <li key={`${sec}-${i}`}>
                          <b>{sec}:</b> {s}
                        </li>
                      ))
                  )}
                </ul>
              </div>

              {/* Bullets */}
              <div className="md:col-span-2 p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Ready-to-use Bullets</div>
                <ul className="list-disc pl-5 text-sm space-y-1">
                  {(data.ready_bullets || []).map((b, i) => (
                    <li key={`rb-${i}`} className="flex items-start gap-2">
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

              {/* Rewrite hints */}
              <div className="md:col-span-2 p-3 rounded-xl border">
                <div className="text-sm opacity-60 mb-1">Rewrite Hints</div>
                <ul className="list-disc pl-5 text-sm space-y-1">
                  {(data.rewrite_hints || []).map((h, i) => (
                    <li key={`rh-${i}`}>{h}</li>
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
