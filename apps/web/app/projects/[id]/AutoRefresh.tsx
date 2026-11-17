"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Re-checks the project every few seconds while the worker is busy. */
export function AutoRefresh({ every = 4000 }: { every?: number }) {
  const router = useRouter();
  useEffect(() => {
    const t = setInterval(() => router.refresh(), every);
    return () => clearInterval(t);
  }, [router, every]);
  return null;
}
