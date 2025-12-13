import React, { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { API_BASE, authHeaders } from "../services/apiClient";
import { useMe } from "../context/MeContext.jsx";
import { useNavigate } from "react-router-dom"; // NEW

export default function AuthModal({ onClose, onSuccess }) {
  const [mode, setMode] = useState("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);
  const [fullName, setFullName] = useState("");
  const { setMe } = useMe();

  const nav = useNavigate(); // NEW

  async function handleSignup() {
    setLoading(true); setMsg(null);
    try {
      const redirectBase = import.meta.env.VITE_PUBLIC_SITE_URL || window.location.origin;

      const redirectTo = `${redirectBase}/auth/callback`;

      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: redirectTo,
          data: fullName ? { full_name: fullName } : {},
        },
      });
      if (error) throw error;

      if (!data?.session) {
        setMsg("Wait for confirmation email to confirm your email.");
        onClose?.();                 // close modal so callback page is visible
        nav("/auth/callback");       // show the pending-confirmation page
        return;
      }

      const session = (await supabase.auth.getSession()).data?.session;
      if (session) {
        setMe({ email: session.user.email, avatar_url: null, credits: null });
        try {
          let resp = await fetch(`${API_BASE}/me`, {
            headers: { Authorization: `Bearer ${session.access_token}` },
          });
          if (resp.status === 404) {
            await fetch(`${API_BASE}/auth/create_profile`, {
              method: "POST",
              headers: { Authorization: `Bearer ${session.access_token}` },
            }).catch(() => { });
            resp = await fetch(`${API_BASE}/me`, {
              headers: { Authorization: `Bearer ${session.access_token}` },
            });
          }
          if (resp.ok) setMe(await resp.json());
        } catch { }
      }

      onSuccess?.();
    } catch (e) {
      setMsg(e.message || "Sign up failed");
    } finally {
      setLoading(false);
    }
  }
  async function handleLogin(e) {
    e.preventDefault();
    setMsg(null);
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      const user = data?.user;
      // Gate login until email confirmed
      if (user && !user.email_confirmed_at) {
        setMsg("Please confirm your email from the link we sent before logging in.");
        await supabase.auth.signOut();
        return;
      }
      onSuccess?.();
    } catch (e) {
      setMsg(e.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rtjc-modal-backdrop" onMouseDown={() => onClose?.()}>
      <div className="rtjc-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="rtjc-modal-header">
          <h3>{mode === "signup" ? "Create account" : "Welcome back"}</h3>
          <button className="modal-close" onClick={() => onClose?.()}>×</button>
        </div>

        <div className="rtjc-tabs">
          <button className={mode === "login" ? "tab active" : "tab"} onClick={() => setMode("login")}>Log In</button>
          <button className={mode === "signup" ? "tab active" : "tab"} onClick={() => setMode("signup")}>Sign Up</button>
        </div>

        {/* single body block */}
        <div className="rtjc-body">
          {mode === "signup" && (
            <label className="field">
              <div className="label">Full name</div>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" />
            </label>
          )}

          <label className="field">
            <div className="label">Email</div>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </label>

          <label className="field">
            <div className="label">Password</div>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </label>

          {msg && <div className="rtjc-msg">{msg}</div>}

          <div className="rtjc-actions-row">
            {mode === "signup" ? (
              <button className="btn btn-primary" onClick={handleSignup} disabled={loading}>
                {loading ? "Signing up…" : "Sign up"}
              </button>
            ) : (
              <button className="btn btn-primary" onClick={handleLogin} disabled={loading}>
                {loading ? "Signing in…" : "Log in"}
              </button>
            )}
            <button className="btn btn-ghost" onClick={() => onClose?.()}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  )
};