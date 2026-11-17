# ClipVerse AI

Turns long videos (podcasts, streams, vlogs, classes, webinars) into short, captioned, vertical clips for Reels and YouTube Shorts, with Hinglish captions done right.

**Current status: Phase 0 (setup).** You can sign up, log in, and see an empty dashboard. Uploading and clip-making arrive in Phase 1.

The full product brief is in [`CLAUDE.md`](CLAUDE.md). Every important choice and the reason for it is in [`DECISIONS.md`](DECISIONS.md).

---

## What's in this folder

| Folder / file | What it is |
|---|---|
| `apps/web/` | The website (Next.js). Pages, buttons, login. |
| `supabase/migrations/` | The database setup, as SQL you paste into Supabase. |
| `scripts/check-env.mjs` | Checks your keys and tells you in plain English what's wrong. |
| `samples/` | Put your test videos here. Private: never uploaded to GitHub. |
| `.env.example` | A template listing every key the app needs. |
| `.env` | **Your real keys.** You create this. Never shared or uploaded. |
| `worker/`, `eval/` | Coming in Phase 1 and 2 (video processing, speech-to-text tests). |

## What each service does

| Service | Job | Needed from | Cost |
|---|---|---|---|
| **Supabase** | Database (projects, clips), login, video storage | Phase 0 | Free tier |
| **Groq** | Speech-to-text (Whisper) | Phase 1 | Free tier (daily limits) |
| **Google Gemini** | AI that picks the best moments | Phase 1 | Free tier (rate-limited) |

---

## How to run it on your computer (Mac or Windows)

On **Mac**, use the **Terminal** app (press Cmd + Space, type "Terminal").
On **Windows**, use **PowerShell** (Start menu, type "PowerShell").

### Step 1 - Check you have the tools

Type each line and press Enter. If you see a version number, you're good.

```bash
git --version
```

```bash
node -v
```

You need Node **v20.9 or higher** (v22 is best). If either is missing:

- **Mac:** install Homebrew from https://brew.sh, then run `brew install git node`
- **Windows:** run `winget install Git.Git OpenJS.NodeJS.LTS`, then close and reopen PowerShell

### Step 2 - Download the code

```bash
git clone https://github.com/mindhorsespodcast-droid/clipverseai.git
```

```bash
cd clipverseai
```

```bash
git checkout claude/inspiring-noether-eh8chf
```

Then install the app's building blocks (takes a minute or two the first time):

```bash
npm install
```

### Step 3 - Create your free Supabase project and add the keys

1. Go to https://supabase.com, sign up (free) and click **New project**.
   - Name: `clipverseai`
   - Database password: click **Generate**, then save it in your password manager.
   - Region: **Mumbai (ap-south-1)**, closest to your users.
2. Wait about 2 minutes for it to finish setting up.
3. Click **Connect** at the top of the project page (or go to **Project Settings → API Keys**) and copy:
   - the **Project URL** (looks like `https://abcd1234.supabase.co`)
   - the **Publishable key** (starts with `sb_publishable_`)
   - **Do not** use the secret key (`sb_secret_`) here.
4. Make your private `.env` file from the template:
   - **Mac:** `cp .env.example .env`
   - **Windows:** `copy .env.example .env`
5. Open `.env` in a text editor and paste your two values after the `=` signs. No spaces, no quotes.
   - **Mac:** `open -e .env` (TextEdit)
   - **Windows:** `notepad .env`
   - Can't see the file in Finder or Explorer? Files starting with a dot are hidden. On Mac press Cmd + Shift + . to show them. On Windows turn on View → Show → Hidden items.
6. Check it worked:

```bash
npm run check-env
```

You should see `All good!`. If not, it tells you exactly what to fix.

### Step 4 - Create the database tables

1. In Supabase, open **SQL Editor** (left sidebar) and click **New query**.
2. Open the file `supabase/migrations/0001_init.sql` from this folder, copy **everything**, and paste it in.
3. Click **Run**. You should see "Success. No rows returned".
4. Optional check: open **Table Editor**. You should see `profiles`, `projects`, `transcripts`, `clips`, `jobs` and `usage_ledger`.

Only run this file once. Running it twice gives "already exists" errors, which are harmless.

### Step 5 - Tell Supabase where the website lives

In Supabase go to **Authentication → URL Configuration**:

- **Site URL:** `http://localhost:3000`
- **Redirect URLs:** click Add URL and enter `http://localhost:3000/**`

**Tip for quick testing:** Supabase's built-in email service only sends a few emails per hour. To test without waiting for emails, go to **Authentication → Sign In / Providers → Email** and switch **Confirm email** off. Turn it back on before real users arrive.

### Step 6 - Start the app

```bash
npm run dev
```

Open **http://localhost:3000** in your browser. To stop the app, click the Terminal or PowerShell window and press Ctrl + C.

Next time you only need `npm run dev`, from inside the `clipverseai` folder.

---

## How to test Phase 0

1. **Home page:** dark design, Slice logo, "Get free clips" button.
2. **Protected page:** go to http://localhost:3000/dashboard while logged out. You should be sent to the login page.
3. **Sign up:** click "Get free clips", enter your email and a password of 8+ characters.
   - If "Confirm email" is on: you'll see "Almost there!". Open the email on the **same computer and browser**, click the link, and you land on the dashboard.
   - If it's off: you go straight to the dashboard.
4. **Dashboard:** you should see "No projects yet" and your email in the top bar.
5. **Database:** in Supabase → Table Editor → `profiles`, your email should appear as a new row.
6. **Log out**, then **log in** again with a wrong password. You should see a friendly "don't match" message, not a technical error.
7. **Phone size:** in Chrome press F12, then click the phone icon and pick a 375px-wide phone. Nothing should overflow sideways.

## When something goes wrong

| You see | What to do |
|---|---|
| "Almost ready: connect Supabase" | `.env` is missing or still has the example values. Do Step 3, then stop the app (Ctrl + C) and run `npm run dev` again. |
| "We couldn't reach the login service" | Check your internet, and that the URL in `.env` is exactly your Project URL. Run `npm run check-env`. |
| "The database tables haven't been created yet" | Do Step 4. |
| "That confirmation link didn't work" | Open the link in the same browser you signed up in, or sign up again. Also check Step 5. |
| `npm: command not found` / `'npm' is not recognized` | Node isn't installed, or you need to reopen the terminal after installing (Step 1). |
| Port 3000 already in use | Another copy is running. Close the other terminal window, or use the address it prints (e.g. 3001). |

## Keys needed (full list)

See `.env.example`. Phase 0 needs only `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` and `NEXT_PUBLIC_SITE_URL`.

## For developers

- `npm run dev`: start the dev server (the website in `apps/web`)
- `npm run build`: production build
- `npm run lint`: code checks
- `npm run check-env`: check the `.env` keys and test the connection to Supabase
- One `.env` at the repo root is shared by the web app and (from Phase 1) the Python worker. `apps/web/next.config.ts` loads it.
- This is Next.js 16: route protection lives in `apps/web/proxy.ts`, which used to be called "middleware".
