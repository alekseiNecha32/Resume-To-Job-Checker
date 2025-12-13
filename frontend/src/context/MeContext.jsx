import React, { createContext, useContext, useEffect, useState, useRef } from "react";
import { API_BASE } from "../services/apiClient.js";
import { supabase } from "../lib/supabaseClient";

const MeContext = createContext(null);

export function MeProvider({ children }) {
  const [me, setMe] = useState(() => {
    try {
      const raw = localStorage.getItem("cachedProfile");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const [loading, setLoading] = useState(true);
  const inFlight = useRef(false);

  async function fetchMe(accessToken) {
    return fetch(`${API_BASE}/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  }

  async function ensureProfile(accessToken) {
    // 1) Try /me
    const resp = await fetchMe(accessToken);

    // 2) If missing, create profile then retry
    if (resp.status === 404) {
      await fetch(`${API_BASE}/auth/create_profile`, {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}` },
      }).catch(() => {});

      const resp2 = await fetchMe(accessToken);
      if (resp2.ok) return await resp2.json();
      return null;
    }

    // 3) If ok, return profile
    if (resp.ok) return await resp.json();

    return null;
  }

  async function revalidate() {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();

      if (!session?.access_token) return; // keep cached me, do not clear

      const profile = await ensureProfile(session.access_token);

      if (profile) {
        setMe(profile);
        try { localStorage.setItem("cachedProfile", JSON.stringify(profile)); } catch {}
      } else {
        // fallback: still show "logged in" state
        setMe((prev) => prev ?? { email: session.user.email, credits: 0 });
      }
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }

  useEffect(() => {
    revalidate();

    const { data: sub } = supabase.auth.onAuthStateChange(async (event) => {
      if (event === "SIGNED_OUT") {
        setMe(null);
        try { localStorage.removeItem("cachedProfile"); } catch {}
        setLoading(false);
        return;
      }

      if (event === "SIGNED_IN" || event === "USER_UPDATED" || event === "TOKEN_REFRESHED") {
        revalidate();
      }
    });

    const onProfileUpdated = (e) => {
      const next = e?.detail;
      if (next) {
        setMe(next);
        try { localStorage.setItem("cachedProfile", JSON.stringify(next)); } catch {}
      } else {
        revalidate();
      }
    };
    window.addEventListener("profile_updated", onProfileUpdated);

    return () => {
      window.removeEventListener("profile_updated", onProfileUpdated);
      sub?.subscription?.unsubscribe?.();
    };
  }, []);

  return (
    <MeContext.Provider value={{ me, setMe, loading, hasProfile: !!me }}>
      {children}
    </MeContext.Provider>
  );
}

export function useMe() {
  return useContext(MeContext);
}