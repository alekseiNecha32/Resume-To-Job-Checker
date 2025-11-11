import React, { createContext, useContext, useEffect, useState } from "react";
import { getMe } from "../services/apiClient.js";
import { supabase } from "../lib/supabaseClient";

const MeContext = createContext(null);

export function MeProvider({ children }) {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const u = await getMe();
        if (mounted && u) {
          setMe(u);
          return;
        }
        // Fallback: if backend is down or unauthorized, still reflect Supabase auth
        const { data } = await supabase.auth.getUser();
        const user = data?.user;
        if (mounted && user) {
          setMe({
            user_id: user.id,
            email: user.email,
            full_name: user.user_metadata?.full_name || null,
            credits: 0, // unknown until backend responds
          });
        }
      } catch {
        // On error, try to at least get the supabase user
        try {
          const { data } = await supabase.auth.getUser();
          const user = data?.user;
          if (mounted && user) {
            setMe({ user_id: user.id, email: user.email, full_name: user.user_metadata?.full_name || null, credits: 0 });
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
      if (e?.detail) setMe(e.detail);
      else load();
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