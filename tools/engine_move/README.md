# Moving the engine private - drafts, not live (prepared 11/24)

The generators (`gen-overrides`) and the sheet mirror (`sheet-mirror`) move to the private repository
`joeymccarrick1/betsweep-site-archive` (it already exists and Claude sessions can already push to it; its default branch `main` stays the
note-only branch). The public repository keeps the built site, the `feeds` / `feeds-sports` branches and the job files.

Files here are the job files and two scripts as they must look on `main`. Every change is a no-op until the switch is set:
`${{ vars.ENGINE_REPO || github.repository }}` and `${{ secrets.ENGINE_TOKEN || github.token }}` fall back to today's behaviour.
- reprice.yml, feeds-sports.yml, social-grade.yml: check the generators (and the mirror) out of ENGINE_REPO with ENGINE_TOKEN.
- sheet-mirror.yml: pushes the mirror to ENGINE_REPO.
- price-moves.yml + price_moves.py, gameday.yml + gameday.py: read the mirror from ENGINE_REPO with the token (never printed).
- push/slip-alerts.ts already reads MIRROR_URL with MIRROR_TOKEN when that function secret is set.

## The switch (owner about 15 minutes, not during a game window)
1. Claude: push these six job files and two scripts to `main` (nothing changes), watch one run of each job.
2. Claude: push the current `gen-overrides` and `sheet-mirror` to the archive repository (done once on 11/24 as a test: both are there).
3. Owner, github.com > Settings > Developer settings > Fine-grained tokens: one token, repository access "Only select repositories" =
   betsweep-site-archive, permission Contents = Read and write, no expiry sooner than the season's end. Copy it.
4. Owner, betsweep-site > Settings > Secrets and variables > Actions: new SECRET `ENGINE_TOKEN` = the token; new VARIABLE `ENGINE_REPO` =
   `joeymccarrick1/betsweep-site-archive`. From the next run every job reads the private copy.
5. Owner, Supabase > Edge Functions > slip-alerts > Secrets: `MIRROR_URL` =
   `https://raw.githubusercontent.com/joeymccarrick1/betsweep-site-archive/sheet-mirror`, `MIRROR_TOKEN` = the same token (or a second,
   read-only one). Redeploy the function (it also carries the 11/24 IR and weather changes).
6. Claude: dispatch sheet-mirror, reprice (publish=all), price-moves, feeds-sports; read each log for "sheet-mirror" / checkout lines;
   confirm the site published. From here Claude pushes generators to the archive repository's `gen-overrides`.
7. Scheduled tasks (the Tuesday load, the boards rebuild, promo drafts) clone `gen-overrides` / `sheet-mirror` from betsweep-site in
   their prompts. They must be pointed at the archive repository BEFORE the public branches are deleted (needs the owner's OK to list and
   edit the tasks). RUNBOOK's clone commands change the same way.
8. Only then - owner, on github.com: delete the public branches gen-overrides, gen-patch, gen-patch2, multisport, promo-drafts,
   promo-studio, sheet-mirror. Optional: ask GitHub Support to purge cached views of them.
Undo at any point before step 8: delete the variable ENGINE_REPO - every job is back on the public branches on its next run.
