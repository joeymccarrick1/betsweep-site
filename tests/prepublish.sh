#!/bin/bash
# The full pre-publish set (RUNBOOK: "the full set to run before a publish"), compact output: one line per test.
#   tests/prepublish.sh [extra reprice.py args]
#   MIRROR=<sheet-mirror clone>/in  CLONE=<site clone>   (defaults: ../sm/in and ~/betsweep-site)
#   SKIPBUILD=1 runs only the tests on the tree as built; SITE=<dir> passes through to the page tests.
# Takes about 20 minutes. Do not edit generators in this tree while it runs; to keep working, copy the tree
# (tar -c --exclude=.git . | tar -x -C /tmp/copy) and run the copy's tests/prepublish.sh - the tests use fixed ports,
# so never run the same test in two trees at the same moment.
# The gate at the end runs on ./site; the gate that counts runs on a copy of the live clone with this build laid over it:
#   rm -rf /tmp/gateclone; mkdir -p /tmp/gateclone; git -C $CLONE archive HEAD | tar -x -C /tmp/gateclone
#   python3 -c "import reprice as R; R.copy_into_clone('/tmp/gateclone')"; SITE=/tmp/gateclone python3 tests/local_gate.py
cd "$(dirname "$0")/.." || exit 1
MIRROR="${MIRROR:-$(cd .. && pwd)/sm/in}"; CLONE="${CLONE:-$HOME/betsweep-site}"; LOG="${TMPDIR:-/tmp}/reprice_local.log"
if [ -z "$SKIPBUILD" ]; then
  python3 reprice.py --mirror "$MIRROR" --clone "$CLONE" --publish none "$@" > "$LOG" 2>&1
  echo "reprice exit $? :: $(grep '^REPRICE ' "$LOG" | tail -1 | cut -c1-700)"
  grep -E '^\[(weekgate|availfix|feeds|voice)\]|CHECK FAILED|FAILED' "$LOG" | cut -c1-220 | head -20
fi
TESTS="home_filing promo_kickoff promo_clock social_feed social_card social_elsewhere social_shot builder_fold boards_fold me_hub social_grade weather_gate finals_build live_finals live_gamemap live_first_screen live_regrade week_end inactive_block reprice_live sgp_price how_stats flag_stats trade_outlook bp_pick fantasy_nav promo_overlap promo_up page_fold calib_floor fantasy_push page_tight trade_find studio new_markets me_profile waiver_truth hunches_page news_up me_livebox risk_close builder_save_pop today_hunch stocks_page nba_board nba_grade nba_stocks epl_board epl_grade cfb_board soccer_leagues header_scroll kick_times saved_post import_batch winner_pre"
for t in $TESTS; do
  out=$(timeout 420 python3 tests/$t.py 2>&1); code=$?
  last=$(echo "$out" | grep -v '^\s*$' | tail -1 | cut -c1-150)
  fails=$(echo "$out" | grep -c '^FAIL')
  echo "$t: exit $code, FAIL lines $fails :: $last"
  if [ "$fails" != "0" ] || [ "$code" != "0" ]; then echo "$out" | grep -E '^FAIL|Error|Traceback' | head -6 | cut -c1-260; fi
done
for j in slipimport_altlines slipimport_load; do out=$(timeout 120 node tests/$j.js 2>&1); echo "$j: exit $? :: $(echo "$out" | tail -1 | cut -c1-120)"; done
out=$(timeout 560 python3 tests/local_gate.py 2>&1); echo "local_gate: exit $? :: $(echo "$out" | tail -1 | cut -c1-200)"
