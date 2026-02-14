import React, { useRef, useEffect, useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useMe } from "../context/MeContext.jsx";
import { API_BASE, cancelSubscription, reactivateSubscription, getSubscription } from "../services/apiClient.js";

export default function ProfileMenu({ me, onClose, onLogout, onBuyCredits }) {
  const ref = useRef(null);
  const { me: ctxMe, setMe } = useMe();
  const displayMe = ctxMe ?? me ?? {};
  const [editing, setEditing] = useState(false);
  const [avatarFile, setAvatarFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [reactivating, setReactivating] = useState(false);

  useEffect(() => {
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [onClose]);

  // Fetch subscription period_end from Stripe if missing
  useEffect(() => {
    async function refreshSubscription() {
      if (
        displayMe.subscription_status &&
        ["active", "cancelling"].includes(displayMe.subscription_status) &&
        !displayMe.subscription_period_end
      ) {
        try {
          const subData = await getSubscription();
          if (subData.period_end) {
            setMe?.(prev => ({
              ...prev,
              subscription_period_end: subData.period_end,
            }));
          }
        } catch (err) {
          console.warn("Failed to refresh subscription:", err);
        }
      }
    }
    refreshSubscription();
  }, [displayMe.subscription_status, displayMe.subscription_period_end, setMe]);


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

  async function handleCancelSubscription() {
    if (cancelling) return;
    if (!confirm("Are you sure you want to cancel your subscription? You'll keep access until the end of your billing period.")) return;
    setCancelling(true);
    setMsg(null);
    try {
      const result = await cancelSubscription();
      setMe?.(prev => ({
        ...prev,
        subscription_status: "cancelling",
        subscription_period_end: result.period_end || prev.subscription_period_end
      }));
      setMsg("Subscription will cancel at end of billing period");
    } catch (err) {
      setMsg(err.message || "Failed to cancel");
    } finally {
      setCancelling(false);
    }
  }

  async function handleReactivateSubscription() {
    if (reactivating) return;
    setReactivating(true);
    setMsg(null);
    try {
      await reactivateSubscription();
      setMe?.(prev => ({ ...prev, subscription_status: "active" }));
      setMsg("Subscription reactivated!");
    } catch (err) {
      setMsg(err.message || "Failed to reactivate");
    } finally {
      setReactivating(false);
    }
  }

  return (
    <div className="profile-dropdown" ref={ref}>
      <div className="profile-dropdown-inner">
        <div className="profile-header-block">
          <div className="profile-header-top">
            <div className="profile-dropdown-email">{displayMe?.email}</div>
            <button
              type="button"
              aria-label="Close"
              className="profile-close-btn"
              onClick={onClose}
            >
              ✕
            </button>
          </div>
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

        {displayMe.subscription_status === "active" && (
          <div style={{ padding: "10px 12px", background: "#e8f5e9", borderRadius: 8, marginBottom: 8 }}>
            <div style={{ fontSize: 13, color: "#2e7d32", fontWeight: 600 }}>Pro Subscription</div>
            <div style={{ fontSize: 12, color: "#388e3c", marginTop: 2 }}>$5/month • 10 credits</div>
            {displayMe.subscription_period_end && (
              <div style={{ fontSize: 11, color: "#666", marginTop: 4 }}>
                Renews: {new Date(displayMe.subscription_period_end * 1000).toLocaleDateString()}
              </div>
            )}
            <button
              type="button"
              onClick={handleCancelSubscription}
              disabled={cancelling}
              style={{ fontSize: 11, color: "#c62828", background: "none", border: "none", padding: 0, cursor: "pointer", marginTop: 6 }}
            >
              {cancelling ? "Cancelling..." : "Cancel subscription"}
            </button>
          </div>
        )}

        {displayMe.subscription_status === "cancelling" && (
          <div style={{ padding: "10px 12px", background: "#fff3e0", borderRadius: 8, marginBottom: 8 }}>
            <div style={{ fontSize: 13, color: "#e65100", fontWeight: 600 }}>Pro Subscription</div>
            <div style={{ fontSize: 12, color: "#f57c00", marginTop: 2 }}>Cancelling at period end</div>
            <div style={{ fontSize: 11, color: "#666", marginTop: 4 }}>
              Ends: {displayMe.subscription_period_end
                ? new Date(displayMe.subscription_period_end * 1000).toLocaleDateString()
                : "Loading..."}
            </div>
            <button
              type="button"
              onClick={handleReactivateSubscription}
              disabled={reactivating}
              style={{ fontSize: 11, color: "#2e7d32", background: "none", border: "none", padding: 0, cursor: "pointer", marginTop: 6 }}
            >
              {reactivating ? "Reactivating..." : "Reactivate subscription"}
            </button>
          </div>
        )}

        {msg && !editing && (
          <div style={{ fontSize: 12, padding: "4px 8px", color: "#666" }}>{msg}</div>
        )}

        <button type="button" className="profile-item" onClick={handleBuy}>Add Credits</button>
        <button type="button" className="profile-item" onClick={handleLogoff} style={{ color: "#c01818" }}>
          Log off
        </button>
      </div>
    </div>
  );
}