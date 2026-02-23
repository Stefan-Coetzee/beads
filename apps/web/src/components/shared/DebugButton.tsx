"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getLTIContext } from "@/lib/lti";

/**
 * Floating debug button — visible only to instructors/admins in LTI sessions,
 * or to anyone in standalone mode (no LTI context).
 * Requires NEXT_PUBLIC_DEBUG=true to render at all.
 */
export function DebugButton() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const ctx = getLTIContext();
    // Show if: no LTI session (standalone dev), instructor role, or legacy session
    // that pre-dates the isInstructor field (undefined → show rather than hide).
    if (!ctx || ctx.isInstructor !== false) {
      setShow(true);
    }
  }, []);

  if (!show) return null;

  return (
    <Link
      href="/debug"
      className="fixed bottom-4 right-4 z-50 bg-yellow-500 hover:bg-yellow-400 text-black text-xs font-bold px-3 py-2 rounded-full shadow-lg"
    >
      🔍 Debug
    </Link>
  );
}
