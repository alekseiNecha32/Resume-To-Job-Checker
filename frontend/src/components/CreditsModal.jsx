import React, { useEffect, useState } from "react";
import { createCheckoutSession } from "../services/apiClient.js";

export default function CreditsModal({ onClose, hasSubscription = false }) {
  const [processing, setProcessing] = useState(false);
  const [msg, setMsg] = useState("");
  const [customCredits, setCustomCredits] = useState(10);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose?.();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function startCheckout(packId, credits) {
    setProcessing(true);
    setMsg("");
    try {
      const creditAmount = packId === "pro" ? 10 : credits;
      try {
        localStorage.setItem(
          "pendingPurchase",
          JSON.stringify({ credits: creditAmount, ts: Date.now() })
        );
      } catch (_) {}

      const payload = packId === "pro"
        ? { packId: "pro" }
        : { packId: "custom", credits };

      const data = await createCheckoutSession(payload);
      if (data?.url) {
        window.location.href = data.url;
        return;
      }
      setMsg("Failed to create checkout session");
    } catch (err) {
      console.error("checkout error", err);
      setMsg(err?.message || "Could not start checkout");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-10 sm:pt-20 bg-black/40 overflow-y-auto"
      role="dialog"
      aria-modal="true"
      onMouseDown={onClose}
    >
      <div
        className="w-full max-w-2xl mx-3 sm:mx-4 my-4 rounded-2xl bg-white shadow-xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start justify-between px-4 sm:px-6 pt-4 sm:pt-6">
          <div className="pr-2">
            <h2 className="text-lg sm:text-xl font-semibold">Buy Smart Analysis Credits</h2>
            <p className="mt-1 text-xs sm:text-sm text-gray-500">
              Unlock Pro smart analysis (critical gaps + matching/missing keywords) and get 5 live AI suggestions
              inside the Resume Constructor to add, or reject while you build. Also you can download file to make additional edits.
            </p>
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 rounded-full p-1.5 sm:p-2 flex-shrink-0"
          >
            ✕
          </button>
        </div>

        <div className="px-4 sm:px-6 py-4 sm:py-6 space-y-4 sm:space-y-6">
          {/* Pro Subscription card - only show if not subscribed */}
          {!hasSubscription && (
            <div className="rounded-xl border-2 border-indigo-300 p-4 sm:p-6">
              <div className="flex justify-center">
                <div className="badge inline-flex items-center bg-indigo-600 text-white px-3 py-1 rounded-full text-xs sm:text-sm">
                  Best Value
                </div>
              </div>
              <div className="text-center mt-3 sm:mt-4">
                <div className="text-base sm:text-lg font-medium">Pro Subscription</div>
                <div className="text-3xl sm:text-4xl font-extrabold mt-2 sm:mt-3">$5<span className="text-base sm:text-lg font-normal text-gray-500">/month</span></div>
                <div className="text-xs sm:text-sm text-gray-500 mt-1">10 credits every month</div>

                <ul className="mt-3 sm:mt-4 space-y-1.5 sm:space-y-2 text-xs sm:text-sm text-gray-700 text-left sm:text-center">
                  <li>✓ Resume Constructor: 5 live AI suggestions you can accept or reject</li>
                  <li>✓ Critical gaps based on the job description</li>
                  <li>✓ Matching keywords + missing keywords + fit estimate</li>
                  <li>✓ Advanced insights</li>
                  <li>✓ Cancel anytime</li>
                </ul>

                <button
                  onClick={() => startCheckout("pro")}
                  disabled={processing}
                  className="mt-4 sm:mt-6 w-full rounded-full bg-indigo-600 text-white py-2.5 sm:py-3 text-sm sm:text-base font-semibold disabled:opacity-60"
                >
                  {processing ? "Processing…" : "Subscribe Now"}
                </button>
              </div>
            </div>
          )}

          {/* Custom Credits - One Time */}
          <div className="rounded-xl border p-4 sm:p-6">
            <div className="text-center">
              <div className="text-base sm:text-lg font-medium">One-Time Purchase</div>
              <div className="text-xs sm:text-sm text-gray-500 mt-1">$1 per credit • No subscription</div>
            </div>

            <div className="mt-3 sm:mt-4 flex items-center justify-center gap-3 sm:gap-4">
              <button
                type="button"
                onClick={() => setCustomCredits(c => Math.max(1, c - 5))}
                className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg border flex items-center justify-center text-xl hover:bg-gray-50 flex-shrink-0"
              >
                −
              </button>

              <div className="text-center">
                <input
                  type="number"
                  value={customCredits}
                  min={1}
                  onChange={(e) => setCustomCredits(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-20 text-center text-2xl font-bold border rounded-lg py-1"
                />
                <div className="text-xs sm:text-sm text-gray-500 mt-1">{customCredits} credits = ${customCredits}</div>
              </div>

              <button
                type="button"
                onClick={() => setCustomCredits(c => c + 5)}
                className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg border flex items-center justify-center text-xl hover:bg-gray-50 flex-shrink-0"
              >
                +
              </button>
            </div>

            <button
              onClick={() => startCheckout("custom", customCredits)}
              disabled={processing || customCredits < 1}
              className="mt-3 sm:mt-4 w-full rounded-full bg-gray-800 text-white py-2.5 sm:py-3 text-sm sm:text-base font-semibold disabled:opacity-60"
            >
              {processing ? "Processing…" : `Buy ${customCredits} Credits for $${customCredits}`}
            </button>
          </div>

          {msg && (
            <div className="rounded-md bg-red-50 border border-red-100 p-3 text-sm text-red-800">
              {msg}
            </div>
          )}

          <div className="text-right">
            <button onClick={onClose} className="text-sm text-gray-600 hover:underline">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}