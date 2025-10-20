import { useState, useEffect } from "react";

export default function TextPanel({ label, hint, placeholder, value, onChange }) {
  const [count, setCount] = useState(value.length);
  useEffect(() => setCount(value.length), [value]);

  return (
    <div className="text-panel">
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{label}</div>
      <div style={{ color:"#64748b", fontSize: 14, marginBottom: 8 }}>{hint}</div>
      <textarea
        rows="14"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <div style={{ color:"#64748b", fontSize: 12, marginTop: 6 }}>{count} characters</div>
    </div>
  );
}
