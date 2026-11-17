import { NextResponse, type NextRequest } from "next/server";
import { mkdir, open, stat } from "node:fs/promises";
import path from "node:path";
import { createClient } from "@/lib/supabase/server";
import { storagePath } from "@/lib/storage";
import { CHUNK_BYTES } from "@/lib/upload-rules";

// Resumable upload in pieces:
//   GET  -> how many bytes we already have
//   PUT  -> add the next piece (header "Upload-Offset" must equal what we have)

async function uploadingProject(id: string) {
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) return { error: NextResponse.json({ error: "Please log in again." }, { status: 401 }) };
  const { data: project } = await supabase
    .from("projects")
    .select("id, status, source_path, source_size_bytes")
    .eq("id", id)
    .maybeSingle();
  if (!project) return { error: NextResponse.json({ error: "Project not found." }, { status: 404 }) };
  if (project.status !== "uploading" || !project.source_path) {
    return { error: NextResponse.json({ error: "This video has already been uploaded." }, { status: 409 }) };
  }
  return { project: project as { id: string; source_path: string; source_size_bytes: number } };
}

async function currentSize(file: string) {
  try {
    return (await stat(file)).size;
  } catch {
    return 0;
  }
}

export async function GET(_req: NextRequest, ctx: RouteContext<"/api/projects/[id]/upload">) {
  const { id } = await ctx.params;
  const { project, error } = await uploadingProject(id);
  if (error) return error;
  return NextResponse.json({ offset: await currentSize(storagePath(project.source_path)) });
}

export async function PUT(req: NextRequest, ctx: RouteContext<"/api/projects/[id]/upload">) {
  const { id } = await ctx.params;
  const { project, error } = await uploadingProject(id);
  if (error) return error;

  const file = storagePath(project.source_path);
  await mkdir(path.dirname(file), { recursive: true });
  const have = await currentSize(file);
  const offset = Number(req.headers.get("upload-offset"));
  if (!Number.isFinite(offset) || offset !== have) {
    return NextResponse.json({ error: "Out of sync", offset: have }, { status: 409 });
  }

  const chunk = Buffer.from(await req.arrayBuffer());
  if (chunk.length === 0 || chunk.length > CHUNK_BYTES) {
    return NextResponse.json({ error: "Bad piece size" }, { status: 400 });
  }
  if (have + chunk.length > project.source_size_bytes) {
    return NextResponse.json({ error: "The file is bigger than expected." }, { status: 400 });
  }

  const fh = await open(file, "a");
  try {
    await fh.write(chunk);
  } finally {
    await fh.close();
  }
  return NextResponse.json({ offset: have + chunk.length });
}
