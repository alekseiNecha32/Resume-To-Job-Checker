import { useState, useRef } from "react";
import {
    suggestResume,
    extractTextFromFileAPI,
    downloadOptimizedResumeDocx,
    smartAnalyze,
    getMe,
} from "../services/apiClient";
import { useMe } from "../context/MeContext.jsx";
import ResumePreview from "./ResumePreview";
import SuggestionsPanel from "./SuggestionsPanel";
import "../styles/resume.css";


const cleanLine = (line) => {
    if (!line) return "";
    let t = line.trim();

    // remove any leading "%Ï" sequences
    t = t.replace(/^(%.\s*)+/g, ""); // e.g. "%Ï "

    // remove normal bullet characters (•, ●, -, *, etc.) + space
    t = t.replace(/^[•●▪·\-*]+\s+/g, "");

    return t.trim();
};

const parseResume = (text) => {
    const rawLines = text
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean);

    const lines = rawLines.map(cleanLine);
    if (!lines.length) {
        return { name: "", title: "", contact: [], sections: [] };
    }

    const name = lines[0] || "";
    const contact = [];
    if (lines[2]) contact.push(lines[2]); // Cincinnati, OH ...
    if (lines[1]) contact.push(lines[1]); // GitHub / LinkedIn

    const bodyLines = lines.slice(3);

    const sections = [];
    let current = {
        id: "section-0",
        title: "",
        items: [],
    };

    const push = () => {
        if (current.title && current.items.length) sections.push(current);
    };

    for (const line of bodyLines) {
        // ALL CAPS = section headers (PROFESSIONAL SUMMARY, TECHNICAL SKILLS, etc.)
        if (/^[A-Z][A-Z\s&]+$/.test(line) && line.length < 60) {
            push();
            current = {
                id: line.toLowerCase().replace(/\s+/g, "-"),
                title: line,
                items: [],
            };
        } else {
            current.items.push({
                id: `it-${current.items.length}-${Date.now()}`,
                type: "bullet",
                text: cleanLine(line),
            });
        }
    }
    push();

    return {
        name,
        title: "",      // if later you want "Software Engineer" subtitle, put it here
        contact,
        sections,
    };
};






