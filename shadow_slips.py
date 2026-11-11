#!/usr/bin/env python3
"""shadow_slips.py - paper slips: several recipes built from the same board every game day, logged and graded, so the house recipe is
chosen by results (owner 11/10 deep dive: "Shadow slips: run three recipes on paper each week and let results pick the house recipe").

Why: graded over Weeks 6-9 the risk score did not separate winners from losers among favorites (low-risk 60.9%, high-risk 64.6%;
research/risk_grade.py), and nobody could say which of our slip rules earns its place. Nothing here is posted as a pick.

Recipes, per game day (Central), three legs each, one per player, at most two per game, FanDuel ids on every leg, overs unless said:
  house     favorites -350..-140 the site shows at or within 2 points of break-even, risk score 0-1      (the Short view's rule)
  no-screen the same without the risk screen                                                            (does the screen help?)
  value     favorites -350..-140 the site shows AT OR ABOVE break-even, no risk screen                  (does "shown above the price" help?)
  under-mix two house favorites + the day's best under (shown 55%+ and at or above break-even)           (does an under help?)
A day that cannot fill a recipe has no slip for it. On a one-game day the three legs come from the one game (flagged same_game: the
legs-multiplied price is then an estimate, not FanDuel's same-game quote).

The log lives on the site (data/shadow-slips.json, kept across builds). A slip follows the board until the first kickoff among its
legs, then it is frozen. Frozen slips are graded from the game log (in/gamelog.json) once their week is in it: a leg whose player has
no row that week is VOID and drops out of the slip (its price too); a slip wins when every remaining leg hit; units at the legs
multiplied, one unit a slip.

  build(in_dir, out_dir, clone) -> out/data/shadow-slips.json (the log) + out/shadow.json (the record per recipe) + a summary line
"""
import datetime, json, os, sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sweep as SW  # noqa: E402

CT = ZoneInfo("America/Chicago")
RECIPES = ("house", "no-screen", "value", "under-mix")
STAT = {"Receptions": ("Receptions",), "Receiving Yards": ("Rec Yds",), "Rushing Yards": ("Rush Yds",), "Passing Yards": ("Pass Yds",),
        "Rush + Rec Yards": ("Rush Yds", "Rec Yds"), "Longest Reception": ("Longest Rec",), "Anytime TD": ("Rush TD", "Rec TD"),
        "Passing TDs": ("Pass TD",), "Completions": ("Completions",), "Rush Attempts": ("Rush Att",), "Interceptions": ("INT",)}


def dec(o): o = float(o); return 1 + o / 100 if o > 0 else 1 + 100 / -o
def day_of(ko_ms): return datetime.datetime.fromtimestamp(ko_ms / 1000, CT).strftime("%Y-%m-%d")


def grade_leg(leg, gl_index, weeks_in_log):
    """leg = {pl, m, ln, week}. -> HIT / MISS / VOID / None (week not in the game log yet, or a market the log cannot grade)."""
    wk = str(leg.get("week")); m = str(leg.get("m")); under = m.startswith("Under "); base = m[6:] if under else m
    if wk not in weeks_in_log or base not in STAT: return None
    row = gl_index.get((wk, str(leg["pl"]).strip().lower()))
    if row is None: return "VOID"
    v = sum(row.get(c, 0.0) for c in STAT[base])
    return ("HIT" if v < float(leg["ln"]) else "MISS") if under else ("HIT" if v >= float(leg["ln"]) else "MISS")


def gamelog_index(in_dir):
    try: gl = json.load(open(os.path.join(in_dir, "gamelog.json"))); gl = gl.get("values", gl) if isinstance(gl, dict) else gl
    except Exception: return {}, set()
    if not gl: return {}, set()
    H = gl[0]; idx = {}; weeks = set()
    for r in gl[1:]:
        if len(r) < 2: continue
        d = {}
        for i, c in enumerate(H):
            if i < len(r):
                try: d[c] = float(r[i] or 0)
                except Exception: pass
        idx[(str(r[0]), str(r[1]).strip().lower())] = d; weeks.add(str(r[0]))
    return idx, weeks


def _take(cand, n=3, per_game=2):
    out, seen, per = [], set(), {}
    for l in cand:
        if l["pl"] in seen or per.get(l["g"], 0) >= per_game: continue
        out.append(l); seen.add(l["pl"]); per[l["g"]] = per.get(l["g"], 0) + 1
        if len(out) == n: break
    return out


