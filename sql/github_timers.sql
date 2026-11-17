-- BetSweep: let the database's timer start the site's scheduled jobs on GitHub.  Run once in the Supabase SQL editor
-- (Project fuwiqijgkgbzvnfnsans > SQL editor > New query > paste > Run).  There is NO secret in this file and nothing to paste:
-- it reuses the GitHub token already stored with the "betsweep-feeds" timer jobs (push/betsweep-live-fast.sql, run 11/5).
--
-- Why (measured 11/16): GitHub's own schedule skips most runs in this repo - 3 of 17 hourly rebuilds, 3 of 48 sheet mirrors,
-- 3 of about 22 Sunday inactive checks - while this database's timer started the live feed every 3 minutes for five hours
-- on Sunday night without a miss. The times below are the ones each workflow file already names; when GitHub's schedule does
-- fire as well, the second run just waits its turn and finds nothing new.
--
-- Safe to run again (it replaces its own jobs). To stop everything it starts:
--   select cron.unschedule(jobname) from cron.job where jobname like 'betsweep-gh-%';
do $$
declare
  tok text;
  j record;
  hdr text;
begin
  select substring(command from 'Bearer ([A-Za-z0-9_]+)') into tok
    from cron.job where jobname like 'betsweep-feeds-%' and command like '%api.github.com%' order by jobid limit 1;
  if tok is null or tok like '%GH_TOKEN%' or length(tok) < 20 then
    raise exception 'No GitHub token found in the betsweep-feeds timer jobs. Run push/betsweep-live-fast.sql (with the token) first.';
  end if;
  perform cron.unschedule(jobname) from cron.job where jobname like 'betsweep-gh-%';
  hdr := format('jsonb_build_object(''Authorization'',''Bearer %s'',''Accept'',''application/vnd.github+json'',''User-Agent'',''betsweep-cron'',''Content-Type'',''application/json'',''X-GitHub-Api-Version'',''2022-11-28'')', tok);
  for j in select * from (values
      -- name                         when (UTC)                 workflow            inputs
      ('betsweep-gh-mirror',          '5,35 * * * *',            'sheet-mirror.yml', null),
      ('betsweep-gh-moves',           '12,42 * * * *',           'price-moves.yml',  null),
      ('betsweep-gh-notes',           '*/30 * * * *',            'risk-notes.yml',   null),
      -- the ESPN mirror (injury report, news, weather, inactives) every ten minutes, all week. Added 11/17: outside game windows it
      -- was left to GitHub's schedule, which started it 38 times in four days where about 600 were due - on Monday 11/16 not once
      -- between 10:57 AM and 5:00 PM Central. The three-minute game-window jobs (betsweep-feeds-*) are not touched.
      ('betsweep-gh-feeds',           '*/10 * * * *',            'feeds.yml',        null),
      -- the rebuild: hourly on game days (Thu / Sun / Mon, 6:20 AM - 11:20 PM Central), every three hours otherwise
      ('betsweep-gh-reprice-day',     '20 12-23 * * 0,1,4',      'reprice.yml',      '{"publish":"changed"}'),
      ('betsweep-gh-reprice-night',   '20 0-5 * * 1,2,5',        'reprice.yml',      '{"publish":"changed"}'),
      ('betsweep-gh-reprice-off',     '20 12,15,18,21 * * 2,3,5,6', 'reprice.yml',   '{"publish":"changed"}'),
      ('betsweep-gh-reprice-off2',    '20 0,3 * * 3,4,6,0',      'reprice.yml',      '{"publish":"changed"}'),
      -- game-day inactives into the sheet: Sundays every half hour, plus Thursday and Monday evenings
      ('betsweep-gh-gameday-sun',     '8,38 13-23 * * 0',        'gameday.yml',      null),
      ('betsweep-gh-gameday-sunlate', '8,38 0,1 * * 1',          'gameday.yml',      null),
      ('betsweep-gh-gameday-night',   '8,38 0 * * 2,5',          'gameday.yml',      null),
      -- Social records: every morning 9:40 AM Central
      ('betsweep-gh-social-grade',    '40 15 * * *',             'social-grade.yml', '{"mode":"grade"}')
    ) as t(name, sched, wf, inputs)
  loop
    perform cron.schedule(j.name, j.sched, format(
      $c$ select net.http_post(url := 'https://api.github.com/repos/joeymccarrick1/betsweep-site/actions/workflows/%s/dispatches', headers := %s, body := '%s'::jsonb); $c$,
      j.wf, hdr, case when j.inputs is null then '{"ref":"main"}' else '{"ref":"main","inputs":' || j.inputs || '}' end));
  end loop;
end $$;
-- what is now on the timer: names and times only (the commands, which hold the token, are not shown)
select jobname, schedule from cron.job where jobname like 'betsweep-%' order by jobname;
