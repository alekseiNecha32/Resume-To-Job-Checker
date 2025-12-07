import React, { useState, useEffect } from "react";
import AuthModal from "./AuthModal";
import ProfileMenu from "./ProfileMenu";
import CreditsModal from "./CreditsModal";
import { supabase } from "../lib/supabaseClient";
import { useMe } from "../context/MeContext.jsx";
import { Link } from "react-router-dom"; // added
import "../styles/resume.css";

import { API_BASE } from "../services/apiClient.js";

function initials(email = "") {
  const [a = "", b = ""] = email.split("@")[0].split(/[.\-_]/);
  return (a[0] || "").toUpperCase() + (b[0] || "").toUpperCase();
}

export default function NavBar() {
  const { me, setMe, loading } = useMe();
  const [showAuth, setShowAuth] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showCreditsModal, setShowCreditsModal] = useState(false);

  const cachedMe = (() => { try { return JSON.parse(localStorage.getItem("cachedProfile") || "null"); } catch { return null; } })();
  const displayMe = me || cachedMe;

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
          for (const t of tryTypes) { try { await supabase.auth.verifyOtp({ type: t, token_hash }); break; } catch { } }
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
        const resp = await fetch(`${API_BASE}/me`, {
          headers: { Authorization: `Bearer ${session.access_token}` }
        });
        if (resp.ok && !cancelled) setMe(await resp.json());
      } catch (e) { console.warn("Initial /api/me failed:", e); }
    })();
    return () => { cancelled = true; };
  }, [setMe]);

  async function hydrateProfile(accessToken) {
    try {
      let resp = await fetch(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      if (resp.status === 404) {
        await fetch(`${API_BASE}/auth/create_profile`, {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` }
        }).catch(() => { });
        resp = await fetch(`${API_BASE}/me`, {
          headers: { Authorization: `Bearer ${accessToken}` }
        });
      }
      if (resp.ok) setMe(await resp.json());
    } catch (e) { console.warn("hydrateProfile failed:", e); }
  }

  useEffect(() => {
    const { data: sub } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (event === "SIGNED_OUT") {
          setMe(null);
          return;
        }

        if (["INITIAL_SESSION", "SIGNED_IN", "USER_UPDATED", "TOKEN_REFRESHED"].includes(event)) {
          if (!session) {
            // skip clearing; let MeContext keep stale profile
            return;
          }
          if (!me) {
            setMe({
              email: session.user.email,
              avatar_url: null,
              credits: null,
            });
          }
          hydrateProfile(session.access_token);
        }
      }
    );
    return () => sub.subscription.unsubscribe();
  }, []);

  function onAuthSuccess() {
    setShowAuth(false); // auth listener will populate me
  }

  async function handleLogout() {
    try { await supabase.auth.signOut(); } catch { }
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
        <div className="rtjc-nav-links">
              
<Link to="/" className="rtjc-nav-btn">Analyze Resume</Link>
<Link to="/constructor" className="rtjc-nav-btn">Resume Constructor</Link>
            </div>

        <div className="rtjc-actions">
          {loading && displayMe ? (
            // Show cached profile while revalidating
            <div className="rtjc-profile">
              <button
                className="rtjc-avatar-btn"
                onClick={() => setShowProfile(s => !s)}
                aria-haspopup="true"
                aria-expanded={showProfile}
              >
                {displayMe.avatar_url
                  ? <img src={displayMe.avatar_url} alt="avatar" style={{ width: 40, height: 40, borderRadius: "50%", objectFit: "cover" }} />
                  : <div className="rtjc-avatar">{initials(displayMe.email)}</div>}
              </button>
              <div className="rtjc-meta">
                <div className="rtjc-email">{displayMe.email}</div>
                <div className="rtjc-credits">{(displayMe.credits ?? 0) + " credits"}</div>
              </div>
            </div>
          ) : loading ? (
            // Fallback skeleton if no cache
            <div className="rtjc-profile" aria-busy="true">
              <div className="rtjc-avatar rtjc-skeleton" />
              <div className="rtjc-meta">
                <div className="rtjc-email rtjc-skeleton-line" style={{ width: 140 }} />
                <div className="rtjc-credits rtjc-skeleton-line" style={{ width: 90, marginTop: 4 }} />
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
                  ? <img src={me.avatar_url} alt="avatar" style={{ width: 40, height: 40, borderRadius: "50%", objectFit: "cover" }} />
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