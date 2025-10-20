export default function ResultCard({ data }) {
  if (!data) return null;

  const s = Number(data.score || 0);
  const color = s >= 80 ? "#059669" : s >= 60 ? "#d97706" : "#b91c1c";

  return (
    <div className="result-card">
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <h2 style={{ fontWeight: 800 }}>ATS Resume Score</h2>
        <span style={{ background: color, color:"#fff", padding:"6px 10px", borderRadius: 999 }}>
          {s}%
        </span>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap: 16, marginTop: 14 }}>
        <div>
          <h3 style={{ color:"#065f46", fontWeight: 700, marginBottom: 8 }}>Matched Keywords</h3>
          <div style={{ display:"flex", flexWrap:"wrap", gap: 8 }}>
            {(data.matched_keywords || []).map(k => (
              <span key={k} className="pill pill-ok">{k}</span>
            ))}
          </div>
        </div>
        <div>
          <h3 style={{ color:"#991b1b", fontWeight: 700, marginBottom: 8 }}>Missing Keywords</h3>
          <div style={{ display:"flex", flexWrap:"wrap", gap: 8 }}>
            {(data.missing_keywords || []).map(k => (
              <span key={k} className="pill pill-miss">{k}</span>
            ))}
          </div>
        </div>
      </div>

      <p style={{ marginTop: 12, color:"#64748b" }}>
        Text similarity: {data.breakdown.text_similarity} • Keyword coverage: {data.breakdown.keyword_coverage} • Title bonus: {data.breakdown.title_bonus}
      </p>
    </div>
  );
}
