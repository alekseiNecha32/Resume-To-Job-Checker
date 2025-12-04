// ...existing code...
export default function ResultCard({ data }) {
  if (!data || typeof data !== "object") return null;

  const score = Number.isFinite(data.score) ? data.score : 0;
  // Raw arrays from backend (support both shapes)
  const rawMatched = Array.isArray(data.matches) ? data.matches : (data.matched_keywords ?? []);
  const rawMissing = Array.isArray(data.missing_keywords) ? data.missing_keywords : [];

  const color =
    score >= 80 ? "#059669" :
    score >= 60 ? "#d97706" :
    "#b91c1c";

  const STOP_PHRASES = [
    "but not limited", "not limited", "related", "degree", "computer",
    "excellent", "strong", "knowledge", "experience", "requirements",
    "responsibilities", "skills", "technical", "science"
  ];
  const STOP_WORDS = new Set([
    "and","or","the","a","an","to","for","of","in","on","with","by","as","at",
    "not","limited","but","related","degree","computer","etc"
  ]);

  const isTechnical = (s) => {
    const t = String(s).toLowerCase().trim();
    if (!t) return false;
    if (t.length < 2) return false;
    if (STOP_PHRASES.some(p => t.includes(p))) return false;
    const tokens = t.split(/\s+/);
    const meaningful = tokens.filter(x => !STOP_WORDS.has(x));
    if (!meaningful.length) return false;
    if (!/[a-z0-9]/i.test(t)) return false;
    return true;
  };

  const dedupe = (arr) => Array.from(new Set(arr.map(x => String(x).trim()).filter(Boolean)));

  // Cleaned arrays for rendering
  const matched = dedupe(rawMatched).filter(isTechnical);
  const missing = dedupe(rawMissing).filter(isTechnical);

  return (
    <div className="glass-card p-5 mt-6">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontWeight: 800 }}>ATS Resume Score</h2>
        {/* <span style={{ background: color, color: "#fff", padding: "6px 10px", borderRadius: 999 }}>{score}%</span> */}
      </div>

      {(matched.length > 0 || missing.length > 0) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 20 }}>
          {matched.length > 0 && (
            <div>
              <h3 style={{ color: "#059669", fontWeight: 700, marginBottom: 12 }}>Matched Keywords</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {matched.map((kw, i) => (
                  <span
                    key={i}
                    style={{
                      background: "#dcfce7",
                      color: "#166534",
                      padding: "4px 10px",
                      borderRadius: 6,
                      fontSize: 14,
                      fontWeight: 600,
                      border: "1px solid #86efac"
                    }}
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {missing.length > 0 && (
            <div>
              <h3 style={{ color: "#dc2626", fontWeight: 700, marginBottom: 12 }}>Missing Keywords</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {missing.map((kw, i) => (
                  <span
                    key={i}
                    style={{
                      background: "#fee2e2",
                      color: "#7f1d1d",
                      padding: "4px 10px",
                      borderRadius: 6,
                      fontSize: 14,
                      fontWeight: 600,
                      border: "1px solid #fca5a5"
                    }}
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
