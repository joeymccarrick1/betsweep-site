#!/usr/bin/env python3
"""research/situational_backtest.py - do "situational spots" beat the closing spread? (owner 11/5: "will a good team play down to another
team or a bad team play well against a good team")

Every spot is graded against the CLOSING consensus spread in nflverse games.csv (spread_line = home margin the market expected), regular
season 2006-2025, pushes dropped. A spot SURVIVES only if:
  - n >= 150 games,
  - the cover rate beats 52.4% (the break-even at -110) in the direction tested, overall AND in both halves (2006-2015 and 2016-2025),
  - two-sided binomial p < 0.05 overall.
Survivors are written to research/situational_spots.json, which build_dossier.py reads; everything else is reported as "no edge" so the
dossier can say so instead of repeating betting folklore.
Run: python3 research/situational_backtest.py  (reads in/games.csv; ~2 seconds)
"""
import csv, json, math, os, collections
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = [g for g in csv.DictReader(open(os.path.join(HERE, "in", "games.csv"))) if g["game_type"] == "REG" and g["home_score"] not in ("", "NA") and g["spread_line"] not in ("", "NA")]
FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}
for g in G: g["home_team"], g["away_team"] = FIX.get(g["home_team"], g["home_team"]), FIX.get(g["away_team"], g["away_team"])
f = float
def team_rows():
    """one row per team-game with everything known BEFORE kickoff, plus whether the team covered"""
    out = []; by_season = collections.defaultdict(list)
    for g in G: by_season[g["season"]].append(g)
    for season, gs in by_season.items():
        gs.sort(key=lambda g: (int(g["week"]), g["gameday"]))
        rec = collections.defaultdict(lambda: [0, 0, 0]); last = {}; sched = collections.defaultdict(list)
        for g in gs: sched[g["home_team"]].append(g); sched[g["away_team"]].append(g)
        meet = collections.defaultdict(list)
        for g in gs:
            for side in ("home", "away"):
                t = g[f"{side}_team"]; o = g["away_team" if side == "home" else "home_team"]
                spr = f(g["spread_line"]); line = -spr if side == "home" else spr          # this team's line (negative = favorite)
                margin = (f(g["home_score"]) - f(g["away_score"])) * (1 if side == "home" else -1)
                cov = margin + line; res = None if cov == 0 else (cov > 0)
                w, l, ti = rec[t]; ow, ol, oti = rec[o]; gp, ogp = w + l + ti, ow + ol + oti
                nxt = [x for x in sched[t] if int(x["week"]) > int(g["week"])]
                nopp = (nxt[0]["away_team"] if nxt[0]["home_team"] == t else nxt[0]["home_team"]) if nxt else None
                rest = g.get(f"{side}_rest"); orest = g.get(f"{'away' if side == 'home' else 'home'}_rest")
                prev_meet = meet[frozenset((t, o))]
                out.append({"season": int(season), "week": int(g["week"]), "team": t, "opp": o, "home": side == "home", "line": line, "cov": res,
                            "wp": (w + .5 * ti) / gp if gp else None, "owp": (ow + .5 * oti) / ogp if ogp else None, "gp": gp,
                            "last": last.get(t), "olast": last.get(o), "div": g.get("div_game") == "1", "thu": g.get("weekday") == "Thursday",
                            "rest": int(rest) if rest not in (None, "", "NA") else None, "orest": int(orest) if orest not in (None, "", "NA") else None,
                            "next_div": bool(nxt) and nxt[0].get("div_game") == "1", "prev_meet": prev_meet[-1].get(t) if prev_meet else None,
                            "last_away": last.get(t + "_away")})
            # update after the game
            hm = f(g["home_score"]) - f(g["away_score"])
            for t, m in ((g["home_team"], hm), (g["away_team"], -hm)):
                r = rec[t]; r[0 if m > 0 else (1 if m < 0 else 2)] += 1; last[t] = m
            last[g["home_team"] + "_away"] = False; last[g["away_team"] + "_away"] = True
            meet[frozenset((g["home_team"], g["away_team"]))].append({g["home_team"]: hm, g["away_team"]: -hm})
    return out
