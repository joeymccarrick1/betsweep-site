"""projsnaps.py - projected offensive snap share per player for the projection week (dev-log item 7).

Data: in/snap_counts_<season>.csv (nflverse; build_snaps.py downloads it), REG games, offense_pct, QB/RB/WR/TE, weeks < WEEK.
Names are spelled the way the model does (same norm() + proj_*.json match as build_snaps.py). Availability from in/avail.json
(OUT / QUESTIONABLE rows for the projection week). A team with no snap rows in a week was on bye: not a missed game.

Model, per team-position room:
  1. base share b = recency-weighted mean of offense_pct over his last 3 PLAYED games (0.5/0.3/0.2 newest first; fewer games ->
     weights renormalised);
  2. room total T = mean over the team's last 2 played games of the sum of offense_pct across everyone at that position;
  3. OUT players leave the room; a returner (not OUT, missed the team's most recent game) keeps his base (an injury-shortened last game is dropped first).
     A player who missed the team's last 2+ games and has NO availability row (OUT / QUESTIONABLE / CLEARED) is treated as still
     absent: the availability tab only lists the notable names, and an untracked IR body must not dilute the room;
  4. proj_i = b_i x T / sum(b) over the active room, capped at 0.97 per player, then the capped excess is handed once to the
     uncapped players in proportion to their share;
  5. no 2026 snaps (fill-ins, returners from 2025) -> no projection: left alone (None).

Backtest (weeks 3..6): projection from weeks < w only; OUT approximated as 'no snap row in week w while the team played'
(so the active set is known exactly, which flatters every method a little vs the live tab); compared with actual offense_pct
for the players who played, against two baselines (last game's share, season-to-date mean): MAE and bias overall, by position
and for two cohorts (rooms with a vacated share >= 0.35; returners).

Usage (from build_boards.py):
    import projsnaps as PS
    P = PS.build(IN, OUT_DIR, WEEK)       # writes out/projsnaps.json + out/projsnaps_backtest.json, returns {model name: {...}}
    P[name] -> {"proj": 0.65, "l3": [0.73, 0.66, 0.50], "n": 5, "why": "Etienne out: +12 pts"}
Standalone: python3 projsnaps.py (prints the backtest table).
"""
import csv, json, os, re
from collections import defaultdict

W3 = (0.5, 0.3, 0.2)
RET_X = 1.0   # first-game-back discount: 0.85 under-projected returners by 11.5 pts in the W3-6 backtest (they play more than that), so none
CAP = 0.97

def norm(s):
    s = re.sub(r"\.", "", str(s)).strip(); s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s, flags=re.I); return re.sub(r"\s+", " ", s).lower()

def load_rows(IN, season=2026):
    """{(norm, pos): [(week, pct, raw name, team), ...]} sorted by week, REG games, offense only."""
    rows = defaultdict(list)
    with open(os.path.join(IN, f"snap_counts_{season}.csv"), newline="") as f:
        for r in csv.DictReader(f):
            pos = {"HB": "RB"}.get(r["position"], r["position"])   # PFR tags a few backs HB (Chase Brown, Perine); fullbacks stay out of the RB room
            if r["game_type"] != "REG" or pos not in ("QB", "RB", "WR", "TE"): continue
            try: wk = int(r["week"]); pct = float(r["offense_pct"])
            except Exception: continue
            rows[(norm(r["player"]), pos)].append((wk, pct, r["player"], r["team"]))
    for g in rows.values(): g.sort()
    return rows

def model_names(IN):
    """(norm, pos) -> model spelling, from the four projection tabs (same as build_snaps.py)."""
    out = {}
    for fn, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
        try:
            for r in json.load(open(os.path.join(IN, fn)))["values"][1:]:
                if r and r[0]: out.setdefault((norm(r[0]), pos), r[0])
        except Exception: pass
    return out

def availability(IN, week):
    """(outs, tracked): normalised names OUT this week, and every name with any availability row this week."""
    outs, tracked = set(), set()
    try:
        for r in json.load(open(os.path.join(IN, "avail.json")))["values"][1:]:
            if len(r) < 5 or str(r[0]) != str(week) or not r[1]: continue
            tracked.add(norm(r[1]))
            if r[4].strip().upper() in ("OUT", "IR", "DOUBTFUL"): outs.add(norm(r[1]))
    except Exception: pass
    return outs, tracked

def wmean(shares):
    """Recency-weighted mean, newest first, weights renormalised when fewer than three games."""
    w = W3[:len(shares)]; return sum(a * b for a, b in zip(w, shares)) / sum(w)

