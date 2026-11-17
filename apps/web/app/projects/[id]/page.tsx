import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { card } from "@/components/ui";
import { createClient } from "@/lib/supabase/server";
import { CONTENT_TYPES } from "@/lib/upload-rules";
import { AutoRefresh } from "./AutoRefresh";
import { ClipCard, type ClipView } from "./ClipCard";
import { ResumeUpload } from "./ResumeUpload";
import { RetryButton } from "./RetryButton";

export const metadata: Metadata = { title: "Project · ClipVerse AI" };

const STEPS = [
  { key: "queued", label: "Uploaded" },
  { key: "transcribing", label: "Transcribing" },
  { key: "finding_clips", label: "Finding moments" },
  { key: "rendering", label: "Making clips" },
  { key: "ready", label: "Ready" },
];
const IN_PROGRESS = ["queued", "transcribing", "finding_clips", "rendering"];
const USD_TO_INR = Number(process.env.USD_TO_INR || 88);

type Project = {
  id: string;
  title: string;
  status: string;
  content_type: string;
  caption_script: "roman" | "devanagari";
  source_filename: string | null;
  source_size_bytes: number | null;
  source_duration_sec: number | null;
  error_message: string | null;
  progress: { detail?: string; cost_usd?: number; cost_usd_per_min?: number } | null;
};

export default async function ProjectPage({ params }: PageProps<"/projects/[id]">) {
  const { id } = await params;
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) redirect("/login");

  const { data: project } = await supabase
    .from("projects")
    .select(
      "id, title, status, content_type, caption_script, source_filename, source_size_bytes, source_duration_sec, error_message, progress",
    )
    .eq("id", id)
    .maybeSingle<Project>();
  if (!project) notFound();

  const { data: clipRows } = await supabase
    .from("clips")
    .select("id, title, reason, score, start_sec, end_sec, outputs")
    .eq("project_id", id)
    .order("score", { ascending: false });
  const clips = (clipRows ?? []) as ClipView[];

  const busy = IN_PROGRESS.includes(project.status);
  const clipBusy = clips.some((c) =>
    Object.values(c.outputs ?? {}).some((o) => o.status === "queued" || o.status === "rendering"),
  );
  const stepIndex = STEPS.findIndex((s) => s.key === project.status);
  const typeLabel = CONTENT_TYPES.find((c) => c.value === project.content_type)?.label ?? "Video";
  const minutes = project.source_duration_sec ? Math.round(project.source_duration_sec / 60) : null;
  const cost = project.progress?.cost_usd;

  return (
    <div className="flex flex-1 flex-col">
      {(busy || clipBusy) && <AutoRefresh />}
      <AppHeader email={auth.user.email} />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:py-12">
        <Link href="/dashboard" className="mb-6 inline-flex min-h-11 items-center text-sm text-muted hover:text-fg">
          ← Your projects
        </Link>
        <h1 className="text-3xl break-words sm:text-4xl">{project.title}</h1>
        <p className="mt-2 text-sm text-muted">
          {typeLabel}
          {minutes !== null && ` · ${minutes} min`}
          {project.source_filename && ` · ${project.source_filename}`}
        </p>

        {project.status === "uploading" && (
          <section className={`${card} mt-8 p-6`}>
            <ResumeUpload
              projectId={project.id}
              filename={project.source_filename ?? ""}
              size={Number(project.source_size_bytes ?? 0)}
            />
          </section>
        )}

        {busy && (
          <section className={`${card} mt-8 p-6`} aria-live="polite">
            <p className="mb-3 text-sm text-muted sm:hidden">
              Step {stepIndex + 1} of {STEPS.length} · <span className="font-semibold text-fg">{STEPS[stepIndex]?.label}</span>
            </p>
            <ol className="grid grid-cols-5 gap-2">
              {STEPS.map((s, i) => (
                <li key={s.key} className="flex flex-col gap-2">
                  <span className={`h-1.5 rounded-full ${i <= stepIndex ? "bg-accent" : "bg-surface-2"}`} />
                  <span className={`hidden text-xs sm:block ${i === stepIndex ? "font-semibold text-fg" : "text-muted"}`}>
                    <span className="sr-only">{i < stepIndex ? "Done: " : i === stepIndex ? "Now: " : "Next: "}</span>
                    {s.label}
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-5 flex items-center gap-3 text-fg">
              <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-line border-t-accent" aria-hidden="true" />
              {project.progress?.detail ?? "Waiting for the video worker to start…"}
            </p>
            <p className="mt-2 text-sm text-muted">
              You can leave this page. Processing keeps going as long as <code>npm run dev</code> is running.
            </p>
          </section>
        )}

        {project.status === "failed" && (
          <section role="alert" className={`${card} mt-8 border-danger/30 p-6`}>
            <h2 className="text-lg">This video couldn&apos;t be processed</h2>
            <p className="mt-2 mb-5 text-muted">{project.error_message ?? "Something went wrong."}</p>
            <RetryButton projectId={project.id} />
          </section>
        )}

        {clips.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-1 text-2xl">
              {clips.length} {clips.length === 1 ? "clip" : "clips"}
            </h2>
            <p className="mb-6 text-sm text-muted">Sorted by score: how likely each clip is to do well on Reels and Shorts.</p>
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {clips.map((c, i) => (
                <ClipCard key={c.id} clip={c} rank={i + 1} defaultScript={project.caption_script} />
              ))}
            </ul>
          </section>
        )}

        {typeof cost === "number" && project.status === "ready" && (
          <p className="mt-10 text-xs text-muted">
            Processing cost estimate if we were on paid plans: ${cost.toFixed(4)} (≈ ₹{(cost * USD_TO_INR).toFixed(2)}) ·
            ${(project.progress?.cost_usd_per_min ?? 0).toFixed(5)} per minute of video. On today&apos;s free tiers: ₹0.
          </p>
        )}
      </main>
    </div>
  );
}
