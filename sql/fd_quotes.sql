-- BetSweep: FanDuel prices typed into the builder (owner 11/25: "keep every FanDuel price you type as a data point").
-- Safe to run twice. There is NO secret in this file: the read function checks the cron secret already stored in feed_private
-- (sql/social_v3.sql), the same one the grading job proves itself with.
--
-- What is kept: the week, the slip's legs (player, market, line, FanDuel's leg price, team, game), FanDuel's price for the whole slip as
-- the reader typed it, and our estimate at that moment. The account is kept on the row only to cap how many one account can send in a
-- day and so that deleting an account deletes its rows; it never leaves the database - fd_quotes_dump() does not return it.

create table if not exists public.fd_quotes (
  id bigserial primary key,
  at timestamptz not null default now(),
  user_id uuid references auth.users(id) on delete cascade,
  week int not null,
  fanduel int not null,                 -- American price for the whole slip, as typed
  est int,                              -- our same-game estimate when it was typed
  src text not null default 'typed',
  legs jsonb not null);
alter table public.fd_quotes enable row level security;            -- no policies: nobody reads or writes the table through the API
create index if not exists fd_quotes_user_at on public.fd_quotes (user_id, at desc);

-- a signed-in reader's typed price. Returns true when the row was kept.
create or replace function public.fd_quote_add(p_week int, p_fanduel int, p_est int, p_src text, p_legs jsonb) returns boolean
language plpgsql security definer set search_path = public as $$
declare uid uuid := auth.uid(); n int;
begin
  if uid is null then return false; end if;
  if p_week is null or p_week < 1 or p_week > 25 then return false; end if;
  if p_fanduel is null or abs(p_fanduel) < 100 or abs(p_fanduel) > 5000000 then return false; end if;
  if p_legs is null or jsonb_typeof(p_legs) <> 'array' or jsonb_array_length(p_legs) < 2 or jsonb_array_length(p_legs) > 12 or length(p_legs::text) > 6000 then return false; end if;
  select count(*) into n from public.fd_quotes where user_id = uid and at > now() - interval '1 day';
  if n >= 60 then return false; end if;
  insert into public.fd_quotes (user_id, week, fanduel, est, src, legs) values (uid, p_week, p_fanduel, p_est, left(coalesce(p_src, 'typed'), 12), p_legs);
  return true;
end $$;
revoke all on function public.fd_quote_add(int, int, int, text, jsonb) from public;
grant execute on function public.fd_quote_add(int, int, int, text, jsonb) to authenticated;

-- the newest 1,000 rows without the account, for the sheet-mirror job (which sends the cron secret)
create or replace function public.fd_quotes_dump(p_secret text) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
  if p_secret is null or p_secret = '__CRON' || '_SECRET__' or p_secret <> (select v from public.feed_private where k = 'cron_secret') then raise exception 'Not allowed'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id', q.id, 'at', q.at, 'week', q.week, 'fanduel', q.fanduel, 'est', q.est, 'src', q.src, 'legs', q.legs) order by q.at desc)
                     from (select * from public.fd_quotes order by at desc limit 1000) q), '[]'::jsonb);
end $$;
revoke all on function public.fd_quotes_dump(text) from public;
grant execute on function public.fd_quotes_dump(text) to anon, authenticated;
