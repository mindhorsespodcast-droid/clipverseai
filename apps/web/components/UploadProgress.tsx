"use client";

import type { Progress } from "@/lib/uploader";

const mb = (b: number) => (b / 1024 ** 2 >= 1024 ? `${(b / 1024 ** 3).toFixed(2)} GB` : `${Math.round(b / 1024 ** 2)} MB`);

export function UploadProgress({ progress }: { progress: Progress }) {
  const pct = progress.total ? Math.floor((progress.sent / progress.total) * 100) : 0;
  return (
    <div className="space-y-2" aria-live="polite">
      <div className="flex justify-between text-sm">
        <span className="font-medium text-fg">Uploading… {pct}%</span>
        <span className="text-muted">
          {mb(progress.sent)} of {mb(progress.total)}
        </span>
      </div>
      <div
        className="h-2.5 overflow-hidden rounded-full bg-surface-2"
        role="progressbar"
        aria-label="Upload progress"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-sm text-muted">Keep this tab open until the upload finishes.</p>
    </div>
  );
}
