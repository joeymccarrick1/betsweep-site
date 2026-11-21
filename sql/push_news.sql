-- BetSweep news alerts (owner 11/20). Two settings per device on push_subs, both off until the device's owner sets them:
--   news  "tell me when a big-name player is ruled out, released or traded"
--   team  a favorite team code (TEN, KC, ...): that team's rule-outs and ESPN stories
-- No secret in this file. Safe to run twice. After it: redeploy the slip-alerts function (slip-alerts.ts) and tell the session,
-- which then sets account.py NEWS_ALERTS = True so the two settings show on My BetSweep > Slip alerts.
-- Undo: alter table public.push_subs drop column if exists news; alter table public.push_subs drop column if exists team;
alter table public.push_subs add column if not exists news boolean not null default false;
alter table public.push_subs add column if not exists team text;
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'push_subs_team_code') then
    alter table public.push_subs add constraint push_subs_team_code check (team is null or team ~ '^[A-Z]{2,3}$');
  end if;
end $$;
-- how many devices have each on (owner only):
--   select count(*) filter (where news) as news_on, count(team) as with_team, count(*) as devices from public.push_subs;
