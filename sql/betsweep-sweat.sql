-- BetSweep sweat rooms (owner 11/10). Run once in the Supabase SQL editor. Safe to re-run.
-- (Pick'em needs nothing new: it is Beat the model at betsweep.co/beat/, tables beat_picks / beat_model from the 11/5 script.)

-- ================= SWEAT ROOMS =================
-- Who is riding a leg ("I'm on it") and live reactions on it. Leg key = "Player|Market|Line", same as the builder.
create table if not exists public.sweat_tails (
  week     int  not null,
  leg      text not null check (length(leg) <= 120),
  user_id  uuid not null default auth.uid() references auth.users (id) on delete cascade,
  at       timestamptz not null default now(),
  primary key (week, leg, user_id)
);
alter table public.sweat_tails enable row level security;
drop policy if exists "tails read" on public.sweat_tails;
create policy "tails read" on public.sweat_tails for select using (true);
drop policy if exists "tails in" on public.sweat_tails;
create policy "tails in" on public.sweat_tails for insert with check (auth.uid() = user_id);
drop policy if exists "tails out" on public.sweat_tails;
create policy "tails out" on public.sweat_tails for delete using (auth.uid() = user_id);

create table if not exists public.sweat_reacts (
  id       bigint generated always as identity primary key,
  week     int  not null,
  leg      text not null check (length(leg) <= 120),
  user_id  uuid not null default auth.uid() references auth.users (id) on delete cascade,
  emoji    text not null check (emoji in ('🔥', '😬', '💀', '🙏', '💰', '😤')),
  at       timestamptz not null default now()
);
create index if not exists sweat_reacts_leg on public.sweat_reacts (week, leg, at desc);
alter table public.sweat_reacts enable row level security;
drop policy if exists "reacts read" on public.sweat_reacts;
create policy "reacts read" on public.sweat_reacts for select using (true);
drop policy if exists "reacts in" on public.sweat_reacts;
-- one reaction per user per leg every 10 seconds (no spam)
create policy "reacts in" on public.sweat_reacts for insert with check (
  auth.uid() = user_id and not exists (
    select 1 from public.sweat_reacts r where r.user_id = auth.uid() and r.week = sweat_reacts.week and r.leg = sweat_reacts.leg and r.at > now() - interval '10 seconds'));

-- live updates on the Live page
do $$ begin
  begin alter publication supabase_realtime add table public.sweat_reacts; exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.sweat_tails; exception when duplicate_object then null; end;
end $$;