export default function ResumeConstructor() {
    const [rawResume, setRawResume] = useState("");
    const [resumeFile, setResumeFile] = useState(null);
    const [jobText, setJobText] = useState("");
    const [jobTitle, setJobTitle] = useState("");        // NEW
    const [resume, setResume] = useState(null);
    const [suggestions, setSuggestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const resumeRef = useRef(null);
    const fileInputRef = useRef(null);                   // NEW
    const [downloading, setDownloading] = useState(false); // ⭐ YOU MUST ADD THIS
    const { me, setMe } = useMe();

    const normalizeExtractedText = (text) => {
        return text
            .replace(/^(%Ï\s*)+/gm, "")          // remove %Ï at line start
            .replace(/^[•●▪·\-*]+\s+/gm, "");     // remove bullet chars at line start
    };

    const handleFilePick = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setResumeFile(file);                 // <-- store selected file
        setError(null);
        setUploading(true);
        try {
            const textRaw = await extractTextFromFileAPI(file);
            const textClean = normalizeExtractedText(textRaw || "");
            setRawResume(textClean);
        } catch (err) {
            setError(err?.message || "Failed to extract text from file.");
        } finally {
            setUploading(false);
        }
    };
    const handleAnalyze = async () => {
        if (loading) return;
        if (!resumeFile && !rawResume.trim()) return;
        setLoading(true);
        setError(null);
        try {
            // Charge credit + run smart analysis (backend deducts)
            const { analysis, profile: refreshedProfile } = await smartAnalyze({
                resumeText: rawResume,
                jobText,
                jobTitle,
            });

            // Refresh credits/profile
            if (refreshedProfile) {
                setMe(refreshedProfile);
            } else {
                const latest = await getMe().catch(() => null);
                if (latest) setMe(latest);
            }

            // Build resume view
            const structured = parseResume(rawResume);
            setResume(structured);

            // Use suggestions from smartAnalyze if present; fallback to suggestResume
            const suggs =
                analysis?.lego_suggestions ||
                analysis?.suggestions ||
                analysis?.data?.lego_suggestions ||
                [];
            const finalSuggestions =
                suggs && suggs.length
                    ? suggs
                    : await suggestResume({ resume: structured, jobText });
            setSuggestions(finalSuggestions);
        } catch (err) {
            console.error(err);
            setError(err.message || "Something went wrong while analyzing.");
        } finally {
            setLoading(false);
        }
    };


    const handleAcceptSuggestion = (suggestion) => {
        if (!resume) return;
        setResume((prev) => {
            if (!prev) return prev;
            const updated = { ...prev, sections: prev.sections.map((s) => ({ ...s, items: [...s.items] })) };

            if (suggestion.type === "add_bullet") {
                const idx = updated.sections.findIndex((s) => s.id === suggestion.targetSectionId);
                if (idx === -1) return prev;
                updated.sections[idx].items.push({
                    id: `item-${Date.now()}`,
                    type: "bullet",
                    text: suggestion.suggestedText,
                });
            }

            if (suggestion.type === "rewrite_bullet") {
                updated.sections = updated.sections.map((section) => ({
                    ...section,
                    items: section.items.map((it) =>
                        it.id === suggestion.targetItemId ? { ...it, text: suggestion.suggestedText } : it
                    ),
                }));
            }

            if (suggestion.type === "project_idea") {
                let idx = updated.sections.findIndex((s) => s.id === suggestion.targetSectionId);
                if (idx === -1) {
                    updated.sections = [
                        ...updated.sections,
                        { id: suggestion.targetSectionId, title: "Projects", items: [] },
                    ];
                    idx = updated.sections.length - 1;
                }
                updated.sections[idx].items.push({
                    id: `proj-${Date.now()}`,
                    type: "bullet",
                    text: suggestion.suggestedText,
                });
            }
            return updated;
        });
        setSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id));
    };

    const handleRejectSuggestion = (id) => {
        setSuggestions((prev) => prev.filter((s) => s.id !== id));
    };


    const handleDownloadDocx = async () => {
        if (!resume) return; // nothing yet

        try {
            setDownloading(true);
            const blob = await downloadOptimizedResumeDocx(resume);

            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "optimized_resume.docx";
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error(err);
            setError(err.message || "Failed to download Word file.");
        } finally {
            setDownloading(false);
        }
    };






    return (
        <div className="ats-layout">
            {/* Main card: upload + job info + Analyze button */}
            <div className="ats-main-card">
                <div className="ats-header-row">
                    <div>
                        <h1 className="ats-heading">Resume ATS Checker</h1>
                        <p className="ats-subtext">
                            Optimize your resume to match job requirements and pass ATS systems.
                        </p>
                    </div>
                </div>

                <div className="ats-grid">
                    {/* LEFT: Upload area */}
                    <div className="ats-left">
                        <label className="ats-label">
                            Upload Your Resume
                            <span className="ats-label-muted"> PDF, DOCX or TXT (max 5MB)</span>
                        </label>

                        <div
                            className="ats-upload-box"
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <div className="ats-upload-icon">⬆</div>
                            <p className="ats-upload-title">
                                Click to upload or drag and drop
                            </p>
                            <p className="ats-upload-sub">
                                PDF, DOCX or TXT (max 5MB)
                            </p>

                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf,.doc,.docx,.txt"
                                onChange={handleFilePick}
                                disabled={uploading || loading}
                                className="ats-file-input-hidden"
                            />
                        </div>
                    </div>

                    {/* RIGHT: Job title + description */}
                    <div className="ats-right">
                        {/* <div className="ats-job-title-wrapper">
              <label className="ats-label">Job Title</label>
              <input
                type="text"
                className="ats-input"
                placeholder="e.g., React Frontend Developer"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
              />
            </div> */}

                        <div className="ats-job-description-wrapper">
                            <label className="ats-label">Job Description</label>
                            <p className="ats-label-help">
                                Paste the job description here... Include requirements, responsibilities, and qualifications.
                            </p>
                            <textarea
                                value={jobText}
                                onChange={(e) => setJobText(e.target.value)}
                                placeholder="(Optional) Paste job description..."
                                rows={4}
                                style={{ width: "100%", marginBottom: "0.5rem" }}
                            />
                        </div>
                    </div>
                </div>

                <div className="ats-center-actions">
                    {/* <button
                    onClick={handleAnalyze}
                    disabled={loading || !resumeFile}   // <-- must have file
                >
                    {loading ? "Analyzing..." : "Run Smart Suggestions"}
                </button> */}
                    {uploading && <span className="ats-status">Extracting text from resume…</span>}
                    {error && <span className="ats-error">{error}</span>}
                </div>

                {/* Smart Analysis card at bottom */}
                <div className="ats-smart-card">
                    <div className="ats-smart-text">
                        <h2 className="ats-smart-title">Smart Analysis</h2>
                        <p className="ats-smart-sub">
                            Use Smart Analysis to get AI suggestions (cost: 1 credit).
                        </p>
                    </div>
                    <div className="ats-smart-actions">
                        <button
                            className="ats-btn-secondary"
                            onClick={handleAnalyze}
                            disabled={
                                loading ||
                                uploading ||
                                (!resumeFile && !rawResume.trim()) ||
                                (me?.credits ?? 0) <= 0
                            }
                        >
                            {loading ? "Analyzing..." : "Run Smart Analysis"}
                        </button>
                        <div className="ats-status">
                            Credits: {me?.credits ?? 0}
                        </div>
                    </div>
                </div>
            </div>

            {resume && (
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "1.2fr 1fr",
                        gap: "1rem",
                        alignItems: "flex-start",
                    }}
                >
                    <div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <h2>Your Resume (Live)</h2>
                            <button
                                onClick={handleDownloadDocx}
                                disabled={downloading || !resume}
                            >
                                {downloading ? "Downloading..." : "Download DOCX"}
                            </button>
                        </div>
                        <div
                            ref={resumeRef}
                            style={{
                                border: "1px solid #ddd",
                                padding: "1rem",
                                borderRadius: "8px",
                                background: "white",
                            }}
                        >
                            <ResumePreview resume={resume} setResume={setResume} />
                        </div>
                    </div>

                    <div>
                        <h2>AI Suggestions</h2>
                        <SuggestionsPanel
                            suggestions={suggestions}
                            onAccept={handleAcceptSuggestion}
                            onReject={handleRejectSuggestion}
                        />
                    </div>

                    <pre
                        style={{
                            whiteSpace: "pre-wrap",
                            fontSize: "12px",
                            marginTop: "20px",
                        }}
                    >
                    </pre>
                </div>
            )}
        </div>
    );
}