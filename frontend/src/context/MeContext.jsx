import React, { createContext, useContext, useEffect, useState } from "react";
import { getMe } from "../services/apiClient.js";
import { supabase } from "../lib/supabaseClient";

const MeContext = createContext(null);

export function MeProvider({ children }) {
  // Initialize from cache synchronously to avoid auth flicker after redirects
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
          try { localStorage.setItem("cachedProfile", JSON.stringify(u)); } catch {}
          return;
        }
        // Fallback: if backend is down or unauthorized, still reflect Supabase auth
        const { data } = await supabase.auth.getUser();
        const user = data?.user;
        if (mounted && user) {
          const fallback = {
            user_id: user.id,
            email: user.email,
            full_name: user.user_metadata?.full_name || null,
            credits: 0, // unknown until backend responds
          };
          setMe(fallback);
          try { localStorage.setItem("cachedProfile", JSON.stringify(fallback)); } catch {}
        }
      } catch {
        // On error, try to at least get the supabase user
        try {
          const { data } = await supabase.auth.getUser();
          const user = data?.user;
          if (mounted && user) {
            const fallback = { user_id: user.id, email: user.email, full_name: user.user_metadata?.full_name || null, credits: 0 };
            setMe(fallback);
            try { localStorage.setItem("cachedProfile", JSON.stringify(fallback)); } catch {}
          } else if (mounted) {
            setMe(null);
          }
        } catch {
          if (mounted) setMe(null);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();

    // refresh on auth changes
    const { data: sub } = supabase.auth.onAuthStateChange(() => {
      load();
    });

    // accept dispatched optimistic/server updates
    const onProfile = (e) => {
      if (e?.detail) {
        setMe(e.detail);
        try { localStorage.setItem("cachedProfile", JSON.stringify(e.detail)); } catch {}
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

  return (
    <MeContext.Provider value={{ me, setMe, loading }}>
      {children}
    </MeContext.Provider>
  );
}

export function useMe() {
  return useContext(MeContext);
}