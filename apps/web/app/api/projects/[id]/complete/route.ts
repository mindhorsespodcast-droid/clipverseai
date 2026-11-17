import { NextResponse, type NextRequest } from "next/server";
import { stat } from "node:fs/promises";
import { createClient } from "@/lib/supabase/server";
import { storagePath } from "@/lib/storage";

// Called after the last piece: check the file is complete, then queue it for processing.
export async function POST(_req: NextRequest, ctx: RouteContext<"/api/projects/[id]/complete">) {
  const { id } = await ctx.params;
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) return NextResponse.json({ error: "Please log in again." }, { status: 401 });

  const { data: project } = await supabase
    .from("projects")
    .select("id, status, source_path, source_size_bytes")
    .eq("id", id)
    .maybeSingle();
  if (!project?.source_path) return NextResponse.json({ error: "Project not found." }, { status: 404 });

  let size = 0;
  try {
    size = (await stat(storagePath(project.source_path))).size;
  } catch {
    /* missing */
  }
  if (size !== Number(project.source_size_bytes)) {
    return NextResponse.json(
      { error: "The upload isn't complete yet. Please keep this page open and try again." },
      { status: 409 },
    );
  }

  const { error } = await supabase.rpc("start_project", { p_project_id: id });
  if (error) {
    const missing = error.code === "PGRST202";
    return NextResponse.json(
      {
        error: missing
          ? "The database needs a quick update first: run supabase/migrations/0002_pipeline.sql in Supabase (README Phase 1, step 2)."
          : "We couldn't start processing. Please refresh and try again.",
      },
      { status: 500 },
    );
  }
  return NextResponse.json({ ok: true });
}
