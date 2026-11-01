-- BetSweep Social: run once in the Supabase SQL editor (Project fuwiqijgkgbzvnfnsans > SQL editor > New query > paste > Run)
create table if not exists public.feed_posts (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  handle text not null check (handle ~ '^[A-Za-z0-9_.]{2,20}$'),
  title text check (title is null or char_length(title) <= 60),
  week int not null check (week between 1 and 23),
  legs jsonb not null check (jsonb_typeof(legs) = 'array' and jsonb_array_length(legs) between 1 and 25),
  fd_odds int check (fd_odds is null or fd_odds between -100000 and 10000000),
  first_ko timestamptz not null,
  last_ko timestamptz not null,
  score int not null default 0,
  status text not null default 'open' check (status in ('open', 'hidden')),
  created_at timestamptz not null default now()
);
create index if not exists feed_posts_open on public.feed_posts (status, last_ko, score desc, created_at desc);
create table if not exists public.feed_votes (
  post_id bigint not null references public.feed_posts(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);
create table if not exists public.feed_reports (
  post_id bigint not null references public.feed_posts(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  reason text check (reason is null or char_length(reason) <= 200),
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);
alter table public.feed_posts enable row level security;
alter table public.feed_votes enable row level security;
alter table public.feed_reports enable row level security;
drop policy if exists "read open" on public.feed_posts;
create policy "read open" on public.feed_posts for select using (status = 'open' or auth.uid() = user_id);
drop policy if exists "post own" on public.feed_posts;
create policy "post own" on public.feed_posts for insert to authenticated with check (auth.uid() = user_id and status = 'open' and score = 0);
drop policy if exists "delete own" on public.feed_posts;
create policy "delete own" on public.feed_posts for delete to authenticated using (auth.uid() = user_id);
drop policy if exists "read votes" on public.feed_votes;
create policy "read votes" on public.feed_votes for select using (true);
drop policy if exists "vote own" on public.feed_votes;
create policy "vote own" on public.feed_votes for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "unvote own" on public.feed_votes;
create policy "unvote own" on public.feed_votes for delete to authenticated using (auth.uid() = user_id);
drop policy if exists "report own" on public.feed_reports;
create policy "report own" on public.feed_reports for insert to authenticated with check (auth.uid() = user_id);
-- posting rules enforced on the server: no slip whose first game has already kicked off, at most 10 posts a day per account
create or replace function public.feed_post_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.first_ko <= now() then raise exception 'A leg in this slip has already kicked off'; end if;
  if new.last_ko < new.first_ko or new.last_ko > now() + interval '14 days' then raise exception 'Bad kickoff times'; end if;
  if (select count(*) from public.feed_posts where user_id = new.user_id and created_at > now() - interval '1 day') >= 10 then
    raise exception 'Posting limit reached (10 a day)'; end if;
  new.score := 0; new.status := 'open'; new.created_at := now();
  return new;
end $$;
drop trigger if exists feed_post_guard on public.feed_posts;
create trigger feed_post_guard before insert on public.feed_posts for each row execute function public.feed_post_guard();
-- upvote count kept on the post (users cannot write it directly)
create or replace function public.feed_vote_count() returns trigger language plpgsql security definer set search_path = public as $$
begin
  update public.feed_posts set score = (select count(*) from public.feed_votes where post_id = coalesce(new.post_id, old.post_id))
   where id = coalesce(new.post_id, old.post_id);
  return null;
end $$;
drop trigger if exists feed_vote_count on public.feed_votes;
create trigger feed_vote_count after insert or delete on public.feed_votes for each row execute function public.feed_vote_count();
-- three reports from different accounts hide a post until the owner looks at it
create or replace function public.feed_report_hide() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if (select count(*) from public.feed_reports where post_id = new.post_id) >= 3 then
    update public.feed_posts set status = 'hidden' where id = new.post_id; end if;
  return null;
end $$;
drop trigger if exists feed_report_hide on public.feed_reports;
create trigger feed_report_hide after insert on public.feed_reports for each row execute function public.feed_report_hide();

-- ---- v2 (10/27): assigned handles + clean titles ----------------------------------------------------------------------------
-- Users no longer type a handle: every account gets one made from its id (BlitzRaven42 style - football words + two digits), the
-- same one every time, and the insert trigger overwrites whatever the client sends. Titles are checked against a profanity list
-- on the server (the builder checks the same list first for instant feedback); a dirty title is refused, not posted.
create or replace function public.feed_handle(u uuid) returns text language sql immutable as $$
  select (array['Blitz','Slant','Wheel','Dagger','Flea','Shovel','Sweep','Scramble','Audible','Hurry','Goal','Fourth','Hail','Zone','Press','Dime','Chalk','Fade','Tail','Hammer','Lock','Edge','Pocket','Cover','Prime','Red','Deep','Quick','Iron','Wild'])
         [1 + mod(('x' || substr(md5(u::text), 1, 8))::bit(32)::int::bigint & 2147483647, 30)]
      || (array['Raven','Hawk','Bronco','Jet','Ram','Lion','Bear','Colt','Titan','Viking','Saint','Falcon','Eagle','Giant','Packer','Charger','Chief','Dolphin','Panther','Jaguar','Texan','Bengal','Cowboy','Steeler','Seahawk','Buc','Cardinal','Raider','Bill','Niner'])
         [1 + mod(('x' || substr(md5(u::text), 9, 8))::bit(32)::int::bigint & 2147483647, 30)]
      || lpad((mod(('x' || substr(md5(u::text), 17, 8))::bit(32)::int::bigint & 2147483647, 90) + 10)::text, 2, '0');
$$;
grant execute on function public.feed_handle(uuid) to anon, authenticated;
create or replace function public.feed_clean(t text) returns boolean language plpgsql immutable as $$
declare n text; w text;
begin
  if t is null then return true; end if;
  -- normalise: lowercase, leetspeak -> letters, drop everything that is not a letter
  n := lower(t); n := translate(n, '0134578@$!|', 'oieastbasil');
  n := regexp_replace(n, '[^a-z ]', '', 'g');
  foreach w in array array['fuck','fck','fuk','fvck','phuck','shit','cunt','bitch','asshole','pussy','whore','slut','nigg','retard','kike','chink','wetback','tranny','dyke','twat','jizz','rape','nazi','hitler','porn','blowjob','handjob','motherf','bastard','douche','wank','bollock','arsehole','pedo','paedo'] loop
    if position(w in replace(n, ' ', '')) > 0 then return false; end if;
  end loop;
  foreach w in array array['ass','damn','piss','tit','hoe','sex','anal','nig','fag','coon','dick','cock','cum','spic','cox'] loop
    if n ~ ('(^|\s)' || w || 's?(\s|$)') then return false; end if;
  end loop;
  return true;
end $$;
grant execute on function public.feed_clean(text) to anon, authenticated;
create or replace function public.feed_post_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.first_ko <= now() then raise exception 'A leg in this slip has already kicked off'; end if;
  if new.last_ko < new.first_ko or new.last_ko > now() + interval '14 days' then raise exception 'Bad kickoff times'; end if;
  if (select count(*) from public.feed_posts where user_id = new.user_id and created_at > now() - interval '1 day') >= 10 then
    raise exception 'Posting limit reached (10 a day)'; end if;
  if not public.feed_clean(new.title) then raise exception 'Keep the title clean'; end if;
  new.handle := public.feed_handle(new.user_id);
  new.score := 0; new.status := 'open'; new.created_at := now();
  return new;
end $$;
drop trigger if exists feed_post_guard on public.feed_posts;
create trigger feed_post_guard before insert on public.feed_posts for each row execute function public.feed_post_guard();
-- owner 10/31: a 17-leg slip was refused by the 15-leg limit; raised to 25 (FanDuel's parlay maximum). Run once on an existing project:
alter table public.feed_posts drop constraint if exists feed_posts_legs_check;
alter table public.feed_posts add constraint feed_posts_legs_check check (jsonb_typeof(legs) = 'array' and jsonb_array_length(legs) between 1 and 25);
