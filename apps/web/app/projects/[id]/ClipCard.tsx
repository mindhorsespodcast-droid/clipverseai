"use client";

import { useState, useTransition } from "react";
import { btnPrimary, btnSecondary, card } from "@/components/ui";
import { requestClipRender } from "../actions";

type Output = { status?: string; error?: string };
export type ClipView = {
  id: string;
  title: string | null;
  reason: string | null;
  score: number | null;
  start_sec: number;
  end_sec: number;
  outputs: Record<string, Output>;
};
type Script = "roman" | "devanagari";

const mmss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

export function ClipCard({ clip, defaultScript, rank }: { clip: ClipView; defaultScript: Script; rank: number }) {
  const [script, setScript] = useState<Script>(defaultScript);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const out = clip.outputs?.[script] ?? {};
  const media = (kind: string, extra = "") => `/api/clips/${clip.id}/media?script=${script}&kind=${kind}${extra}`;
  const scriptName = script === "roman" ? "Roman" : "Devanagari";

  return (
    <li className={`${card} flex flex-col overflow-hidden`}>
      <div className="relative aspect-[9/16] w-full bg-surface-2">
        {out.status === "ready" ? (
          <video
            key={script}
            controls
            playsInline
            preload="metadata"
            poster={media("thumb")}
            src={media("video")}
            className="h-full w-full object-cover"
          >
            <track kind="captions" />
          </video>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
            {out.status === "failed" ? (
              <p className="text-sm text-danger">{out.error || "This clip couldn't be made."}</p>
            ) : out.status ? (
              <>
                <span className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-accent" aria-hidden="true" />
                <p className="text-sm text-muted">Making the {scriptName} version…</p>
              </>
            ) : (
              <>
                <p className="text-sm text-muted">No {scriptName} version yet.</p>
                <button
                  type="button"
                  disabled={pending}
                  className={btnSecondary}
                  onClick={() =>
                    start(async () => {
                      const r = await requestClipRender(clip.id, script);
                      setError(r.error ?? null);
                    })
                  }
                >
                  {pending ? "Starting…" : `Make ${scriptName} version`}
                </button>
              </>
            )}
          </div>
        )}
        <span className="absolute top-3 left-3 rounded-full bg-accent px-2.5 py-1 text-xs font-bold text-bg">
          {clip.score ?? "–"}
          <span className="sr-only"> out of 100</span>
        </span>
        <span className="absolute top-3 right-3 rounded-full bg-black/70 px-2.5 py-1 text-xs text-fg">
          {mmss(clip.end_sec - clip.start_sec)}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div>
          <h3 className="text-base leading-snug">
            <span className="sr-only">Clip {rank}: </span>
            {clip.title}
          </h3>
          {clip.reason && <p className="mt-1 text-sm text-muted">{clip.reason}</p>}
          <p className="mt-1 text-xs text-muted">
            From {mmss(clip.start_sec)} to {mmss(clip.end_sec)} in the original
          </p>
        </div>

        <div className="mt-auto flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Caption script" className="flex rounded-full border border-line p-1">
            {(["roman", "devanagari"] as const).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={script === s}
                onClick={() => setScript(s)}
                className={`min-h-9 rounded-full px-3 text-sm ${script === s ? "bg-fg font-semibold text-bg" : "text-muted"}`}
              >
                {s === "roman" ? "Roman" : "देवनागरी"}
              </button>
            ))}
          </div>
          {out.status === "ready" && (
            <a href={media("video", "&download=1")} className={`${btnPrimary} ml-auto`} download>
              Download
            </a>
          )}
        </div>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </li>
  );
}
