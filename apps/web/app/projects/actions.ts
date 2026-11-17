"use server";

import { randomUUID } from "node:crypto";
import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { sourceKey } from "@/lib/storage";
import {
  CONTENT_TYPES,
  LANGUAGES,
  MAX_UPLOAD_BYTES,
  SCRIPTS,
  extensionOf,
  isAllowedVideo,
} from "@/lib/upload-rules";

type NewProject = {
  title: string;
  contentType: string;
  language: string;
  captionScript: string;
  filename: string;
  size: number;
};

const NEEDS_MIGRATION =
  "The database needs a quick update first: run supabase/migrations/0002_pipeline.sql in Supabase (README Phase 1, step 2).";

export async function createProject(input: NewProject): Promise<{ id?: string; error?: string }> {
  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) return { error: "Please log in again." };

  if (!isAllowedVideo(input.filename)) {
    return { error: "Please choose a video file: MP4, MOV, MKV or WEBM." };
  }
  if (!(input.size > 0) || input.size > MAX_UPLOAD_BYTES) {
    return { error: "This file is too big. The limit is 20 GB (about 6 hours of HD video)." };
  }
  const pick = <T extends readonly { value: string }[]>(list: T, v: string, fallback: string) =>
    list.some((x) => x.value === v) ? v : fallback;

  const id = randomUUID();
  const { error } = await supabase.from("projects").insert({
    id,
    user_id: auth.user.id,
    title: input.title.trim().slice(0, 120) || "Untitled video",
    content_type: pick(CONTENT_TYPES, input.contentType, "other"),
    language: pick(LANGUAGES, input.language, "auto"),
    caption_script: pick(SCRIPTS, input.captionScript, "roman"),
    status: "uploading",
    source_filename: input.filename.slice(0, 255),
    source_size_bytes: input.size,
    source_path: sourceKey(id, extensionOf(input.filename)),
  });
  if (error) {
    return { error: error.code === "PGRST204" ? NEEDS_MIGRATION : "We couldn't create the project. Please try again." };
  }
  return { id };
}

export async function requestClipRender(clipId: string, script: "roman" | "devanagari") {
  const supabase = await createClient();
  const { error } = await supabase.rpc("request_clip_render", { p_clip_id: clipId, p_script: script });
  if (error) return { error: "We couldn't start that. Please refresh and try again." };
  revalidatePath("/projects/[id]", "page");
  return {};
}

export async function retryProject(projectId: string) {
  const supabase = await createClient();
  const { error } = await supabase.rpc("start_project", { p_project_id: projectId });
  if (error) return { error: "We couldn't restart this project. Please refresh and try again." };
  revalidatePath("/projects/[id]", "page");
  return {};
}
