import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { connection } from "next/server";
import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";
import { SetupNotice } from "@/components/SetupNotice";
import { btnPrimary, card } from "@/components/ui";
import { isSupabaseConfigured } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Dashboard · ClipVerse AI" };

type Project = {
  id: string;
  title: string;
  status: string;
  content_type: string;
  created_at: string;
};

const STATUS_LABEL: Record<string, string> = {
  uploading: "Upload not finished",
  queued: "Waiting to start",
  transcribing: "Transcribing",
  finding_clips: "Finding clips",
  rendering: "Making clips",
  ready: "Ready",
  failed: "Needs attention",
};

export default async function DashboardPage() {
  await connection(); // always render fresh, per logged-in user
  if (!isSupabaseConfigured) {
    return (
      <main className="mx-auto w-full max-w-md px-4 py-16">
        <SetupNotice />
      </main>
    );
  }

  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) redirect("/login");

  const { data, error } = await supabase
    .from("projects")
    .select("id, title, status, content_type, created_at")
    .order("created_at", { ascending: false });

  const projects = (data ?? []) as Project[];
  const tablesMissing = error && (error.code === "PGRST205" || error.code === "42P01");

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader email={auth.user.email} />

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:py-12">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl sm:text-4xl">Your projects</h1>
            <p className="mt-2 text-muted">Every long video you upload shows up here.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className={`${card} flex min-h-11 items-center gap-3 px-4`}>
              <span className="h-2 w-2 rounded-full bg-accent" aria-hidden="true" />
              <span className="text-sm text-muted">
                Free plan · <span className="text-fg">60 min</span> / month
              </span>
            </div>
            {projects.length > 0 && (
              <Link href="/projects/new" className={btnPrimary}>
                + New project
              </Link>
            )}
          </div>
        </div>

        {error ? (
          <div role="alert" className={`${card} border-danger/30 p-6`}>
            <h2 className="text-lg">We couldn&apos;t load your projects</h2>
            <p className="mt-2 text-sm text-muted">
              {tablesMissing
                ? "The database tables haven't been created yet. Follow README step 4 (run the setup SQL in Supabase), then refresh this page."
                : "Something went wrong talking to the database. Please refresh in a moment."}
            </p>
          </div>
        ) : projects.length === 0 ? (
          <section className={`${card} flex flex-col items-center px-6 py-14 text-center sm:py-20`}>
            <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-surface-2">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 16V4m0 0-5 5m5-5 5 5M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="#FF6B3D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h2 className="text-2xl">No projects yet</h2>
            <p className="mt-2 max-w-sm text-muted">
              Upload a long video (a podcast, stream, class or vlog) and we&apos;ll find the moments worth posting.
            </p>
            <Link href="/projects/new" className={`${btnPrimary} mt-8`}>
              Upload a video
            </Link>
            <p className="mt-3 text-sm text-muted">MP4, MOV, MKV or WEBM · up to 6 hours</p>
          </section>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/projects/${p.id}`}
                  className={`${card} block p-5 transition hover:border-muted/50`}
                >
                  <h2 className="truncate text-lg">{p.title}</h2>
                  <p className="mt-2 flex items-center gap-2 text-sm text-muted">
                    <span
                      aria-hidden="true"
                      className={`h-2 w-2 rounded-full ${
                        p.status === "ready" ? "bg-accent" : p.status === "failed" ? "bg-danger" : "bg-muted"
                      }`}
                    />
                    {STATUS_LABEL[p.status] ?? p.status} ·{" "}
                    {new Date(p.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
