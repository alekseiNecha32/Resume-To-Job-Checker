import React, { createContext, useContext, useEffect, useState, useRef } from "react";
import { getMe } from "../services/apiClient.js";
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
// Start true to avoid flicker on first paint
  const [loading, setLoading] = useState(true);
  const inFlight = useRef(false);

async function revalidate() {
  if (inFlight.current) return;
  inFlight.current = true;
  setLoading(true); // start in loading state
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) return; // keep cached me, do not clear
    const profile = await getMe();
    if (profile) {
      setMe(profile);
      try { localStorage.setItem("cachedProfile", JSON.stringify(profile)); } catch {}
    }
  } catch {
    // keep stale me on error
  } finally {
    inFlight.current = false;
    setLoading(false);
  }
}


useEffect(() => {
  // show cache immediately, then refresh
  setLoading(true);
  revalidate();

  const { data: sub } = supabase.auth.onAuthStateChange(async (event) => {
    if (event === "SIGNED_OUT") {
      setMe(null);
      try { localStorage.removeItem("cachedProfile"); } catch {}
      return;
    }
    if (event === "SIGNED_IN" || event === "USER_UPDATED" || event === "TOKEN_REFRESHED") {
      setLoading(true);
      revalidate();
    }
    // do not clear on INITIAL_SESSION
  });

  const onFocus = () => {
    setLoading(true);
    revalidate();
  };
  const onVisible = () => {
    if (document.visibilityState === "visible") {
      setLoading(true);
      revalidate();
    }
  };
  window.addEventListener("focus", onFocus);
  document.addEventListener("visibilitychange", onVisible);

  const onProfileUpdated = (e) => {
    const next = e?.detail;
    if (next) {
      setMe(next);
      try { localStorage.setItem("cachedProfile", JSON.stringify(next)); } catch {}
    } else {
      setLoading(true);
      revalidate();
    }
  };
  window.addEventListener("profile_updated", onProfileUpdated);

  return () => {
    window.removeEventListener("focus", onFocus);
    document.removeEventListener("visibilitychange", onVisible);
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