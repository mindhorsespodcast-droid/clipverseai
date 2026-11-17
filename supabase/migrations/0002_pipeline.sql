-- =====================================================================
-- ClipVerse AI - database setup, part 2 (Phase 1: the video pipeline)
-- HOW TO RUN: Supabase dashboard > SQL Editor > New query >
--             paste this whole file > Run. Run it once, after 0001.
-- =====================================================================

-- ---------- projects: a few more details ----------
alter table public.projects
  add column caption_script    text not null default 'roman'
    check (caption_script in ('roman', 'devanagari')),
  add column source_filename   text,
  add column source_size_bytes bigint,
  -- what the worker is doing right now, e.g. {"detail": "Transcribing part 2 of 5"}
  add column progress          jsonb not null default '{}'::jsonb;

-- ---------- transcripts: sentence-level segments too ----------
alter table public.transcripts
  -- [{ "start": 1.2, "end": 4.8, "text": "..." }, ...]  (used to cut clips on full sentences)
  add column segments jsonb not null default '[]'::jsonb;

-- ---------- clips: per-script outputs, caption words, crop path ----------
alter table public.clips
  drop column output_path,
  -- {"roman": {"status": "ready", "video": "projects/<id>/clips/<clip>-roman.mp4", "thumb": "..."},
  --  "devanagari": {"status": "queued"}}
  add column outputs    jsonb not null default '{}'::jsonb,
  -- caption words: [{ "start": 0.4, "end": 0.7, "text": "...", "roman": "...", "devanagari": "...", "hl": true }]
  add column words      jsonb,
  -- where the 9:16 window sits over time: {"layout": "crop", "points": [[t, x_center], ...]}
  add column crop_track jsonb,
  add column error      text;

-- =====================================================================
-- Functions the WEBSITE may call (as the logged-in user).
-- Each one checks that the project/clip belongs to the caller.
-- =====================================================================

-- Called when an upload finishes: mark the project queued and add a job.
create or replace function public.start_project(p_project_id uuid)
returns void language plpgsql security definer set search_path = '' as $$
declare
  v_user uuid := auth.uid();
begin
  update public.projects
     set status = 'queued', error_message = null, progress = '{}'::jsonb
   where id = p_project_id and user_id = v_user and status in ('uploading', 'failed');
  if not found then
    raise exception 'Project not found or already started';
  end if;

  insert into public.jobs (project_id, user_id, type)
  select p_project_id, v_user, 'process_project'
  where not exists (
    select 1 from public.jobs
     where project_id = p_project_id and type = 'process_project' and status in ('queued', 'running'));
end;
$$;

-- "Make the Devanagari (or Roman) version" button on a clip.
create or replace function public.request_clip_render(p_clip_id uuid, p_script text)
returns void language plpgsql security definer set search_path = '' as $$
declare
  v_user uuid := auth.uid();
  v_project uuid;
begin
  if p_script not in ('roman', 'devanagari') then
    raise exception 'Unknown caption script';
  end if;

  select c.project_id into v_project
    from public.clips c join public.projects p on p.id = c.project_id
   where c.id = p_clip_id and p.user_id = v_user;
  if v_project is null then
    raise exception 'Clip not found';
  end if;

  -- Already made or already on its way? Nothing to do.
  if exists (select 1 from public.clips
              where id = p_clip_id and outputs -> p_script ->> 'status' in ('ready', 'queued', 'rendering')) then
    return;
  end if;

  update public.clips
     set outputs = outputs || jsonb_build_object(p_script, jsonb_build_object('status', 'queued'))
   where id = p_clip_id;

  insert into public.jobs (project_id, user_id, type, payload)
  values (v_project, v_user, 'render_clip', jsonb_build_object('clip_id', p_clip_id, 'script', p_script));
end;
$$;

revoke all on function public.start_project(uuid) from public, anon;
revoke all on function public.request_clip_render(uuid, text) from public, anon;
grant execute on function public.start_project(uuid) to authenticated;
grant execute on function public.request_clip_render(uuid, text) to authenticated;

-- =====================================================================
-- Functions only the WORKER may call (it uses the secret key).
-- =====================================================================

-- Take the next waiting job. "skip locked" means two workers never grab the same job.
create or replace function public.claim_job()
returns setof public.jobs language sql as $$
  update public.jobs j
     set status = 'running', locked_at = now(), attempts = j.attempts + 1
   where j.id = (
     select id from public.jobs
      where status = 'queued' and run_after <= now()
      order by created_at
      for update skip locked
      limit 1)
  returning j.*;
$$;

-- Jobs left "running" by a worker that crashed or was closed go back in the queue.
create or replace function public.requeue_stale_jobs(p_older_than_minutes int default 0)
returns int language sql as $$
  with moved as (
    update public.jobs
       set status = 'queued', locked_at = null
     where status = 'running'
       and locked_at < now() - make_interval(mins => p_older_than_minutes)
    returning 1)
  select count(*)::int from moved;
$$;

revoke all on function public.claim_job() from public, anon, authenticated;
revoke all on function public.requeue_stale_jobs(int) from public, anon, authenticated;
grant execute on function public.claim_job() to service_role;
grant execute on function public.requeue_stale_jobs(int) to service_role;
