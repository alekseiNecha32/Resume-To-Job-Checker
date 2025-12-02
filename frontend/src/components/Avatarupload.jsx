import React, { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { apiCallWithAuth } from "../services/apiClient";  // ✅ Import from apiClient

export default function AvatarUploader({ onDone }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState(null);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setMsg(null);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;
      if (!token) throw new Error("Not authenticated");
      
      const form = new FormData();
      form.append("avatar", file);
      
      // ✅ Use apiCall directly (don't use apiCallWithAuth which adds JSON header)
      const resp = await apiCall("/profile", {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },  // ✅ Add auth manually
        body: form  // ✅ FormData - no Content-Type header needed
      });
      
      const uploadData = await resp.json();
      if (!resp.ok) throw new Error(uploadData.error || "Upload failed");
      
      console.log("✅ Avatar uploaded:", uploadData);
      setMsg("Updated");
      onDone?.(uploadData);
    } catch (e) {
      console.error("❌ Upload error:", e);
      setMsg(e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <input 
        type="file" 
        accept="image/*" 
        onChange={e => setFile(e.target.files?.[0] || null)} 
      />
      {file && (
        <img 
          src={URL.createObjectURL(file)} 
          alt="preview" 
          style={{ width: 64, height: 64, borderRadius: "50%", objectFit: "cover", marginTop: 8 }} 
        />
      )}
      <button disabled={!file || uploading} onClick={handleUpload}>
        {uploading ? "Uploading…" : "Save Avatar"}
      </button>
      {msg && <div style={{ fontSize: 12 }}>{msg}</div>}
    </div>
  );
}