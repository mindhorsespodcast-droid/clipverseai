-- =====================================================================
-- ClipVerse AI - database setup, part 1 (Phase 0)
-- HOW TO RUN: Supabase dashboard > SQL Editor > New query >
--             paste this whole file > Run. Safe to run only once.
--
-- Privacy: every table has Row Level Security (RLS) ON, so a logged-in
-- user can only ever see their own rows. The Python worker (Phase 1)
-- uses the secret key, which is allowed to see everything.
--
-- Later phases add: workspaces, workspace_members, plans, subscriptions,
-- brand_kits, exports (see DECISIONS.md).
-- =====================================================================

-- ---------- Lists of allowed values ----------
create type public.content_type as enum
  ('podcast', 'gaming', 'vlog', 'education', 'webinar', 'other');

create type public.language_code as enum
  ('auto', 'hinglish', 'hi', 'en');

create type public.project_status as enum
  ('uploading', 'queued', 'transcribing', 'finding_clips', 'rendering', 'ready', 'failed');

create type public.clip_status as enum
  ('pending', 'rendering', 'ready', 'failed');

create type public.job_status as enum
  ('queued', 'running', 'done', 'failed');

-- ---------- Helper: keep updated_at fresh ----------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------- profiles: one row per user (extra info beside Supabase Auth) ----------
create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  email       text,
  full_name   text,
  plan        text not null default 'free',   -- real billing arrives in Phase 3
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create trigger profiles_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();

-- Create a profile automatically whenever someone signs up.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------- projects: one uploaded long video ----------
create table public.projects (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users (id) on delete cascade,
  title               text not null default 'Untitled video',
  content_type        public.content_type not null default 'other',
  language            public.language_code not null default 'auto',
  status              public.project_status not null default 'uploading',
  source_path         text,           -- where the original video sits in Storage
  source_duration_sec numeric,
  error_message       text,           -- plain-English error shown to the user
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index projects_user_id_idx on public.projects (user_id, created_at desc);
create trigger projects_updated_at before update on public.projects
  for each row execute function public.set_updated_at();

-- ---------- transcripts: words with timestamps + speakers ----------
create table public.transcripts (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null unique references public.projects (id) on delete cascade,
  provider    text not null,          -- e.g. 'groq', 'faster_whisper'
  language    text,
  -- [{ "w": "Yeh", "start": 1.20, "end": 1.38, "speaker": 0 }, ...]
  words       jsonb not null default '[]'::jsonb,
  created_at  timestamptz not null default now()
);

-- ---------- clips: the short videos we cut out ----------
create table public.clips (
  id             uuid primary key default gen_random_uuid(),
  project_id     uuid not null references public.projects (id) on delete cascade,
  start_sec      numeric not null,
  end_sec        numeric not null,
  score          smallint check (score between 0 and 100),
  reason         text,                -- one-line "why this clip"
  title          text,
  layout         text not null default 'auto',
  caption_style  text not null default 'default',
  caption_script text not null default 'roman',  -- roman | devanagari | english
  status         public.clip_status not null default 'pending',
  output_path    text,                -- finished MP4 in Storage
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  check (end_sec > start_sec)
);

create index clips_project_id_idx on public.clips (project_id, score desc);
create trigger clips_updated_at before update on public.clips
  for each row execute function public.set_updated_at();

-- ---------- jobs: the to-do list the worker picks up ----------
create table public.jobs (
  id                 uuid primary key default gen_random_uuid(),
  project_id         uuid references public.projects (id) on delete cascade,
  user_id            uuid not null references auth.users (id) on delete cascade,
  type               text not null,   -- e.g. 'process_project', 'render_clip'
  status             public.job_status not null default 'queued',
  attempts           int not null default 0,
  max_attempts       int not null default 3,
  payload            jsonb not null default '{}'::jsonb,
  error              text,
  run_after          timestamptz not null default now(),
  locked_at          timestamptz,
  -- cost tracking (rule 8 in the brief)
  minutes_processed  numeric not null default 0,
  cost_estimate_usd  numeric(12, 6) not null default 0,
  cost_breakdown     jsonb not null default '{}'::jsonb,  -- {"stt": 0.01, "llm": 0.002}
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index jobs_queue_idx on public.jobs (status, run_after) where status = 'queued';
create trigger jobs_updated_at before update on public.jobs
  for each row execute function public.set_updated_at();

-- ---------- usage_ledger: minutes used (positive) or added (negative) ----------
create table public.usage_ledger (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references auth.users (id) on delete cascade,
  project_id  uuid references public.projects (id) on delete set null,
  minutes     numeric not null,
  reason      text not null,          -- 'processing', 'top_up', 'monthly_reset'
  created_at  timestamptz not null default now()
);

create index usage_ledger_user_idx on public.usage_ledger (user_id, created_at desc);

-- =====================================================================
-- Privacy rules (Row Level Security)
-- =====================================================================
alter table public.profiles     enable row level security;
alter table public.projects     enable row level security;
alter table public.transcripts  enable row level security;
alter table public.clips        enable row level security;
alter table public.jobs         enable row level security;
alter table public.usage_ledger enable row level security;

-- profiles: see and edit only your own (plan can't be changed by the user - see trigger below)
create policy "own profile: read" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "own profile: update" on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

-- Users must not be able to upgrade their own plan.
create or replace function public.protect_profile_plan()
returns trigger language plpgsql as $$
begin
  if new.plan is distinct from old.plan and current_user = 'authenticated' then
    raise exception 'plan can only be changed by billing';
  end if;
  return new;
end;
$$;
create trigger profiles_protect_plan before update on public.profiles
  for each row execute function public.protect_profile_plan();

-- projects: full control over your own
create policy "own projects: read" on public.projects
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own projects: create" on public.projects
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own projects: update" on public.projects
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own projects: delete" on public.projects
  for delete to authenticated using ((select auth.uid()) = user_id);

-- transcripts & clips: readable/editable if the project is yours
create policy "own transcripts: read" on public.transcripts
  for select to authenticated using (
    exists (select 1 from public.projects p where p.id = project_id and p.user_id = (select auth.uid())));

create policy "own clips: read" on public.clips
  for select to authenticated using (
    exists (select 1 from public.projects p where p.id = project_id and p.user_id = (select auth.uid())));
create policy "own clips: update" on public.clips
  for update to authenticated using (
    exists (select 1 from public.projects p where p.id = project_id and p.user_id = (select auth.uid())));
create policy "own clips: delete" on public.clips
  for delete to authenticated using (
    exists (select 1 from public.projects p where p.id = project_id and p.user_id = (select auth.uid())));

-- jobs & usage: read-only for users (only the worker writes them)
create policy "own jobs: read" on public.jobs
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "own usage: read" on public.usage_ledger
  for select to authenticated using ((select auth.uid()) = user_id);
