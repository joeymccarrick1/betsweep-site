"""An imported FanDuel slip's wager is in dollars; My BetSweep counts slips in units (owner 11/24: "it's saying a lot of the bets were
-20u or -25u. That shouldn't be the case"). account.py stakeU / unitNow / wagerOf, run in node with a made-up localStorage.
  python3 tests/stake_units.py"""
import json, os, re, subprocess, sys
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
import account as A
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
src = A.ME_JS
fns = "\n".join(re.search(r"  function " + n + r"\(.*", src).group(0) for n in ("g", "unitNow", "wagerOf", "stakeU"))
def run(store, slips):
    js = "var S = " + json.dumps(store) + "; var localStorage = {getItem: function(k){ return k in S ? S[k] : null; }};\n" + fns + "\nconsole.log(JSON.stringify(" + json.dumps(slips) + ".map(function(s){ return [stakeU(s), wagerOf(s)]; })));"
    return json.loads(subprocess.check_output(["node", "-e", js], text=True))
imp20 = {"src": "fanduel-screenshot", "stake": 20}; imp25 = {"src": "fanduel-screenshot", "stake": 25}; built = {"stake": 1}; half = {"stake": 0.5}; none = {"src": "fanduel-screenshot"}; tail = {"promo": 1, "stake": 1}
r = run({}, [imp20, imp25, built, half, none, tail])
check(r == [[1, 20], [1, 25], [1, 0], [1, 0.5], [1, 0], [1, 0]] and run({}, [{"stake": 25}, {"stake": 20, "promo": 1}]) == [[1, 25], [1, 20]], f"with no bankroll tracker a $20 or $25 slip - imported, or typed in the Live page's stake box - counts 1 unit (not 20 or 25) and keeps its dollars for the row; the builder's default stake of 1 is one unit ({r})")
plan = {"bs_bankroll_plan": json.dumps({"start": 1250, "pct": 2, "since": 10}), "bs_bankroll": "90"}
r = run(plan, [imp20, imp25, built, {"stake": 5}, {"wager": 50, "stake": 1}])
check(r == [[0.8, 20], [1, 25], [1, 0], [0.2, 5], [2, 50]], f"with a tracker started at $1,250 and 2% a unit ($25; the running bankroll is not read, so units do not move from one visit to the next): $20 is 0.8u, $25 is 1u, $5 is 0.2u, $50 is 2u ({r})")
r = run({"bs_bankroll_plan": json.dumps({"start": 500, "pct": 1, "since": 10})}, [imp20]); r2 = run({"bs_bankroll_plan": "{broken"}, [imp20]); r3 = run({"bs_bankroll_plan": json.dumps({"start": 500, "pct": 0})}, [imp20])
check(r == [[4, 20]] and r2 == [[1, 20]] and r3 == [[1, 20]], "a tracker started at $500 and 1% is $5 a unit, so $20 is 4u; a tracker that cannot be read, or has no percent, counts 1 unit")
check("var stake = stakeU(s)" in src and src.count("+s.stake ||") == 1 and src.count("stakeU(s)") >= 3 and "wagerOf(s) ? ' ($'" in src, "the slips list, the weekly profit, the bankroll rows and the exposure card all read a slip's stake through that one rule, and the row shows the dollars bet")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
