import React, { useRef, useEffect, useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useMe } from "../context/MeContext.jsx";
import { API_BASE } from "../services/apiClient.js";

export default function ProfileMenu({ me, onClose, onLogout, onBuyCredits }) {
  const ref = useRef(null);
  const { me: ctxMe, setMe } = useMe();
  const displayMe = ctxMe ?? me ?? {};
  const [editing, setEditing] = useState(false);
  const [avatarFile, setAvatarFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [onClose]);

  async function handleSave(e) {
    e?.preventDefault();
    if (!avatarFile || saving) return;
    setSaving(true); setMsg(null);
    try {
      const token = (await supabase.auth.getSession()).data?.session?.access_token;
      if (!token) throw new Error("Not authenticated");
      const form = new FormData();
      form.append("avatar", avatarFile);
      const resp = await fetch( `${API_BASE}/profile`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Upload failed");
      setMe?.(prev => ({ ...(prev || {}), ...data }));
      setMsg("Updated");
      setEditing(false);
      setAvatarFile(null);
    } catch (err) {
      setMsg(err.message || "Error");
    } finally {
      setSaving(false);
    }
  }

  function handleEdit() {
    setEditing(true);
    setMsg(null);
  }

  function handleCancel() {
    setEditing(false);
    setAvatarFile(null);
    setMsg(null);
  }

  async function handleLogoff() {
    await supabase.auth.signOut();
    onLogout?.();
  }

  async function handleBuy() {
    onBuyCredits?.();
  }

  return (
    <div className="profile-dropdown" ref={ref}>
      <div className="profile-dropdown-inner">
        <div className="profile-header-block">
          <div className="profile-dropdown-email">{displayMe?.email}</div>
          {displayMe?.avatar_url && !editing && (
            <img
              src={displayMe.avatar_url}
              alt="avatar"
              style={{ width: 64, height: 64, borderRadius: "50%", objectFit: "cover", marginTop: 8 }}
            />
          )}
        </div>

        {editing ? (
          <form onSubmit={handleSave} className="space-y-2" style={{ marginTop: 12 }}>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setAvatarFile(e.target.files?.[0] || null)}
              className="w-full rounded-md border px-2 py-1 text-sm"
            />
            {(avatarFile || displayMe?.avatar_url) && (
              <img
                src={avatarFile ? URL.createObjectURL(avatarFile) : displayMe.avatar_url}
                alt="preview"
                style={{ width: 64, height: 64, borderRadius: "50%", objectFit: "cover" }}
              />
            )}
            {msg && <div style={{ fontSize: 12 }}>{msg}</div>}
            <div className="flex gap-2">
              <button
                disabled={!avatarFile || saving}
                type="submit"
                className="profile-item"
                style={{ background: "var(--primary)", color: "#fff" }}
              >
                {saving ? "Uploading…" : "Save"}
              </button>
              <button type="button" className="profile-item" onClick={handleCancel}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <>
            <button type="button" className="profile-item" onClick={handleEdit}>
              ✎ Change Avatar
            </button>
          </>
        )}

           <div className="credits-gradient">
          <div className="credits-label">Smart Analysis Credits</div>
          <div className="credits-value">{displayMe?.credits ?? 0} credits</div>
        </div>

        <button type="button" className="profile-item" onClick={handleBuy}>Buy Credits</button>
        <button type="button" className="profile-item" onClick={handleLogoff} style={{ color: "#c01818" }}>
          Log off
        </button>
      </div>
    </div>
  );
}