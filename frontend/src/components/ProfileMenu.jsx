
import React, { useEffect, useRef, useState } from "react";
import { useMe } from "../context/MeContext.jsx";
import { createCheckoutSession, updateProfile } from "../services/apiClient";
import { supabase } from "../lib/supabaseClient";

export default function ProfileMenu({ me, onClose, onLogout, onBuyCredits }) {
  const ref = useRef(null);
  const { me: ctxMe, setMe } = useMe();
  const displayMe = ctxMe ?? me ?? {};
  const [editing, setEditing] = useState(false);
  const [fullNameDraft, setFullNameDraft] = useState(displayMe?.full_name || "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  // No local profile state here; rely solely on MeContext so values stay consistent

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [onClose]);

  async function handleBuy() {
    // prefer parent-provided handler (opens CreditsModal)
    if (onBuyCredits) {
      try {
        onBuyCredits();
      } finally {
        // close the dropdown after triggering modal
        onClose?.();
      }
      return;
    }

    try {
      const sess = await createCheckoutSession();
      if (sess?.url) {
        window.location.href = sess.url;
      } else if (sess?.id) {
        window.location.href = `/pay/checkout/${sess.id}`;
      }
    } catch (e) {
      console.error("checkout error", e);
      alert("Could not start checkout.");
    } finally {
      onClose?.();
    }
  }

  function handleEdit() {
    setFullNameDraft(displayMe?.full_name || "");
    setEditing(true);
  }

  async function handleSave(e) {
    e?.preventDefault();
    if (saving) return;
    setSaving(true);
    setMsg(null);
    try {
      const updated = await updateProfile({ full_name: fullNameDraft });
      setMe?.(prev => ({ ...(prev || {}), ...updated }));
      setMsg("Saved");
      setEditing(false);
      // broadcast so any other listeners update
      try { window.dispatchEvent(new CustomEvent("profile_updated", { detail: updated })); } catch {}
    } catch (err) {
      setMsg(err.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setEditing(false);
    setMsg(null);
  }

  async function handleLogoff() {
    if (onLogout) {
      await onLogout();
    } else {
      try {
        await supabase.auth.signOut();
      } catch {}
    }
    onClose?.();
    window.location.reload();
  }


 return (
    <div ref={ref} className="profile-dropdown" role="menu" aria-label="Profile menu">
      <div className="profile-dropdown-header">
        {!editing ? (
          <>
            <div className="profile-dropdown-name">
              {displayMe?.full_name || (displayMe?.email ? displayMe.email.split("@")[0] : "")}
            </div>
            <div className="profile-dropdown-email">{displayMe?.email}</div>
          </>
        ) : (
          <form onSubmit={handleSave} className="space-y-2">
            <input
              type="text"
              autoFocus
              className="w-full rounded-md border px-2 py-1 text-sm"
              placeholder="Full name"
              value={fullNameDraft}
              onChange={(e) => setFullNameDraft(e.target.value)}
              maxLength={80}
            />
            <div className="flex gap-2">
              <button disabled={saving} type="submit" className="flex-1 profile-item" style={{marginTop:0, background:"var(--primary)", color:"white"}}>
                {saving ? "Saving…" : "Save"}
              </button>
              <button type="button" onClick={handleCancel} className="flex-1 profile-item" style={{marginTop:0}}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      <div className="profile-credits-card">
        <div className="credits-title">Smart Analysis Credits</div>
        <div className="credits-value">{(displayMe?.credits ?? 0) + " credits"}</div>
      </div>

      {!editing && <button type="button" className="profile-item" onClick={handleEdit}>✎ Edit Profile</button>}
      <button type="button" className="profile-item" onClick={handleBuy} aria-label="Buy credits">💳 Buy Credits</button>
      <button type="button" className="profile-item danger" onClick={handleLogoff}>⤫ Log off</button>
      {msg && !editing && <div className="mt-2 text-xs text-center opacity-70">{msg}</div>}
    </div>
  );
}