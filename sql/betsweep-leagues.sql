-- BetSweep: friend leagues for Beat the model (owner 11/10: "I'd love for us to start 1-3").
-- Run once in the Supabase SQL editor (Dashboard > SQL Editor > New query > paste > Run). Safe to run again.
-- Needs the 11/5 script to have been run first (tables beat_picks and beat_model).
--
-- What it adds: two tables that nobody can read directly, and seven functions the /beat/ page calls.
--   A league is a name and an invite code (betsweep.co/beat/?league=<code>). Joining needs the code and a signed-in account.
--   Only members can see a league's board. The board shows the name each person put on the leaderboard and their hits -
--   never a user id or an e-mail. A league counts the weeks graded after it was created, so everyone starts level.
--   Limits: 10 leagues created per person, 25 leagues joined per person, 200 people per league.

create table if not exists public.beat_leagues (
  id uuid primary key default gen_random_uuid(),
  code text not null unique check (code ~ '^[a-z0-9]{6,12}$'),
  name text not null check (char_length(btrim(name)) between 1 and 40),
  owner_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);
create table if not exists public.beat_league_members (
  league_id uuid not null references public.beat_leagues(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  joined_at timestamptz not null default now(),
  primary key (league_id, user_id)
);
create index if not exists beat_league_members_user on public.beat_league_members (user_id);

-- Row level security is on and there are no policies: the tables are reached only through the functions below.
alter table public.beat_leagues enable row level security;
alter table public.beat_league_members enable row level security;
revoke all on public.beat_leagues from anon, authenticated;
revoke all on public.beat_league_members from anon, authenticated;

-- start a league: returns its code and name; the creator is its first member
create or replace function public.beat_league_create(p_name text)
returns table (code text, name text)
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  v_uid uuid := auth.uid(); v_name text := left(btrim(coalesce(p_name, '')), 40); v_code text; v_id uuid; v_try int := 0;
begin
  if v_uid is null then raise exception 'Sign in first.'; end if;
  if v_name = '' then raise exception 'Give the league a name.'; end if;
  if (select count(*) from beat_leagues l where l.owner_id = v_uid) >= 10 then raise exception 'Ten leagues is the limit for one account.'; end if;
  if (select count(*) from beat_league_members m where m.user_id = v_uid) >= 25 then raise exception 'You are in 25 leagues already.'; end if;
  loop
    v_code := substr(md5(gen_random_uuid()::text), 1, 8);
    begin
      insert into beat_leagues (code, name, owner_id) values (v_code, v_name, v_uid) returning id into v_id;
      exit;
    exception when unique_violation then
      v_try := v_try + 1; if v_try > 5 then raise; end if;
    end;
  end loop;
  insert into beat_league_members (league_id, user_id) values (v_id, v_uid) on conflict do nothing;
  return query select v_code, v_name;
end $$;

-- join with an invite code (joining twice is harmless)
create or replace function public.beat_league_join(p_code text)
returns table (code text, name text)
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  v_uid uuid := auth.uid(); v_id uuid; v_code text; v_name text; v_in boolean;
begin
  if v_uid is null then raise exception 'Sign in first.'; end if;
  select l.id, l.code, l.name into v_id, v_code, v_name from beat_leagues l where l.code = lower(btrim(coalesce(p_code, '')));
  if v_id is null then raise exception 'No league has that code.'; end if;
  select exists (select 1 from beat_league_members m where m.league_id = v_id and m.user_id = v_uid) into v_in;
  if not v_in then
    if (select count(*) from beat_league_members m where m.league_id = v_id) >= 200 then raise exception 'That league is full.'; end if;
    if (select count(*) from beat_league_members m where m.user_id = v_uid) >= 25 then raise exception 'You are in 25 leagues already.'; end if;
    insert into beat_league_members (league_id, user_id) values (v_id, v_uid) on conflict do nothing;
  end if;
  return query select v_code, v_name;
end $$;

-- leave a league. If the owner leaves, the longest-standing member becomes the owner; the last one out closes it.
create or replace function public.beat_league_leave(p_code text)
returns boolean
language plpgsql security definer set search_path = public, pg_temp as $$
declare
  v_uid uuid := auth.uid(); v_id uuid; v_owner uuid; v_next uuid;
begin
  if v_uid is null then raise exception 'Sign in first.'; end if;
  select l.id, l.owner_id into v_id, v_owner from beat_leagues l where l.code = lower(btrim(coalesce(p_code, '')));
  if v_id is null then return false; end if;
  delete from beat_league_members m where m.league_id = v_id and m.user_id = v_uid;
  if not found then return false; end if;
  if v_owner = v_uid then
    select m.user_id into v_next from beat_league_members m where m.league_id = v_id order by m.joined_at, m.user_id limit 1;
    if v_next is null then delete from beat_leagues l where l.id = v_id;
    else update beat_leagues l set owner_id = v_next where l.id = v_id;
    end if;
  end if;
  return true;
end $$;

-- rename (owner only)
create or replace function public.beat_league_rename(p_code text, p_name text)
returns boolean
language plpgsql security definer set search_path = public, pg_temp as $$
declare v_name text := left(btrim(coalesce(p_name, '')), 40);
begin
  if auth.uid() is null then raise exception 'Sign in first.'; end if;
  if v_name = '' then raise exception 'Give the league a name.'; end if;
  update beat_leagues l set name = v_name where l.code = lower(btrim(coalesce(p_code, ''))) and l.owner_id = auth.uid();
  return found;
end $$;

-- close a league for everyone (owner only)
create or replace function public.beat_league_delete(p_code text)
returns boolean
language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if auth.uid() is null then raise exception 'Sign in first.'; end if;
  delete from beat_leagues l where l.code = lower(btrim(coalesce(p_code, ''))) and l.owner_id = auth.uid();
  return found;
end $$;

-- my leagues
create or replace function public.beat_league_mine()
returns table (code text, name text, members bigint, owner boolean, created_at timestamptz)
language sql stable security definer set search_path = public, pg_temp as $$
  select l.code, l.name, (select count(*) from beat_league_members x where x.league_id = l.id), l.owner_id = auth.uid(), l.created_at
  from beat_leagues l join beat_league_members m on m.league_id = l.id and m.user_id = auth.uid()
  order by l.created_at;
$$;

-- a league's board, for its members only: one row per member plus the model. hits / weeks count the weeks graded after the league
-- was created; week_hits / picked are for the week asked about. No user ids, no e-mails.
create or replace function public.beat_league_board(p_code text, p_week int)
returns table (name text, hits bigint, weeks bigint, week_hits int, picked boolean, me boolean, model boolean)
language sql stable security definer set search_path = public, pg_temp as $$
  with l as (
    select bl.id, bl.created_at from beat_leagues bl
    where bl.code = lower(btrim(coalesce(p_code, '')))
      and exists (select 1 from beat_league_members m where m.league_id = bl.id and m.user_id = auth.uid())
  ),
  mem as (select m.user_id, m.joined_at, l.created_at from beat_league_members m join l on l.id = m.league_id),
  brd as (
    select coalesce((select nullif(btrim(p.name), '') from beat_picks p where p.user_id = mem.user_id and nullif(btrim(p.name), '') is not null order by p.week desc limit 1), 'Player') as name,
           coalesce((select sum(p.hits) from beat_picks p where p.user_id = mem.user_id and p.hits is not null and p.graded_at >= mem.created_at), 0)::bigint as hits,
           (select count(*) from beat_picks p where p.user_id = mem.user_id and p.hits is not null and p.graded_at >= mem.created_at) as weeks,
           (select p.hits from beat_picks p where p.user_id = mem.user_id and p.week = p_week) as week_hits,
           exists (select 1 from beat_picks p where p.user_id = mem.user_id and p.week = p_week) as picked,
           mem.user_id = auth.uid() as me, false as model, mem.joined_at
    from mem
    union all
    select 'The model', coalesce(sum(bm.hits), 0)::bigint, count(bm.hits),
           (select x.hits from beat_model x where x.week = p_week), exists (select 1 from beat_model x where x.week = p_week), false, true, null::timestamptz
    from beat_model bm
    where exists (select 1 from l)
      and bm.hits is not null
      and bm.week in (select distinct p.week from beat_picks p, l where p.hits is not null and p.graded_at >= l.created_at)
    having exists (select 1 from l)
  )
  select r.name, r.hits, r.weeks, r.week_hits, r.picked, r.me, r.model from brd r
  order by r.hits desc, r.weeks asc, r.model asc, r.joined_at asc nulls last;
$$;

revoke execute on function public.beat_league_create(text), public.beat_league_join(text), public.beat_league_leave(text),
  public.beat_league_rename(text, text), public.beat_league_delete(text), public.beat_league_mine(), public.beat_league_board(text, int)
  from public, anon;
grant execute on function public.beat_league_create(text), public.beat_league_join(text), public.beat_league_leave(text),
  public.beat_league_rename(text, text), public.beat_league_delete(text), public.beat_league_mine(), public.beat_league_board(text, int)
  to authenticated;

-- tell the API layer the new functions exist (Supabase normally notices on its own; this makes it immediate)
notify pgrst, 'reload schema';
