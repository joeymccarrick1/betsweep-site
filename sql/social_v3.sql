-- BetSweep Social v3 (11/16): people. Profiles, follows, tails, one-tap reactions and graded results.
-- Run ONCE in the Supabase SQL editor (Project > SQL editor > New query > paste > Run), on top of the 10/26 install and the 10/27 v2.
-- Safe to run twice. Before running, replace __CRON_SECRET__ (one place, near the end) with the cron secret; never commit the filled copy.

-- ---- 1. profiles: one row per account, made the first time the account opens Social --------------------------------------------
create table if not exists public.feed_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  handle text not null,
  color smallint not null default 0 check (color between 0 and 7),      -- which of the eight avatar colours
  created_at timestamptz not null default now()
);
create index if not exists feed_profiles_handle on public.feed_profiles (handle);
alter table public.feed_profiles enable row level security;
drop policy if exists "read profiles" on public.feed_profiles;
create policy "read profiles" on public.feed_profiles for select using (true);
drop policy if exists "recolor own" on public.feed_profiles;
create policy "recolor own" on public.feed_profiles for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- the handle is assigned (same rule as posts) and can never be edited; only the colour is the user's to change
create or replace function public.feed_profile_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  new.handle := public.feed_handle(new.user_id);
  if tg_op = 'UPDATE' then new.user_id := old.user_id; new.created_at := old.created_at; end if;
  return new;
end $$;
drop trigger if exists feed_profile_guard on public.feed_profiles;
create trigger feed_profile_guard before insert or update on public.feed_profiles for each row execute function public.feed_profile_guard();
-- called by the page for a signed-in account: makes the profile if it is not there and returns it
create or replace function public.feed_profile_me() returns public.feed_profiles language plpgsql security definer set search_path = public as $$
declare r public.feed_profiles;
begin
  if auth.uid() is null then raise exception 'Sign in first'; end if;
  insert into public.feed_profiles (user_id, handle, color)
    values (auth.uid(), public.feed_handle(auth.uid()), mod(('x' || substr(md5(auth.uid()::text), 25, 8))::bit(32)::int::bigint & 2147483647, 8))
    on conflict (user_id) do nothing;
  select * into r from public.feed_profiles where user_id = auth.uid();
  return r;
end $$;
revoke all on function public.feed_profile_me() from public;
grant execute on function public.feed_profile_me() to authenticated;

-- ---- 2. follows ---------------------------------------------------------------------------------------------------------------
create table if not exists public.feed_follows (
  follower uuid not null default auth.uid() references auth.users(id) on delete cascade,
  followee uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (follower, followee),
  check (follower <> followee)
);
create index if not exists feed_follows_followee on public.feed_follows (followee);
alter table public.feed_follows enable row level security;
drop policy if exists "read follows" on public.feed_follows;
create policy "read follows" on public.feed_follows for select using (true);
drop policy if exists "follow own" on public.feed_follows;
create policy "follow own" on public.feed_follows for insert to authenticated with check (auth.uid() = follower);
drop policy if exists "unfollow own" on public.feed_follows;
create policy "unfollow own" on public.feed_follows for delete to authenticated using (auth.uid() = follower);

-- ---- 3. new columns on a post: tail count, reaction counts, graded result ---------------------------------------------------------
alter table public.feed_posts add column if not exists tails int not null default 0;
alter table public.feed_posts add column if not exists rx jsonb not null default '{}'::jsonb;
alter table public.feed_posts add column if not exists result text check (result is null or result in ('won', 'lost', 'push'));
alter table public.feed_posts add column if not exists units numeric(8,2);
alter table public.feed_posts add column if not exists graded_at timestamptz;
create index if not exists feed_posts_user on public.feed_posts (user_id, created_at desc);
-- the insert guard again, so a client cannot post a slip that arrives already tailed, reacted to or graded
create or replace function public.feed_post_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.first_ko <= now() then raise exception 'A leg in this slip has already kicked off'; end if;
  if new.last_ko < new.first_ko or new.last_ko > now() + interval '14 days' then raise exception 'Bad kickoff times'; end if;
  if (select count(*) from public.feed_posts where user_id = new.user_id and created_at > now() - interval '1 day') >= 10 then
    raise exception 'Posting limit reached (10 a day)'; end if;
  if not public.feed_clean(new.title) then raise exception 'Keep the title clean'; end if;
  new.handle := public.feed_handle(new.user_id);
  new.score := 0; new.status := 'open'; new.created_at := now();
  new.tails := 0; new.rx := '{}'::jsonb; new.result := null; new.units := null; new.graded_at := null;
  return new;
end $$;

