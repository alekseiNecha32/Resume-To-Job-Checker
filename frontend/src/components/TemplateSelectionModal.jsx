import React, { useEffect, useState } from "react";
import { getResumeTemplates, downloadStyledResume } from "../services/apiClient.js";

const TEMPLATE_ICONS = {
  classic: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="7" y1="8" x2="17" y2="8" />
      <line x1="7" y1="12" x2="17" y2="12" />
      <line x1="7" y1="16" x2="13" y2="16" />
    </svg>
  ),
  modern: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <rect x="6" y="6" width="5" height="3" rx="0.5" />
      <line x1="6" y1="12" x2="18" y2="12" />
      <line x1="6" y1="15" x2="18" y2="15" />
      <line x1="6" y1="18" x2="14" y2="18" />
    </svg>
  ),
  compact: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-8 h-8">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="6" y1="7" x2="18" y2="7" />
      <line x1="6" y1="10" x2="18" y2="10" />
      <line x1="6" y1="13" x2="18" y2="13" />
      <line x1="6" y1="16" x2="18" y2="16" />
      <line x1="6" y1="19" x2="12" y2="19" />
    </svg>
  ),
};

export default function TemplateSelectionModal({ resume, onClose }) {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState("classic");
  const [downloading, setDownloading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose?.();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    async function fetchTemplates() {
      try {
        const data = await getResumeTemplates();
        setTemplates(data);
        if (data.length > 0) {
          setSelectedTemplate(data[0].id);
        }
      } catch (err) {
        console.error("Failed to load templates:", err);
        // Use default templates if fetch fails
        setTemplates([
          { id: "classic", name: "Classic", description: "Traditional single-column layout with clean typography." },
          { id: "modern", name: "Modern", description: "Clean sans-serif design with subtle styling." },
          { id: "compact", name: "Compact", description: "Dense layout maximizing content." },
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetchTemplates();
  }, []);

  async function handleDownload() {
    if (!resume || downloading) return;

    setDownloading(true);
    setError("");

    try {
      const blob = await downloadStyledResume(resume, selectedTemplate);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `resume_${selectedTemplate}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      onClose?.();
    } catch (err) {
      console.error("Download failed:", err);
      setError(err.message || "Failed to download resume");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/40"
      role="dialog"
      aria-modal="true"
      onMouseDown={onClose}
    >
      <div
        className="w-full max-w-2xl mx-4 rounded-2xl bg-white shadow-xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6">
          <div>
            <h2 className="text-xl font-semibold">Download Resume</h2>
            <p className="mt-1 text-sm text-gray-500">
              Choose a template style for your ATS-optimized resume
            </p>
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 rounded-full p-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          ) : (
            <>
              {/* Template Cards */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => setSelectedTemplate(template.id)}
                    className={`relative flex flex-col items-center p-4 rounded-xl border-2 transition-all ${
                      selectedTemplate === template.id
                        ? "border-indigo-600 bg-indigo-50"
                        : "border-gray-200 hover:border-gray-300 bg-white"
                    }`}
                  >
                    {/* Selection indicator */}
                    {selectedTemplate === template.id && (
                      <div className="absolute top-2 right-2 w-5 h-5 bg-indigo-600 rounded-full flex items-center justify-center">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    )}

                    {/* Template icon */}
                    <div
                      className={`mb-3 p-3 rounded-lg ${
                        selectedTemplate === template.id ? "bg-indigo-100 text-indigo-600" : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {TEMPLATE_ICONS[template.id] || TEMPLATE_ICONS.classic}
                    </div>

                    {/* Template name */}
                    <span
                      className={`font-medium ${
                        selectedTemplate === template.id ? "text-indigo-600" : "text-gray-900"
                      }`}
                    >
                      {template.name}
                    </span>

                    {/* Template description */}
                    <span className="mt-1 text-xs text-gray-500 text-center line-clamp-2">
                      {template.description}
                    </span>
                  </button>
                ))}
              </div>

              {/* Template details */}
              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <div className="text-sm text-gray-600">
                  {templates.find((t) => t.id === selectedTemplate)?.description}
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Format: DOCX (Microsoft Word) - ATS compatible
                </div>
              </div>

              {/* Error message */}
              {error && (
                <div className="mb-4 rounded-md bg-red-50 border border-red-100 p-3 text-sm text-red-800">
                  {error}
                </div>
              )}

              {/* Download button */}
              <button
                onClick={handleDownload}
                disabled={downloading || !resume}
                className="w-full rounded-full bg-indigo-600 text-white py-3 font-semibold disabled:opacity-60 hover:bg-indigo-700 transition-colors flex items-center justify-center gap-2"
              >
                {downloading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>Generating...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                      />
                    </svg>
                    <span>Download Resume</span>
                  </>
                )}
              </button>

              <div className="mt-4 text-center">
                <button onClick={onClose} className="text-sm text-gray-600 hover:underline">
                  Cancel
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
