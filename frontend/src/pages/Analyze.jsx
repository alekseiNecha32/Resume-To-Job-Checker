import { useCallback, useRef, useState, useEffect } from "react";
import ResultCard from "../components/ResultCard.jsx";
import {
  scoreResume,
  extractTextFromFileAPI,
  getMe,
  createCheckoutSession,
  smartAnalyze,
} from "../services/apiClient.js";
import SmartSuggestions from "../components/SmartSuggestions.jsx";
import { supabase } from "../lib/supabaseClient.js";
import CreditsModal from "../components/CreditsModal.jsx";

export default function Analyze() {
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeText, setResumeText] = useState("");
  const [job, setJob] = useState("");
  const [loading, setLoading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [result, setResult] = useState(null);
  const [jobTitle, setJobTitle] = useState("");

  // profile / credits
  const [me, setMe] = useState(null);
  const [loadingMe, setLoadingMe] = useState(true);

  // smart analysis state
  const [smartResult, setSmartResult] = useState(null);
  const [runningSmart, setRunningSmart] = useState(false);

  // fetch profile
  useEffect(() => {
    let mounted = true;
    async function loadMe() {
      try {
        const u = await getMe();
        if (mounted) setMe(u);
      } catch {
        if (mounted) setMe(null);
      } finally {
        if (mounted) setLoadingMe(false);
      }
    }
    loadMe();

    // subscribe to auth changes so UI updates automatically after login/logout
    const { data: sub } = supabase.auth.onAuthStateChange(() => {
      // re-fetch profile when auth state changes
      loadMe();
    });
    return () => {
      mounted = false;
      sub?.subscription?.unsubscribe?.();
    };
  }, []);

  const [showCreditsModal, setShowCreditsModal] = useState(false);

  function handleBuyCredits() {
    setShowCreditsModal(true);
  }

  // Run smart analysis on click. Backend should handle decrementing credits.
  async function handleRunSmartAnalysis() {
    if (runningSmart) return;
    if (!resumeText.trim() || !job.trim()) {
      alert("Provide resume text and job description first.");
      return;
    }
    if (!me) {
      alert("Please log in to run Smart Analysis.");
      return;
    }
    if ((me.credits ?? 0) <= 0) {
      alert("You don't have credits. Buy credits to use Smart Analysis.");
      return;
    }

    setRunningSmart(true);
    setSmartResult(null);
    try {
      const data = await smartAnalyze({ resumeText, jobText: job, jobTitle });
      setSmartResult(data);
      // refresh profile to pick up new credits balance from server
      try {
        const refreshed = await getMe();
        setMe(refreshed);
      } catch (e) {
        // ignore refresh error
      }
    } catch (e) {
      alert(e.message || "Smart analysis failed.");
    } finally {
      setRunningSmart(false);
    }
  }

  const ready = resumeText.trim().length > 0 && job.trim().length > 0;

  const inputRef = useRef(null);
  const onBrowseClick = () => inputRef.current?.click();

  const handleFileChosen = useCallback(async (file) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      alert("File is larger than 5MB.");
      return;
    }
    setResumeFile(file);
    setResult(null);
    setParsing(true);
    try {
      const text = await extractTextFromFileAPI(file);
      setResumeText(text || "");
    } catch (e) {
      alert(e.message || "Could not extract text.");
      setResumeText("");
    } finally {
      setParsing(false);
    }
  }, []);

  const onDrop = (e) => {
    e.preventDefault();
    handleFileChosen(e.dataTransfer.files?.[0]);
  };

  async function handleAnalyze() {
    if (!ready || loading || parsing) return;
    setLoading(true);
    setResult(null);
    try {
      const data = await scoreResume(resumeText, job);
      setResult(data);
    } catch (e) {
      alert(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen p-6 overflow-hidden">
      {/* background */}
      <div
        className="pointer-events-none absolute inset-0 -z-10
        [background:
          radial-gradient(60%_40%_at_15%_0%,hsl(var(--primary)/.18),transparent),
          radial-gradient(50%_35%_at_85%_0%,hsl(230_89%_65%/.18),transparent),
          radial-gradient(80%_60%_at_50%_100%,hsl(217_91%_60%/.08),transparent),
          linear-gradient(180deg,hsl(var(--background)),hsl(var(--background)))]"
      />

      <div className="mx-auto max-w-6xl glass-card p-6 sm:p-8">
        <header className="mb-6">
          <h1 className="text-3xl font-bold">Resume ATS Checker</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Optimize your resume to match job requirements and pass ATS systems.
          </p>
        </header>

        <div className="grid gap-6 md:grid-cols-2">
          {/* LEFT: Upload */}
          <section>
            <div className="text-sm font-semibold">Upload Your Resume</div>
            <div className="text-xs text-muted-foreground mb-2">
              PDF, DOCX or TXT (max 5MB)
            </div>

            <div
              className="dropzone h-[260px] relative cursor-pointer"
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              onClick={onBrowseClick}
              role="button"
              aria-label="Upload resume"
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => handleFileChosen(e.target.files?.[0])}
              />
              <div>
                <div className="text-4xl mb-2">⬆️</div>
                <div className="text-sm font-medium">
                  {parsing ? "Reading file…" : "Click to upload or drag and drop"}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {resumeFile ? `Selected: ${resumeFile.name}` : "PDF, DOCX or TXT (max 5MB)"}
                </div>
                {resumeText && !parsing && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    Extracted {resumeText.length.toLocaleString()} characters
                  </div>
                )}
              </div>
            </div>
          </section>

          {/*Job Description */}
          <section>
            <div className="text-sm font-semibold mb-2">Job Title</div>
            <input
              type="text"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              placeholder="e.g., React Frontend Developer"
              className="w-full rounded-2xl border border-border bg-white/60 dark:bg-white/5 p-3 mb-4 focus:outline-none focus:ring-2 focus:ring-ring"
            />

            <div className="text-sm font-semibold">Job Description</div>
            <div className="text-xs text-muted-foreground mb-2">
              Paste the job description here… Include requirements, responsibilities, and qualifications.
            </div>
            <textarea
              className="w-full h-[260px] resize-none rounded-2xl border border-border bg-white/60 dark:bg-white/5 p-4 focus:outline-none focus:ring-2 focus:ring-ring"
              value={job}
              onChange={(e) => setJob(e.target.value)}
              placeholder="Paste the job description here..."
            />
          </section>
        </div>

        {/* Action */}
        <div className="mt-8 flex justify-center">
          <button
            className={`px-4 py-2 rounded-xl bg-indigo-600 text-white hover:opacity-90 disabled:opacity-50`}
            onClick={handleAnalyze}
            disabled={!ready || loading || parsing}
          >
            {loading ? "Analyzing…" : "Analyze Resume"}
          </button>
        </div>

        {/* Results */}
        <div className="mt-6">
          {result && <ResultCard data={result} />}

          {result?.matchedKeywords && result?.missingKeywords && (
            <div className="mt-8 space-y-6">
              <h3 className="text-lg font-semibold">Keyword Analysis</h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Matched */}
                <div className="p-4 rounded-xl border bg-green-50 border-green-200">
                  <h4 className="font-medium text-green-800 mb-2">
                    ✅ Matched Keywords ({result.matchedKeywords.length})
                  </h4>

                  {result.matchedKeywords.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {result.matchedKeywords.map((word) => (
                        <span
                          key={`m-${word}`}
                          className="px-2 py-1 text-sm rounded-full bg-green-200 text-green-800"
                        >
                          {word}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">No matched keywords found.</p>
                  )}
                </div>

                {/* Missing */}
                <div className="p-4 rounded-xl border bg-rose-50 border-rose-200">
                  <h4 className="font-medium text-rose-800 mb-2">
                    ⚠️ Missing Keywords ({result.missingKeywords.length})
                  </h4>

                  {result.missingKeywords.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {result.missingKeywords.map((word) => (
                        <span
                          key={`x-${word}`}
                          className="px-2 py-1 text-sm rounded-full bg-rose-200 text-rose-900"
                        >
                          {word}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">None missing — great match!</p>
                  )}
                </div>
              </div>

              <div className="flex justify-center mt-8 w-full">
                <div className="w-full max-w-4xl">
                  {loadingMe ? (
                    <div className="p-6 rounded-xl border bg-white/50 text-center">Checking account…</div>
                  ) : !me ? (
                    <div className="p-6 rounded-xl border bg-white/50 text-center">
                      <h3 className="font-semibold">Smart Analysis — Login required</h3>
                      <p className="text-sm text-muted-foreground">Please log in or sign up to access Smart Analysis.</p>
                    </div>
                  ) : (me.credits ?? 0) <= 0 ? (
                    <div className="p-6 rounded-xl border bg-white/50 text-center">
                      <h3 className="font-semibold">Smart Analysis — Locked</h3>
                      <p className="text-sm text-muted-foreground">You have {me.credits ?? 0} credits. Buy credits to see AI suggestions.</p>
                      <div className="mt-3">
                        <button className="px-4 py-2 rounded-xl bg-indigo-600 text-white" onClick={handleBuyCredits}>
                          Buy Credits
                        </button>
                          {showCreditsModal && (
                            <CreditsModal onClose={() => setShowCreditsModal(false)} />
                          )}
                      </div>
                    </div>
                  ) : smartResult ? (
                    <SmartSuggestions data={smartResult} resumeText={resumeText} jobText={job} jobTitle={jobTitle} />
                  ) : (
                    <div className="p-6 rounded-xl border bg-white/50 text-center">
                      <h3 className="font-semibold">Smart Analysis</h3>
                      <p className="text-sm text-muted-foreground">Use Smart Analysis to get AI suggestions (cost: 1 credit).</p>
                      <div className="mt-3 flex items-center justify-center gap-3">
                        <button
                          className="px-4 py-2 rounded-xl bg-indigo-600 text-white"
                          onClick={handleRunSmartAnalysis}
                          disabled={!ready || runningSmart}
                        >
                          {runningSmart ? "Running…" : "Run Smart Analysis"}
                        </button>
                        <div className="text-sm text-muted-foreground">Credits: {(me.credits ?? 0)}</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )};