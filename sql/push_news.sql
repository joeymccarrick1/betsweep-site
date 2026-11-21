-- BetSweep: "tell me when a big-name player is ruled out or released" (owner 11/20). One switch per device on push_subs, off until
-- its owner turns it on. No secret in this file. Safe to run twice. After it: redeploy the slip-alerts function (slip-alerts.ts) and
-- tell the session, which then sets account.py NEWS_ALERTS = True so the switch shows on My BetSweep > Slip alerts.
-- Undo: alter table public.push_subs drop column if exists news;
alter table public.push_subs add column if not exists news boolean not null default false;
-- how many devices have it on (owner only):
--   select count(*) filter (where news) as on_, count(*) as devices from public.push_subs;
