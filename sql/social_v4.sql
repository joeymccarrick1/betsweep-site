-- BetSweep Social v4 (11/16): people choose their own username and avatar. Run ONCE in the Supabase SQL editor, on top of v3.
-- Safe to run twice. No secret in this one - run it exactly as it is.

alter table public.feed_profiles add column if not exists emoji text check (emoji is null or char_length(emoji) <= 8);
alter table public.feed_profiles add column if not exists handle_changed_at timestamptz;

-- a username belongs to one account (upper / lower case ignored). Any clash among the names made so far gets three characters added.
update public.feed_profiles p set handle = left(p.handle, 17) || substr(md5(p.user_id::text), 1, 3)
 where exists (select 1 from public.feed_profiles q where lower(q.handle) = lower(p.handle) and q.user_id < p.user_id);
create unique index if not exists feed_profiles_handle_u on public.feed_profiles (lower(handle));

-- profiles are changed only through feed_profile_set() below: the old trigger pinned the assigned name, and direct edits are closed
drop trigger if exists feed_profile_guard on public.feed_profiles;
drop policy if exists "recolor own" on public.feed_profiles;

-- the name a new account starts with: the assigned one, with digits added if somebody already has it
create or replace function public.feed_profile_me() returns public.feed_profiles language plpgsql security definer set search_path = public as $$
declare r public.feed_profiles; h text; i int := 0;
begin
  if auth.uid() is null then raise exception 'Sign in first'; end if;
  select * into r from public.feed_profiles where user_id = auth.uid();
  if found then return r; end if;
  h := public.feed_handle(auth.uid());
  while exists (select 1 from public.feed_profiles where lower(handle) = lower(h)) and i < 50 loop
    i := i + 1; h := left(public.feed_handle(auth.uid()), 17) || lpad(i::text, 2, '0');
  end loop;
  insert into public.feed_profiles (user_id, handle, color)
    values (auth.uid(), h, mod(('x' || substr(md5(auth.uid()::text), 25, 8))::bit(32)::int::bigint & 2147483647, 8))
    on conflict (user_id) do nothing;
  select * into r from public.feed_profiles where user_id = auth.uid();
  return r;
end $$;
revoke all on function public.feed_profile_me() from public;
grant execute on function public.feed_profile_me() to authenticated;

-- choose a username, a colour and an avatar. Username: 3-20 letters, digits or underscores, clean, not taken, not a staff-sounding
-- name, and it can be changed once every 30 days. The avatar is one of a fixed set (no uploads). Old posts take the new name.
create or replace function public.feed_profile_set(p_handle text, p_color int, p_emoji text) returns public.feed_profiles language plpgsql security definer set search_path = public as $$
declare r public.feed_profiles; h text := btrim(coalesce(p_handle, '')); e text := nullif(btrim(coalesce(p_emoji, '')), '');
begin
  if auth.uid() is null then raise exception 'Sign in first'; end if;
  perform public.feed_profile_me();
  select * into r from public.feed_profiles where user_id = auth.uid();
  if p_color is null or p_color < 0 or p_color > 7 then raise exception 'Pick one of the eight colours'; end if;
  if e is not null and not (e = any (array['🏈','🔥','🔒','💰','🎯','🚀','🐐','👑','💎','🍀','⚡','🧠','🎲','🦅','🐻','🦁','🐯','🐬','🐴','🏴‍☠️','🤠','😎','🥶','🤑'])) then
    raise exception 'Pick an avatar from the list'; end if;
  if h is distinct from r.handle then
    if h !~ '^[A-Za-z0-9_]{3,20}$' then raise exception 'Usernames are 3 to 20 letters, numbers or underscores'; end if;
    if not public.feed_clean(h) or not public.feed_clean(regexp_replace(h, '_', ' ', 'g')) then raise exception 'Keep the username clean'; end if;
    if lower(h) ~ '(betsweep|admin|support|official|moderator|staff|fanduel|draftkings)' then raise exception 'That username is reserved'; end if;
    if exists (select 1 from public.feed_profiles where lower(handle) = lower(h) and user_id <> auth.uid()) then raise exception 'That username is taken'; end if;
    if lower(h) <> lower(r.handle) and r.handle_changed_at is not null and r.handle_changed_at > now() - interval '30 days' then
      raise exception 'You can change your username again on %', to_char(r.handle_changed_at + interval '30 days', 'Mon DD'); end if;
    update public.feed_profiles set handle = h, handle_changed_at = case when lower(h) <> lower(r.handle) then now() else handle_changed_at end where user_id = auth.uid();
    update public.feed_posts set handle = h where user_id = auth.uid();
  end if;
  update public.feed_profiles set color = p_color, emoji = e where user_id = auth.uid();
  select * into r from public.feed_profiles where user_id = auth.uid();
  return r;
end $$;
revoke all on function public.feed_profile_set(text, int, text) from public;
grant execute on function public.feed_profile_set(text, int, text) to authenticated;

-- a new post carries the account's chosen username (the assigned one until a profile exists)
alter table public.feed_posts drop constraint if exists feed_posts_handle_check;
alter table public.feed_posts add constraint feed_posts_handle_check check (handle ~ '^[A-Za-z0-9_.]{2,20}$');
create or replace function public.feed_post_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.first_ko <= now() then raise exception 'A leg in this slip has already kicked off'; end if;
  if new.last_ko < new.first_ko or new.last_ko > now() + interval '14 days' then raise exception 'Bad kickoff times'; end if;
  if (select count(*) from public.feed_posts where user_id = new.user_id and created_at > now() - interval '1 day') >= 10 then
    raise exception 'Posting limit reached (10 a day)'; end if;
  if not public.feed_clean(new.title) then raise exception 'Keep the title clean'; end if;
  new.handle := coalesce((select handle from public.feed_profiles where user_id = new.user_id), public.feed_handle(new.user_id));
  new.score := 0; new.status := 'open'; new.created_at := now();
  new.tails := 0; new.rx := '{}'::jsonb; new.result := null; new.units := null; new.graded_at := null;
  return new;
end $$;
