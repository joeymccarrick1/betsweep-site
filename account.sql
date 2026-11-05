-- BetSweep accounts: run once in the Supabase SQL editor
create table if not exists public.user_state (
  user_id uuid not null references auth.users(id) on delete cascade,
  key text not null,
  value jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, key)
);
alter table public.user_state enable row level security;
drop policy if exists "own rows" on public.user_state;
create policy "own rows" on public.user_state for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