def project(rows, week, outs, tracked=None, active=None):
    """Projection for `week` from games before it. outs: normalised names out. tracked: names with an availability row (live mode
    guard for untracked long absences); active: exact set of (norm,pos) who play (backtest mode) - then outs/tracked are ignored.
    Returns {(norm,pos): {"proj","l3","n","why","team","base","vac","ret"}} for everyone with a game before `week`."""
    hist = {k: [x for x in g if x[0] < week] for k, g in rows.items()}
    hist = {k: g for k, g in hist.items() if g}
    team_weeks = defaultdict(set)
    for g in hist.values():
        for wk, _, _, tm in g: team_weeks[tm].add(wk)
    rooms = defaultdict(list)                      # (team,pos) -> keys; a player's room is his most recent team
    for k, g in hist.items(): rooms[(g[-1][3], k[1])].append(k)
    res = {}
    for (tm, pos), keys in rooms.items():
        tw = sorted(team_weeks[tm]); last_w = tw[-1]; last2 = tw[-2:]
        # room total: sum of shares at the position in each of the team's last two games, averaged
        tot = [sum(x[1] for k in keys for x in hist[k] if x[0] == w and x[3] == tm) for w in last2]
        T = sum(tot) / len(tot)
        info = {}
        for k in keys:
            g = [x for x in hist[k] if x[3] == tm]  # games with this team only
            if not g: continue
            l3 = [x[1] for x in g[-3:]][::-1]
            missed = sum(1 for w in tw if w > g[-1][0])   # team games he has missed since his last one (byes never count)
            # a returner's last game is usually the one he got hurt in (Barkley 7%, Rice 10%): if it was under half the game before, it says
            # nothing about his role - base him on the three games before it (backtest W3-6: returners MAE 17.5 -> 16.2, bias -11.5 -> -6.5)
            if missed >= 1 and len(g) >= 2 and g[-1][1] < 0.5 * g[-2][1]: l3 = [x[1] for x in g[-4:-1]][::-1]
            if active is not None: is_out = k not in active
            else: is_out = k[0] in outs or (missed >= 2 and k[0] not in (tracked or set()))
            info[k] = {"base": wmean(l3), "l3": l3, "n": len(g), "out": is_out, "ret": (not is_out) and missed >= 1, "missed": missed}
        act = {k: v for k, v in info.items() if not v["out"]}
        eff = {k: v["base"] * (RET_X if v["ret"] else 1.0) for k, v in act.items()}
        # returners take their role back: they keep their own base and only the stand-ins (whose bases grew while he was out) are scaled
        # to fill what is left of the room; if the returners alone exceed the room, fall back to scaling everyone (backtest: returners
        # bias -6.5 -> see table; the stand-ins' MAE is what this trades)
        rets = {k: e for k, e in eff.items() if act[k]["ret"]}; rest = {k: e for k, e in eff.items() if not act[k]["ret"]}
        left = T - sum(rets.values()); rs = sum(rest.values())
        if rets and rest and left > 0 and rs > 0: proj = dict(rets); proj.update({k: e * left / rs for k, e in rest.items()})
        else:
            s = sum(eff.values())
            proj = {k: (e * T / s if s > 0 else 0.0) for k, e in eff.items()}
        over = sum(p - CAP for p in proj.values() if p > CAP)
        if over > 0:
            proj = {k: min(p, CAP) for k, p in proj.items()}
            free = {k: p for k, p in proj.items() if p < CAP}; fs = sum(free.values())
            if fs > 0: proj.update({k: min(1.0, p + over * p / fs) for k, p in free.items()})
        vac = sum(v["base"] for v in info.values() if v["out"])
        outs_here = sorted([k for k, v in info.items() if v["out"] and v["base"] >= 0.10], key=lambda k: -info[k]["base"])
        rets_here = sorted([k for k, v in act.items() if v["ret"] and v["base"] >= 0.10], key=lambda k: -info[k]["base"])
        last = lambda k: next((t for t in reversed(hist[k][-1][2].split()) if t.rstrip(".").upper() not in ("JR", "SR", "II", "III", "IV", "V")), hist[k][-1][2])
        for k, v in info.items():
            if v["out"]:
                res[k] = {"proj": None, "l3": v["l3"], "n": v["n"], "why": "out", "team": tm, "base": v["base"], "vac": vac, "ret": False}; continue
            # why: his own first-game-back discount, then what the room did to him - absences hand him share ("Etienne out: +12 pts"),
            # a returner takes it back ("Mason back: -8 pts"); d is measured after his own discount so it is the room effect only
            p = proj[k]; d = (p - eff[k]) * 100; why = []
            if v["ret"]: why.append("first game back")
            rets_o = [r for r in rets_here if r != k]
            if d >= 1 and outs_here: why.append(f"{', '.join(last(o) for o in outs_here[:2])} out: {d:+.0f} pts")
            elif d <= -1 and rets_o: why.append(f"{', '.join(last(r) for r in rets_o[:2])} back: {d:+.0f} pts")
            elif abs(d) >= 3: why.append(f"room total: {d:+.0f} pts")
            res[k] = {"proj": round(p, 3), "l3": [round(x, 2) for x in v["l3"]], "n": v["n"], "why": "; ".join(why), "team": tm, "base": v["base"], "vac": vac, "ret": v["ret"]}
    return res

