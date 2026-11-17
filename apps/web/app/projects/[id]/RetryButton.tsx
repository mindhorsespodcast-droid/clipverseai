"use client";

import { useState, useTransition } from "react";
import { btnPrimary } from "@/components/ui";
import { retryProject } from "../actions";

export function RetryButton({ projectId }: { projectId: string }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <div>
      <button
        type="button"
        disabled={pending}
        className={btnPrimary}
        onClick={() => start(async () => setError((await retryProject(projectId)).error ?? null))}
      >
        {pending ? "Restarting…" : "Try again"}
      </button>
      {error && <p role="alert" className="mt-2 text-sm text-danger">{error}</p>}
    </div>
  );
}
