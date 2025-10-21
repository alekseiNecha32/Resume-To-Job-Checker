import { useCallback, useRef, useState } from "react";
import ResultCard from "../components/ResultCard.jsx";
import { scoreResume, extractTextFromFileAPI } from "../services/apiClient.js";

export default function Analyze() {
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeText, setResumeText] = useState("");
  const [job, setJob] = useState("");
  const [loading, setLoading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [result, setResult] = useState(null);

  // ready when we have extracted text + job text
  const ready = resumeText.trim().length > 0 && job.trim().length > 0;

  // --- File handling (open picker → extract on backend) ---
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
      const text = await extractTextFromFileAPI(file); // backend returns { text }
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
      const data = await scoreResume({
        resume_text: resumeText,
        job_text: job,
        job_title: null,
        isPro: false,
      });
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
      <div className="pointer-events-none absolute inset-0 -z-10
        [background:
          radial-gradient(60%_40%_at_15%_0%,hsl(var(--primary)/.18),transparent),
          radial-gradient(50%_35%_at_85%_0%,hsl(230_89%_65%/.18),transparent),
          radial-gradient(80%_60%_at_50%_100%,hsl(217_91%_60%/.08),transparent),
          linear-gradient(180deg,hsl(var(--background)),hsl(var(--background)))]" />

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
                accept=".pdf,.docx,.txt"   // no .doc (unsupported)
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

          {/* RIGHT: Job Description */}
          <section>
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
            className={`glass-button px-6 py-2 [background-image:var(--gradient-primary)]
              hover:brightness-105 active:scale-[.99]
              ${(!ready || loading || parsing) ? "opacity-60 cursor-not-allowed" : ""}`}
            onClick={handleAnalyze}
            disabled={!ready || loading || parsing}
          >
            {loading ? "Analyzing…" : "Analyze Resume"}
          </button>
        </div>

        {/* Results */}
        <div className="mt-6">
          {result && <ResultCard data={result} />}
        </div>
      </div>
    </div>
  );
}
