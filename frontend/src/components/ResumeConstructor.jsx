import { useState, useRef } from "react";
import {
    suggestResume,
    extractTextFromFileAPI,
    smartAnalyze,
    getMe,
} from "../services/apiClient";
import { useMe } from "../context/MeContext.jsx";
import ResumePreview from "./ResumePreview";
import SuggestionsPanel from "./SuggestionsPanel";
import TemplateSelectionModal from "./TemplateSelectionModal";
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
    if (lines[2]) contact.push(lines[2]);
    if (lines[1]) contact.push(lines[1]);

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
    const [jobTitle, setJobTitle] = useState("");
    const [resume, setResume] = useState(null);
    const [suggestions, setSuggestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const resumeRef = useRef(null);
    const fileInputRef = useRef(null);
    const [showTemplateModal, setShowTemplateModal] = useState(false);
    const { me, setMe } = useMe();
    const [highlightedIds, setHighlightedIds] = useState([]);
    const [missingKeywords, setMissingKeywords] = useState([]);
    const [criticalGaps, setCriticalGaps] = useState([]);
    const [fitEstimate, setFitEstimate] = useState(null);
    const [presentSkills, setPresentSkills] = useState([]);

    const [extractedChars, setExtractedChars] = useState(0);
    const [extractedWords, setExtractedWords] = useState(0);

    const normalizeExtractedText = (text) => {
        return text
            .replace(/^(%Ï\s*)+/gm, "")
            .replace(/^[•●▪·\-*]+\s+/gm, "");
    };

    const handleFilePick = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setResumeFile(file);
        setError(null);
        setUploading(true);

        // NEW: reset stats until we finish extracting
        setExtractedChars(0);
        setExtractedWords(0);

        try {
            const textRaw = await extractTextFromFileAPI(file);
            const textClean = normalizeExtractedText(textRaw || "");
            setRawResume(textClean);

            // NEW: compute stats
            const chars = textClean.length;
            const words = textClean.trim() ? textClean.trim().split(/\s+/).length : 0;

            setExtractedChars(chars);
            setExtractedWords(words);
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

            // NEW: capture fit estimate & skill buckets
            setFitEstimate(
                analysis?.fit_estimate ??
                analysis?.data?.fit_estimate ??
                null
            );
            setPresentSkills(
                analysis?.present_skills ||
                analysis?.data?.present_skills ||
                []
            );
            setMissingKeywords(
                analysis?.missing_skills ||
                analysis?.missing_keywords ||
                analysis?.data?.missing_skills ||
                analysis?.data?.missing_keywords ||
                []
            );
            setCriticalGaps(
                analysis?.critical_gaps ||
                analysis?.data?.critical_gaps ||
                []
            );

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
            let newId = null;

            if (suggestion.type === "add_bullet") {
                const idx = updated.sections.findIndex((s) => s.id === suggestion.targetSectionId);
                if (idx === -1) return prev;
                newId = `item-${Date.now()}`;
                updated.sections[idx].items.push({
                    id: newId,
                    type: "bullet",
                    text: suggestion.suggestedText,
                });
            }

            if (suggestion.type === "rewrite_bullet") {
                updated.sections = updated.sections.map((section) => ({
                    ...section,
                    items: section.items.map((it) =>
                        it.id === suggestion.targetItemId
                            ? ((newId = it.id), { ...it, text: suggestion.suggestedText })
                            : it
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
                newId = `proj-${Date.now()}`;
                updated.sections[idx].items.push({
                    id: newId,
                    type: "bullet",
                    text: suggestion.suggestedText,
                });
            }

            // highlight the affected item briefly
            if (newId) {
                setHighlightedIds((prevIds) => [...prevIds.filter((id) => id !== newId), newId]);
                setTimeout(() => {
                    setHighlightedIds((prevIds) => prevIds.filter((id) => id !== newId));
                }, 5000);
            }

            return updated;
        });
        setSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id));
    };

    const handleRejectSuggestion = (id) => {
        setSuggestions((prev) => prev.filter((s) => s.id !== id));
    };






    return (
        <div className="ats-layout">
            {/* Main card: upload + job info + Analyze button */}
            <div className="ats-main-card">
                <div className="ats-header-row">
                    <div>
                        <h1 className="ats-heading">Resume Constructor</h1>
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
                            {uploading && (
                                <p className="ats-upload-sub" style={{ marginTop: "0.5rem" }}>
                                    Extracting text…
                                </p>
                            )}

                            {!uploading && !error && extractedChars > 0 && (
                                <p className="ats-upload-sub" style={{ marginTop: "0.5rem" }}>
                                    Extracted {extractedChars.toLocaleString()} characters
                                    {extractedWords ? ` (${extractedWords.toLocaleString()} words)` : ""}
                                    {resumeFile?.name ? ` • ${resumeFile.name}` : ""}
                                </p>
                            )}
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

                    <div className="ats-right">


                        <div className="ats-job-description-wrapper">
                            <label className="ats-label">Job Description</label>
                            <p className="ats-label-help">
                                Paste the job description here... Include requirements, responsibilities, and qualifications.
                            </p>
                            <textarea
                                value={jobText}
                                onChange={(e) => setJobText(e.target.value)}
                                placeholder="Paste job description..."
                                rows={6}
                                className="ats-textarea"
                                disabled={loading || uploading}
                            />

                        </div>
                    </div>
                </div>

                <div className="ats-center-actions">

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
                        {/* CHANGED: use a styled header row + button */}
                        <div className="ats-resume-header">
                            <h2 className="ats-resume-title">Your Resume (Live)</h2>

                            <button
                                type="button"
                                className="ats-btn-secondary ats-download-btn"
                                onClick={() => setShowTemplateModal(true)}
                                disabled={!resume}
                            >
                                Download Resume
                            </button>
                        </div>
                        <div
                            ref={resumeRef}
                            className="live-resume-box"
                            style={{
                                border: "1px solid #ddd",
                                padding: "1rem",
                                borderRadius: "8px",
                                background: "white",
                            }}
                        >
                            <ResumePreview
                                resume={resume}
                                setResume={setResume}
                                highlightedItemIds={highlightedIds}
                            />
                        </div>
                    </div>

                    <div>
                        {/* Fit + Gaps / Matched + Missing */}
                        <div className="ats-match-grid2">
                            <div className="ats-fit-card">
                                <div className="ats-fit-value">
                                    {fitEstimate != null ? `${Math.round(fitEstimate)}%` : "--"}
                                </div>
                                <div>
                                    <div className="ats-fit-label">Fit estimate</div>
                                    <div className="ats-fit-note">
                                        Heuristic only — not an ATS guarantee.
                                    </div>
                                </div>
                            </div>
                            <div className="ats-gap-card">
                                <div className="ats-match-title">Top Critical Gaps</div>
                                <div className="ats-chip-row">
                                    {criticalGaps.length === 0 ? (
                                        <span className="ats-chip ats-chip-muted">None</span>
                                    ) : (
                                        criticalGaps.map((k, i) => (
                                            <span key={i} className="ats-chip ats-chip-amber">{k}</span>
                                        ))
                                    )}
                                </div>
                            </div>
                            <div className="ats-match-card">
                                <div className="ats-match-title">Matched (Expanded)</div>
                                <div className="ats-chip-row">
                                    {presentSkills.length === 0 ? (
                                        <span className="ats-chip ats-chip-muted">None</span>
                                    ) : (
                                        presentSkills.map((k, i) => (
                                            <span key={i} className="ats-chip ats-chip-green">{k}</span>
                                        ))
                                    )}
                                </div>
                            </div>
                            <div className="ats-match-card">
                                <div className="ats-match-title">Missing (Smart)</div>
                                <div className="ats-chip-row">
                                    {missingKeywords.length === 0 ? (
                                        <span className="ats-chip ats-chip-muted">None</span>
                                    ) : (
                                        missingKeywords.map((k, i) => (
                                            <span key={i} className="ats-chip ats-chip-red">{k}</span>
                                        ))
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="ats-suggestions-card">
                            <div className="ats-sugg-header">
                                <h2 className="ats-sugg-title">AI Suggestions</h2>
                                <span className="ats-sugg-note">
                                    Accept to apply instantly to your live resume.
                                </span>
                            </div>
                            <div className="ats-sugg-body">
                                {loading ? (
                                    <div className="ats-sugg-placeholder">Wait for the magic to happen…</div>
                                ) : (
                                    <SuggestionsPanel
                                        suggestions={suggestions}
                                        onAccept={handleAcceptSuggestion}
                                        onReject={handleRejectSuggestion}
                                    />
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {showTemplateModal && (
                <TemplateSelectionModal
                    resume={resume}
                    onClose={() => setShowTemplateModal(false)}
                />
            )}
        </div>
    );
}