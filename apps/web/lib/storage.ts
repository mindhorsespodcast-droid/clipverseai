import "server-only";
import path from "node:path";

// Storage plug for the website (mirror of worker/clipverse_worker/providers/storage).
// Phase 1: a folder on this computer. Phase 3: cloud storage behind the same functions.

// turbopackIgnore: user videos are data, not code - never bundle them into the website build.
const repoRoot = path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..", "..");
const configured = process.env.STORAGE_DIR || "storage";
export const storageRoot = path.resolve(/*turbopackIgnore: true*/ repoRoot, configured);

/** Turn a storage key like "projects/<id>/source.mp4" into a safe local path. */
export function storagePath(key: string): string {
  const p = path.resolve(/*turbopackIgnore: true*/ storageRoot, key);
  if (!p.startsWith(storageRoot + path.sep)) throw new Error("Invalid storage key");
  return p;
}

export const sourceKey = (projectId: string, ext: string) => `projects/${projectId}/source.${ext}`;
export const clipKey = (projectId: string, clipId: string, script: string, kind: "video" | "thumb") =>
  `projects/${projectId}/clips/${clipId}-${script}.${kind === "video" ? "mp4" : "jpg"}`;
