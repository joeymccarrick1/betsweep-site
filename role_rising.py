#!/usr/bin/env python3
"""role_rising.py - the pre-breakout profile (owner 11/4 context desk, item 6): snaps climbing faster than the box score.

A receiver or back whose offensive snap share is rising while his targets / carries have not caught up is the player the projection
(season averages) under-rates; one whose snaps are falling while the averages still look fine is the one it over-rates. Sources, both
reachable from the sandbox: nflverse snap_counts_2026.csv (offense_pct per game) and in/gamelog.json (targets, carries per game).

Rules (RB / WR / TE with 4+ games, excluding games the injury layer marks as limited):
  last-2 snap share vs the 4 games before: +15 pts or more and last-2 >= 60%  -> "Role rising" (WATCH, not good - see below) ... if the
                                                                                  target/carry share also rose >= 4 pts it is "Role up" (info)
  -18 pts or more (healthy, not a fill-in fading - those have their own flag) -> "Snaps falling" (info)
BACKTEST (dig2/tprr_study.py, 11/4): on nflverse 2025 a snap-trend multiplier (k=0.6) cut the targets MAE 2.05 -> 2.02 and TPRR x routes
2.05 -> 1.99, but on 2026 and on THIS MODEL's frozen Week 6-8 projections it made things worse (rec yds MAE 22.2 -> 22.6, receptions 1.63 -> 1.66):
players whose snap share rose 15+ pts delivered 9% UNDER the model's projection (n=60, actual/proj 0.908) and those whose share fell 15+ beat it
by 11% (n=29). The model's recent-game weighting + Snap Trends factor already price the role change, if anything too far. So: no multiplier,
and the flags say that - a rising role is a reason NOT to pay extra for the name, a falling one is not a fade.
Writes in/ctx_role.json players notes. Usage: python3 role_rising.py <WEEK>
"""
import csv, io, json, os, re, subprocess, sys, datetime as dt, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in")
def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def num(v):
    try: return float(v)
    except Exception: return None
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
def main(week):
    week = int(week); now = dt.datetime.now()
    txt = subprocess.check_output(["curl", "-fsSL", "--max-time", "60", "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2026.csv"]).decode()
    SN = {}   # nn -> {week: (pct, team, pos, name)}
    for r in csv.DictReader(io.StringIO(txt)):
        if r["game_type"] != "REG" or r["position"] not in ("RB", "WR", "TE", "FB"): continue
        w = int(r["week"]); pct = num(r["offense_pct"])
        if w >= week or pct is None: continue
        SN.setdefault(nn(r["player"]), {})[w] = (pct, r["team"], r["position"], r["player"])
    # team targets / carries per week from the game log -> each player's share
    GL = vals("gamelog.json"); H = {c: i for i, c in enumerate(GL[0])} if GL else {}
    team_tot = {}; pl = {}
    for r in GL[1:]:
        try: w = int(r[H["Week"]])
        except Exception: continue
        if w >= week: continue
        t = r[H["Team"]]; tg = num(r[H["Targets"]]) or 0; ca = num(r[H["Rush Att"]]) or 0
        tt = team_tot.setdefault((t, w), [0, 0]); tt[0] += tg; tt[1] += ca
        pl.setdefault(nn(r[H["Player"]]), {})[w] = (tg, ca, t, r[H["Pos"]])
    # injury-limited games to set aside
    try:
        import injweeks as INJ; IW = INJ.load(IN, week)
    except Exception: IW = None
    notes = []
    for k, ws in SN.items():
        weeks = sorted(ws)
        if len(weeks) < 4: continue
        name, team, pos = ws[weeks[-1]][3], ws[weeks[-1]][1], ws[weeks[-1]][2]
        lim = set((IW.limited(name, team) or {}).keys()) if IW else set()
        good = [w for w in weeks if w not in lim]
        if len(good) < 4: continue
        last2 = good[-2:]; prior = good[-6:-2]
        if len(prior) < 2: continue
        s_last = statistics.mean(ws[w][0] for w in last2); s_prior = statistics.mean(ws[w][0] for w in prior)
        def share(w):
            p = pl.get(k, {}).get(w); tt = team_tot.get((team, w))
            if not p or not tt: return None
            if pos == "RB": return (p[1] / tt[1]) if tt[1] else None
            return (p[0] / tt[0]) if tt[0] else None
        sh_last = [x for x in (share(w) for w in last2) if x is not None]; sh_prior = [x for x in (share(w) for w in prior) if x is not None]
        d_sh = (statistics.mean(sh_last) - statistics.mean(sh_prior)) if sh_last and sh_prior else None
        unit = "carry" if pos == "RB" else "target"
        wk = f"Weeks {last2[0]}-{last2[-1]} vs {prior[0]}-{prior[-1]}"
        if s_last - s_prior >= 0.15 and s_last >= 0.60:
            if d_sh is not None and d_sh >= 0.04:
                notes.append({"player": name, "team": team, "pos": pos, "k": "info", "tag": "Role up", "txt": f"Snap share {s_prior*100:.0f}% -> {s_last*100:.0f}% and {unit} share {statistics.mean(sh_prior)*100:.0f}% -> {statistics.mean(sh_last)*100:.0f}% ({wk}). The role has grown and the box score agrees; the projection's recent-game weighting already carries it."})
            else:
                notes.append({"player": name, "team": team, "pos": pos, "k": "watch", "tag": "Role rising", "txt": f"Snap share {s_prior*100:.0f}% -> {s_last*100:.0f}% ({wk})" + (f" while his {unit} share only moved {statistics.mean(sh_prior)*100:.0f}% -> {statistics.mean(sh_last)*100:.0f}%" if d_sh is not None else "") + ". More snaps, not yet more volume. Our Week 6-8 check: players with a 15+ pt snap rise produced about 9% UNDER the model's projection (n=60) - the projection already leans into the new role, so do not pay extra for the name."})
        elif s_prior - s_last >= 0.18 and s_prior >= 0.50 and (not IW or IW.healthy_now(name)):
            notes.append({"player": name, "team": team, "pos": pos, "k": "info", "tag": "Snaps falling", "txt": f"Snap share {s_prior*100:.0f}% -> {s_last*100:.0f}% ({wk}) with no injury on the report." + (f" {unit.title()} share {statistics.mean(sh_prior)*100:.0f}% -> {statistics.mean(sh_last)*100:.0f}%." if d_sh is not None else "") + " The model's snap-decline factor already cuts his projection; in Weeks 6-8 such players beat the cut number by about 11% (n=29), so this is not a fade on its own."})
    json.dump({"week": week, "built": now.isoformat(), "players": notes, "games": {}}, open(os.path.join(IN, "ctx_role.json"), "w"), indent=1)
    from collections import Counter
    print(f"role_rising week {week}: {len(notes)} notes", dict(Counter(n["tag"] for n in notes)))
    for n in sorted(notes, key=lambda n: n["tag"]): print(f"  [{n['tag']}] {n['player']} ({n['team']} {n['pos']}): {n['txt'][:120]}")
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else 9)
