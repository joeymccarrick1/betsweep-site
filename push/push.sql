-- BetSweep slip alerts: run once in the Supabase SQL editor (project fuwiqijgkgbzvnfnsans).
-- 1) where each device's push subscription lives (each signed-in user manages only their own rows)
create table if not exists public.push_subs (
  endpoint   text primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  p256dh     text not null,
  auth       text not null,
  ua         text,
  created_at timestamptz not null default now()
);
alter table public.push_subs enable row level security;
drop policy if exists "own subs" on public.push_subs;
create policy "own subs" on public.push_subs for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 2) alerts already sent (one per user, week, player, status) - only the alert function (service role) reads or writes it
create table if not exists public.push_sent (
  user_id uuid not null references auth.users(id) on delete cascade,
  week    int  not null,
  player  text not null,
  status  text not null,
  sent_at timestamptz not null default now(),
  primary key (user_id, week, player, status)
);
alter table public.push_sent enable row level security;

-- 3) run the alert function every 10 minutes
create extension if not exists pg_cron;
create extension if not exists pg_net;
select cron.unschedule('betsweep-slip-alerts') where exists (select 1 from cron.job where jobname = 'betsweep-slip-alerts');
select cron.schedule('betsweep-slip-alerts', '*/10 * * * *', $$
  select net.http_post(
    url     := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-cron-secret', '__CRON_SECRET__'),
    body    := '{}'::jsonb);
$$);

-- 4) (10/30 evening) per-device choices for live slip updates and the Thursday Model's Best note
alter table public.push_subs add column if not exists live boolean not null default true;
alter table public.push_subs add column if not exists weekly boolean not null default true;

-- 5) Thursday 9 AM Central (15:00 UTC in standard time): "This week's Model's Best is up"
select cron.unschedule('betsweep-weekly-best') where exists (select 1 from cron.job where jobname = 'betsweep-weekly-best');
select cron.schedule('betsweep-weekly-best', '0 15 * * 4', $$
  select net.http_post(
    url     := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-cron-secret', '__CRON_SECRET__'),
    body    := '{"mode":"weekly"}'::jsonb);
$$);
