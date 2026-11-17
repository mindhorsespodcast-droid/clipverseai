import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { card } from "@/components/ui";
import { createClient } from "@/lib/supabase/server";
import { UploadForm } from "./UploadForm";

export const metadata: Metadata = { title: "New project · ClipVerse AI" };

export default async function NewProjectPage() {
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) redirect("/login");

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader email={auth.user.email} />
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-8 sm:py-12">
        <Link href="/dashboard" className="mb-6 inline-flex min-h-11 items-center text-sm text-muted hover:text-fg">
          ← Your projects
        </Link>
        <h1 className="text-3xl sm:text-4xl">New project</h1>
        <p className="mt-2 mb-8 text-muted">Upload a long video. We&apos;ll transcribe it and find the best moments.</p>
        <div className={`${card} p-5 sm:p-8`}>
          <UploadForm />
        </div>
      </main>
    </div>
  );
}
