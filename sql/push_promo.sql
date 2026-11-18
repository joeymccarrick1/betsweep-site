-- BetSweep: "tell me when a slip posts" (owner 11/17). One switch per device on push_subs, off until its owner turns it on.
-- No secret in this file. Safe to run twice. After it: redeploy the slip-alerts function (push/slip-alerts.ts) and tell the session,
-- which then sets account.py PROMO_ALERTS = True so the switch shows on My BetSweep > Slip alerts.
-- Undo: alter table public.push_subs drop column if exists promo;
alter table public.push_subs add column if not exists promo boolean not null default false;
-- how many devices have it on (owner only):
--   select count(*) filter (where promo) as on_, count(*) as devices from public.push_subs;
