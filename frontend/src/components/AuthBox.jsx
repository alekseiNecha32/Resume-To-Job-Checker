import { useState } from "react";
import { supabase } from "../lib/supabaseClient";

export default function AuthBox({ onDone }) {
  const [email, setEmail] = useState("");
  const [password, setPwd] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function signIn() {
    setErr("");
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) setErr(error.message);
    else onDone?.();
  }

  async function signUp() {
    setErr("");
    setLoading(true);
    const { error } = await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (error) setErr(error.message);
    else onDone?.();
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
          Sign in
        </button>
        <button
          onClick={signUp}
          disabled={loading}
          className="px-3 py-2 rounded border"
        >
          Sign up
        </button>
      </div>
    </div>
  );
}
