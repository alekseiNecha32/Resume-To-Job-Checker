import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";

function hasAuthParams(url) {
  // Supabase can return either:
  // - ?code=... (PKCE)
  // - or #access_token=... (implicit)
  return (
    url.searchParams.has("code") ||
    url.hash.includes("access_token=") ||
    url.searchParams.has("access_token")
  );
}

export default function AuthCallback() {
  const nav = useNavigate();
  const [status, setStatus] = useState("Loading…");
  const [canGoHome, setCanGoHome] = useState(false);

  useEffect(() => {
    let alive = true;

    (async () => {
      const url = new URL(window.location.href);

      // If user was sent here right after clicking "Sign up"
      // (no tokens yet), show the "check email" message.
      if (!hasAuthParams(url)) {
        if (!alive) return;
        setStatus("Wait for confirmation email to confirm your email.");
        setCanGoHome(true);
        return;
      }


      // If we DO have auth params, complete the login.
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
        setStatus("Email confirmed. You are now logged in.");
        setCanGoHome(true);

        // Force MeContext to revalidate immediately
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