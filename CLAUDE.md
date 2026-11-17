# ClipVerse AI - Build Brief for Claude Code

You are building **ClipVerse AI**, a web app that turns long videos into short, captioned, vertical clips (Reels, YouTube Shorts) for Indian creators. The owner (Dyna) is a marketer, not a developer. Explain decisions in plain English, keep her in the loop, and never assume she knows a technical term.

---

## 1. Product in one paragraph

A creator uploads a long video (podcast, gaming stream, vlog, live class, webinar, interview - up to 6 hours). ClipVerse AI transcribes it with accurate **Hindi / Hinglish / English** speech-to-text, finds the moments worth posting, scores each clip with a one-line reason, reframes it to 9:16 with the right layout, adds captions in Roman Hinglish, Devanagari or English, and lets the creator edit and export or post. The edge over global tools (OpusClip, Klap, Vizard): **it gets Hinglish right, picks moments Indian audiences actually share, and is priced in rupees with UPI.**

---

## 2. How to work with me (rules for Claude Code)

1. **Work in phases** (section 6). Finish, run and demo one phase before starting the next. At the end of each phase, tell me what works, what doesn't, and how to try it.
2. **Plan first.** Before writing code for a phase, show a short plan and wait for my OK.
3. **Ask before anything that costs money** - paid APIs, cloud services, new subscriptions. List the cost model in one line.
4. **Secrets:** all keys go in `.env` (never committed). Keep `.env.example` updated. Add `.env` to `.gitignore` on day one.
5. **Keep a `README.md`** with: how to run locally, what each service does, and which keys are needed.
6. **Keep a `DECISIONS.md`** - one line per important choice and why.
7. **Pluggable providers:** speech-to-text, LLM and storage must sit behind small interfaces so we can swap vendors without rewriting the app.
8. **Track cost per job:** every processing job logs minutes processed and estimated API cost. We must know our cost per minute of video.
9. **Prefer simple and boring tech.** No microservices until we need them.
10. **Test with real Hinglish content.** Keep a `samples/` folder (gitignored) and an evaluation script (section 9).

---

## 3. Tech stack (default - propose changes if you have a strong reason)

| Part | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind CSS |
| Auth, database, file storage | Supabase (Postgres, Auth, Storage with resumable uploads) |
| Processing worker | Python 3.11+ service: FFmpeg, OpenCV / MediaPipe for face tracking |
| Job queue | Start with a `jobs` table in Postgres that the worker polls; move to Redis + a proper queue only when needed |
| Speech-to-text | Provider interface. Evaluate Hinglish accuracy of 2-3 options (e.g. Sarvam AI, Deepgram, OpenAI, local faster-whisper) on our sample set before choosing. Must return **word-level timestamps** |
| Moment picking, titles, hashtags | Anthropic Claude API via a provider interface; model name in an env var |
| Captions rendering | ASS subtitles burned in with FFmpeg/libass. Bundle Noto Sans + Noto Sans Devanagari; verify Devanagari renders correctly (conjuncts, matras) |
| Payments | Razorpay subscriptions with UPI autopay |
| Emails | Resend (or similar) |
| Hosting (later) | Vercel for the web app; a rented server/VPS for the worker. Local-only during Phases 0-2 |

**No GPU required** for Phases 0-3. Do not add GPU dependencies.

---

## 4. Design system (match our landing page)

- Dark UI: background `#0B0B0D`, surfaces `#111114` / `#141417`, borders `#23232A`, text `#F5F5F7`, secondary text `#A1A1AA`.
- One accent: `#FF6B3D` (use sparingly: scores, active states, key highlights).
- Fonts: **Inter Tight** (headings, semibold, tight letter-spacing), **Inter** (body).
- Rounded cards (16-24px radius), generous spacing, white primary buttons with dark text.
- Logo: "Slice" mark - a rounded 16:9 outline with a tall 9:16 accent bar cut through it, plus the wordmark "ClipVerse AI".
- Mobile-first: every screen must work at 375px wide. Accessible: real buttons, labels, 4.5:1 contrast, 44px tap targets.
- Reference design: https://claude.ai/artifact/2JgvCaSXh5Tzq5vpLXUtnn (landing page + logo).

---

## 5. Full feature list (the "best tool" target)

