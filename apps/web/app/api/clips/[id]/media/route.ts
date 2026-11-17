import { type NextRequest } from "next/server";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createClient } from "@/lib/supabase/server";
import { clipKey, storagePath } from "@/lib/storage";

// Node's Readable.toWeb() crashes the server when a video player cancels a request
// midway (normal when seeking), so we bridge the file stream by hand and stop cleanly.
function fileStream(file: string, start?: number, end?: number): ReadableStream<Uint8Array> {
  const node = createReadStream(file, { start, end });
  let closed = false;
  return new ReadableStream({
    start(controller) {
      node.on("data", (chunk) => {
        if (closed) return;
        controller.enqueue(new Uint8Array(chunk as Buffer));
        if ((controller.desiredSize ?? 1) <= 0) node.pause();
      });
      node.on("end", () => {
        if (!closed) {
          closed = true;
          controller.close();
        }
      });
      node.on("error", (e) => {
        if (!closed) {
          closed = true;
          controller.error(e);
        }
      });
    },
    pull() {
      node.resume();
    },
    cancel() {
      closed = true;
      node.destroy();
    },
  });
}

// Streams a finished clip (or its thumbnail) - only to the clip's owner.
// Supports "Range" requests so the video player can seek.
export async function GET(req: NextRequest, ctx: RouteContext<"/api/clips/[id]/media">) {
  const { id } = await ctx.params;
  const script = req.nextUrl.searchParams.get("script") === "devanagari" ? "devanagari" : "roman";
  const kind = req.nextUrl.searchParams.get("kind") === "thumb" ? "thumb" : "video";
  const download = req.nextUrl.searchParams.get("download") === "1";

  const supabase = await createClient();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) return new Response("Please log in", { status: 401 });
  // Privacy rules (RLS) mean this only finds clips in the caller's own projects.
  const { data: clip } = await supabase
    .from("clips")
    .select("id, project_id, title, outputs")
    .eq("id", id)
    .maybeSingle();
  const output = (clip?.outputs as Record<string, { status?: string }> | null)?.[script];
  if (!clip || output?.status !== "ready") return new Response("Not found", { status: 404 });

  // Build the path ourselves (never trust a stored path).
  const file = storagePath(clipKey(clip.project_id, clip.id, script, kind));
  let size: number;
  try {
    size = (await stat(file)).size;
  } catch {
    return new Response("Not found", { status: 404 });
  }

  const headers = new Headers({
    "Content-Type": kind === "video" ? "video/mp4" : "image/jpeg",
    "Accept-Ranges": "bytes",
    "Cache-Control": "private, max-age=3600",
  });
  if (download) {
    const safe = (clip.title || "clip").replace(/[^\w\s-]+/g, "").trim().slice(0, 60) || "clip";
    headers.set("Content-Disposition", `attachment; filename="${safe} (${script}).mp4"`);
  }

  const range = req.headers.get("range")?.match(/bytes=(\d*)-(\d*)/);
  if (range && kind === "video") {
    const start = range[1] ? Number(range[1]) : Math.max(0, size - Number(range[2]));
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    if (start >= size || start > end) {
      return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } });
    }
    headers.set("Content-Range", `bytes ${start}-${end}/${size}`);
    headers.set("Content-Length", String(end - start + 1));
    return new Response(fileStream(file, start, end), { status: 206, headers });
  }

  headers.set("Content-Length", String(size));
  return new Response(fileStream(file), { headers });
}