R = [r for r in team_rows() if r["cov"] is not None and r["season"] >= 2006]
SPOTS = [
    ("big_fav_vs_worse", "Favorite of 7+ against a team with a worse record (\"playing down\")", lambda r: r["line"] <= -7 and r["gp"] >= 3 and r["owp"] is not None and r["wp"] > r["owp"]),
    ("bad_dog_vs_good", "Bad team (win% <= .35) as an underdog to a good team (>= .65), week 5+", lambda r: r["week"] >= 5 and r["line"] > 0 and r["wp"] is not None and r["wp"] <= .35 and r["owp"] >= .65),
    ("letdown_after_blowout", "Favorite coming off a 21+ point win", lambda r: r["line"] < 0 and r["last"] is not None and r["last"] >= 21),
    ("bounce_after_blowout_loss", "Team coming off a 21+ point loss", lambda r: r["last"] is not None and r["last"] <= -21),
    ("thursday_road", "Road team on Thursday (short week), week 2+", lambda r: r["thu"] and not r["home"] and r["week"] >= 2),
    ("div_dog", "Underdog in a division game", lambda r: r["div"] and r["line"] > 0),
    ("div_dog_7", "Underdog of 7+ in a division game", lambda r: r["div"] and r["line"] >= 7),
    ("rest_edge", "Team with 3+ more days of rest (off a bye, Thursday-to-Sunday-week)", lambda r: r["rest"] is not None and r["orest"] is not None and r["rest"] - r["orest"] >= 3),
    ("lookahead_fav", "Favorite of 3+ whose next game is a division game", lambda r: r["line"] <= -3 and r["next_div"]),
    ("revenge", "Team that lost the first meeting this season (division rematch)", lambda r: r["prev_meet"] is not None and r["prev_meet"] < 0),
    ("home_dog", "Home underdog", lambda r: r["home"] and r["line"] > 0),
    ("road_fav_2nd_road", "Road favorite playing a second straight road game", lambda r: not r["home"] and r["line"] < 0 and r["last_away"] is True),
    ("double_digit_fav", "Favorite of 10+", lambda r: r["line"] <= -10),
]
def p_two(k, n):
    if n == 0: return 1.0
    z = (k - n / 2) / math.sqrt(n / 4); return math.erfc(abs(z) / math.sqrt(2))
def rate(rs): k = sum(1 for r in rs if r["cov"]); return k, len(rs), (k / len(rs) if rs else 0)
lines = ["Situational spots vs the closing spread, NFL regular season 2006-2025 (nflverse games.csv), pushes dropped",
         "break-even at -110 = 52.4%. SURVIVES = n>=150, beats 52.4% overall and in both halves (2006-15, 2016-25), p<0.05 overall", ""]
lines.append(f"{'spot':<28}{'n':>6}{'cover%':>8}{'06-15':>8}{'16-25':>8}{'21-25':>8}{'p':>8}  verdict")
keep = []
for key, label, fn in SPOTS:
    rs = [r for r in R if fn(r)]
    k, n, cr = rate(rs); a = rate([r for r in rs if r["season"] <= 2015]); b = rate([r for r in rs if r["season"] >= 2016]); c = rate([r for r in rs if r["season"] >= 2021])
    # test both directions: the spot team covering, or fading it
    side = "with" if cr >= .5 else "fade"
    eff = lambda x: x if side == "with" else 1 - x
    p = p_two(k, n)
    ok = n >= 150 and eff(cr) > .524 and eff(a[2]) > .524 and eff(b[2]) > .524 and p < .05
    lines.append(f"{key:<28}{n:>6}{cr*100:>7.1f}%{a[2]*100:>7.1f}%{b[2]*100:>7.1f}%{c[2]*100:>7.1f}%{p:>8.3f}  {'SURVIVES (' + side + ')' if ok else 'no edge'}")
    lines.append(f"    {label}")
    if ok: keep.append({"tier": "strong" if p < .05 / len(SPOTS) else "lean", "key": key, "label": label, "side": side, "n": n, "cover": round(cr, 4), "first_half": round(a[2], 4), "second_half": round(b[2], 4), "recent": round(c[2], 4), "p": round(p, 4)})
lines += ["", f"Multiple testing: {len(SPOTS)} spots were tested, so a p-value has to be under {0.05/len(SPOTS):.4f} (Bonferroni) to count as strong evidence.",
          "Survivors above that line are tagged 'lean' in situational_spots.json: shown in the dossier as a lean, never used in a projection."]
txt = "\n".join(lines); print(txt)
open(os.path.join(HERE, "research", "situational_backtest.txt"), "w").write(txt + "\n")
json.dump({"built": "2026-11-05", "seasons": "2006-2025", "spots": keep, "tested": [k for k, _, _ in SPOTS]}, open(os.path.join(HERE, "research", "situational_spots.json"), "w"), indent=1)
print(f"\n{len(keep)} of {len(SPOTS)} spots survive")
