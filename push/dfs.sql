-- BetSweep DFS salaries shared with every visitor (10/30): DraftKings pulled every 3 hours by the slip-alerts function (mode dk),
-- FanDuel shared by the owner from the DFS page ("Share these salaries with everyone"). Run once in the Supabase SQL editor.
create table if not exists public.dfs_salaries (
  site       text not null check (site in ('dk', 'fd')),
  week       int  not null,
  slate      text,
  csv        text not null check (length(csv) < 2000000),
  players    int,
  updated_at timestamptz not null default now(),
  primary key (site, week)
);
alter table public.dfs_salaries enable row level security;

-- who may share salaries from the site: the owner's account only
create or replace function public.bs_is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select lower(coalesce(auth.jwt() ->> 'email', '')) in ('__OWNER_EMAIL__')
$$;
grant execute on function public.bs_is_admin() to anon, authenticated;

drop policy if exists "read salaries" on public.dfs_salaries;
create policy "read salaries" on public.dfs_salaries for select using (true);
drop policy if exists "owner shares salaries" on public.dfs_salaries;
create policy "owner shares salaries" on public.dfs_salaries for insert with check (public.bs_is_admin());
drop policy if exists "owner updates salaries" on public.dfs_salaries;
create policy "owner updates salaries" on public.dfs_salaries for update using (public.bs_is_admin()) with check (public.bs_is_admin());

-- DraftKings main-slate salaries every 3 hours
select cron.unschedule('betsweep-dk-salaries') where exists (select 1 from cron.job where jobname = 'betsweep-dk-salaries');
select cron.schedule('betsweep-dk-salaries', '20 */3 * * *', $$
  select net.http_post(
    url     := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-cron-secret', '__CRON_SECRET__'),
    body    := '{"mode":"dk"}'::jsonb);
$$);
-- pull once right now too
select net.http_post(
  url     := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
  headers := jsonb_build_object('Content-Type', 'application/json', 'x-cron-secret', '__CRON_SECRET__'),
  body    := '{"mode":"dk"}'::jsonb);