-- ---- 4. tails: "I'm on this one". Only before the slip's first kickoff; the count lives on the post -------------------------------
create table if not exists public.feed_tails (
  post_id bigint not null references public.feed_posts(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);
create index if not exists feed_tails_user on public.feed_tails (user_id, created_at desc);
alter table public.feed_tails enable row level security;
drop policy if exists "read tails" on public.feed_tails;
create policy "read tails" on public.feed_tails for select using (true);
drop policy if exists "tail own" on public.feed_tails;
create policy "tail own" on public.feed_tails for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "untail own" on public.feed_tails;
create policy "untail own" on public.feed_tails for delete to authenticated using (auth.uid() = user_id);
create or replace function public.feed_tail_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from public.feed_posts p where p.id = new.post_id and p.status = 'open' and p.first_ko > now()) then
    raise exception 'This slip has already kicked off'; end if;
  new.created_at := now();
  return new;
end $$;
drop trigger if exists feed_tail_guard on public.feed_tails;
create trigger feed_tail_guard before insert on public.feed_tails for each row execute function public.feed_tail_guard();
create or replace function public.feed_tail_count() returns trigger language plpgsql security definer set search_path = public as $$
begin
  update public.feed_posts set tails = (select count(*) from public.feed_tails where post_id = coalesce(new.post_id, old.post_id))
   where id = coalesce(new.post_id, old.post_id);
  return null;
end $$;
drop trigger if exists feed_tail_count on public.feed_tails;
create trigger feed_tail_count after insert or delete on public.feed_tails for each row execute function public.feed_tail_count();

-- ---- 5. reactions: one tap, one per account per post, four kinds, no comments ----------------------------------------------------
create table if not exists public.feed_reactions (
  post_id bigint not null references public.feed_posts(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  kind text not null check (kind in ('fire', 'lock', 'fade', 'rip')),
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);
alter table public.feed_reactions enable row level security;
drop policy if exists "read reactions" on public.feed_reactions;
create policy "read reactions" on public.feed_reactions for select using (true);
drop policy if exists "react own" on public.feed_reactions;
create policy "react own" on public.feed_reactions for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "change own reaction" on public.feed_reactions;
create policy "change own reaction" on public.feed_reactions for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "unreact own" on public.feed_reactions;
create policy "unreact own" on public.feed_reactions for delete to authenticated using (auth.uid() = user_id);
create or replace function public.feed_rx_count() returns trigger language plpgsql security definer set search_path = public as $$
declare pid bigint := coalesce(new.post_id, old.post_id);
begin
  update public.feed_posts set rx = coalesce((select jsonb_object_agg(kind, n) from (select kind, count(*) n from public.feed_reactions where post_id = pid group by kind) t), '{}'::jsonb)
   where id = pid;
  return null;
end $$;
drop trigger if exists feed_rx_count on public.feed_reactions;
create trigger feed_rx_count after insert or update or delete on public.feed_reactions for each row execute function public.feed_rx_count();

-- ---- 6. graded results: written only by the grading job, which proves itself with the cron secret ----------------------------------
create table if not exists public.feed_private (k text primary key, v text not null);
alter table public.feed_private enable row level security;            -- no policies: nobody reads it through the API
insert into public.feed_private (k, v) values ('cron_secret', '__CRON_SECRET__') on conflict (k) do update set v = excluded.v;
-- rows = [{"id": 123, "result": "won", "units": 3.08}, ...]; units = profit on a 1-unit stake (lost = -1, push = 0). Returns rows written.
create or replace function public.feed_grade(p_secret text, p_rows jsonb) returns int language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if p_secret is null or p_secret = '__CRON' || '_SECRET__' or p_secret <> (select v from public.feed_private where k = 'cron_secret') then raise exception 'Not allowed'; end if;
  update public.feed_posts p set result = r.result, units = r.units, graded_at = now()
    from jsonb_to_recordset(p_rows) as r(id bigint, result text, units numeric)
   where p.id = r.id and r.result in ('won', 'lost', 'push') and p.last_ko < now();
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.feed_grade(text, jsonb) from public;
grant execute on function public.feed_grade(text, jsonb) to anon, authenticated;

-- ---- 7. each account's record, for the profile view and the "this week's sharps" strip --------------------------------------------
create or replace view public.feed_records with (security_invoker = true) as
  select p.user_id, max(p.handle) as handle,
         count(*) filter (where p.result is not null) as graded,
         count(*) filter (where p.result = 'won') as won,
         count(*) filter (where p.result = 'lost') as lost,
         coalesce(sum(p.units) filter (where p.result is not null), 0)::numeric(10,2) as units,
         count(*) as posts, max(p.created_at) as last_post
    from public.feed_posts p where p.status = 'open' group by p.user_id;
grant select on public.feed_records to anon, authenticated;
