-- BetSweep short links: run once in the Supabase SQL editor (Project fuwiqijgkgbzvnfnsans > SQL editor > New query > paste > Run)
create table if not exists public.short_links (
  code text primary key check (code ~ '^[a-z0-9]{5,10}$'),
  week int,
  title text check (title is null or length(title) <= 80),
  legs jsonb not null check (jsonb_typeof(legs) = 'array' and jsonb_array_length(legs) between 1 and 20),
  fd_odds int,
  link text check (link is null or (length(link) <= 4000 and link like 'https://sportsbook.fanduel.com/%')),
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);
alter table public.short_links enable row level security;
drop policy if exists "read links" on public.short_links;
create policy "read links" on public.short_links for select using (true);
drop policy if exists "make links" on public.short_links;
create policy "make links" on public.short_links for insert with check (true);
-- nobody updates or deletes through the API (no policy) - the owner edits in the dashboard

create table if not exists public.link_hits (
  code text primary key,
  hits int not null default 0,
  last_hit timestamptz
);
alter table public.link_hits enable row level security;
drop policy if exists "read hits" on public.link_hits;
create policy "read hits" on public.link_hits for select using (true);
create or replace function public.link_hit(c text) returns void
language sql security definer set search_path = public as $$
  insert into public.link_hits (code, hits, last_hit) values (c, 1, now())
  on conflict (code) do update set hits = public.link_hits.hits + 1, last_hit = now();
$$;
grant execute on function public.link_hit(text) to anon, authenticated;
