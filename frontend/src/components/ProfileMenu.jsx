// import React, { useEffect, useRef } from "react";
// import { createCheckoutSession } from "../services/apiClient";
// import { supabase } from "../lib/supabaseClient";
// // ...existing code...
// export default function ProfileMenu({ me, onClose, onLogout, onBuyCredits }) {
//   const ref = useRef(null);

//   useEffect(() => {
//     function onDoc(e) {
//       if (ref.current && !ref.current.contains(e.target)) onClose?.();
//     }
//     document.addEventListener("mousedown", onDoc);
//     return () => document.removeEventListener("mousedown", onDoc);
//   }, [onClose]);

//   async function handleBuy() {
//     // prefer parent-provided handler (opens CreditsModal)
//     if (onBuyCredits) {
//       onBuyCredits();
//       return;
//     }

//     try {
//       const sess = await createCheckoutSession();
//       if (sess?.url) {
//         window.location.href = sess.url;
//       } else if (sess?.id) {
//         window.location.href = `/pay/checkout/${sess.id}`;
//       }
//     } catch (e) {
//       console.error("checkout error", e);
//       alert("Could not start checkout.");
//     }
//   }

//   async function handleEdit() {
//     onClose?.();
//     window.location.href = "/profile#edit";
//   }

//   async function handleLogoff() {
//     if (onLogout) {
//       await onLogout();
//     } else {
//       try {
//         await supabase.auth.signOut();
//       } catch {}
//     }
//     onClose?.();
//     window.location.reload();
//   }

//   return (
//     <div ref={ref} className="profile-dropdown" role="menu" aria-label="Profile menu">
//       <div className="profile-dropdown-header">
//         <div className="profile-dropdown-name">{me.full_name || me.email.split("@")[0]}</div>
//         <div className="profile-dropdown-email">{me.email}</div>
//       </div>

//       <div className="profile-credits-card">
//         <div className="credits-title">Smart Analysis Credits</div>
//         <div className="credits-value">{(me.credits ?? 0) + " credits"}</div>
//       </div>

//       <button className="profile-item" onClick={handleEdit}>✎ Edit Profile</button>
//       <button className="profile-item" onClick={handleBuy}>💳 Buy Credits</button>
//       <button className="profile-item danger" onClick={handleLogoff}>⤫ Log off</button>
//     </div>
//   );
// }
// ...existing code...


// ...existing code...
import React, { useEffect, useRef } from "react";
import { createCheckoutSession } from "../services/apiClient";
import { supabase } from "../lib/supabaseClient";
// ...existing code...

export default function ProfileMenu({ me, onClose, onLogout, onBuyCredits }) {
  const ref = useRef(null);

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [onClose]);

  async function handleBuy() {
    // prefer parent-provided handler (opens CreditsModal)
    if (onBuyCredits) {
      try {
        onBuyCredits();
      } finally {
        // close the dropdown after triggering modal
        onClose?.();
      }
      return;
    }

    try {
      const sess = await createCheckoutSession();
      if (sess?.url) {
        window.location.href = sess.url;
      } else if (sess?.id) {
        window.location.href = `/pay/checkout/${sess.id}`;
      }
    } catch (e) {
      console.error("checkout error", e);
      alert("Could not start checkout.");
    } finally {
      onClose?.();
    }
  }

  async function handleEdit() {
    onClose?.();
    window.location.href = "/profile#edit";
  }

  async function handleLogoff() {
    if (onLogout) {
      await onLogout();
    } else {
      try {
        await supabase.auth.signOut();
      } catch {}
    }
    onClose?.();
    window.location.reload();
  }

  return (
    <div ref={ref} className="profile-dropdown" role="menu" aria-label="Profile menu">
      <div className="profile-dropdown-header">
        <div className="profile-dropdown-name">{me.full_name || me.email.split("@")[0]}</div>
        <div className="profile-dropdown-email">{me.email}</div>
      </div>

      <div className="profile-credits-card">
        <div className="credits-title">Smart Analysis Credits</div>
        <div className="credits-value">{(me.credits ?? 0) + " credits"}</div>
      </div>

      <button type="button" className="profile-item" onClick={handleEdit}>✎ Edit Profile</button>
      <button type="button" className="profile-item" onClick={handleBuy} aria-label="Buy credits">💳 Buy Credits</button>
      <button type="button" className="profile-item danger" onClick={handleLogoff}>⤫ Log off</button>
    </div>
  );
}