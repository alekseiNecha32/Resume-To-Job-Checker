import { useState, useEffect } from "react";
import { smartAnalyze, getMe, createCheckoutSession } from "../services/apiClient";
import AuthBox from "./AuthBox";


export default function SmartSuggestions({ resumeText, jobText, jobTitle, data: initialData = null }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(initialData);
  const [err, setErr] = useState(null);
  const [needAuth, setNeedAuth] = useState(false);
const [legoResume, setLegoResume] = useState(null);       // NEW
const [legoSuggestions, setLegoSuggestions] = useState([]); // NEW
  // If parent passes data, open panel and display it (do NOT call smartAnalyze again)
  useEffect(() => {
    if (initialData) {
      setData(initialData);
      setErr(null);
      setNeedAuth(false);
      setOpen(true);
    }
  }, [initialData]);

  const run = async () => {
    // If caller already provided data, just open the panel
    if (initialData) {
      setOpen(true);
      return;
    }

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
      // smartAnalyze returns { analysis, profile } in your apiClient; support both shapes:
      const payload = res?.analysis ?? res ?? null;
      setData(payload);
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
function parseSuggestions(text = "") {
  try {
    const lines = String(text)
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);

    const items = [];
    let buffer = "";

    for (const l of lines) {
      // New bullet starts with -, •, or numbered lists "1)"/"1."
      if (/^(-|•|\d+[.)])\s+/.test(l)) {
        if (buffer) items.push(buffer.trim());
        buffer = l.replace(/^(-|•|\d+[.)])\s+/, "");
      } else {
        buffer = buffer ? `${buffer} ${l}` : l;
      }
    }
    if (buffer) items.push(buffer.trim());

    return items.length ? items : [String(text || "").trim()];
  } catch {
    return [String(text || "").trim()];
  }
}
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

  const fit = Number(data?.fit_estimate ?? 0);
  const ringStyle = (pct) => ({
    background: `conic-gradient(hsl(var(--primary)) ${Math.min(100, Math.max(0, pct)) * 3.6}deg, rgba(2,6,23,0.08) 0deg)`,
  });

  const colorForSection = (sec = "") => {
    const s = String(sec).toLowerCase();
    if (s.includes("experience")) return "sa-c-indigo";
    if (s.includes("project")) return "sa-c-emerald";
    if (s.includes("summary")) return "sa-c-sky";
    if (s.includes("education")) return "sa-c-purple";
    if (s.includes("skill")) return "sa-c-amber";
    if (s.includes("achievement") || s.includes("impact")) return "sa-c-rose";
    return "sa-c-slate";
  };

  return (
    <div className="w-full flex flex-col items-center mt-6">
      {/* Centered trigger - only used when not provided data from parent */}
      {!initialData && (
        <button
          onClick={run}
          disabled={loading}
          className={`px-4 py-2 rounded-xl bg-indigo-600 text-white hover:opacity-90 disabled:opacity-50`}
        >
          {loading ? "Generating…" : "Smart Suggestions"}
        </button>
      )}

      {/* Panel */}
      {open && (
        <div className="sa-panel relative mx-auto mt-4 w-full max-w-5xl rounded-2xl border shadow-elevated overflow-hidden">
          {/* Header */}
          <div className="sa-header relative">
            <div className="sa-header-bg" />
            <div className="relative z-10 flex items-center justify-between gap-4 p-5">
              <div>
                <div className="text-xs uppercase tracking-wider text-white/80">AI Powered</div>
                <h3 className="text-xl sm:text-2xl font-semibold text-white">Smart Suggestions</h3>
              </div>
              <button
                onClick={closePanel}
                className="sa-close"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>

          <div className="sa-body p-6 sm:p-8 bg-white/70 backdrop-blur">

            {/* States */}
            {err && (
              <div className="mt-4 text-center">
                <p className="text-rose-600 text-sm">{err}</p>

                {err.includes("credits") && (
                  <button
                    onClick={onBuyClick}
                    className="mt-3 inline-flex px-4 py-2 rounded-xl bg-indigo-600 text-white shadow hover:opacity-90"
                  >
                    Buy 7 Smart Analyses — $7
                  </button>
                )}
              </div>
            )}

            {!err && loading && (
              <div className="mt-6 flex flex-col items-center gap-3 text-sm opacity-80">
                <div className="sa-spinner" aria-hidden />
                <div>Analyzing your resume against the job description…</div>
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
              <div className="mt-4 grid gap-6 md:grid-cols-2">
                {/* Fit estimate ring */}
                <div className="sa-card flex items-center gap-5">
                  <div className="sa-ring" style={ringStyle(fit)}>
                    <div className="sa-ring-inner">
                      <div className="text-2xl font-bold">{fit}%</div>
                      <div className="text-[10px] uppercase tracking-wide opacity-60">Fit</div>
                    </div>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <div className="font-semibold text-foreground">Fit estimate</div>
                    <div className="text-xs opacity-70">Heuristic only — not an ATS guarantee.</div>
                  </div>
                </div>

                {/* Critical gaps */}
                <div className="sa-card">
                  <div className="sa-card-title">Top Critical Gaps</div>
                  <div className="sa-pill-cloud sa-pill-amber">
                    {(data.critical_gaps || []).map((k) => (
                      <span key={`cg-${k}`} className="sa-pill">{k}</span>
                    ))}
                  </div>
                </div>

                {/* Present */}
                <div className="sa-card">
                  <div className="sa-card-title">Matched (Expanded)</div>
                  <div className="sa-pill-cloud sa-pill-green">
                    {(data.present_skills || []).map((k) => (
                      <span key={`ps-${k}`} className="sa-pill">{k}</span>
                    ))}
                  </div>
                </div>

                {/* Missing */}
                <div className="sa-card">
                  <div className="sa-card-title">Missing (Smart)</div>
                  <div className="sa-pill-cloud sa-pill-rose">
                    {(data.missing_skills || []).map((k) => (
                      <span key={`ms-${k}`} className="sa-pill">{k}</span>
                    ))}
                  </div>
                </div>

            {/* Personal suggestions */}
                <div className="md:col-span-2 sa-card">
                  <div className="sa-card-title flex items-center justify-between">
                    <span>Personal Suggestions</span>
                    {data.personal_suggestions && (
                      <button
                        className="text-xs px-2 py-1 rounded bg-indigo-600 text-white hover:opacity-90"
                        onClick={() => {
                          const items = parseSuggestions(data.personal_suggestions);
                          const txt = Array.isArray(items) ? items.join("\n") : String(items || "");
                          navigator.clipboard.writeText(txt).catch(() => {});
                        }}
                        aria-label="Copy suggestions"
                      >
                        Copy
                      </button>
                    )}
                  </div>

                  {data.personal_suggestions ? (
                    <ul className="mt-2 space-y-2">
                      {parseSuggestions(data.personal_suggestions).map((item, idx) => (
                        <li
                          key={`psg-${idx}`}
                          className="flex items-start gap-2 rounded-lg border bg-white/70 px-3 py-2"
                        >
                          <span
                            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white text-xs mt-0.5"
                            aria-hidden
                          >
                            •
                          </span>
                          <span className="text-sm leading-relaxed">{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : data.personal_suggestions_error ? (
                    <div className="text-xs p-2 rounded bg-amber-100 text-amber-800">
                      {data.personal_suggestions_error}
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      Suggestions will appear here after Smart Analysis.
                    </div>
                  )}
                </div>
                  


              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


   {/* Section suggestions (MiniLM) */}
                {/* <div className="md:col-span-2 sa-card">
                  <div className="sa-card-title">Section Suggestions</div>
                  <ul className="sa-suggest-list">
                    {Object.entries(data.section_suggestions || {}).flatMap(([sec, arr]) =>
                      (arr || []).map((s, i) => {
                        const color = colorForSection(sec);
                        return (
                          <li key={`${sec}-${i}`} className={`sa-suggest-item ${color}`}>
                            <span className="sa-dot" aria-hidden />
                            <span className="sa-badge" aria-label={`${sec} badge`}>{sec}</span>
                            <span className="sa-suggest-text">{s}</span>
                          </li>
                        );
                      })
                    )}
                  </ul>
                </div> */}