def backtest(rows, weeks=(3, 4, 5, 6)):
    """MAE / bias of the projection vs actual offense_pct for players who played, against 'last game' and 'season mean' baselines."""
    recs = []
    for w in weeks:
        active = {k for k, g in rows.items() if any(x[0] == w for x in g)}
        pr = project(rows, w, set(), None, active)
        for k, v in pr.items():
            if v["proj"] is None or k not in active: continue
            g = [x for x in rows[k] if x[0] < w]; actual = next(x[1] for x in rows[k] if x[0] == w)
            recs.append({"w": w, "pos": k[1], "act": actual, "proj": v["proj"], "last": g[-1][1], "mean": sum(x[1] for x in g) / len(g), "vac": v["vac"], "ret": v["ret"]})
    def stats(rs):
        out = {"n": len(rs)}
        for m in ("proj", "last", "mean"):
            if rs:
                e = [r[m] - r["act"] for r in rs]; out[m] = {"mae": sum(abs(x) for x in e) / len(e), "bias": sum(e) / len(e)}
            else: out[m] = {"mae": None, "bias": None}
        return out
    table = {"all": stats(recs)}
    for pos in ("QB", "RB", "WR", "TE"): table[pos] = stats([r for r in recs if r["pos"] == pos])
    table["vacated>=0.35"] = stats([r for r in recs if r["vac"] >= 0.35])
    table["returners"] = stats([r for r in recs if r["ret"]])
    for w in weeks: table[f"week {w}"] = stats([r for r in recs if r["w"] == w])
    return table

def table_text(t, weeks=(3, 4, 5, 6)):
    lines = [f"projected snaps backtest, weeks {weeks[0]}-{weeks[-1]} (OUT approximated as 'no snap row that week while the team played'; MAE/bias in share points, players who played, proj from earlier weeks only)",
             f"{'cohort':<16}{'n':>6}   {'proj MAE':>9}{'bias':>7}   {'last MAE':>9}{'bias':>7}   {'mean MAE':>9}{'bias':>7}"]
    for k, s in t.items():
        if not s["n"]: lines.append(f"{k:<16}{0:>6}   (no players)"); continue
        f = lambda m: f"{s[m]['mae']*100:>9.1f}{s[m]['bias']*100:>+7.1f}"
        lines.append(f"{k:<16}{s['n']:>6}   {f('proj')}   {f('last')}   {f('mean')}")
    return "\n".join(lines)

def build(IN, OUT, week, season=2026):
    rows = load_rows(IN, season); names = model_names(IN); outs, tracked = availability(IN, week)
    pr = project(rows, week, outs, tracked)
    players = {}
    for k, v in pr.items():
        if v["proj"] is None: continue
        nm = names.get(k, rows[k][-1][2])
        players[nm] = {"proj": v["proj"], "l3": v["l3"], "n": v["n"], "why": v["why"]}
    bt = backtest(rows)
    json.dump({"week": week, "note": "projected offensive snap share for this game; l3 = last three played games newest first", "players": players}, open(os.path.join(OUT, "projsnaps.json"), "w"))
    json.dump({"weeks": [3, 4, 5, 6], "out_rule": "no snap row in week w while the team played", "table": bt}, open(os.path.join(OUT, "projsnaps_backtest.json"), "w"), indent=1)
    print(table_text(bt))
    mn = set(names.values())
    print(f"wrote out/projsnaps.json: {len(players)} players projected for week {week} ({sum(1 for v in pr.values() if v['proj'] is None)} treated as out, {sum(1 for k in players if k in mn)} spelled as the model)")
    return players

if __name__ == "__main__":
    HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
    WEEK = int(float(json.load(open(os.path.join(IN, "boards.json")))["values"][1][1]))
    build(IN, OUT, WEEK)
