import React, { useEffect, useState } from "react";
import AuthModal from "./AuthModal";
import ProfileMenu from "./ProfileMenu";
import { getMe } from "../services/apiClient";
import { supabase } from "../lib/supabaseClient";

export default function NavBar() {
  const [me, setMe] = useState(null);
  const [showAuth, setShowAuth] = useState(false);
  const [showProfile, setShowProfile] = useState(false); // <-- added

  useEffect(() => {
    (async () => {
      try {
        const u = await getMe();
        setMe(u);
      } catch {
        setMe(null);
      }
    })();
  }, []);

  async function onAuthSuccess() {
    setShowAuth(false);
    try {
      const u = await getMe();
      setMe(u);
    } catch {
      setMe(null);
    }
  }

  async function handleLogout() {
    try {
      await supabase.auth.signOut();
    } catch (e) {
      console.warn("signOut error", e);
    } finally {
      setMe(null);
      setShowProfile(false);
    }
  }

  function initials(email) {
    if (!email) return "U";
    return email.split(/[.@]/)[0].slice(0, 2).toUpperCase();
  }

  return (
    <>
      <nav className="rtjc-nav">
        <div className="rtjc-brand">
          <div className="rtjc-logo">🎁</div>
          <div>
            <div className="rtjc-title">Resume to Job Checker</div>
            <div className="rtjc-sub">Optimize your resume for ATS</div>
          </div>
        </div>

        <div className="rtjc-actions">
          {!me ? (
            <>
              <button className="btn btn-ghost" onClick={() => setShowAuth(true)}>
                Log In
              </button>
              <button className="btn btn-primary" onClick={() => setShowAuth(true)}>
                Sign Up
              </button>
            </>
          ) : (
            <div className="rtjc-profile">
              <button
                className="rtjc-avatar-btn"
                onClick={() => setShowProfile((s) => !s)}
                aria-haspopup="true"
                aria-expanded={showProfile}
              >
                <div className="rtjc-avatar">{initials(me.email)}</div>
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
        <ProfileMenu me={me} onClose={() => setShowProfile(false)} onLogout={handleLogout} />
      )}
    </>
  );
}