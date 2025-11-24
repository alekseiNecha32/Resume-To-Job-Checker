import React, { useState, useEffect } from "react";
import AuthModal from "./AuthModal";
import ProfileMenu from "./ProfileMenu";
import CreditsModal from "./CreditsModal";
import { supabase } from "../lib/supabaseClient";
import { useMe } from "../context/MeContext.jsx";


function initials(email = "") {
  const [a = "", b = ""] = email.split("@")[0].split(/[.\-_]/);
  return (a[0] || "").toUpperCase() + (b[0] || "").toUpperCase();
}

export default function NavBar() {
  const { me, setMe, loading } = useMe();
  const [showAuth, setShowAuth] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showCreditsModal, setShowCreditsModal] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const url = new URL(window.location.href);
      const qs = url.searchParams;
      const hash = new URLSearchParams(url.hash.replace(/^#/, "?"));
      const token_hash = qs.get("token_hash") || hash.get("token_hash");
      const type = qs.get("type") || hash.get("type");
      const code = qs.get("code") || hash.get("code");
      const access_token = qs.get("access_token") || hash.get("access_token");
      const refresh_token = qs.get("refresh_token") || hash.get("refresh_token");

      try {
        if (code) {
          await supabase.auth.exchangeCodeForSession(window.location.href);
        } else if (token_hash) {
          const tryTypes = [type, "signup", "magiclink", "recovery", "email"].filter(Boolean);
          for (const t of tryTypes) { try { await supabase.auth.verifyOtp({ type: t, token_hash }); break; } catch {} }
        } else if (access_token && refresh_token) {
          await supabase.auth.setSession({ access_token, refresh_token });
        }
        if (token_hash || type || code || access_token || refresh_token) {
          window.history.replaceState({}, document.title, url.origin + url.pathname);
        }
      } catch (e) { console.warn("Auth callback failed:", e); }

      const session = (await supabase.auth.getSession()).data?.session;
      if (!session) return;
      try {
        const resp = await fetch("/api/me", {
          headers: { Authorization: `Bearer ${session.access_token}` }
        });
        if (resp.ok && !cancelled) setMe(await resp.json());
      } catch (e) { console.warn("Initial /api/me failed:", e); }
    })();
    return () => { cancelled = true; };
  }, [setMe]);

  async function hydrateProfile(accessToken) {
    try {
      let resp = await fetch("/api/me", {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (resp.status === 404) {
        await fetch("/api/auth/create_profile", {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` }
        }).catch(()=>{});
        resp = await fetch("/api/me", {
          headers: { Authorization: `Bearer ${accessToken}` }
        });
      }
      if (resp.ok) setMe(await resp.json());
    } catch (e) { console.warn("hydrateProfile failed:", e); }
  }

  // SINGLE auth listener
  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (!session) { setMe(null); return; }
      if (["INITIAL_SESSION","SIGNED_IN","USER_UPDATED","TOKEN_REFRESHED"].includes(event)) {
        if (!me) {
          setMe({ email: session.user.email, avatar_url: null, credits: null });
        }
        hydrateProfile(session.access_token);
      }
    });
    return () => sub.subscription.unsubscribe();
  }, [me, setMe]);

 function onAuthSuccess() {
    setShowAuth(false); // auth listener will populate me
  }

  async function handleLogout() {
    try { await supabase.auth.signOut(); } catch {}
    setMe(null);
    setShowProfile(false);
  }

  function handleCloseCreditsModal() { setShowCreditsModal(false); }
 return (
    <>
      <nav className="rtjc-nav">
        <div className="rtjc-brand">
          <div className="rtjc-logo">🔍</div>
          <div>
            <div className="rtjc-title">Resume to Job Checker</div>
            <div className="rtjc-sub">Optimize your resume for ATS</div>
          </div>
        </div>
        <div className="rtjc-actions">
          {loading ? (
            <div className="rtjc-profile" aria-busy="true">
              <div className="rtjc-avatar rtjc-skeleton" />
              <div className="rtjc-meta">
                <div className="rtjc-email rtjc-skeleton-line" style={{ width:140 }} />
                <div className="rtjc-credits rtjc-skeleton-line" style={{ width:90, marginTop:4 }} />
              </div>
            </div>
          ) : !me ? (
            <>
              <button className="btn btn-ghost" onClick={() => setShowAuth(true)}>Log In</button>
              <button className="btn btn-primary" onClick={() => setShowAuth(true)}>Sign Up</button>
            </>
          ) : (
            <div className="rtjc-profile">
              <button
                className="rtjc-avatar-btn"
                onClick={() => setShowProfile(s => !s)}
                aria-haspopup="true"
                aria-expanded={showProfile}
              >
                {me.avatar_url
                  ? <img src={me.avatar_url} alt="avatar" style={{ width:40, height:40, borderRadius:"50%", objectFit:"cover" }} />
                  : <div className="rtjc-avatar">{initials(me.email)}</div>}
              </button>
              <div className="rtjc-meta">
                <div className="rtjc-email">{me.email}</div>
                <div className="rtjc-credits">{(me.credits ?? 0) + " credits"}</div>
              </div>
            </div>
          )}
        </div>
      </nav>

      {showAuth && <AuthModal onClose={() => setShowAuth(false)} onSuccess={onAuthSuccess} />}
      {showProfile && me && (
        <ProfileMenu
          me={me}
          onClose={() => setShowProfile(false)}
          onLogout={handleLogout}
          onBuyCredits={() => setShowCreditsModal(true)}
        />
      )}
      {showCreditsModal && <CreditsModal onClose={handleCloseCreditsModal} />}
    </>
  );
}