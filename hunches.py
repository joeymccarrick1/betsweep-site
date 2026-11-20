#!/usr/bin/env python3
"""hunches.py - Hunches, /hunches/ (owner 11/19: "Can we make a thing that's like hunches? We can look at historical data,
losing/winning streaks, weather, similar defenses, things that could seriously affect players/the game"; "Wr/cb matchups, and history
like we're doing with RBs can be used for WR/TEs for hunches. Figure out how to put QBs on there too").

A hunch is a reason to like (or doubt) something that the projection does not spell out, written down with the evidence for it, the
strongest case against it, a verdict and - when FanDuel posts one - a leg to act on. Nothing here changes a projection or a price.

Engines (each is a plain count from this season's game log unless it says otherwise):
  rb      a lead back (12+ carries a game lately) against a defense lead backs have run on
  wr      the owner's weekly WR-vs-CB chart says FAVORABLE, and the defense has given up yards to lead receivers
  te      a tight end with real targets against a defense that tight ends have hurt
  qb      a quarterback against a defense that gives up passing TDs, with a team total that supports it
  back    a player in his first game back after missing two or more of his team's games (a caution, with what returns have done)
  streak  a team on a 3+ game winning or losing streak, with what such teams did against the spread the next week (games.csv)
  wind    15+ mph at an outdoor game, with what totals did in such games (games.csv)
  rematch the two teams have already met this season: what happened

Verdicts: Backed (evidence clears the bar and nothing serious against), Mixed (evidence for and a real case against), Caution, Info.
The first time a hunch appears in a week it is frozen with its leg in <clone>/data/hunches-w<W>.json so it can be graded later;
grade() marks last week's from the game log.

python3 hunches.py [<clone dir>] [<week>]   reads out/builder_data.json + in/*.json, writes out/hunches.html, out/hunches.json
python3 hunches.py --selftest
"""
import csv, html, json, os, re, sys
from mktxt import low as _mlow

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); IN = os.path.join(HERE, "in"); E = html.escape
sys.path.insert(0, HERE)


def num(x):
    try: return float(str(x).replace("%", "").strip() or 0)
    except Exception: return 0.0


def load_log(path=None):
    """This season's game log as dicts: w, pl, tm, pos, opp, att (pass), pyd, ptd, car, ryd, rtd, tgt, rec, recy, rectd."""
    v = json.load(open(path or os.path.join(IN, "gamelog.json")))["values"]; h = {k: i for i, k in enumerate(v[0])}; out = []
    g = lambda r, k: r[h[k]] if h.get(k) is not None and h[k] < len(r) else ""
    for r in v[1:]:
        if not r or not str(r[0]).isdigit(): continue
        out.append({"w": int(r[0]), "pl": g(r, "Player"), "tm": g(r, "Team"), "pos": g(r, "Pos"), "opp": g(r, "Opponent"), "att": num(g(r, "Pass Att")), "pyd": num(g(r, "Pass Yds")),
                    "ptd": num(g(r, "Pass TD")), "car": num(g(r, "Rush Att")), "ryd": num(g(r, "Rush Yds")), "rtd": num(g(r, "Rush TD")), "tgt": num(g(r, "Targets")),
                    "rec": num(g(r, "Receptions")), "recy": num(g(r, "Rec Yds")), "rectd": num(g(r, "Rec TD"))})
    return out


def leads(log, pos, key, floor):
    """Per defense: the stat lines of each opponent's lead player at `pos` (most `key` in that team-game, at least `floor`)."""
    by = {}
    for r in log:
        if r["pos"] == pos and r[key] >= floor:
            k = (r["opp"], r["w"], r["tm"])
            if k not in by or r[key] > by[k][key]: by[k] = r
    out = {}
    for (d, w, t), r in by.items(): out.setdefault(d, []).append(r)
    for d in out: out[d].sort(key=lambda r: r["w"])
    return out


def rank_worst(vals, team):
    """1 = most allowed. vals = {team: number}."""
    order = sorted(vals, key=lambda t: -vals[t]); return order.index(team) + 1 if team in order else None


def recent(log, pl, n=3):
    rows = sorted([r for r in log if r["pl"] == pl], key=lambda r: r["w"]); return rows[-n:], rows


def pick_leg(BD, pl, market, lo=-260, hi=130, want=-150, line=None):
    c = [l for l in BD["legs"] if l["pl"] == pl and l["m"] == market and not l.get("gl") and l.get("o") is not None and (l.get("fd") or {}).get("m") and lo <= l["o"] <= hi and (line is None or abs(l["ln"] - line) < 0.01)]
    if not c: return None
    dec = lambda o: 1 + o / 100 if o > 0 else 1 + 100 / -o
    l = min(c, key=lambda l: abs(dec(l["o"]) - dec(want)))
    bad = [f[1] for f in (l.get("fh") or []) if f and f[0] == "bad"]
    t = f"{pl} {int(l['ln']) if float(l['ln']).is_integer() else l['ln']}+ {_mlow(market)}"
    return {"t": t, "pl": pl, "m": market, "ln": l["ln"], "o": int(l["o"]), "p": round(l.get("p") or 0, 3), "fm": l["fd"]["m"], "fs": l["fd"]["s"], "bad": bad[:3]}


def game_of(BD, tm):
    for g in BD["games"]:
        if tm in (g["a"], g["b"]): return g
    return None


def script_against(g, tm):
    """The model's chance this team loses by 10+ (probs = [a by 10+, close and low, shootout, b by 10+], in %)."""
    try: return float(g["probs"][3] if tm == g["a"] else g["probs"][0])
    except Exception: return 0.0


def verdict(strength, against):
    serious = [a for a in against if a.get("s")]
    if strength >= 2 and not serious: return "Backed"
    if strength >= 1: return "Mixed"
    return "Info"


