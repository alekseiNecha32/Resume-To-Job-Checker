import React, { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { API_BASE } from "../services/apiClient";

export default function AuthModal({ onClose, onSuccess }) {
  const [mode, setMode] = useState("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  async function callCreateProfile(token) {
    if (!fullName.trim()) return;
    try {
      await fetch(`${API_BASE}/auth/create_profile`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ full_name: fullName.trim() }),
      });
    } catch (e) {
      console.warn("create_profile failed", e);
    }
  }

  async function handleSignup() {
    setLoading(true);
    setMsg(null);
    try {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: { full_name: fullName } },
      });
      if (error) throw error;

      try {
        await supabase.auth.signInWithPassword({ email, password });
      } catch (e) {
        // email confirmation might be required; proceed
      }

      const token = (await supabase.auth.getSession()).data?.session?.access_token;
      if (token) await callCreateProfile(token);

      setMsg("Account created. Check your inbox if confirmation is required.");
      setLoading(false);
      if (onSuccess) onSuccess();
    } catch (e) {
      setMsg(e.message || String(e));
      setLoading(false);
    }
  }

  async function handleLogin() {
    setLoading(true);
    setMsg(null);
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      setLoading(false);
      if (onSuccess) onSuccess();
    } catch (e) {
      setMsg(e.message || String(e));
      setLoading(false);
    }
  }

  return (
    <div className="rtjc-modal-backdrop" onMouseDown={() => onClose?.()}>
      <div className="rtjc-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="rtjc-modal-header">
          <h3>{mode === "signup" ? "Create account" : "Welcome back"}</h3>
          <button className="modal-close" onClick={() => onClose?.()}>
            ×
          </button>
        </div>

        <div className="rtjc-tabs">
          <button className={mode === "login" ? "tab active" : "tab"} onClick={() => setMode("login")}>
            Log In
          </button>
          <button className={mode === "signup" ? "tab active" : "tab"} onClick={() => setMode("signup")}>
            Sign Up
          </button>
        </div>

        <div className="rtjc-body">
          {mode === "signup" && (
            <label className="field">
              <div className="label">Full name</div>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Jane Doe" />
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

            <button className="btn btn-ghost" onClick={() => onClose?.()}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}