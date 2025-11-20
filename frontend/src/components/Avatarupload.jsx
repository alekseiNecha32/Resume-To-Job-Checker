import React, { useState } from "react";
import { supabase } from "../lib/supabaseClient";

export default function AvatarUploader({ onDone }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState(null);

  async function handleUpload() {
    if (!file) return;
    setUploading(true); setMsg(null);
    try {
      const token = (await supabase.auth.getSession()).data?.session?.access_token;
      if (!token) throw new Error("Not authenticated");
      const form = new FormData();
      form.append("avatar", file);
      const resp = await fetch("/api/profile", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Upload failed");
      setMsg("Updated");
      onDone?.(data);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <input type="file" accept="image/*" onChange={e => setFile(e.target.files?.[0] || null)} />
      {file && <img src={URL.createObjectURL(file)} alt="preview" style={{ width: 64, height: 64, borderRadius: "50%", objectFit: "cover", marginTop: 8 }} />}
      <button disabled={!file || uploading} onClick={handleUpload}>
        {uploading ? "Uploading…" : "Save Avatar"}
      </button>
      {msg && <div style={{ fontSize: 12 }}>{msg}</div>}
    </div>
  );
}