### A. Input
- Upload video files (mp4, mov, mkv, webm) up to 6 hours, resumable, with progress bar.
- Import from Google Drive / Dropbox link.
- YouTube link import **behind a feature flag, off by default** - downloading from YouTube may break YouTube's Terms of Service; flag this to me and do not enable it without my decision.
- Content-type picker at upload: Podcast/Interview, Gaming, Vlog, Education/Live class, Webinar/Talk, Other. This tunes moment detection and default layout.
- Language: auto-detect, with manual override (Hindi, Hinglish, English; later Tamil, Telugu, Marathi, Bengali).

### B. Transcription
- Word-level timestamps, speaker labels (diarization).
- Handles Hindi-English code-switching mid-sentence.
- Numbers written as digits ("90%", "₹200"), not spelled out.
- Script output: Roman Hinglish, Devanagari, or English translation - switchable per project and per clip (transliteration layer).
- Custom vocabulary per user (names, brand words, game terms like BGMI, Conqueror, chicken dinner).

### C. AI moment detection ("Clip finder")
- Combine signals: transcript (LLM), audio energy/laughter/volume spikes, speaker changes, scene changes.
- Content-type profiles:
  - Podcast/interview: hooks, hot takes, stories, strong opinions, quotable lines.
  - Gaming: hype moments from commentary (screams, laughs, sudden volume), reactions, fails, clutches.
  - Vlog: funny, scenic, relatable, surprising moments.
  - Education: tips, tricks, one-concept explainers, common mistakes, exam-focused bits.
  - Webinar/talk: key takeaways, quotable advice, Q&A highlights.
- Each clip: start/end snapped to sentence boundaries, 15-90 sec (user can set range), **score 0-100 + one-line reason**, auto title.
- "Find moments about…" prompt box: user types a topic ("pricing", "funny moments", "Virat Kohli") and gets clips on that.
- Return 10-30 clips per hour of video, sorted by score; no near-duplicate clips.

### D. Reframing and layouts (9:16, plus 1:1 and 16:9)
- Speaker tracking crop that follows the active speaker (face detection + who is talking).
- Layouts: single speaker, two speakers stacked (podcasts), **facecam-on-top + gameplay below** (gaming), screen + speaker (education/webinar), fit with background.
- Layout chosen automatically by content type, editable per clip; user can save a default.

### E. Captions
- 8-10 styles that match what performs on Reels/Shorts (word-by-word highlight, karaoke, boxed, minimal, bold pop).
- Keyword highlight in accent colour; numbers and names emphasized.
- Fully editable: change words, timing, line breaks, position, size, font, colours.
- Readable over busy backgrounds (gaming) - stroke/box options.
- Optional auto emoji: OFF by default.

### F. Editor
- Transcript-based editing: delete words in the transcript to cut the video.
- Trim handles on a timeline; extend clip into surrounding context.
- Remove silences and filler words (English: um, uh, like; Hinglish: "matlab", "basically", "toh", "na" - configurable, conservative by default).
- Hook title overlay for the first 3 seconds.
- Audio: loudness normalization, background noise reduction option.
- Brand kit: logo watermark, fonts, colours, intro/outro clip, caption preset.
- Undo/redo, autosave.

### G. Output
- Export 1080p (720p on free plan, with watermark), MP4 H.264 + AAC.
- Batch export, ZIP download.
- AI-generated title, description and hashtags per platform, in Hinglish or English.
- Thumbnail/cover frame picker.
- Share link for review (client/team approval).

### H. Publishing (later phase)
- Post and schedule to YouTube Shorts (YouTube Data API) and Instagram Reels (Instagram Graph API - needs a business/creator account and Meta app review; plan for that). LinkedIn later.
- Content calendar view.

### I. Accounts, teams and billing
- Sign up with email or Google (Supabase Auth).
- Plans (launch pricing, configurable in one place):
  - Free: ₹0, 60 min/month, watermark, 720p
  - Creator: ₹499/month, 300 min, no watermark, 1080p, all caption styles
  - Streams & lives: ₹699/month, 1,500 min for long videos
  - Pro: ₹1,199/month, 900 min, brand kit, priority processing
  - Annual: 2 months free
