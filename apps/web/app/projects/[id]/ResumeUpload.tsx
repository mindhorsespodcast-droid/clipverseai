"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UploadProgress } from "@/components/UploadProgress";
import { uploadFile, type Progress } from "@/lib/uploader";

/** Finish an upload that was interrupted: pick the same file, continue from where it stopped. */
export function ResumeUpload({ projectId, filename, size }: { projectId: string; filename: string; size: number }) {
  const router = useRouter();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function go(file: File | undefined) {
    if (!file) return;
    if (file.size !== size || file.name !== filename) {
      setError(`That's a different file. Please choose "${filename}" again.`);
      return;
    }
    setError(null);
    setProgress({ sent: 0, total: size });
    try {
      await uploadFile(projectId, file, setProgress);
      router.refresh();
    } catch (e) {
      setProgress(null);
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-muted">
        This upload didn&apos;t finish. Choose <span className="text-fg">{filename}</span> again and we&apos;ll continue
        from where it stopped.
      </p>
      {progress ? (
        <UploadProgress progress={progress} />
      ) : (
        <label className="inline-flex min-h-11 cursor-pointer items-center rounded-full bg-fg px-5 text-sm font-semibold text-bg has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent">
          Choose the file to continue
          <input type="file" className="sr-only" onChange={(e) => go(e.target.files?.[0])} />
        </label>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
