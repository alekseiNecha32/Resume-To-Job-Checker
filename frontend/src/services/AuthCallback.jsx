import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";

function hasAuthParams(url) {
  return (
    url.searchParams.has("code") ||
    url.hash.includes("access_token=") ||
    url.searchParams.has("access_token")
  );
}

function readPendingSignup() {
  try {
    const raw = sessionStorage.getItem("pendingSignup");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const ts = Number(parsed?.ts || 0);

    // expire after 15 minutes
    if (!ts || Date.now() - ts > 15 * 60 * 1000) {
      sessionStorage.removeItem("pendingSignup");
      return null;
    }
    if (!parsed?.email || !parsed?.password) return null;
    return parsed;
  } catch {
    return null;
  }
}

function clearPendingSignup() {
  try { sessionStorage.removeItem("pendingSignup"); } catch {}
}

export default function AuthCallback() {
  const nav = useNavigate();
  const [status, setStatus] = useState("Loading…");
  const [canGoHome, setCanGoHome] = useState(false);

  useEffect(() => {
    let alive = true;

    (async () => {
      const url = new URL(window.location.href);

      if (!hasAuthParams(url)) {
        const pending = readPendingSignup();
        setCanGoHome(true);

        if (!pending) {
          setStatus("Wait for confirmation email to confirm your email.");
          return;
        }

        setStatus("Waiting for confirmation… We’ll sign you in automatically once confirmed.");

        // Poll: once email is confirmed, password sign-in will start succeeding
        let attempts = 0;
        const maxAttempts = 40; // ~2 minutes at 3s interval
        const tickMs = 3000;

        const timer = setInterval(async () => {
          if (!alive) return;
          attempts += 1;

          try {
            const { error } = await supabase.auth.signInWithPassword({
              email: pending.email,
              password: pending.password,
            });

            if (!alive) return;

            if (!error) {
              clearInterval(timer);
              clearPendingSignup();

              setStatus("Email confirmed. You are now logged in.");
              setCanGoHome(true);

              // Force MeContext to revalidate immediately
              window.dispatchEvent(new CustomEvent("profile_updated", { detail: null }));

              setTimeout(() => {
                if (alive) nav("/", { replace: true });
              }, 600);
              return;
            }

            const msg = String(error.message || "").toLowerCase();

            // keep polling while not confirmed yet
            if (msg.includes("confirm") || msg.includes("not confirmed")) {
              if (attempts >= maxAttempts) {
                clearInterval(timer);
                setStatus("Confirmed? Please click Continue to Home and log in.");
              }
              return;
            }

            // Any other error: stop polling (bad password, rate limit, etc.)
            clearInterval(timer);
            setStatus("Could not sign you in automatically. Please log in.");
          } catch {
            if (attempts >= maxAttempts) {
              clearInterval(timer);
              setStatus("Confirmed? Please click Continue to Home and log in.");
            }
          }
        }, tickMs);

        return () => clearInterval(timer);
      }

      // CASE B: we DO have auth params (confirmation link opened on this same device)
      setStatus("Confirming your email…");

      // For PKCE links, exchange code for a session
       const code = url.searchParams.get("code");
      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (!alive) return;
        if (error) {
          setStatus("Confirmation failed. Please try logging in.");
          setCanGoHome(true);
          return;
        }
      }

      const { data, error } = await supabase.auth.getSession();
      if (!alive) return;


      if (error) {
        setStatus("Confirmation failed. Please try logging in.");
        setCanGoHome(true);
        return;
      }

       if (data?.session) {
        clearPendingSignup();
        setStatus("Email confirmed. You are now logged in.");
        setCanGoHome(true);

        window.dispatchEvent(new CustomEvent("profile_updated", { detail: null }));

        setTimeout(() => {
          if (alive) nav("/", { replace: true });
        }, 1200);
      } else {
        setStatus("Confirmation link opened, but no session found. Please log in.");
        setCanGoHome(true);
      }
    })();

    return () => {
      alive = false;
    };
  }, [nav]);

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="glass-card p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold m-0">{status}</h2>
            <p className="text-sm text-muted-foreground mt-2">
              If you confirmed your email in another tab, you can return to the home page here.
            </p>
          </div>

          {canGoHome && (
            <button
              type="button"
              className="btn btn-ghost"
              aria-label="Close"
              onClick={() => nav("/", { replace: true })}
              title="Close"
            >
              ✕
            </button>
          )}
        </div>

        {canGoHome && (
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => nav("/", { replace: true })}
            >
              Continue to Home
            </button>
          </div>
        )}
      </div>
    </div>
  );
}