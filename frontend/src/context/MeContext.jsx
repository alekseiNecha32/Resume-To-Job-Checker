import React, { createContext, useContext, useEffect, useState } from "react";
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
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    let inFlight = false;

    async function loadMeOnce() {
      if (inFlight) return;
      inFlight = true;
      setLoading(true);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) return; // no session yet; skip
        const profile = await getMe();      // uses API_BASE under the hood
        if (mounted && profile) {
          setMe(profile);
          try { localStorage.setItem("cachedProfile", JSON.stringify(profile)); } catch {}
        }
      } catch {
        // tolerate 401/404 during cold start
      } finally {
        inFlight = false;
        if (mounted) setLoading(false);
      }
    }

    // Initial attempt (only runs if a token exists)
    loadMeOnce();

    const { data: sub } = supabase.auth.onAuthStateChange(async (event) => {
      // Only fetch after we know the user is signed in or updated
      if (event === "SIGNED_IN" || event === "USER_UPDATED") {
        await loadMeOnce();
      }
      if (event === "SIGNED_OUT") {
        setMe(null);
        try { localStorage.removeItem("cachedProfile"); } catch {}
      }
      // Skip INITIAL_SESSION to avoid duplicate fetches
    });

    // Listen for manual profile updates (e.g., after avatar upload)
    const onProfileUpdated = (e) => {
      if (e?.detail) {
        setMe(e.detail);
        try { localStorage.setItem("cachedProfile", JSON.stringify(e.detail)); } catch {}
      } else {
        loadMeOnce();
      }
    };
    window.addEventListener("profile_updated", onProfileUpdated);

    return () => {
      mounted = false;
      window.removeEventListener("profile_updated", onProfileUpdated);
      sub?.subscription?.unsubscribe?.();
    };
  }, []);

  useEffect(() => {
    try {
      if (me) localStorage.setItem("cachedProfile", JSON.stringify(me));
    } catch {}
  }, [me]);

  return (
    <MeContext.Provider value={{ me, setMe, loading, hasProfile: !!me }}>
      {children}
    </MeContext.Provider>
  );
}

export function useMe() {
  return useContext(MeContext);
}
