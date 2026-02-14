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

    // Read expected credits from localStorage for comparison
    let expectedCredits = 0;
    let previousCredits = me?.credits || 0;
    try {
      const raw = localStorage.getItem("pendingPurchase");
      if (raw) {
        const { credits } = JSON.parse(raw);
        if (credits && Number.isFinite(credits)) {
          expectedCredits = credits;
          // Show optimistic update immediately
          setMe?.(prev => ({ ...(prev || {}), credits: (prev?.credits || 0) + credits }));
          setMsg("Payment successful — updating your profile…");
        }
      }
    } catch {}

    async function tryRefresh(attempt = 1) {
      // Sync payment/subscription from Stripe using session_id (first attempt only)
      if (sessionId && attempt === 1) {
        try {
          await syncSubscription(sessionId);
          console.log("Payment synced successfully");
        } catch (err) {
          console.warn("Failed to sync payment:", err);
        }
      }

      try {
        const json = await getProfile();
        if (json) {
          const serverCredits = json.credits ?? 0;

          // If we know credits were purchased, verify they actually increased
          // before declaring success and redirecting
          if (expectedCredits > 0 && serverCredits <= previousCredits && attempt < 10) {
            if (!active) return;
            setMsg(`Payment processed. Waiting for credits to update… (${attempt}/10)`);
            setTimeout(() => tryRefresh(attempt + 1), 1200);
            return;
          }

          try { setMe?.(prev => ({ ...(prev || {}), ...json })); } catch {}
          try { window.dispatchEvent(new CustomEvent("profile_updated", { detail: json })); } catch {}
          if (!active) return;
          setMsg("Payment successful — credits added. Redirecting...");
          try { localStorage.removeItem("pendingPurchase"); } catch {}
          setTimeout(() => (window.location.href = "/"), 1000);
          return;
        }
      } catch {}

      if (!active) return;
      if (attempt < 10) {
        setMsg(`Payment processed. Syncing profile… (${attempt}/10)`);
        setTimeout(() => tryRefresh(attempt + 1), 1200);
      } else {
        // After all retries, redirect anyway — credits may appear shortly
        setMsg("Payment succeeded. Redirecting...");
        try { localStorage.removeItem("pendingPurchase"); } catch {}
        setTimeout(() => (window.location.href = "/"), 1500);
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