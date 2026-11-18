# ClipVerse AI

Turns long videos (podcasts, streams, vlogs, classes, webinars) into short, captioned, vertical clips for Reels and YouTube Shorts, with Hinglish captions done right.

**Current status: Phase 2A (Hinglish speech-to-text test).** Phase 1 (the prototype) works end to end. Upload a video. ClipVerse AI transcribes it, picks the best moments with a score and a reason, crops them to 9:16 following the speaker's face, and burns in Roman Hinglish or Devanagari captions. You can preview and download each clip.

The full product brief is in [`CLAUDE.md`](CLAUDE.md). Every important choice and the reason for it is in [`DECISIONS.md`](DECISIONS.md).

---

## What's in this folder

| Folder / file | What it is |
|---|---|
| `apps/web/` | The website (Next.js): pages, login, upload, clip previews. |
| `worker/` | The "video factory" (Python): transcribes, finds moments, crops, adds captions. |
| `worker/assets/` | Bundled fonts (Noto Sans + Noto Sans Devanagari) and the face-detection model. |
| `supabase/migrations/` | Database setup, as SQL files you paste into Supabase, in order. |
| `scripts/` | Helpers: key checker, worker setup, worker launcher. |
| `storage/` | Created automatically: your uploaded videos and finished clips. Private, never uploaded to GitHub. |
| `samples/` | Put your own test videos here. Private, never uploaded to GitHub. |
| `.env.example` | A template listing every key the app needs. |
| `.env` | **Your real keys.** You create it. Never shared or uploaded. |

## What each service does

| Service | Job | Cost |
|---|---|---|
| **Supabase** | Database (projects, clips, jobs) and login | Free tier |
| **Groq** | Speech-to-text (Whisper): every word with its exact timing | Free tier (daily limits) |
| **Google Gemini** | Picks the best moments; converts captions to Roman and Devanagari | Free tier (rate limits) |
| **FFmpeg** (on your computer) | Cuts, crops and renders the clips | Free |

Phase 1 costs **₹0**. Each finished project still shows what it *would* cost on paid plans, so we know our real cost per minute of video.

---

## How the pipeline works

1. **Upload.** The file is sent in 8 MB pieces and resumes if the internet drops. It's saved in `storage/` on your computer.
2. **Check.** It must be a real video, with sound, at most 6 hours long.
3. **Transcript (Groq).** The audio is split at natural pauses into ~10-minute pieces for the free tier, then every word is written down with its timing.
4. **Find moments (Gemini).** The AI reads the transcript in 12-minute windows, guided by the content type (podcast, gaming…). It picks 15–90 second moments that start and end on full sentences, each with a score from 0 to 100, a title and a one-line reason. Overlapping picks are removed.
5. **For each clip:**
   - Face tracking keeps the speaker centred in the 9:16 frame and moves smoothly. If there's no face, the whole frame is shown over a blurred background.
   - Gemini converts the words to Roman Hinglish **and** Devanagari, with numbers as digits ("90%", "₹200").
   - FFmpeg renders a 1080×1920 MP4 with bold captions: the spoken word pops slightly bigger and key words are orange.
6. **Wrap up.** Minutes used and the estimated cost are logged. One failed clip never fails the whole project. If a free-tier limit is hit, the job pauses and continues by itself.

---

## Setup: Phase 0 (website and login)

On **Windows** use **PowerShell**. On **Mac** use **Terminal**.

1. **Check the tools:** `git --version` and `node -v` (you need Node v20.9 or newer).
   - If PowerShell says "running scripts is disabled", run this once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (answer **Y**).
2. **Download the code:**
   ```bash
   git clone https://github.com/mindhorsespodcast-droid/clipverseai.git
   ```
   ```bash
   cd clipverseai
   ```
   ```bash
   git checkout claude/inspiring-noether-eh8chf
   ```
   ```bash
   npm install
   ```
3. **Create a free Supabase project** at supabase.com (region: **South Asia (Mumbai)**). Then create your `.env` file:
   - Windows: `copy .env.example .env` then `notepad .env`
   - Mac: `cp .env.example .env` then `open -e .env`

   Paste in these two values:
   - `NEXT_PUBLIC_SUPABASE_URL`: from **Project Settings → Data API**, the Project URL **without** `/rest/v1/` at the end.
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`: from **Project Settings → API Keys**, the **Publishable** key. Use its copy button, because the key is longer than what's shown.

   Then run `npm run check-env`. It should say **All good!**
4. **Create the database tables.** Copy the setup file:
   - Windows: `Get-Content supabase\migrations\0001_init.sql -Raw | Set-Clipboard`
   - Mac: `pbcopy < supabase/migrations/0001_init.sql`

   Then in Supabase open **SQL Editor → New query**, paste, and click **Run**. You should see "Success. No rows returned".
5. **Auth settings:** in Supabase open **Authentication → URL Configuration**. Set the Site URL to `http://localhost:3000` and add `http://localhost:3000/**` under Redirect URLs.
   - For easy testing, switch off **Authentication → Sign In / Providers → Email → Confirm email**. Turn it back on before real users arrive.