# ---------------------------------------------------------------- engines
def eng_rb(BD, log, W):
    out = []; L = leads(log, "RB", "car", 12)
    ypc = {}
    for d in {r["opp"] for r in log}:
        rb = [r for r in log if r["opp"] == d and r["pos"] == "RB"]; c = sum(r["car"] for r in rb)
        if c >= 60: ypc[d] = sum(r["ryd"] for r in rb) / c
    teams = {l["tm"]: l["opp"] for l in BD["legs"] if not l.get("gl") and l.get("tm")}
    for tm, opp in teams.items():
        g = game_of(BD, tm)
        if not g or g.get("fin"): continue
        backs = {l["pl"] for l in BD["legs"] if l.get("tm") == tm and l.get("pos") == "RB" and l["m"] == "Rushing Yards"}
        best = None
        for pl in backs:
            last, allr = recent(log, pl)
            if len(last) < 2: continue
            c = sum(r["car"] for r in last) / len(last)
            if c >= 12 and (best is None or c > best[1]): best = (pl, c, last, allr)
        if not best or opp not in L or len(L[opp]) < 4: continue
        pl, c, last, allr = best; rows = L[opp]; n = len(rows); hit = sum(1 for r in rows if r["ryd"] >= 60); avg = sum(r["ryd"] for r in rows) / n
        rk = rank_worst(ypc, opp) if opp in ypc else None
        strength = (1 if hit / n >= 0.7 else 0) + (1 if rk and rk <= 8 else 0) + (1 if avg >= 85 else 0)
        if strength < 2: continue
        ev = [f"{n} lead backs have had 12+ carries against {opp}: {hit} cleared 60 yards, average {avg:.0f}."]
        if rk: ev.append(f"{opp} allows {ypc[opp]:.2f} yards a carry to running backs, {ordinal(rk)} most in the league.")
        ev.append(f"{pl} has averaged {c:.0f} carries over his last {len(last)} games ({', '.join(str(int(r['ryd'])) for r in last)} yards).")
        ag = []
        sa = script_against(g, tm)
        if sa >= 40: ag.append({"t": f"The model has {tm} losing by 10+ in {sa:.0f}% of endings. Carries dry up when a team is chasing.", "s": 1})
        y = sum(r["ryd"] for r in last) / max(1, sum(r["car"] for r in last))
        if y < 3.4: ag.append({"t": f"He has averaged {y:.1f} yards a carry over those games.", "s": 1})
        leg = pick_leg(BD, pl, "Rushing Yards")
        if leg and leg["bad"]: ag.append({"t": "The builder flags this leg: " + ", ".join(leg["bad"]) + ".", "s": 1})
        if not ag: ag.append({"t": "A defense's record against lead backs is a handful of games; one long run or one blowout moves it.", "s": 0})
        out.append({"id": f"rb|{pl}", "kind": "rb", "g": g["gid"], "tm": tm, "who": pl, "title": f"{pl} can run on {opp}", "strength": strength, "ev": ev, "vs": ag, "leg": leg, "verdict": verdict(strength, ag)})
    return out


def ordinal(n): return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def eng_wr(BD, log, W, wrcb):
    out = []
    if not wrcb or len(wrcb) < 2: return out
    h = {k: i for i, k in enumerate(wrcb[0])}; L = leads(log, "WR", "tgt", 6)
    allowed = {}
    for d in {r["opp"] for r in log}:
        rows = [r for r in log if r["opp"] == d and r["pos"] == "WR"]; gms = len({r["w"] for r in rows})
        if gms >= 4: allowed[d] = sum(r["recy"] for r in rows) / gms
    legs_pl = {l["pl"]: l for l in BD["legs"] if not l.get("gl") and l["m"] == "Receiving Yards"}
    for r in wrcb[1:]:
        g = lambda k: r[h[k]] if h.get(k) is not None and h[k] < len(r) else ""
        if str(g("Week")) != str(W) or g("CB Matchup Flag") not in ("FAVORABLE", "DIFFICULT") or g("Flag Confidence") not in ("HIGH", "MEDIUM"): continue
        pl = g("WR"); l0 = legs_pl.get(pl); share = num(g("Proj Target %")); share = share * 100 if share <= 1 else share      # the chart writes 0.24 some weeks and 24% others
        if not l0 or share < 17: continue
        if g("CB Matchup Flag") == "DIFFICULT":
            gm = game_of(BD, l0["tm"])
            if gm and not gm.get("fin"):
                cb = g("Primary CB")
                out.append({"id": f"wrx|{pl}", "kind": "wr", "g": gm["gid"], "tm": l0["tm"], "who": pl, "title": f"{pl} draws a tough matchup against {l0['opp']}", "strength": 0,
                            "ev": [f"The WR-vs-CB chart rates this matchup difficult ({g('Flag Confidence').lower()} confidence)" + (f": mostly {cb}" if cb else "") + ".", f"He projects for about {share:.0f}% of his team's targets."],
                            "vs": [{"t": "A top receiver gets his targets against anyone, and the chart projects coverage rather than knowing it.", "s": 0}], "leg": None, "verdict": "Caution", "note": "Go easy on his yardage overs this week."})
            continue
        tm, opp = l0["tm"], l0["opp"]; gm = game_of(BD, tm)
        if not gm or gm.get("fin"): continue
        last, allr = recent(log, pl)
        if len(last) < 2: continue
        tg = sum(x["tgt"] for x in last) / len(last)
        if tg < 5.5: continue
        rows = L.get(opp, []); n = len(rows); hit = sum(1 for x in rows if x["recy"] >= 60); rk = rank_worst(allowed, opp) if opp in allowed else None
        strength = 1 + (1 if n >= 4 and hit / n >= 0.6 else 0) + (1 if rk and rk <= 10 else 0)
        cb = g("Primary CB"); ev = [f"The WR-vs-CB chart rates this matchup favorable ({g('Flag Confidence').lower()} confidence)" + (f": mostly {cb}" if cb else "") + "."]
        if n >= 4: ev.append(f"{n} lead receivers have had 6+ targets against {opp}: {hit} cleared 60 yards, average {sum(x['recy'] for x in rows) / n:.0f}.")
        if rk: ev.append(f"{opp} allows {allowed[opp]:.0f} yards a game to wide receivers, {ordinal(rk)} most.")
        ev.append(f"{pl} has averaged {tg:.1f} targets over his last {len(last)} games ({', '.join(str(int(x['recy'])) for x in last)} yards).")
        ag = []
        season = sum(x["tgt"] for x in allr) / len(allr)
        if len(allr) >= 5 and tg < season * 0.75: ag.append({"t": f"His targets are trending down: {tg:.1f} lately against {season:.1f} on the season.", "s": 1})
        leg = pick_leg(BD, pl, "Receiving Yards")
        flags = [f[1] for f in (l0.get("fh") or []) if f and f[0] == "bad"]
        if any("QB" in f for f in flags): ag.append({"t": "His quarterback situation is flagged (" + ", ".join(f for f in flags if "QB" in f) + ").", "s": 1})
        if leg and leg["bad"]: ag.append({"t": "The builder flags this leg: " + ", ".join(leg["bad"]) + ".", "s": 1})
        if script_against(gm, tm) < 15 and (gm["probs"][0] if tm == gm["a"] else gm["probs"][3]) >= 55: ag.append({"t": f"The model has {tm} winning big most of the time; a team in front throws less late.", "s": 0})
        if not ag: ag.append({"t": "The chart projects who covers whom; a defense can move its best corner or play more zone.", "s": 0})
        out.append({"id": f"wr|{pl}", "kind": "wr", "g": gm["gid"], "tm": tm, "who": pl, "title": f"{pl} has the matchup against {opp}", "strength": strength, "ev": ev, "vs": ag, "leg": leg, "verdict": verdict(strength, ag)})
    return out


