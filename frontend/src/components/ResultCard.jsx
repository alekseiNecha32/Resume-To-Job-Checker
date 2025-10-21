// frontend/src/components/ResultCard.jsx
export default function ResultCard({ data }) {
  if (!data || typeof data !== "object") return null;

  // Safe reads with defaults
  const score = Number.isFinite(data.score) ? data.score : 0;
  const matched = Array.isArray(data.matches) ? data.matches : (data.matched_keywords ?? []);
  const missing = Array.isArray(data.missing_keywords) ? data.missing_keywords : [];

  // Optional breakdown values (if your backend starts sending them later)
  const textSimilarity = data?.breakdown?.text_similarity;
  const keywordCoverage = data?.breakdown?.keyword_coverage;

  // Simple color badge like you had
  const color =
    score >= 80 ? "#059669" :   // green
      score >= 60 ? "#d97706" :   // amber
        "#b91c1c";    // red

  return (
    <div className="glass-card p-5 mt-6">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontWeight: 800 }}>ATS Resume Score</h2>
        <span style={{ background: color, color: "#fff", padding: "6px 10px", borderRadius: 999 }}>
          {score}%
        </span>
      </div>

      {/* Matched keywords (uses data.matches when available) */}
      {matched.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 14 }}>
          <div>
            <p className="mt-2 text-sm text-muted-foreground">
              {matched.length} matched keywords • {data.score}% overall match
            </p>
            <h3 style={{ color: "#065f46", fontWeight: 700, marginBottom: 8 }}>Matched Keywords</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {matched.map((k, i) => (
                <span key={`${k}-${i}`} className="pill pill-ok">{k}</span>
              ))}
            </div>
          </div>

          {/* Missing only if backend provides it */}
          {missing.length > 0 && (
            <div>
              <h3 style={{ color: "#991b1b", fontWeight: 700, marginBottom: 8 }}>Missing Keywords</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {missing.map((k, i) => (
                  <span key={`${k}-${i}`} className="pill pill-miss">{k}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {(textSimilarity != null || keywordCoverage != null) && (
        <p style={{ marginTop: 12, color: "#64748b" }}>
          {textSimilarity != null && <>Text similarity: {textSimilarity} • </>}
          {keywordCoverage != null && <>Keyword coverage: {keywordCoverage}</>}
        </p>
      )}
    </div>
  );
}
