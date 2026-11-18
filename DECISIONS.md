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

## Phase 1 - Core pipeline (2026-11-17)

- **Videos stay on the laptop in Phase 1** (`storage/` folder, behind a storage plug): Supabase's free plan caps files at 50 MB and 1 GB in total, and long videos are GBs. Moving to cloud storage in Phase 3 means writing one new storage file, not rewriting the app.
- **Uploads in 8 MB pieces that resume:** a dropped connection on a 2 GB upload continues instead of restarting. The server only accepts a piece at the exact byte where the last one ended, so the file can't get scrambled.
- **The worker talks to Supabase over its REST API with the secret key** (plain `httpx`, no SDK): fewer dependencies, easy to fake in tests. The secret key lives only in `.env` and is only used by the worker.
- **Jobs claimed with `for update skip locked`:** two workers can never take the same job. Jobs left "running" by a closed laptop are re-queued when the worker starts.
- **Retries:** a free-tier "slow down" pauses the job until the provider says to retry and doesn't use up an attempt. Unexpected errors retry 3 times with growing waits. Clear problems (not a video, no sound) fail at once with a plain-English message.
- **Every step saves its result** (transcript parts, transcript, clip list, face track, caption words, each render), so retries continue where they stopped.
- **Groq Whisper `whisper-large-v3`** (not turbo) as the Phase 1 speech-to-text: better Hindi accuracy for a small price difference. The Phase 2 bake-off decides the long-term choice.
- **Audio sent as 16 kHz mono FLAC in ~10-minute pieces, cut in pauses:** stays under Groq's 25 MB free-tier upload limit, is lossless for accuracy, and no word gets cut in half.
- **Language hint: Hindi for "Hinglish" and "Hindi", English for "English", none for auto.** To be tuned in the Phase 2 bake-off.
- **Clips are cut on sentence edges:** the AI picks sentence numbers, not timestamps, so clips never start or end mid-word. Sentences longer than 20 s are split at pauses so clip lengths stay flexible.
- **About 20 clips per hour of video** (brief: 10–30), at least 3, capped by `MAX_CLIPS_PER_VIDEO` (default 10 in Phase 1 to keep laptop render time reasonable). Overlapping picks (more than 40% overlap) are removed, keeping the higher score.
- **Captions in both scripts come from the LLM, per clip** (not the whole video): far fewer AI calls. Numbers become digits and keywords get highlighted. If the AI answers badly, the original words are used, so a clip is never lost.
- **English words in Devanagari captions are written phonetically** (creators → क्रिएटर्स), matching the landing page example and what Hindi creators post.
- **One caption style, "Bold pop":** big bold white text with a thick black outline (readable on gaming footage too), 1–3 words at a time, the spoken word pops 12% bigger, keywords in accent orange. Positioned above the bottom area that Reels/Shorts cover with buttons.
- **Fonts bundled:** Noto Sans Bold and Noto Sans Devanagari Bold (SIL Open Font License, `worker/assets/fonts/OFL.txt`). Devanagari joined letters (क्ष, त्र, श्रृ, द्व) and vowel signs (कि) were checked visually in renders.
- **Face detection: OpenCV's built-in YuNet model** (MIT licence, 230 KB, bundled): runs on CPU, no GPU and no MediaPipe install hassles on Windows. Detection runs on a small 480p, 10 fps proxy copy for speed.
- **Smooth "camera operator" crop:** ignores tiny head movements, glides toward real movement, and jumps instantly on camera cuts. It prefers the face it's already following. If there's a face in less than 35% of the clip, it uses the "fit" layout (whole frame over a blurred background) instead.
- **Crop movement via FFmpeg `sendcmd`**, positions interpolated 15 times per second: one FFmpeg pass per clip, no frame-by-frame Python, so it's fast on a laptop.
- **Output: 1080×1920 H.264 (CRF 21) + AAC 128k, with "faststart"** so it plays instantly in browsers and on phones.
- **Telling two speakers apart and following the one who's talking is Phase 2.** Groq Whisper doesn't label speakers, so Phase 1 follows the most prominent face.
- **Cost logging:** each job records audio seconds, AI tokens and estimated USD from list prices (`pricing.py`). The project page shows cost and cost per video minute. The real bill on free tiers is ₹0.
- **Minimum Python 3.12:** the current numpy requires it, and Windows packages exist for 3.12–3.14.
- **One command still runs everything:** `npm run dev` starts the website and the worker (via `concurrently`). If the worker isn't set up, it prints what to do and the website keeps running.
- **Videos are served only through a login-checked route that builds the file path itself** (never trusting a path stored in the database) and supports seeking (HTTP Range).
- **The Anthropic/Claude provider isn't written yet:** the brief's default is Claude, but we chose free Gemini for Phase 1. Adding Claude is one file in `providers/llm/` when we decide to test it.
- **numpy and OpenCV pinned to older, very widely used releases (numpy 2.2.6, OpenCV 4.11):** on Dyna's Windows laptop, Smart App Control blocked the brand-new OpenCV 5.1 ("An Application Control policy has blocked this file"). It trusts files with a long download history, and these releases have one. Same results in our tests.
- **Face tracking is optional at run time:** if OpenCV can't load, clips still get made with the "fit" layout, and `npm run check-worker` explains why. Switching Smart App Control off is a last resort and Dyna's decision (it may not be easy to turn back on).
