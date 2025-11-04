import React, { useEffect, useState } from "react";

export default function CreditsModal({ onClose }) {
  const [processing, setProcessing] = useState(false);
  const [msg, setMsg] = useState("");
  const [customCredits, setCustomCredits] = useState(15);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose?.();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Pricing: custom pack = $1 per credit
  function calcPriceForCredits(credits) {
    return Math.max(0, Math.floor(credits));
  }

  async function purchasePack(credits, label) {
    const price = calcPriceForCredits(credits);
    setProcessing(true);
    setMsg("");
    try {
      // simulate network / checkout flow
      await new Promise((r) => setTimeout(r, 700));
      setMsg(`Purchased ${label} — ${credits} credits — $${price}`);
    } catch {
      setMsg("Purchase failed");
    } finally {
      setProcessing(false);
    }
  }

  const packs = [
    { id: "pro", name: "Pro Pack", price: "$5", credits: 10, note: "Most popular" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/40"
      role="dialog"
      aria-modal="true"
      onMouseDown={onClose}
    >
      <div
        className="w-full max-w-2xl mx-4 rounded-2xl bg-white shadow-xl overflow-hidden"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start justify-between px-6 pt-6">
          <div>
            <h2 className="text-xl font-semibold">Buy Smart Analysis Credits</h2>
            <p className="mt-1 text-sm text-gray-500">
              Use credits to unlock AI-powered smart analysis with detailed insights and personalized recommendations.
            </p>
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 rounded-full p-2"
          >
            ✕
          </button>
        </div>

        <div className="px-6 py-6 space-y-6">
          {/* Pro Pack card */}
          <div className="rounded-xl border-2 border-indigo-300 p-6">
            <div className="flex justify-center">
              <div className="badge inline-flex items-center bg-indigo-600 text-white px-3 py-1 rounded-full text-sm">Most Popular</div>
            </div>
            <div className="text-center mt-4">
              <div className="text-lg font-medium">Pro Pack</div>
              <div className="text-4xl font-extrabold mt-3">$5</div>
              <div className="text-sm text-gray-500 mt-1">10 credits</div>

              <ul className="mt-4 space-y-2 text-sm text-gray-700">
                <li>✓ 10 Smart Analyses</li>
                <li>✓ Advanced Insights</li>
                <li>✓ Priority Support</li>
                <li>✓ Valid for 6 months</li>
              </ul>

              <button
                onClick={() => purchasePack(10, "Pro Pack")}
                disabled={processing}
                className="mt-6 w-full rounded-full bg-indigo-600 text-white py-3 font-semibold disabled:opacity-60"
              >
                {processing ? "Processing…" : "Purchase"}
              </button>
            </div>
          </div>

          {/* Custom pack */}
          <div className="rounded-xl border p-6 bg-white">
            <div className="text-center">
              <div className="text-lg font-medium">Custom Pack</div>
              <div className="text-sm text-gray-500 mt-1">Choose your own credit amount</div>
            </div>

            <div className="mt-6 flex items-center justify-center gap-6">
              <button
                type="button"
                onClick={() => setCustomCredits((c) => Math.max(1, c - 1))}
                className="w-10 h-10 rounded-lg border flex items-center justify-center text-xl hover:bg-gray-50"
                aria-label="Decrease credits"
              >
                −
              </button>

              <div className="text-center">
                <div className="text-3xl font-extrabold">${calcPriceForCredits(customCredits)}</div>
                <div className="text-sm text-gray-500">
                  <input
                    type="number"
                    value={customCredits}
                    min={1}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      setCustomCredits(Number.isNaN(v) ? 1 : Math.max(1, v));
                    }}
                    className="w-20 text-center bg-transparent outline-none px-2 py-1 text-sm font-medium"
                  />
                  <div className="mt-1">{customCredits} credits</div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setCustomCredits((c) => c + 1)}
                className="w-10 h-10 rounded-lg border flex items-center justify-center text-xl hover:bg-gray-50"
                aria-label="Increase credits"
              >
                +
              </button>
            </div>

            <div className="mt-4 text-center text-sm text-gray-500">
              Pricing: $1 = 1 credit. Edit amount directly or use the buttons.
            </div>

            <div className="mt-6 flex justify-center">
              <button
                onClick={() => purchasePack(customCredits, `Custom ${customCredits}`)}
                disabled={processing || customCredits < 1}
                className="rounded-full bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 font-semibold shadow disabled:opacity-60"

              >
                {processing ? "Processing…" : `Purchase for $${calcPriceForCredits(customCredits)}`}
              </button>
            </div>

            <ul className="mt-6 space-y-2 text-sm text-gray-700">
              <li>✓ Advanced Insights</li>
              <li>✓ Valid for 6 months</li>
            </ul>
          </div>

          {msg && (
            <div className="rounded-md bg-green-50 border border-green-100 p-3 text-sm text-green-800">
              {msg}
            </div>
          )}

          <div className="text-right">
            <button onClick={onClose} className="text-sm text-gray-600 hover:underline">Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}