def eng_te(BD, log, W):
    out = []; L = leads(log, "TE", "tgt", 4)
    for pl, l0 in {l["pl"]: l for l in BD["legs"] if not l.get("gl") and l["m"] == "Receiving Yards" and l.get("pos") == "TE"}.items():
        tm, opp = l0["tm"], l0["opp"]; gm = game_of(BD, tm)
        if not gm or gm.get("fin"): continue
        last, allr = recent(log, pl)
        if len(last) < 2 or sum(x["tgt"] for x in last) / len(last) < 5: continue
        rows = L.get(opp, []); n = len(rows)
        if n < 4: continue
        hit = sum(1 for x in rows if x["recy"] >= 45); avg = sum(x["recy"] for x in rows) / n
        strength = (1 if hit / n >= 0.6 else 0) + (1 if avg >= 55 else 0)
        if strength < 2: continue
        tg = sum(x["tgt"] for x in last) / len(last)
        ev = [f"{n} lead tight ends have had 4+ targets against {opp}: {hit} cleared 45 yards, average {avg:.0f}.", f"{pl} has averaged {tg:.1f} targets over his last {len(last)} games ({', '.join(str(int(x['recy'])) for x in last)} yards)."]
        ag = []; leg = pick_leg(BD, pl, "Receiving Yards")
        if leg and leg["bad"]: ag.append({"t": "The builder flags this leg: " + ", ".join(leg["bad"]) + ".", "s": 1})
        if not ag: ag.append({"t": "Tight-end yardage swings on one or two catches; four to nine games is a thin record for a defense.", "s": 0})
        out.append({"id": f"te|{pl}", "kind": "te", "g": gm["gid"], "tm": tm, "who": pl, "title": f"{pl} against a defense tight ends have hurt", "strength": strength, "ev": ev, "vs": ag, "leg": leg, "verdict": verdict(strength, ag)})
    return out


def eng_qb(BD, log, W, wind):
    out = []; per = {}
    for d in {r["opp"] for r in log}:
        gm = {}
        for r in log:
            if r["opp"] == d and r["pos"] == "QB" and r["att"] >= 15: gm[(r["w"], r["tm"])] = r
        if len(gm) >= 4: per[d] = list(gm.values())
    rate = {d: sum(r["ptd"] for r in rows) / len(rows) for d, rows in per.items()}
    for pl, l0 in {l["pl"]: l for l in BD["legs"] if not l.get("gl") and l["m"] == "Passing TDs"}.items():
        tm, opp = l0["tm"], l0["opp"]; gm = game_of(BD, tm)
        if not gm or gm.get("fin") or opp not in per: continue
        imp = gm["pa"] if tm == gm["a"] else gm["pb"]; rows = per[opp]; n = len(rows); two = sum(1 for r in rows if r["ptd"] >= 2); rk = rank_worst(rate, opp)
        strength = (1 if rk <= 8 else 0) + (1 if two / n >= 0.6 else 0) + (1 if imp >= 24 else 0)
        if strength < 2 or imp < 21: continue
        last, allr = recent(log, pl)
        ev = [f"{opp} has allowed {rate[opp]:.1f} passing TDs a game, {ordinal(rk)} most: {two} of {n} starting quarterbacks threw 2 or more.", f"The betting lines put {tm} at about {imp:.0f} points."]
        if last: ev.append(f"{pl}'s last {len(last)} games: {', '.join(str(int(r['ptd'])) for r in last)} passing TDs.")
        ag = []
        if wind.get(gm["gid"], 0) >= 15: ag.append({"t": f"Wind is forecast around {wind[gm['gid']]:.0f} mph. See the weather hunch for this game.", "s": 1})
        why = (gm.get("ia") if tm == gm["a"] else gm.get("ib")) or {}
        outs = [w for w in (why.get("why") or []) if " out" in w]
        if outs: ag.append({"t": "Missing pieces on his side: " + "; ".join(outs[:2]) + ".", "s": 1})
        if last and len(allr) >= 4 and sum(r["ptd"] for r in allr) / len(allr) < 1.2: ag.append({"t": f"He has averaged {sum(r['ptd'] for r in allr) / len(allr):.1f} passing TDs a game this season.", "s": 1})
        leg = pick_leg(BD, pl, "Passing TDs", lo=-400, hi=250, want=-120, line=2)
        if not ag: ag.append({"t": "Touchdowns are the least predictable stat on the board: a team can score three times on the ground.", "s": 0})
        out.append({"id": f"qb|{pl}", "kind": "qb", "g": gm["gid"], "tm": tm, "who": pl, "title": f"{pl} against a defense that gives up passing TDs", "strength": strength, "ev": ev, "vs": ag, "leg": leg, "verdict": verdict(strength, ag)})
    return out


