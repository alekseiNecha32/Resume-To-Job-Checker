import React, { useState } from "react";
import AuthModal from "./AuthModal";
import ProfileMenu from "./ProfileMenu";
import CreditsModal from "./CreditsModal";
import { supabase } from "../lib/supabaseClient";
import { useMe } from "../context/MeContext.jsx";

export default function NavBar() {
  // Use global profile from context so credits stay in sync everywhere
  const { me, setMe, loading } = useMe();
  const [showAuth, setShowAuth] = useState(false);
  const [showProfile, setShowProfile] = useState(false); // <-- added
  const [showCreditsModal, setShowCreditsModal] = useState(false);

  async function onAuthSuccess() {
    // Close modal; MeProvider will refresh on auth state change
    setShowAuth(false);
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
  const handleBuyCreditsClick = () => {
    setShowCreditsModal(true);
  };

  const handleCloseCreditsModal = () => {
    setShowCreditsModal(false);
  };
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
          {loading ? (
            // Subtle skeleton to avoid visible disappearance
            <div className="rtjc-profile" aria-busy="true" aria-live="polite">
              <div className="rtjc-avatar rtjc-skeleton" />
              <div className="rtjc-meta">
                <div className="rtjc-email rtjc-skeleton-line" style={{ width: 140 }} />
                <div className="rtjc-credits rtjc-skeleton-line" style={{ width: 90, marginTop: 4 }} />
              </div>
            </div>
          ) : !me ? (
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