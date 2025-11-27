export default function ResultCard({ data }) {
  if (!data || typeof data !== "object") return null;

  const score = Number.isFinite(data.score) ? data.score : 0;
  const matched = Array.isArray(data.matches) ? data.matches : (data.matched_keywords ?? []);
  const missing = Array.isArray(data.missing_keywords) ? data.missing_keywords : [];

  const color =
    score >= 80 ? "#059669" : 
      score >= 60 ? "#d97706" : 
        "#b91c1c";

  return (
    <div className="glass-card p-5 mt-6">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontWeight: 800 }}>ATS Resume Score</h2>
        <span style={{ background: color, color: "#fff", padding: "6px 10px", borderRadius: 999 }}>
          {score}%
        </span>
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