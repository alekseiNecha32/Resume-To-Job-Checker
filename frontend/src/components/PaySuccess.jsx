import React, { useEffect, useState } from "react";
import { getProfile, syncSubscription } from "../services/apiClient";
import { useMe } from "../context/MeContext.jsx";

export default function PaySuccess() {
  const [msg, setMsg] = useState("Processing payment...");
  const { me, setMe } = useMe();

  useEffect(() => {
    let active = true;
    const qs = new URLSearchParams(window.location.search);
    const sessionId = qs.get("session_id");

    // Apply optimistic credits from localStorage immediately for a snappy UX
    try {
      const raw = localStorage.getItem("pendingPurchase");
      if (raw) {
        const { credits } = JSON.parse(raw);
        if (credits && Number.isFinite(credits)) {
          setMe?.(prev => ({ ...(prev || {}), credits: (prev?.credits || 0) + credits }));
          try { window.dispatchEvent(new CustomEvent("profile_updated", { detail: { ...(me || {}), credits: (me?.credits || 0) + credits } })); } catch {}
          setMsg("Payment successful — updating your profile…");
        }
      }
    } catch {}

    async function tryRefresh(attempt = 1) {
      // Sync subscription from Stripe using session_id
      if (sessionId && attempt === 1) {
        try {
          await syncSubscription(sessionId);
          console.log("Subscription synced successfully");
        } catch (err) {
          console.warn("Failed to sync subscription:", err);
        }
      }

      try {
        const json = await getProfile();
        if (json) {
          try { setMe?.(prev => ({ ...(prev || {}), ...json })); } catch {}
          try { window.dispatchEvent(new CustomEvent("profile_updated", { detail: json })); } catch {}
          if (!active) return;
          setMsg("Payment successful — credits added. Redirecting...");
          // clear pending optimistic purchase once we have server truth
          try { localStorage.removeItem("pendingPurchase"); } catch {}
          setTimeout(() => (window.location.href = "/"), 1000);
          return;
        }
      } catch {}

      if (!active) return;
      if (attempt < 8) {
        setMsg(`Payment processed. Syncing profile… (${attempt}/8)`);
        setTimeout(() => tryRefresh(attempt + 1), 800);
      } else {
        setMsg("Payment succeeded but failed to refresh profile.");
      }
    }

    // Start refresh attempts; webhook can take a moment
    tryRefresh(1);
    return () => { active = false; };
  }, [setMe]);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-2">Payment successful</h1>
      <p className="text-sm text-gray-600">{msg}</p>
    </div>
  );
}