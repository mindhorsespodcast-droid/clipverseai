// Shared by the upload form (browser) and the server.
export const VIDEO_EXTENSIONS = ["mp4", "mov", "mkv", "webm"] as const;
export const MAX_UPLOAD_BYTES = 20 * 1024 ** 3; // 20 GB - enough for ~6 hours of 1080p
export const CHUNK_BYTES = 8 * 1024 * 1024; // upload in 8 MB pieces so it can resume

export const CONTENT_TYPES = [
  { value: "podcast", label: "Podcast / Interview" },
  { value: "gaming", label: "Gaming" },
  { value: "vlog", label: "Vlog" },
  { value: "education", label: "Education / Live class" },
  { value: "webinar", label: "Webinar / Talk" },
  { value: "other", label: "Other" },
] as const;

export const LANGUAGES = [
  { value: "auto", label: "Auto-detect" },
  { value: "hinglish", label: "Hinglish" },
  { value: "hi", label: "Hindi" },
  { value: "en", label: "English" },
] as const;

export const SCRIPTS = [
  { value: "roman", label: "Roman Hinglish", sample: "Yeh galti 90% creators karte hain" },
  { value: "devanagari", label: "देवनागरी", sample: "यह गलती 90% क्रिएटर्स करते हैं" },
] as const;

export function extensionOf(filename: string): string {
  return filename.split(".").pop()?.toLowerCase() ?? "";
}

export function isAllowedVideo(filename: string): boolean {
  return (VIDEO_EXTENSIONS as readonly string[]).includes(extensionOf(filename));
}
