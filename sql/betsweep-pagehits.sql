-- BetSweep page counts (owner 11/10: "Anonymous page counts")
-- How many times each page was opened, per day. One row per (day, page) with a counter and nothing else:
-- no cookie, no visitor id, no IP address, no browser details. Run once in the Supabase SQL editor.
-- The site only starts counting after account.py PAGE_COUNTS is switched on (the privacy page changes in the same build).

create table if not exists public.page_hits (
  day  date   not null default ((now() at time zone 'America/Chicago')::date),
  path text   not null,
  n    bigint not null default 0,
  primary key (day, path)
);
alter table public.page_hits enable row level security;   -- no policies: nobody reads or writes the table directly

create or replace function public.hit(p text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if p is null or length(p) > 80 or p !~ '^/[a-z0-9/_-]*$' then return; end if;
  insert into public.page_hits (day, path, n) values ((now() at time zone 'America/Chicago')::date, p, 1)
  on conflict (day, path) do update set n = public.page_hits.n + 1;
end $$;
revoke all on function public.hit(text) from public;
grant execute on function public.hit(text) to anon, authenticated;

-- Reading it (SQL editor, owner only). Last 7 days, busiest first:
--   select path, sum(n) as views from public.page_hits where day >= current_date - 7 group by 1 order by 2 desc limit 50;
-- Every player page as one line:
--   select case when path like '/player/%' then '/player/*' else path end as page, sum(n) as views
--   from public.page_hits where day >= current_date - 7 group by 1 order by 2 desc;

notify pgrst, 'reload schema';
