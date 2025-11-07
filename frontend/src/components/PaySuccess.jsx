import React, { useEffect, useState } from "react";
import { getProfile } from "../services/apiClient";

export default function PaySuccess() {
  const [msg, setMsg] = useState("Processing payment...");

  useEffect(() => {
    async function refreshProfile() {
      try {
        const json = await getProfile();
        if (!json) {
          setMsg("Payment succeeded but failed to refresh profile.");
          return;
        }
        // optionally update global state / context here if you have one
        setMsg("Payment successful — credits added. Redirecting...");
        setTimeout(() => (window.location.href = "/"), 1200);
      } catch (err) {
        setMsg("Payment succeeded but could not refresh profile.");
      }
    }
    refreshProfile();
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-2">Payment successful</h1>
      <p className="text-sm text-gray-600">{msg}</p>
    </div>
  );
}