def eng_back(BD, log, W):
    """First game back after missing 2+ of his team's games. History: every such return this season (3+ games before the gap)."""
    out = []; tw = {}; pw = {}
    for r in log: tw.setdefault(r["tm"], set()).add(r["w"]); pw.setdefault(r["pl"], []).append(r)
    main = lambda r: r["ryd"] if r["pos"] == "RB" else r["recy"]
    ratios = []
    for pl, rows in pw.items():
        rows.sort(key=lambda r: r["w"])
        if rows[0]["pos"] not in ("RB", "WR", "TE"): continue
        for i in range(3, len(rows)):
            miss = sum(1 for w in tw.get(rows[i]["tm"], ()) if rows[i - 1]["w"] < w < rows[i]["w"]); before = sum(main(x) for x in rows[:i]) / i
            if miss >= 2 and before >= 30: ratios.append(main(rows[i]) / before)
    hist = (sorted(ratios)[len(ratios) // 2], len(ratios), sum(1 for x in ratios if x >= 1)) if len(ratios) >= 8 else None      # the median: one big day back should not carry the average
    for pl in {l["pl"] for l in BD["legs"] if not l.get("gl") and l.get("pos") in ("RB", "WR", "TE")}:
        rows = sorted(pw.get(pl, []), key=lambda r: r["w"])
        if len(rows) < 3: continue
        tm = next(l["tm"] for l in BD["legs"] if l["pl"] == pl); gm = game_of(BD, tm)
        if not gm or gm.get("fin"): continue
        miss = sum(1 for w in tw.get(tm, ()) if w > rows[-1]["w"])
        if miss < 2: continue
        ev = [f"{pl} has not played since Week {rows[-1]['w']}; {tm} has played {miss} games without him."]
        if hist: ev.append(f"This season {hist[1]} players have come back after missing 2+ games: {hist[2]} matched their usual yardage in the first game back, and the typical one got {hist[0] * 100:.0f}% of it.")
        out.append({"id": f"back|{pl}", "kind": "back", "g": gm["gid"], "tm": tm, "who": pl, "title": f"{pl}: first game back", "strength": 0, "ev": ev,
                    "vs": [{"t": "A team that activates a player expects to use him; the price may already have the rust in it.", "s": 0}], "leg": None, "verdict": "Caution"})
    return out


def read_games(path=None):
    try: return list(csv.DictReader(open(path or os.path.join(IN, "games.csv"))))
    except Exception: return []


def eng_streak(BD, games, season):
    """3+ game streaks. History: every regular-season game in games.csv where a team came in on a 3+ streak, against the spread."""
    out = []; done = [g for g in games if g.get("game_type") == "REG" and g.get("home_score") not in ("", None)]
    done.sort(key=lambda g: (int(g["season"]), int(g["week"])))
    cover = {"W": [0, 0], "L": [0, 0]}; cur = {}
    for g in done:
        s = int(g["season"]); res = num(g["home_score"]) - num(g["away_score"]); sp = g.get("spread_line")
        for tm, mine in ((g["home_team"], res), (g["away_team"], -res)):
            k = (s, tm); st = cur.get(k, ("", 0))
            if st[1] >= 3 and sp not in ("", None) and s < int(season):
                line = num(sp) if tm == g["home_team"] else -num(sp)          # points this team is favoured by
                if mine != line: cover[st[0]][1] += 1; cover[st[0]][0] += 1 if mine > line else 0
            r = "W" if mine > 0 else "L" if mine < 0 else "T"
            cur[k] = (r, st[1] + 1) if r == st[0] else (r, 1)
    for g in BD["games"]:
        if g.get("fin"): continue
        for tm in (g["a"], g["b"]):
            st = cur.get((int(season), tm))
            if not st or st[1] < 3 or st[0] == "T": continue
            c = cover[st[0]]; pct = c[0] / c[1] * 100 if c[1] >= 100 else None; word = "won" if st[0] == "W" else "lost"
            ev = [f"{tm} has {word} {st[1]} straight."]
            if pct is not None: ev.append(f"In earlier seasons, teams that had {word} 3 or more in a row covered the spread {pct:.0f}% of the time the next week ({c[1]} games).")
            flat = pct is None or 47.5 <= pct <= 52.5
            ag = [{"t": "The spread already knows about the streak." + (" The record above is a coin flip: no edge either way." if flat else ""), "s": 0}]
            out.append({"id": f"streak|{tm}", "kind": "streak", "g": g["gid"], "tm": tm, "who": tm, "title": f"{tm}: {st[1]} straight {'wins' if st[0] == 'W' else 'losses'}", "strength": 0, "ev": ev, "vs": ag, "leg": None, "verdict": "Info"})
    return out


def eng_wind(BD, games, wx, W):
    out = []; wind = {}
    if not wx or len(wx) < 2: return out, wind
    h = {k: i for i, k in enumerate(wx[0])}
    hi = [g for g in games if g.get("game_type") == "REG" and g.get("home_score") not in ("", None) and g.get("total_line") not in ("", None) and g.get("wind") not in ("", None) and num(g["wind"]) >= 15 and g.get("roof") in ("outdoors", "open")]
    n = len(hi); under = sum(1 for g in hi if num(g["home_score"]) + num(g["away_score"]) < num(g["total_line"])); push = sum(1 for g in hi if num(g["home_score"]) + num(g["away_score"]) == num(g["total_line"]))
    for r in wx[1:]:
        g = lambda k: r[h[k]] if h.get(k) is not None and h[k] < len(r) else ""
        if str(g("Week")) != str(W): continue
        gm = next((x for x in BD["games"] if {x["a"], x["b"]} == {g("Matchup Team 1"), g("Matchup Team 2")}), None)
        if not gm or gm.get("fin"): continue
        w = num(g("Wind MPH")); wind[gm["gid"]] = w if g("Roof Status") == "outdoors" else 0
        if g("Roof Status") != "outdoors" or w < 15: continue
        ev = [f"Forecast at kickoff: {w:.0f} mph wind" + (f", gusts to {num(g('Gust MPH')):.0f}" if num(g("Gust MPH")) > w else "") + (f", {g('Precipitation Type')}" if g("Precipitation Type") not in ("", "none") else "") + f" ({g('Forecast Updated')})."]
        if n >= 40: ev.append(f"In {n} outdoor games with 15+ mph wind, {under} finished under the total and {n - under - push} over ({under / max(1, n - push) * 100:.0f}% under).")
        out.append({"id": f"wind|{gm['gid']}", "kind": "wind", "g": gm["gid"], "tm": "", "who": gm["gid"], "title": f"Wind in {gm['a']}-{gm['b']}", "strength": 0, "ev": ev,
                    "vs": [{"t": "Forecasts move, and the total has usually been bet down by the time the wind is news.", "s": 0}], "leg": None, "verdict": "Caution", "note": "Think twice about long passing and deep-receiver legs here."})
    return out, wind


def eng_rematch(BD, games, log, season):
    out = []
    for g in BD["games"]:
        if g.get("fin"): continue
        prev = [x for x in games if x.get("season") == str(season) and x.get("game_type") == "REG" and x.get("home_score") not in ("", None) and {x["home_team"], x["away_team"]} == {g["a"], g["b"]}]
        if not prev: continue
        x = prev[-1]; w = int(x["week"])
        ev = [f"Week {w}: {x['away_team']} {int(num(x['away_score']))}, {x['home_team']} {int(num(x['home_score']))}."]
        tops = sorted([r for r in log if r["w"] == w and r["tm"] in (g["a"], g["b"]) and r["opp"] in (g["a"], g["b"])], key=lambda r: -(r["ryd"] + r["recy"] + r["pyd"] / 4))[:4]
        for r in tops:
            ev.append(f"{r['pl']}: " + (f"{int(r['pyd'])} passing yards, {int(r['ptd'])} TD" if r["pos"] == "QB" else f"{int(r['car'])} carries for {int(r['ryd'])}" if r["pos"] == "RB" else f"{int(r['rec'])} catches for {int(r['recy'])} on {int(r['tgt'])} targets") + ".")
        out.append({"id": f"rematch|{g['gid']}", "kind": "rematch", "g": g["gid"], "tm": "", "who": g["gid"], "title": f"{g['a']}-{g['b']} is a rematch", "strength": 0, "ev": ev,
                    "vs": [{"t": "Rosters change between meetings. Check who has been traded, hurt or returned since before leaning on these lines.", "s": 0}], "leg": None, "verdict": "Info"})
    return out


# ---------------------------------------------------------------- freeze, grade, page
STAT = {"Rushing Yards": "ryd", "Receiving Yards": "recy", "Passing TDs": "ptd"}


def grade(frozen, log):
    """Mark each frozen hunch that carries a leg: hit / miss / no game, from the game log for its week."""
    w = int(frozen.get("week") or 0); rows = {r["pl"]: r for r in log if r["w"] == w}; n = hit = 0
    if not any(r["w"] == w for r in log): return None
    for hch in frozen.get("hunches", []):
        l = hch.get("leg")
        if not l or l["m"] not in STAT: continue
        r = rows.get(l["pl"])
        if not r: hch["res"] = "no game"; continue
        v = r[STAT[l["m"]]]; hch["res"] = "hit" if v >= l["ln"] else "miss"; hch["got"] = v
        if hch.get("verdict") == "Backed": n += 1; hit += hch["res"] == "hit"
    frozen["graded"] = {"backed": n, "hit": hit}
    return frozen


def build(clone=None, week=None):
    BD = json.load(open(os.path.join(OUT, "builder_data.json"))); W = int(week or BD["week"]); log = [r for r in load_log() if r["w"] < W]
    games = read_games(); season = max((int(g["season"]) for g in games), default=2026)
    try: wx = json.load(open(os.path.join(IN, "weather.json")))["values"]
    except Exception: wx = []
    try: wrcb = json.load(open(os.path.join(IN, "wrcb.json")))["values"]
    except Exception: wrcb = []
    wh, wind = eng_wind(BD, games, wx, W)
    H = eng_rb(BD, log, W) + eng_wr(BD, log, W, wrcb) + eng_te(BD, log, W) + eng_qb(BD, log, W, wind) + eng_back(BD, log, W) + wh + eng_streak(BD, games, season) + eng_rematch(BD, games, log, season)
    # the injury report is a case against any hunch that leans on the player (owner rule: read injuries before a slip)
    try:
        av = json.load(open(os.path.join(IN, "avail.json")))["values"]
        q = {r[1]: r[4].title() for r in av[1:] if len(r) > 4 and str(r[0]) == str(W) and r[4] in ("QUESTIONABLE", "DOUBTFUL", "OUT")}
    except Exception: q = {}
    for hch in H:
        st = q.get(hch["who"])
        if st and hch["kind"] in ("rb", "wr", "te", "qb") and hch["verdict"] in ("Backed", "Mixed"):
            hch["vs"] = [{"t": f"He is listed {st} on the injury report.", "s": 1}] + [a for a in hch["vs"] if a.get("s")]
            hch["verdict"] = "Caution" if st in ("Doubtful", "Out") else verdict(hch["strength"], hch["vs"])
            if st in ("Doubtful", "Out"): hch["leg"] = None
    # freeze: a hunch keeps the leg and verdict it first appeared with (so the grade is of what was shown), evidence refreshes
    ddir = os.path.join(clone, "data") if clone else None; prev = {}; last = None
    if ddir:
        try: prev = {x["id"]: x for x in json.load(open(os.path.join(ddir, f"hunches-w{W}.json"))).get("hunches", [])}
        except Exception: prev = {}
        try:
            lf = json.load(open(os.path.join(ddir, f"hunches-w{W - 1}.json")))
            if not lf.get("graded"): lf = grade(lf, load_log()) or lf
            last = lf
        except Exception: last = None
    for hch in H:
        p = prev.get(hch["id"])
        if p: hch["first"] = p.get("first"); hch["leg0"] = p.get("leg0") or p.get("leg"); hch["verdict0"] = p.get("verdict0") or p.get("verdict")
        else: hch["first"] = BD.get("built"); hch["leg0"] = hch.get("leg"); hch["verdict0"] = hch["verdict"]
    keep = [dict(p, gone=1) for i, p in prev.items() if i not in {h["id"] for h in H}]      # shown earlier this week, no longer firing: still graded
    data = {"week": W, "built": BD.get("built"), "hunches": H + keep, "games": {g["gid"]: {"a": g["a"], "b": g["b"], "kick": g.get("kick", ""), "ko": g.get("ko") or 0} for g in BD["games"]}}
    frozen = {"week": W, "hunches": [{"id": h["id"], "kind": h["kind"], "g": h["g"], "who": h["who"], "title": h["title"], "verdict": h.get("verdict0") or h["verdict"], "leg": h.get("leg0"), "leg0": h.get("leg0"), "verdict0": h.get("verdict0"), "first": h.get("first")} for h in H + keep]}
    json.dump(data, open(os.path.join(OUT, "hunches.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(frozen, open(os.path.join(OUT, f"hunches-w{W}.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    if last and last.get("graded"): json.dump(last, open(os.path.join(OUT, f"hunches-w{W - 1}.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    open(os.path.join(OUT, "hunches.html"), "w").write(page(data, last))
    k = {}
    for h in H: k[h["kind"]] = k.get(h["kind"], 0) + 1
    return f"wrote out/hunches.html + hunches.json: {len(H)} hunches, week {W} ({', '.join(f'{v} {a}' for a, v in sorted(k.items()))}); {sum(1 for h in H if h['verdict'] == 'Backed')} backed"


KIND = {"rb": "Run game", "wr": "WR vs CB", "te": "Tight end", "qb": "Quarterback", "back": "Back from injury", "wind": "Weather", "streak": "Streak", "rematch": "Rematch"}
ORDER = {"Backed": 0, "Mixed": 1, "Caution": 2, "Info": 3}


def amo(o): return f"+{o}" if o > 0 else f"−{-o}"


def card(h):
    leg = h.get("leg"); v = h["verdict"]
    lg = ""
    if leg:
        url = f"https://sportsbook.fanduel.com/addToBetslip?marketId[0]={E(str(leg['fm']))}&amp;selectionId[0]={E(str(leg['fs']))}"
        lg = f'<div class="hleg"><span><small>The leg</small><b>{E(leg["t"])}</b></span><span class="hpr">{amo(leg["o"])}</span><a class="bsbtn" href="{url}" target="_blank" rel="noopener sponsored">Open on FanDuel</a></div>'
    elif h.get("note"): lg = f'<p class="hnote">{E(h["note"])}</p>'
    return (f'<article class="hc v{v.lower()}" data-kind="{h["kind"]}" data-v="{v}"><header><span class="hk">{E(KIND[h["kind"]])}</span><span class="hv">{E(v)}</span></header>'
            f'<h3>{E(h["title"])}</h3><ul class="hev">{"".join(f"<li>{E(x)}</li>" for x in h["ev"])}</ul>'
            f'<p class="hvs"><b>The case against.</b> {" ".join(E(a["t"]) for a in h["vs"])}</p>{lg}</article>')


def page(data, last=None):
    W = data["week"]; G = data["games"]; live = [h for h in data["hunches"] if not h.get("gone")]
    by = {}
    for h in live: by.setdefault(h["g"], []).append(h)
    secs = []
    for gid in sorted(by, key=lambda g: (G.get(g, {}).get("ko") or 0, g)):
        hs = sorted(by[gid], key=lambda h: (ORDER[h["verdict"]], -h.get("strength", 0))); g = G.get(gid, {})
        secs.append(f'<section class="hg" id="h-{E(gid)}"><h2>{E(g.get("a", ""))} at {E(g.get("b", ""))} <small>{E(g.get("kick", ""))}</small></h2>{"".join(card(h) for h in hs)}</section>')
    kinds = [k for k in KIND if any(h["kind"] == k for h in live)]
    chips = '<button type="button" class="on" data-k="">All</button><button type="button" data-k="Backed">Backed only</button>' + "".join(f'<button type="button" data-k="{k}">{E(KIND[k])}</button>' for k in kinds)
    rec = ""
    if last and last.get("graded") and last["graded"]["backed"]:
        gr = last["graded"]; rec = f'<p class="hrec">Last week\'s backed hunches: <b>{gr["hit"]} of {gr["backed"]}</b> legs hit.</p>'
    else: rec = '<p class="hrec">Hunches are graded each Tuesday against the leg they were first shown with. The record starts with this week.</p>'
    nb = sum(1 for h in live if h["verdict"] == "Backed")
    try:
        import account as ACCT; _link, _base = ACCT._base_css()
    except Exception: _link, _base = "", ""
    return f"""<title>Hunches · BetSweep</title>
<meta name="description" content="NFL Week {W} hunches with the evidence: lead backs against soft run defenses, receivers with the cornerback matchup, quarterbacks against leaky secondaries, streaks, weather and returns from injury. Each with the case against.">
{_link}
<style>{_base}
{CSS}</style>
<div class="hx">
<div class="hhead"><h1>Hunches</h1><span class="sub">Week {W}. Reasons to like or doubt a spot that the projection does not spell out. Each comes with its evidence, the case against, and a verdict. {len(live)} this week, {nb} backed.</span></div>
{rec}
<div class="hchips" id="hchips" role="group" aria-label="Filter hunches">{chips}</div>
{"".join(secs) if secs else '<p class="hnone">No hunches clear the bar yet this week. Prop prices fill in by Thursday.</p>'}
<p class="hnone" id="hempty" hidden>Nothing of that kind this week.</p>
<p class="foot">A hunch is a lead, not a projection. Counts come from this season's game log; a defense's record against one position is a small sample. Backed means the evidence cleared our bar and we found no serious case against, not that it will hit. 21+ | Gamble responsibly.</p>
</div>
<script>{JS}</script>
"""


CSS = """
.hx{max-width:720px;margin:14px auto 40px;padding:0 12px}
.hx .hhead{margin:0 4px 12px} .hx h1{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:40px;letter-spacing:-.02em;line-height:1}
.hx .sub{display:block;margin-top:6px;color:var(--mute);font-size:14px;line-height:1.45}
.hx .hrec{margin:0 4px 12px;font-size:14px;line-height:1.45;color:var(--ink)}
.hx .hchips{display:flex;gap:8px;overflow-x:auto;padding:2px 0 10px;margin:0 0 4px;scrollbar-width:none} .hx .hchips::-webkit-scrollbar{display:none}
.hx .hchips button{flex:none;font:inherit;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.04em;min-height:40px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer}
.hx .hchips button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.hx .hg{margin:0 0 18px} .hx .hg h2{margin:14px 4px 10px;font-family:var(--display);font-weight:700;font-size:21px;line-height:1.15;color:var(--ink);display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.hx .hg h2 small{font-family:var(--body);font-weight:500;font-size:13.5px;color:var(--mute)}
.hx .hc{border:1px solid var(--line);border-left-width:5px;border-radius:12px;background:var(--card);padding:12px 14px;margin:0 0 10px}
.hx .hc.vbacked{border-left-color:var(--good)} .hx .hc.vmixed{border-left-color:var(--gold,#c98a1b)} .hx .hc.vcaution{border-left-color:var(--red)} .hx .hc.vinfo{border-left-color:var(--line)}
.hx .hc header{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:0 0 6px;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.04em;color:var(--mute)}
.hx .hc .hv{color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:3px 10px} .hx .hc.vbacked .hv{background:var(--good);border-color:var(--good);color:#fff}
.hx .hc h3{margin:0 0 8px;font-family:var(--display);font-weight:700;font-size:19px;line-height:1.2;color:var(--ink)}
.hx .hev{margin:0 0 8px;padding:0 0 0 18px;font-size:14.5px;line-height:1.45;color:var(--ink)} .hx .hev li{margin:0 0 4px}
.hx .hvs{margin:0 0 4px;font-size:14px;line-height:1.45;color:var(--mute)} .hx .hvs b{color:var(--ink);font-weight:700}
.hx .hnote{margin:8px 0 0;font-size:14px;line-height:1.45;color:var(--ink);font-weight:600}
.hx .hleg{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 12px;align-items:center;margin-top:10px;padding-top:10px;border-top:1px solid var(--line)}
.hx .hleg small{display:block;font-size:12px;color:var(--mute)} .hx .hleg b{font-size:15.5px;font-weight:700;color:var(--ink)} .hx .hleg .hpr{font-family:var(--display);font-weight:800;font-size:20px;color:var(--ink)}
.hx .hleg a.bsbtn{grid-column:1 / -1;text-decoration:none;display:flex;min-height:46px;justify-content:center;align-items:center;font-size:15px;box-sizing:border-box}
.hx .hnone{color:var(--mute);font-size:15px;line-height:1.5;margin:10px 4px} .hx .foot{margin:18px 4px 0;color:var(--mute);font-size:12px;line-height:1.5}
@media (max-width:380px){.hx h1{font-size:34px}}
"""

JS = r"""
(function(){
  var chips = document.getElementById('hchips'); if(!chips) return;
  function apply(k){ var any = false;
    document.querySelectorAll('.hx .hg').forEach(function(sec){ var n = 0; sec.querySelectorAll('.hc').forEach(function(c){ var ok = !k || c.getAttribute('data-kind') === k || c.getAttribute('data-v') === k; c.hidden = !ok; if(ok) n++; }); sec.hidden = !n; if(n) any = true; });
    document.getElementById('hempty').hidden = any; }
  chips.addEventListener('click', function(e){ var b = e.target.closest && e.target.closest('button'); if(!b) return;
    chips.querySelectorAll('button').forEach(function(x){ x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); }); apply(b.getAttribute('data-k')); });
  if(location.hash && document.querySelector(location.hash)) document.querySelector(location.hash).scrollIntoView();
})();
"""


def selftest():
    ok = [0, 0]
    def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
    mk = lambda w, pl, tm, pos, opp, **k: dict({"w": w, "pl": pl, "tm": tm, "pos": pos, "opp": opp, "att": 0, "pyd": 0, "ptd": 0, "car": 0, "ryd": 0, "rtd": 0, "tgt": 0, "rec": 0, "recy": 0, "rectd": 0}, **k)
    log = []
    for w, (t, y) in enumerate([("AAA", 110), ("BBB", 95), ("CCC", 72), ("DDD", 130), ("EEE", 40)], 1):
        log.append(mk(w, f"Back {t}", t, "RB", "SOFT", car=20, ryd=y)); log.append(mk(w, f"Sub {t}", t, "RB", "SOFT", car=5, ryd=12))
    for w in (3, 4, 5): log.append(mk(w, "Lead Guy", "XXX", "RB", "ZZZ", car=18, ryd=80))
    for d in ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"):
        for w in (1, 2, 3, 4): log.append(mk(w, f"R{d}{w}", "T" + d, "RB", d, car=20, ryd=60))
    L = leads(log, "RB", "car", 12)
    check(len(L["SOFT"]) == 5 and all(r["pl"].startswith("Back") for r in L["SOFT"]), "leads(): one lead back per team-game, the backup is not counted")
    BD = {"week": 6, "built": "t", "games": [{"gid": "SOFT-XXX", "a": "SOFT", "b": "XXX", "pa": 17, "pb": 27, "probs": [5, 30, 25, 40], "ko": 1, "kick": "Sun"}],
          "legs": [{"pl": "Lead Guy", "tm": "XXX", "opp": "SOFT", "pos": "RB", "g": "SOFT-XXX", "m": "Rushing Yards", "ln": 60.0, "o": -150, "p": .6, "fd": {"m": "1.1", "s": "22"}, "fh": []},
                   {"pl": "Lead Guy", "tm": "XXX", "opp": "SOFT", "pos": "RB", "g": "SOFT-XXX", "m": "Rushing Yards", "ln": 100.0, "o": 300, "p": .2, "fd": {"m": "1.1", "s": "23"}, "fh": []}]}
    H = eng_rb(BD, log, 6)
    check(len(H) == 1 and H[0]["who"] == "Lead Guy" and H[0]["verdict"] == "Backed" and H[0]["leg"]["ln"] == 60.0 and H[0]["leg"]["fs"] == "22", f"a lead back against a defense 4 of 5 lead backs cleared 60 on is Backed, with the leg nearest -150 ({[(h['who'], h['verdict']) for h in H]})")
    BD2 = json.loads(json.dumps(BD)); BD2["games"][0]["probs"] = [50, 20, 20, 10]
    H2 = eng_rb(BD2, log, 6)
    check(H2 and H2[0]["verdict"] == "Mixed" and any("losing by 10+" in a["t"] for a in H2[0]["vs"]), "the same hunch is Mixed when the model has his team losing big half the time")
    BD3 = json.loads(json.dumps(BD)); BD3["legs"][0]["fh"] = [["bad", "Losing side", ""]]
    check(eng_rb(BD3, log, 6)[0]["verdict"] == "Mixed", "a builder risk flag on the leg makes it Mixed")
    fr = {"week": 6, "hunches": [{"id": "rb|Lead Guy", "verdict": "Backed", "leg": {"pl": "Lead Guy", "m": "Rushing Yards", "ln": 60.0}}, {"id": "x", "verdict": "Backed", "leg": {"pl": "Nobody", "m": "Rushing Yards", "ln": 10}}]}
    g = grade(fr, log + [mk(6, "Lead Guy", "XXX", "RB", "SOFT", car=22, ryd=61)])
    check(g["graded"] == {"backed": 1, "hit": 1} and g["hunches"][0]["res"] == "hit" and g["hunches"][1]["res"] == "no game", f"grade(): 61 clears 60; a player with no game is not counted ({g['graded']})")
    check(grade({"week": 9, "hunches": []}, log) is None, "grade() waits for the week's game log")
    games = []
    for s in (2020, 2021):
        for w in range(1, 9):
            games.append({"season": str(s), "week": str(w), "game_type": "REG", "home_team": "WIN", "away_team": f"O{w}", "home_score": "30", "away_score": "10", "spread_line": "7", "total_line": "44", "wind": "18", "roof": "outdoors"})
    games += [{"season": "2026", "week": str(w), "game_type": "REG", "home_team": "SOFT", "away_team": f"Q{w}", "home_score": "10", "away_score": "20", "spread_line": "0", "total_line": "44", "wind": "", "roof": "dome"} for w in (1, 2, 3)]
    S = eng_streak(BD, games, 2026)
    check(len(S) == 1 and S[0]["who"] == "SOFT" and "lost 3 straight" in S[0]["ev"][0] and S[0]["verdict"] == "Info", "three straight losses is an Info hunch")
    wx = [["Week", "Matchup Team 1", "Matchup Team 2", "Roof Status", "Wind MPH", "Gust MPH", "Precipitation Type", "Forecast Updated"], ["6", "SOFT", "XXX", "outdoors", "18", "25", "none", "now"]]
    Wd, wind = eng_wind(BD, games, wx, 6)
    check(len(Wd) == 1 and wind["SOFT-XXX"] == 18 and Wd[0]["verdict"] == "Caution", "18 mph outdoors is a Caution hunch")
    wx[1][3] = "dome"; check(eng_wind(BD, games, wx, 6)[0] == [], "a dome game gets no wind hunch")
    pg = page({"week": 6, "hunches": H + S + Wd, "games": {"SOFT-XXX": {"a": "SOFT", "b": "XXX", "kick": "Sun", "ko": 1}}})
    check("Open on FanDuel" in pg and "marketId[0]=1.1&amp;selectionId[0]=22" in pg and pg.count('class="hc ') == 3 and "The case against." in pg, "the page carries every card, the case against and the FanDuel link by ids")
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)


if __name__ == "__main__":
    if "--selftest" in sys.argv: selftest()
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    print(build(a[0] if a else None, a[1] if len(a) > 1 else None))