def recipes_for(bd, gids):
    fav = [l for l in bd["legs"] if l["g"] in gids and not l.get("gl") and not l.get("u") and not str(l["m"]).startswith("Under")
           and l["m"] not in ("First TD", "Longest Reception", "Rushing Yards") and l.get("o") is not None and l.get("p") is not None
           and -350 <= l["o"] <= -140 and (l.get("fd") or {}).get("m") and (l.get("fd") or {}).get("s")]
    fav.sort(key=lambda l: (-l["p"], l["pl"]))
    near = [l for l in fav if l["p"] >= (l.get("bk") or 1) - 0.02]
    pg = 2 if len({l["g"] for l in fav}) >= 2 else 3      # a one-game day (Thursday, Monday) is a same-game slip: three legs from the one game
    house = _take([l for l in near if SW.risk_score(l, bd) < 2], per_game=pg); noscreen = _take(near, per_game=pg)
    value = _take([l for l in fav if l["p"] >= 1 / dec(l["o"])], per_game=pg)
    und = [l for l in bd["legs"] if l["g"] in gids and str(l["m"]).startswith("Under ") and l.get("o") is not None and l.get("p") is not None
           and l["p"] >= 0.55 and l["p"] >= 1 / dec(l["o"]) and (l.get("fd") or {}).get("s")]
    und.sort(key=lambda l: -(l["p"] - 1 / dec(l["o"])))
    mix = []
    if und and len(house) >= 2:
        two = [l for l in house if l["pl"] != und[0]["pl"]][:2]
        if len(two) == 2: mix = two + [und[0]]
    return {"house": house if len(house) == 3 else [], "no-screen": noscreen if len(noscreen) == 3 else [],
            "value": value if len(value) == 3 else [], "under-mix": mix}


def build(in_dir="in", out_dir="out", clone=None, now_ms=None):
    now_ms = now_ms or int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    bd = json.load(open(os.path.join(out_dir, "builder_data.json"))); W = bd.get("week")
    clone = clone or os.environ.get("BS_SITE") or "/home/claude/betsweep-site"
    log = []
    for p in (os.path.join(clone, "data", "shadow-slips.json"), os.path.join(out_dir, "data", "shadow-slips.json")):
        try:
            log = json.load(open(p)); log = log if isinstance(log, list) else []
            if log: break
        except Exception: pass
    keep = [e for e in log if (e.get("ko") or 0) <= now_ms]; frozen = {(e["date"], e["recipe"]) for e in keep}
    days = {}
    for g in bd.get("games") or []:
        if g.get("ko") and g["ko"] > now_ms: days.setdefault(day_of(g["ko"]), set()).add(g["gid"])
    KO = {g["gid"]: g.get("ko") or 0 for g in bd.get("games") or []}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); new = 0
    for d, gids in sorted(days.items()):
        for name, legs in recipes_for(bd, gids).items():
            if not legs or (d, name) in frozen: continue
            dd = 1.0; pp = 1.0
            for l in legs: dd *= dec(l["o"]); pp *= l["p"]
            keep.append({"date": d, "week": W, "recipe": name, "ko": min(KO[l["g"]] for l in legs), "dec": round(dd, 4), "p_all": round(pp, 4), "at_utc": stamp,
                         "same_game": len({l["g"] for l in legs}) == 1,      # legs multiplied is not FanDuel's same-game quote: units for these are an estimate
                         "legs": [{"pl": l["pl"], "m": l["m"], "ln": l["ln"], "o": int(l["o"]), "p": round(l["p"], 4), "g": l["g"], "risk": int(SW.risk_score(l, bd))} for l in legs], "res": None})
            new += 1
    idx, weeks = gamelog_index(in_dir)
    for e in keep:
        if e.get("res") in ("WIN", "LOSS", "VOID") or (e.get("ko") or 0) > now_ms: continue
        rs = [grade_leg(dict(l, week=e["week"]), idx, weeks) for l in e["legs"]]
        if any(r is None for r in rs): continue
        for l, r in zip(e["legs"], rs): l["res"] = r
        live = [(l, r) for l, r in zip(e["legs"], rs) if r != "VOID"]
        if not live: e["res"] = "VOID"; continue
        dd = 1.0
        for l, _ in live: dd *= dec(l["o"])
        e["res"] = "WIN" if all(r == "HIT" for _, r in live) else "LOSS"; e["units"] = round(dd - 1, 3) if e["res"] == "WIN" else -1.0
    keep.sort(key=lambda e: (e["date"], RECIPES.index(e["recipe"]) if e["recipe"] in RECIPES else 9))
    rec = {}
    for name in RECIPES:
        g = [e for e in keep if e["recipe"] == name and e.get("res") in ("WIN", "LOSS")]
        legs = [l for e in g for l in e["legs"] if l.get("res") in ("HIT", "MISS")]
        rec[name] = {"slips": len(g), "won": sum(1 for e in g if e["res"] == "WIN"), "units": round(sum(e.get("units") or 0 for e in g), 2),
                     "legs": len(legs), "legs_hit": sum(1 for l in legs if l["res"] == "HIT"), "open": sum(1 for e in keep if e["recipe"] == name and not e.get("res"))}
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    json.dump(keep, open(os.path.join(out_dir, "data", "shadow-slips.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"week": W, "record": rec}, open(os.path.join(out_dir, "shadow.json"), "w"), ensure_ascii=False)
    return ("shadow slips: " + "; ".join(f"{n} {r['won']}-{r['slips'] - r['won']} ({r['units']:+.2f}u, legs {r['legs_hit']}/{r['legs']}, {r['open']} open)" for n, r in rec.items())
            + f"; {new} written or refreshed this run, log {len(keep)} slips")


if __name__ == "__main__":
    print(build())