6. **Start the app** with `npm run dev` and open **http://localhost:3000**.

## Setup: Phase 1 (the video worker)

Do these once, in order. Run every command from inside the `clipverseai` folder.

### 1. Get the latest code

```bash
git pull
```

```bash
npm install
```

### 2. Install Python and FFmpeg

**Windows:**

```bash
winget install Python.Python.3.12
```

```bash
winget install Gyan.FFmpeg
```

Then **close PowerShell and open it again**, so Windows notices the new programs. Go back into the folder with `cd ~\clipverseai` and check both are there:

```bash
py -3.12 --version
```

```bash
ffmpeg -version
```

**Mac:** `brew install python@3.12 ffmpeg`

### 3. Set up the worker

```bash
npm run setup:worker
```

This makes a private Python folder (`worker/.venv`) and installs what the worker needs. It ends with "Done!".

### 4. Update the database

Copy the Phase 1 database file:
- Windows: `Get-Content supabase\migrations\0002_pipeline.sql -Raw | Set-Clipboard`
- Mac: `pbcopy < supabase/migrations/0002_pipeline.sql`

Then in Supabase open **SQL Editor → New query**, paste, and click **Run**. You should see "Success. No rows returned".

### 5. Add three keys to `.env`

Open `.env` (`notepad .env` on Windows) and **add these lines at the end**:

```
SUPABASE_SECRET_KEY=
STT_PROVIDER=groq
GROQ_API_KEY=
GROQ_STT_MODEL=whisper-large-v3
LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
```

Then fill in the three keys after their `=` signs:

