import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// Keys live in ONE .env file in the main clipverseai folder (shared with the
// Python worker from Phase 1), so load it from two folders up.
// (forceReload=true: Next.js has already looked in apps/web, so make it look again here.)
const repoRoot = path.resolve(process.cwd(), "..", "..");
const isDev = process.env.NODE_ENV !== "production";
const { combinedEnv } = loadEnvConfig(repoRoot, isDev, { info: () => {}, error: console.error }, true);

// Pass the browser-safe NEXT_PUBLIC_* values through to every part of the app.
// Plus the few server-side settings the website reads.
const SERVER_KEYS = ["STORAGE_DIR", "USD_TO_INR"];
const publicEnv = Object.fromEntries(
  Object.entries(combinedEnv).filter(
    (entry): entry is [string, string] =>
      (entry[0].startsWith("NEXT_PUBLIC_") || SERVER_KEYS.includes(entry[0])) && typeof entry[1] === "string",
  ),
);

const nextConfig: NextConfig = {
  env: publicEnv,
  turbopack: {
    root: repoRoot,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
