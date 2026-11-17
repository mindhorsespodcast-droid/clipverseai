# Decisions

One line per important choice, and why. Newest at the bottom of each phase.

## Phase 0 - Setup (2026-11-17)

- **Free stack for the prototype:** Groq (Whisper) for speech-to-text and Google Gemini for moment picking, both on free tiers. Dyna asked for ₹0 running cost while we prototype. Claude and Deepgram stay as swap-in options behind the provider interfaces.
- **Gemini free tier is for our own test videos only:** Google may use free-tier data to improve its products, which is not OK for customers' videos. We switch to a paid tier or another provider before real users upload.
- **Email + password login only:** "Sign in with Google" moves to Phase 3. It needs a Google Cloud setup and isn't needed to prototype.
- **Supabase free cloud project, not local:** running Supabase locally needs Docker, a large extra install. The free cloud tier is enough for Phase 0-1 testing.
- **Mumbai region for Supabase:** closest to Indian users, so the app feels faster.
- **One repo, two apps:** `apps/web` (Next.js website) and, from Phase 1, `worker/` (Python video processing). Simple to run, no microservices.
- **npm workspaces at the root:** `npm install` and `npm run dev` from the main folder. That's the "one command" rule.
- **One `.env` at the repo root:** the website and the Python worker share the same keys file. `next.config.ts` loads it explicitly, because Next.js normally only looks inside `apps/web`.
- **Next.js 16 (latest), Tailwind CSS v4, TypeScript:** the brief's default stack.
- **Cache Components switched off:** this new Next.js caching feature adds complexity around login cookies. Pages load fresh each time, which is fine at our size. We can revisit for speed later.
- **Login check in `proxy.ts`** (Next.js 16's new name for "middleware"): it keeps logins fresh and sends logged-out people to /login. The dashboard also re-checks the user itself, so it doesn't rely on the proxy alone.
- **Supabase "publishable" key (`sb_publishable_`) in the browser, "secret" key only on servers:** Supabase's current key system. The secret key is never sent to the browser.
- **Row Level Security on every table:** each user can only see their own projects, clips, jobs and usage. Tested with two fake users on a real Postgres. Users can't change their own plan (a database trigger blocks it).
- **Phase 0 tables: profiles, projects, transcripts, clips, jobs, usage_ledger.** Workspaces, plans, subscriptions, brand_kits and exports are added in the phase that needs them, to avoid building unused tables now.
- **Jobs table doubles as the queue:** the worker will poll it. Cost columns (`minutes_processed`, `cost_estimate_usd`, `cost_breakdown`) are there from day one to track cost per minute.
- **Transcript words stored as JSON** (`[{w, start, end, speaker}]`) in one row per project: simple, fast to load in the editor, and good enough for 6-hour videos.
- **Fonts via `next/font`** (Inter + Inter Tight): downloaded once at build time and served from our own site, so there are no font requests to Google from users' browsers.
- **Plain-English errors:** Supabase error codes are translated in `app/(auth)/actions.ts`, and a setup notice appears when keys are missing instead of a crash.
- **Known, accepted:** `npm audit` reports high-severity issues only in code-checking tools (ESLint's file-matching libraries). They're not in the website itself, so no action now; they'll be fixed when those tools update.
