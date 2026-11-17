// Browser-side resumable uploader: sends the file in 8 MB pieces and retries
// a piece a few times if the internet blips, continuing from where it stopped.
import { CHUNK_BYTES } from "./upload-rules";

export type Progress = { sent: number; total: number };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function serverOffset(projectId: string): Promise<number> {
  const res = await fetch(`/api/projects/${projectId}/upload`, { cache: "no-store" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || "We couldn't check the upload.");
  return body.offset as number;
}

export async function uploadFile(
  projectId: string,
  file: File,
  onProgress: (p: Progress) => void,
): Promise<void> {
  let offset = await serverOffset(projectId);
  onProgress({ sent: offset, total: file.size });

  while (offset < file.size) {
    const piece = file.slice(offset, Math.min(offset + CHUNK_BYTES, file.size));
    let attempt = 0;
    for (;;) {
      try {
        const res = await fetch(`/api/projects/${projectId}/upload`, {
          method: "PUT",
          headers: { "Upload-Offset": String(offset), "Content-Type": "application/octet-stream" },
          body: piece,
        });
        const body = await res.json().catch(() => ({}));
        if (res.status === 409 && typeof body.offset === "number") {
          offset = body.offset; // server has a different amount: continue from there
          break;
        }
        if (!res.ok) throw new Error(body.error || `Upload error ${res.status}`);
        offset = body.offset;
        break;
      } catch (e) {
        attempt += 1;
        if (attempt >= 6) {
          throw new Error(
            "The upload keeps getting interrupted. Check your internet, then open this project again to continue from where it stopped.",
            { cause: e },
          );
        }
        await sleep(Math.min(30_000, 1000 * 2 ** attempt));
        offset = await serverOffset(projectId).catch(() => offset);
      }
    }
    onProgress({ sent: offset, total: file.size });
  }

  const res = await fetch(`/api/projects/${projectId}/complete`, { method: "POST" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || "We couldn't start processing.");
}
