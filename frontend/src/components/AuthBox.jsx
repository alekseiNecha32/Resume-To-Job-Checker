import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useNavigate } from "react-router-dom"; // NEW

export default function AuthBox({ onDone }) {
  const [email, setEmail] = useState("");
  const [password, setPwd] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const nav = useNavigate()

  async function signIn() {
    setErr("");
    setInfo("");
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    setLoading(false);
    if (error) setErr(error.message);
    else onDone?.();
  }


  async function signUp() {
    setErr("");
    setInfo("");
    setLoading(true);

    const redirectBase = import.meta.env.VITE_PUBLIC_SITE_URL || window.location.origin;
    const redirectTo = `${redirectBase}/auth/callback`;

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: redirectTo },
    });

    setLoading(false);

    if (error) {
      setErr(error.message);
      return;
    }

    // Email confirmations ON => session is null, show message + go to callback page
    if (!data?.session) {
      // NEW: enable auto-login polling on /auth/callback
      try {
        sessionStorage.setItem(
          "pendingSignup",
          JSON.stringify({ email, password, ts: Date.now() })
        );
      } catch {}

      setInfo("Wait for confirmation email to confirm your email.");
      nav("/auth/callback");
      return;
    }

    onDone?.();
  }

  return (
    <div className="p-4 rounded-xl border bg-white/70 space-y-3">
      <h2 className="text-lg font-semibold">Sign in or create account</h2>
      <input
        className="w-full p-2 rounded border"
        placeholder="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        className="w-full p-2 rounded border"
        type="password"
        placeholder="password"
        value={password}
        onChange={(e) => setPwd(e.target.value)}
      />
      {err && <div className="text-rose-600 text-sm">{err}</div>}
      <div className="flex gap-2">
        <button
          onClick={signIn}
          disabled={loading}
          className="px-3 py-2 rounded bg-indigo-600 text-white"
        >
          {loading ? "Working..." : "Sign in"}
        </button>
        <button
          onClick={signUp}
          disabled={loading}
          className="px-3 py-2 rounded border"
        >
          {loading ? "Working..." : "Sign up"}

        </button>
      </div>
    </div>
  );
}