| Key | Where to get it |
|---|---|
| `SUPABASE_SECRET_KEY` | Supabase → **Project Settings → API Keys** → **Secret keys** → click the 👁 to reveal it, then copy. It starts with `sb_secret_`. **Never share this one.** |
| `GROQ_API_KEY` | Sign in at **console.groq.com** → **API Keys** → **Create API Key** → copy it (it's shown only once). Starts with `gsk_`. |
| `GEMINI_API_KEY` | Sign in at **aistudio.google.com** with your Google account → **Get API key** → **Create API key** → copy it. |

Save the file.

### 6. Check everything

```bash
npm run check-worker
```

Every line should say **OK**. If the Gemini model name isn't available, the check lists the names your key can use: put one in `GEMINI_MODEL`.

### 7. Run it

```bash
npm run dev
```

This one command starts **both** the website (lines marked `[web]`) and the video worker (lines marked `[worker]`). Open **http://localhost:3000**, log in, click **Upload a video**, and choose a 5–20 minute Hinglish video from your `samples/` folder.

---

## How to test Phase 1

1. **Upload:** pick the video, its type (e.g. Podcast) and the language **Hinglish**, then click **Upload and find clips**. The progress bar should reach 100%.
2. **Progress:** the project page moves through *Transcribing → Finding moments → Making clips*. The `[worker]` lines in PowerShell show the same steps. A 10-minute video usually takes a few minutes. Most of that is rendering on your laptop.
3. **Clips:** each card shows a score, length, title and reason. Press play, and check:
   - the speaker's face stays in frame;
   - the captions follow the speech, numbers are digits, and key words are orange.
4. **Devanagari:** on a clip, tap **देवनागरी**, then **Make Devanagari version**. After a minute it plays with Devanagari captions. Check that joined letters like क्ष and त्र and vowel signs like कि look right.
5. **Download:** tap **Download**. The MP4 should play on your phone.
6. **Cost:** at the bottom of a finished project you'll see the estimated cost if we were on paid plans, plus the cost per minute of video.
7. **Resume:** start uploading a big video, close the tab halfway, then open the project from the dashboard and choose the same file again. It continues from where it stopped.

## Phase 2A: the Hinglish speech-to-text test

This finds out which speech-to-text option writes down Hinglish most accurately, using **your** videos.

| Option | Cost | Runs on |
|---|---|---|
| Groq Whisper large-v3 (current default) | Free tier | Internet |
| Groq Whisper large-v3 turbo | Free tier | Internet |
| Oriserve Whisper-Hindi2Hinglish "Swift" | Free (Apache 2.0) | Your laptop |
| Srota (Qwen3-ASR Hinglish) | Free (Apache 2.0) | Your laptop |

### 1. Add your samples

Put **5–10 videos** (or audio files) in the `samples` folder. Only the **first 3 minutes** of each is used, so pick videos where people start talking straight away. Good mix:
- a Hinglish podcast or interview
- a gaming stream with commentary
- a vlog
- a Hindi class or lecture
- an English + Hindi webinar

Use your own videos, or ones you have the rights to. Give them short names like `podcast1.mp4` or `bgmi1.mp4`.

### 2. Install the test toolkit (one time, 1–2 GB)

```bash
npm run eval:setup
```

### 3. Make draft answer keys

```bash
npm run eval:draft
```

This creates a `.txt` file next to each sample (for example `samples/podcast1.txt`) containing a **draft** transcript in Roman Hinglish.

### 4. Correct the answer keys

This is the important part. Open each `.txt` in Notepad, play the first 3 minutes of the video, and fix the text so it matches **exactly what is said**:
- Write in **Roman Hinglish**, the way you'd type it ("yeh", "nahi", "matlab"). English words stay in English.
- Write **numbers as digits**: 90%, ₹200, 2024.
- Don't fix the speaker's grammar. Write what they actually said.
- Fix everything, even if the draft looks "nearly right". The draft comes from one of the options being tested, so lazy corrections would favour it.
- Spelling variations like *hai / he* or *nahi / nahin* are fine. The scoring ignores them.

### 5. Run the test

```bash
npm run eval
```

The first run downloads the two laptop models (about 2 GB). Each laptop model can take a few minutes per sample. At the end it prints the path of **`eval/report.html`**: open it in your browser. It shows, for each option:
- **word mistakes** (lower is better);
- **numbers as digits**;
- **time per minute of audio**;
- **cost per minute**;
- and what each one wrote, side by side.

Results are saved, so running it again only tests what's new. To start over, add `--fresh`: `npm run eval -- --fresh`.

## When something goes wrong

| You see | What to do |
|---|---|
| `[worker] The video worker isn't installed yet` | Run `npm run setup:worker` (Phase 1, step 3). |
| `[worker] ... isn't set up yet` with a list | Add the listed keys to `.env`, then press Ctrl + C and run `npm run dev` again. |
| "The database needs a quick update first" | Run `0002_pipeline.sql` (Phase 1, step 4). |
| Project stuck on "Waiting for the video worker to start…" | Check the PowerShell window is still running `npm run dev` and shows `[worker] ready`. |
| "Paused: Groq/Gemini free-tier limit reached…" | Nothing to do: it continues automatically. When Gemini's limit is reached, the worker switches to the free Groq backup AI by itself. |
| "This video couldn't be processed" | Read the message. It says why (not a video, no sound, too long…). Fix that, then click **Try again** or upload again. |
| `py` or `ffmpeg` "is not recognized" | Close and reopen PowerShell after installing (Phase 1, step 2). |
| "Almost ready: connect Supabase" | `.env` is missing or still has the example values (Phase 0, step 3). |
| "We couldn't reach the login service" | Check your internet and the Supabase URL in `.env`. Run `npm run check-env`. |

## Keys needed (full list)

See `.env.example`.
- **Phase 0:** `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_SITE_URL`
- **Phase 1** adds: `SUPABASE_SECRET_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`

## For developers

- `npm run dev`: website and worker together. `npm run dev:web` or `npm run dev:worker` runs just one.
- `npm run check-env` / `npm run check-worker`: settings checks.
- Worker tests (offline: fake database, fake speech-to-text and fake LLM, plus a generated video):
  `worker/.venv/bin/python -m pip install -r worker/requirements-dev.txt`, then
  `cd worker && .venv/bin/python -m pytest -q`. On Windows use `.venv\Scripts\python`.
  Set `CLIPVERSE_TEST_FACE=/path/to/face.jpg` to test the face-tracking crop.
- **Providers** (swappable, rule 7): `worker/clipverse_worker/providers/{stt,llm,storage}`. Add a vendor as one file, then register it in `providers/__init__.py` and choose it in `.env`.
- **Job queue:** the `jobs` table. The worker claims jobs with `claim_job()` (`for update skip locked`); retries and back-off live in `worker/clipverse_worker/worker.py`.
- **Cost per job:** `jobs.cost_breakdown`, `cost_estimate_usd` and `minutes_processed`. Prices are in `worker/clipverse_worker/pricing.py`.
- This is Next.js 16: route protection is in `apps/web/proxy.ts`, which used to be called "middleware".
