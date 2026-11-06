-- BetSweep: live leg alerts close to real time (owner 11/5: "How come I'm not getting live notifications about legs hitting?")
-- Why they were late: ESPN blocks Supabase, so the alerts read the ESPN mirror that a GitHub job refreshes. GitHub only ran that job about once
-- every 45-60 minutes tonight (its schedules are best-effort). Fix: during game windows Supabase asks GitHub to run the mirror every 3 minutes
-- (on-demand runs are not throttled the way schedules are), and the alerts check 1 minute after each refresh.
-- Needs one GitHub token: github.com > Settings > Developer settings > Fine-grained tokens > Generate: repository = joeymccarrick1/betsweep-site,
-- permission Actions = Read and write, expiry 1 year. Paste it in place of __GH_TOKEN__ below (keep this file private once it has the token).
create extension if not exists pg_net;
-- game windows (UTC): Sunday 11:30 AM - 11:30 PM CT, Monday and Thursday nights 6 PM - 11:30 PM CT
select cron.unschedule(j) from unnest(array['betsweep-feeds-sun','betsweep-feeds-night','betsweep-feeds-late','betsweep-alerts-live-sun','betsweep-alerts-live-night','betsweep-alerts-live-late']) j where exists (select 1 from cron.job where jobname = j);
select cron.schedule('betsweep-feeds-sun', '*/3 16-23 * * 0', $$ select net.http_post(url := 'https://api.github.com/repos/joeymccarrick1/betsweep-site/actions/workflows/feeds.yml/dispatches',
  headers := jsonb_build_object('Authorization','Bearer __GH_TOKEN__','Accept','application/vnd.github+json','User-Agent','betsweep-cron','X-GitHub-Api-Version','2022-11-28'), body := '{"ref":"main"}'::jsonb); $$);
select cron.schedule('betsweep-feeds-night', '*/3 0-5 * * 1,2,5', $$ select net.http_post(url := 'https://api.github.com/repos/joeymccarrick1/betsweep-site/actions/workflows/feeds.yml/dispatches',
  headers := jsonb_build_object('Authorization','Bearer __GH_TOKEN__','Accept','application/vnd.github+json','User-Agent','betsweep-cron','X-GitHub-Api-Version','2022-11-28'), body := '{"ref":"main"}'::jsonb); $$);
select cron.schedule('betsweep-feeds-late', '*/3 23 * * 1,4', $$ select net.http_post(url := 'https://api.github.com/repos/joeymccarrick1/betsweep-site/actions/workflows/feeds.yml/dispatches',
  headers := jsonb_build_object('Authorization','Bearer __GH_TOKEN__','Accept','application/vnd.github+json','User-Agent','betsweep-cron','X-GitHub-Api-Version','2022-11-28'), body := '{"ref":"main"}'::jsonb); $$);
-- the alerts themselves, 2 minutes after each mirror request, in the same windows (the every-10-minute job keeps running too)
select cron.schedule('betsweep-alerts-live-sun', '2-59/3 16-23 * * 0', $$ select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
  headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{}'::jsonb); $$);
select cron.schedule('betsweep-alerts-live-night', '2-59/3 0-5 * * 1,2,5', $$ select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
  headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{}'::jsonb); $$);
select cron.schedule('betsweep-alerts-live-late', '2-59/3 23 * * 1,4', $$ select net.http_post(url := 'https://fuwiqijgkgbzvnfnsans.supabase.co/functions/v1/slip-alerts',
  headers := jsonb_build_object('Content-Type','application/json','x-cron-secret','__CRON_SECRET__'), body := '{}'::jsonb); $$);
