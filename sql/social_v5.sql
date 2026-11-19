-- BetSweep Social v5 (11/19): more avatars - one emoji for every NFL team (56 in all). Run once in the Supabase SQL editor, after v4.
-- No secret in this file. It only replaces feed_profile_set with a longer avatar list; nothing else changes and it is safe to run twice.
create or replace function public.feed_profile_set(p_handle text, p_color int, p_emoji text) returns public.feed_profiles language plpgsql security definer set search_path = public as $$
declare r public.feed_profiles; h text := btrim(coalesce(p_handle, '')); e text := nullif(btrim(coalesce(p_emoji, '')), '');
begin
  if auth.uid() is null then raise exception 'Sign in first'; end if;
  perform public.feed_profile_me();
  select * into r from public.feed_profiles where user_id = auth.uid();
  if p_color is null or p_color < 0 or p_color > 7 then raise exception 'Pick one of the eight colours'; end if;
  if e is not null and not (e = any (array['🏈','🔥','🔒','💰','🎯','🚀','🐐','👑','💎','🍀','⚡','🧠','🎲','🦅','🐻','🦁','🐯','🐬','🐴','🏴‍☠️','🤠','😎','🥶','🤑','🌵','🍑','🐦‍⬛','🦬','🐈‍⬛','🐶','⭐','🧀','🐂','🐎','🐆','🏹','🐏','🪓','🇺🇸','⚜️','🗽','✈️','⚒️','⛏️','🐦','☠️','⚔️','🪖'])) then
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
