import React, { createContext, useContext, useEffect, useState } from "react";
import { getMe } from "../services/apiClient.js";
import { supabase } from "../lib/supabaseClient";

const MeContext = createContext(null);

export function MeProvider({ children }) {
  // Initialize from cache synchronously to avoid any logged-off flicker after redirects
  const [me, setMe] = useState(() => {
    try {
      const raw = localStorage.getItem("cachedProfile");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(() => (localStorage.getItem("cachedProfile") ? false : true));

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const u = await getMe();
        if (mounted && u) {
          setMe(u);
          try { localStorage.setItem("cachedProfile", JSON.stringify(u)); } catch { }
          return;
        }
        const { data } = await supabase.auth.getUser();
        const user = data?.user;
        if (mounted && user) {
          setMe(prev => ({
            user_id: user.id,
            email: user.email,
            full_name: user.user_metadata?.full_name || prev?.full_name || null,
            credits: prev?.credits ?? 0,
          }));
        } else {
          // No user found - clear state
          if (mounted) {
            setMe(null);
            try { localStorage.removeItem("cachedProfile"); } catch { }
          }
        }
      } catch {

      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    const { data: sub } = supabase.auth.onAuthStateChange((event) => {
      console.log('Auth event:', event); // Debug log

      if (event === 'SIGNED_OUT') {
        // User logged out - clear everything
        if (mounted) {
          setMe(null);
          try {
            localStorage.removeItem("cachedProfile");
          } catch { }
        }
      } else {
        // Refresh in background to avoid visible flicker
        load();
      }
    });

    const onProfile = (e) => {
      if (e?.detail) {
        setMe(e.detail);
        try { localStorage.setItem("cachedProfile", JSON.stringify(e.detail)); } catch { }
      } else {
        load();
      }
    };
    window.addEventListener("profile_updated", onProfile);

    return () => {
      mounted = false;
      window.removeEventListener("profile_updated", onProfile);
      sub?.subscription?.unsubscribe?.();
    };
  }, []);

  // Persist latest profile for instant rehydration next mount
  useEffect(() => {
    try {
      if (me) localStorage.setItem("cachedProfile", JSON.stringify(me));
    } catch { }
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
