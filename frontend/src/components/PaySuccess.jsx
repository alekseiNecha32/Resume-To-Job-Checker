import React, { useEffect, useMemo, useState } from "react";
import { getProfile } from "../services/apiClient";
import { useMe } from "../context/MeContext.jsx";

export default function PaySuccess() {
  const [msg, setMsg] = useState("Processing payment...");
  const { setMe } = useMe();

  useEffect(() => {
    let active = true;
    const qs = new URLSearchParams(window.location.search);
    const sessionId = qs.get("session_id");

    async function tryRefresh(attempt = 1) {
      try {
        const json = await getProfile();
        if (json) {
          try { setMe?.(prev => ({ ...(prev || {}), ...json })); } catch {}
          try { window.dispatchEvent(new CustomEvent("profile_updated", { detail: json })); } catch {}
          if (!active) return;
          setMsg("Payment successful — credits added. Redirecting...");
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