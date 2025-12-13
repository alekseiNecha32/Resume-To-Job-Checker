export default function SuggestionsPanel({
  suggestions,
  onAccept,
  onReject,
}) {
  if (!suggestions || suggestions.length === 0) {
    return <p>No AI suggestions yet. Run analysis or update your resume.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {suggestions.map((s) => (
        <SuggestionCard
          key={s.id}
          suggestion={s}
          onAccept={() => onAccept(s)}
          onReject={() => onReject(s.id)}
        />
      ))}
    </div>
  );
}

function SuggestionCard({ suggestion, onAccept, onReject }) {
  const label =
    suggestion.type === "add_bullet"
      ? "Add bullet"
      : suggestion.type === "rewrite_bullet"
      ? "Rewrite bullet"
      : "Project idea";

  return (
    <div
      style={{
        border: "1px solid #ddd",
        borderRadius: "8px",
        padding: "0.75rem",
        background: "#fafafa",
      }}
    >
      <div style={{ fontSize: "0.8rem", opacity: 0.7 }}>{label}</div>
      <h4 style={{ margin: "0.2rem 0 0.4rem" }}>{suggestion.title}</h4>

      {suggestion.type === "rewrite_bullet" && (
        <>
          <p style={{ fontSize: "0.8rem", marginBottom: "0.2rem" }}>
            <strong>Original:</strong> {suggestion.originalText}
          </p>
          <p style={{ fontSize: "0.8rem", marginBottom: "0.4rem" }}>
            <strong>Suggested:</strong> {suggestion.suggestedText}
          </p>
        </>
      )}

      {suggestion.type !== "rewrite_bullet" && (
        <p style={{ fontSize: "0.85rem", marginBottom: "0.4rem" }}>
          {suggestion.suggestedText}
        </p>
      )}

      {suggestion.reason && (
        <p style={{ fontSize: "0.75rem", opacity: 0.7 }}>
          Why: {suggestion.reason}
        </p>
      )}

      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
         <button className="ats-btn-accept" onClick={onAccept}>Accept</button>
        <button className="ats-btn-reject" onClick={onReject}>Reject</button>
      </div>
    </div>
  );
}