- Minute-based metering; clear "minutes left" meter in the UI; top-up packs.
- Razorpay subscriptions + UPI autopay; GST-ready invoices.
- Free-tier abuse limits (one free account per verified phone/UPI or email + device checks).
- Workspaces for teams/agencies: multiple brands, roles (owner, editor, viewer), shared brand kits.

### J. Dashboard and notifications
- Projects list with status (uploading, transcribing, finding clips, ready).
- Email + in-app notification when clips are ready.
- Usage and billing page.

### K. Admin (internal)
- Users, plans, jobs, failures, cost per job, cost per minute, total minutes processed, free vs paid usage.

### L. Privacy, safety and legal
- Uploads auto-deleted after N days (configurable); finished clips kept until the user deletes them.
- Private by default; signed URLs for all media.
- Privacy policy and terms pages (placeholders - I will get them reviewed). Design with India's DPDP Act in mind (consent, data deletion on request).
- Rate limits, file-type validation, virus/malware-safe handling of uploads.

### M. Later / stretch
- On-screen game event detection for BGMI / Free Fire (kills, wins) - computer vision, will need GPU; design the pipeline so this can plug in later.
- AI dubbing into other Indian languages.
- Performance feedback loop: pull views from connected accounts and use them to improve clip scoring.
- Public API and Zapier/Make integration for agencies.
- Mobile-friendly PWA upload from phone.

---

## 6. Build phases

**Phase 0 - Setup (no paid services)**
Repo, Next.js app with the design system, Supabase project (local or free tier), `.env.example`, README, DECISIONS.md, basic auth, empty dashboard.

**Phase 1 - Core pipeline on my laptop (the prototype)**
Upload → transcription (one provider) → moment detection with Claude → cut clips → speaker-tracking 9:16 crop → burned-in captions (one style, Roman + Devanagari) → preview and download. Process one video end to end. Log cost per minute.

**Phase 2 - Speech-to-text bake-off + quality**
Evaluation script (section 9) comparing 2-3 STT providers on Hinglish samples; pick the winner. Add content-type profiles, all layouts incl. gaming split, caption styles, transcript editor, silence/filler removal.

**Phase 3 - Real product basics**
Plans, minute metering, Razorpay + UPI, emails, project dashboard, brand kit, AI titles/hashtags, "find moments about…", auto-delete, admin page. Deploy: web on Vercel, worker on one rented server.

**Phase 4 - Growth features**
Publishing + scheduling, team workspaces, share-for-review links, more languages, analytics feedback loop.

**Phase 5 - Stretch**
Game event detection (GPU), dubbing, public API.

---

## 7. Data model (starting point)

`users`, `workspaces`, `workspace_members`, `plans`, `subscriptions`, `usage_ledger` (minutes in/out), `projects` (source video, content type, language, status), `transcripts` (words with timestamps, speakers), `clips` (start, end, score, reason, title, layout, caption style, status), `brand_kits`, `jobs` (type, status, attempts, error, cost_estimate, minutes), `exports`.

---

## 8. Pipeline (worker)

1. Download source from storage → normalize audio (16kHz mono for STT) and make a low-res proxy video.
2. Transcribe (word timestamps + speakers) → save.
3. Audio features: loudness curve, laughter/scream spikes, silences.
4. Chunk transcript (with overlap) → Claude scores candidate moments per content-type profile → merge, de-duplicate, snap to sentence boundaries → top N clips.
5. For each clip: face/speaker tracking on the proxy → crop path → render with FFmpeg (layout + captions + brand kit) → upload → mark ready.
6. Update usage ledger and cost log. Notify user.
Every step is resumable and retried on failure; one failed clip never fails the whole project.

---

## 9. Quality bar and evaluation

- `samples/` with 10+ real clips: Hinglish podcast, BGMI stream, vlog, Hindi class, English+Hindi webinar.
- Eval script reports: word error rate per provider, Devanagari/Roman caption correctness, number formatting, processing time per minute, cost per minute.
- Product metrics to track from day one: % of clips exported without edits, caption corrections per clip, time from upload to first clip, week-4 retention, free-to-paid conversion.

---

## 10. Definition of done for each phase

- Runs locally with one command (documented in README).
- I can try it myself with a sample video by following the README.
- No secrets in the repo. Errors are shown to the user in plain language.
- DECISIONS.md and README updated.
