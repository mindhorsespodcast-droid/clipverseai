"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { btnPrimary, input, label } from "@/components/ui";
import { UploadProgress } from "@/components/UploadProgress";
import { createProject } from "../actions";
import { uploadFile, type Progress } from "@/lib/uploader";
import { CONTENT_TYPES, LANGUAGES, SCRIPTS, VIDEO_EXTENSIONS, isAllowedVideo } from "@/lib/upload-rules";

const chip =
  "flex min-h-11 cursor-pointer items-center justify-center rounded-full border border-line bg-surface-2 px-4 text-sm text-fg transition has-[:checked]:border-accent has-[:checked]:bg-accent/10 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent";

export function UploadForm() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = progress !== null;

  // Warn before closing the tab mid-upload.
  useEffect(() => {
    if (!busy) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy]);

  function choose(f: File | undefined) {
    setError(null);
    if (!f) return;
    if (!isAllowedVideo(f.name)) {
      setError("Please choose a video file: MP4, MOV, MKV or WEBM.");
      return;
    }
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").slice(0, 120));
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!file) {
      setError("Please choose a video first.");
      return;
    }
    const form = new FormData(e.currentTarget);
    setError(null);
    setProgress({ sent: 0, total: file.size });
    try {
      const created = await createProject({
        title,
        contentType: String(form.get("contentType")),
        language: String(form.get("language")),
        captionScript: String(form.get("captionScript")),
        filename: file.name,
        size: file.size,
      });
      if (!created.id) throw new Error(created.error);
      await uploadFile(created.id, file, setProgress);
      router.push(`/projects/${created.id}`);
    } catch (err) {
      setProgress(null);
      setError((err as Error).message || "Something went wrong. Please try again.");
    }
  }

  return (
    <form onSubmit={submit} className="space-y-7">
      <div>
        <span className={label} id="file-label">
          Video
        </span>
        <label
          htmlFor="file"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!busy) choose(e.dataTransfer.files[0]);
          }}
          className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-10 text-center transition ${
            dragging ? "border-accent bg-accent/5" : "border-line bg-surface-2 hover:border-muted/60"
          }`}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 16V4m0 0-5 5m5-5 5 5M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="#FF6B3D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {file ? (
            <>
              <span className="max-w-full truncate font-medium text-fg">{file.name}</span>
              <span className="text-sm text-muted">{(file.size / 1024 ** 2).toFixed(0)} MB · tap to change</span>
            </>
          ) : (
            <>
              <span className="font-medium text-fg">Tap to choose a video, or drag it here</span>
              <span className="text-sm text-muted">MP4, MOV, MKV or WEBM · up to 6 hours</span>
            </>
          )}
        </label>
        <input
          ref={fileRef}
          id="file"
          type="file"
          aria-labelledby="file-label"
          accept={VIDEO_EXTENSIONS.map((e) => `.${e}`).join(",") + ",video/*"}
          className="sr-only"
          disabled={busy}
          onChange={(e) => choose(e.target.files?.[0])}
        />
      </div>

      <div>
        <label htmlFor="title" className={label}>
          Project name
        </label>
        <input id="title" className={input} value={title} maxLength={120} disabled={busy}
          onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Episode 42 - Creator economy" />
      </div>

      <fieldset disabled={busy}>
        <legend className={label}>What kind of video is it?</legend>
        <p className="-mt-1 mb-3 text-sm text-muted">This helps the AI pick the right kind of moments.</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {CONTENT_TYPES.map((c, i) => (
            <label key={c.value} className={chip}>
              <input type="radio" name="contentType" value={c.value} defaultChecked={i === 0} className="sr-only" />
              {c.label}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <label htmlFor="language" className={label}>
            Spoken language
          </label>
          <select id="language" name="language" defaultValue="hinglish" disabled={busy} className={input}>
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <fieldset disabled={busy}>
          <legend className={label}>Caption script</legend>
          <div className="grid grid-cols-2 gap-2">
            {SCRIPTS.map((s, i) => (
              <label key={s.value} className={chip}>
                <input type="radio" name="captionScript" value={s.value} defaultChecked={i === 0} className="sr-only" />
                {s.label}
              </label>
            ))}
          </div>
          <p className="mt-2 text-sm text-muted">You can switch any clip later.</p>
        </fieldset>
      </div>

      {error && (
        <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      {progress ? (
        <UploadProgress progress={progress} />
      ) : (
        <button type="submit" className={`${btnPrimary} w-full sm:w-auto`}>
          Upload and find clips
        </button>
      )}
    </form>
  );
}
