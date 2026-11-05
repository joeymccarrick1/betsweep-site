-- BetSweep 11/5 additions (owner: "do all of your out of the box things"). Run once in the Supabase SQL editor after deploying the
-- updated slip-alerts function. Everything here is additive; nothing existing changes.

-- 1) marks that are not per user (Discord posts, model-wide sends, line-move dedupe) - service role only
create table if not exists public.bs_marks (key text primary key, sent_at timestamptz not null default now());
alter table public.bs_marks enable row level security;

-- 2) Sleeper rosters saved by signed-in users (the Fantasy page writes the roster it graded; each user sees only their own)
create table if not exists public.fantasy_rosters (
  user_id    uuid not null references auth.users(id) on delete cascade,
  league_id  text not null,
  league     text,
  sleeper    text,
  starters   jsonb not null default '[]'::jsonb,   -- [{name, pos, team}]
  bench      jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, league_id)
);
alter table public.fantasy_rosters enable row level security;
drop policy if exists "own rosters" on public.fantasy_rosters;
create policy "own rosters" on public.fantasy_rosters for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 3) email digest opt-in (Resend); the account page writes it (the signed-in user's own address), the function reads it
create table if not exists public.email_prefs (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  digest boolean not null default true,
  updated_at timestamptz not null default now()
);
alter table public.email_prefs enable row level security;
drop policy if exists "own email" on public.email_prefs;
create policy "own email" on public.email_prefs for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 4) Ask the model: one row per question (rate limit 20 a day per user; the function enforces it)
create table if not exists public.ask_log (
  id bigserial primary key, user_id uuid references auth.users(id) on delete cascade, asked_at timestamptz not null default now(),
  q text not null, a text, tokens int);
alter table public.ask_log enable row level security;
drop policy if exists "own asks" on public.ask_log;
create policy "own asks" on public.ask_log for select using (auth.uid() = user_id);

-- 5) Beat the model: five legs a week per user, graded on Tuesday by the function (mode "grade")
create table if not exists public.beat_picks (
  user_id uuid not null references auth.users(id) on delete cascade,
  week int not null,
  keys jsonb not null,                 -- ["Player|Market|Line", ...] exactly five
  name text,                           -- display name chosen on the page
  submitted_at timestamptz not null default now(),
  hits int, graded_at timestamptz,
  primary key (user_id, week)
);
alter table public.beat_picks enable row level security;
drop policy if exists "own picks" on public.beat_picks;
create policy "own picks" on public.beat_picks for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "read graded picks" on public.beat_picks;
create policy "read graded picks" on public.beat_picks for select using (true);   -- the leaderboard is public (names only, no emails)
create table if not exists public.beat_model (week int primary key, keys jsonb not null, hits int, frozen_at timestamptz not null default now());
alter table public.beat_model enable row level security;
drop policy if exists "read model picks" on public.beat_model;
create policy "read model picks" on public.beat_model for select using (true);

-- 6) schedules (CST: UTC-6; move an hour earlier in March)
select cron.unschedule('betsweep-inactives') where exists (select 1 from cron.job where jobname = 'betsweep-inactives');
select cron.schedule('betsweep-inactives', '35,5 15-23 * * 0', $$
  select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{"mode":"inactives"}'::jsonb);
$$);
select cron.unschedule('betsweep-inactives-night') where exists (select 1 from cron.job where jobname = 'betsweep-inactives-night');
select cron.schedule('betsweep-inactives-night', '35 23 * * 1,4', $$
  select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{"mode":"inactives"}'::jsonb);
$$);
select cron.unschedule('betsweep-startsit') where exists (select 1 from cron.job where jobname = 'betsweep-startsit');
select cron.schedule('betsweep-startsit', '5 1 * * 0', $$
  select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{"mode":"startsit"}'::jsonb);
$$);
select cron.unschedule('betsweep-email') where exists (select 1 from cron.job where jobname = 'betsweep-email');
select cron.schedule('betsweep-email', '20 15 * * 0,4', $$
  select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{"mode":"email"}'::jsonb);
$$);
select cron.unschedule('betsweep-grade') where exists (select 1 from cron.job where jobname = 'betsweep-grade');
select cron.schedule('betsweep-grade', '40 16 * * 2', $$
  select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{"mode":"grade"}'::jsonb);
$$);
select cron.unschedule('betsweep-recap') where exists (select 1 from cron.job where jobname = 'betsweep-recap');
select cron.schedule('betsweep-recap', '35 5 * * 1,2,5', $$
  select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{"mode":"recap"}'::jsonb);
$$);
-- secrets to add in Supabase > Edge Functions > slip-alerts > Secrets (all optional - a mode without its secret does nothing):
--   DISCORD_WEBHOOK   a channel webhook URL (Discord > channel settings > Integrations > Webhooks)
--   RESEND_API_KEY    from resend.com, with a verified sending domain; EMAIL_FROM like "BetSweep <brief@betsweep.co>"
--   ANTHROPIC_API_KEY for Ask the model (console.anthropic.com); ASK_MODEL defaults to claude-haiku-5-5
