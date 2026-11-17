// Checks your .env file and tells you, in plain English, what is missing.
// Run it with:  npm run check-env
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const envPath = path.join(root, ".env");

const ok = (msg) => console.log(`  OK    ${msg}`);
const bad = (msg) => console.log(`  FIX   ${msg}`);

console.log("\nChecking your ClipVerse AI settings...\n");

if (!existsSync(envPath)) {
  bad('No ".env" file found in the main clipverseai folder.');
  console.log('        Copy ".env.example", rename the copy to ".env", then fill in your keys.\n');
  process.exit(1);
}

const env = {};
for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
  if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, "");
}

let problems = 0;
const url = env.NEXT_PUBLIC_SUPABASE_URL || "";
const key = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

if (!url || url.includes("your-project-id")) {
  bad("NEXT_PUBLIC_SUPABASE_URL is still the example value. Paste your Supabase Project URL.");
  problems++;
} else if (!/^https:\/\/.+\.supabase\.co\/?$/.test(url)) {
  bad(`NEXT_PUBLIC_SUPABASE_URL looks unusual (${url}). It should look like https://abcd1234.supabase.co`);
  problems++;
} else ok("Supabase URL is filled in");

if (!key || key.includes("xxxx")) {
  bad("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is still the example value. Paste your publishable key.");
  problems++;
} else if (key.startsWith("sb_secret_")) {
  bad("You pasted the SECRET key into NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY. Use the PUBLISHABLE key (sb_publishable_...) instead.");
  problems++;
} else ok("Supabase publishable key is filled in");

if (problems === 0) {
  try {
    const res = await fetch(`${url.replace(/\/$/, "")}/auth/v1/settings`, { headers: { apikey: key } });
    if (res.ok) ok("Connected to Supabase successfully");
    else {
      bad(`Supabase answered with an error (${res.status}). Double-check the URL and the key match the same project.`);
      problems++;
    }
  } catch {
    bad("Could not reach Supabase. Check your internet connection and the Project URL.");
    problems++;
  }
}

console.log(problems ? `\n${problems} thing(s) to fix above.\n` : "\nAll good! Run: npm run dev\n");
process.exit(problems ? 1 : 0);
