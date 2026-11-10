-- BetSweep sweat rooms (owner 11/10). Run once in the Supabase SQL editor. Safe to re-run.
-- (Pick'em needs nothing new: it is Beat the model at betsweep.co/beat/, tables beat_picks / beat_model from the 11/5 script.)
--
-- Privacy (audit 11/10): nobody can read WHO is riding a leg or who sent a reaction. Each table is readable only by the row's owner;
-- the Live page gets counts and emoji through two functions that never return a user. (The first draft let anyone read every row,
-- user id included. If that draft was already run, this script replaces its policies.)

-- ================= SWEAT ROOMS =================
-- Who is riding a leg ("I'm on it") and reactions on it. Leg key = "Player|Market|Line", same as the builder.
create table if not exists public.sweat_tails (
  week     int  not null,
  leg      text not null check (length(leg) <= 120),
  user_id  uuid not null default auth.uid() references auth.users (id) on delete cascade,
  at       timestamptz not null default now(),
  primary key (week, leg, user_id)
);
alter table public.sweat_tails enable row level security;
drop policy if exists "tails read" on public.sweat_tails;
drop policy if exists "tails read own" on public.sweat_tails;
create policy "tails read own" on public.sweat_tails for select using (auth.uid() = user_id);
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
drop policy if exists "reacts read own" on public.sweat_reacts;
create policy "reacts read own" on public.sweat_reacts for select using (auth.uid() = user_id);
drop policy if exists "reacts in" on public.sweat_reacts;
-- one reaction per user per leg every 10 seconds (no spam); the check reads the user's own earlier reactions
create policy "reacts in" on public.sweat_reacts for insert with check (
  auth.uid() = user_id and not exists (
    select 1 from public.sweat_reacts r where r.user_id = auth.uid() and r.week = sweat_reacts.week and r.leg = sweat_reacts.leg and r.at > now() - interval '10 seconds'));

-- What the Live page reads. Counts per leg (and whether the caller is one of them), and the latest reactions as emoji + time.
create or replace function public.sweat_counts(p_week int)
returns table (leg text, n bigint, mine boolean)
language sql stable security definer set search_path = public as $$
  select t.leg, count(*)::bigint, coalesce(bool_or(t.user_id = auth.uid()), false)
  from public.sweat_tails t where t.week = p_week group by t.leg
$$;
create or replace function public.sweat_feed(p_week int)
returns table (leg text, emoji text, at timestamptz)
language sql stable security definer set search_path = public as $$
  select r.leg, r.emoji, r.at from public.sweat_reacts r where r.week = p_week order by r.at desc limit 500
$$;
revoke all on function public.sweat_counts(int) from public;
revoke all on function public.sweat_feed(int) from public;
grant execute on function public.sweat_counts(int) to anon, authenticated;
grant execute on function public.sweat_feed(int) to anon, authenticated;

-- The first draft added both tables to the realtime publication, which would broadcast whole rows. The page polls instead.
do $$ begin
  begin alter publication supabase_realtime drop table public.sweat_reacts; exception when others then null; end;
  begin alter publication supabase_realtime drop table public.sweat_tails; exception when others then null; end;
end $$;
