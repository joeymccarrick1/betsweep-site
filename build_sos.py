#!/usr/bin/env python3
"""
Strength-of-schedule adjustment ('AUTO - SOS Adjust') - owner 10/27 "do the others", shipped 2026-10-29.

Two things the current one-sided matchup factor cannot see:
  1. a defense's "allowed" numbers depend on who it has played (a soft schedule looks like a bad defense);
  2. a player's season average depends on who HE has played (seven games against tough pass defenses understate a QB).

Model (scratchpad sos/backtest.py, nflverse 2019-26): per position-stat, team-game totals y ~ L * a[offense] * b[defense],
solved by iterative proportional fitting with pseudo-count shrinkage K toward a prior 1 + RHO x (last season's final factor - 1).
With a == 1 this collapses to the sheet's own factor fs = (n r + 4) / (n + 4), so the ONLY new information is the opponent
adjustment. Per player: schedule divisor D = (m + WD (S - m)) / m, S = sum of b over the defenses he has faced this season
(D > 1: he has had a soft schedule, his average is inflated; D < 1: a tough one). Opponent factor stays ONE-SIDED like the
10/20 production factor: 1 + WF x min(0, b[opp] - 1) - a soft defense never raises a projection.

Tested 2024-26 (train 2019-23), uniform K=4 RHO=0.35 WD=0.5 WF=0.75, against the ACTUAL production factor (one-sided,
k=4, weights 0.5-0.75, none on receptions): MAE lower for all 10 stats, 10 of 10 significant (game-level bootstrap),
mean -1.2% (QB pass yds -1.2%, RB rec yds -2.5%, RB rec -2.2%, TE rec -1.7%, RB rush -1.1%, QB rush -1.1%, WR rec yds -0.6%);
Week 6+ only: -0.85%, 9 of 10. Symmetric factors were NOT adopted (QB rush / TE rec yds got worse). sos/hybrid.json.

Output: out/sos_values.json -> written to 'AUTO - SOS Adjust'!A2:W700 in Step 2b (same pattern as Snap Trends). Each row
is one model player: the multiplier per market = (1/D) x (1 + WF min(0, b[opp] - 1)) / (the sheet's own factor for that
stat, reproduced here from the same game log), so 'V2 - Leg Board'!H (z_s) and the boards chips (build_boards.py SMULT)
apply the SOS version on top of a projection that already carries the old factor, without double counting. 1 = no change.
Rollback: clear 'AUTO - SOS Adjust'!A2:W700 (every lookup falls back to 1).

Usage: python3 build_sos.py [--week W] [--in DIR] [--out DIR]
  reads in/gamelog.json, in/settings.json, in/proj_{qb,rb,wr,te}.json, in/stats_player_week_<prior>.csv (downloaded if missing)
"""
import os, sys, json, csv, math, urllib.request

K, RHO, WD, WF = 4, 0.35, 0.5, 0.75
PRIOR_SEASON = 2025
TEAMFIX = {"LAR": "LA", "OAK": "LV", "SD": "LAC", "STL": "LA"}
# stat key -> (position, game-log column, nflverse column, sheet prod-weight label fragment, market, chip key)
STATS = {
    "QB_pass_yds": ("QB", "Pass Yds", "passing_yards", "QB pass yds tough-matchup weight", "Passing Yards", "x Pass yds"),
    "QB_rush_yds": ("QB", "Rush Yds", "rushing_yards", "QB rush yds tough-matchup weight", "Rushing Yards", "x Rush yds"),
    "RB_rush_yds": ("RB", "Rush Yds", "rushing_yards", "RB rush yds tough-matchup weight", "Rushing Yards", "x Rush yds"),
    "RB_rec": ("RB", "Receptions", "receptions", None, "Receptions", "x Receptions"),
    "RB_rec_yds": ("RB", "Rec Yds", "receiving_yards", None, "Receiving Yards", "x Rec yds"),
    "WR_rec": ("WR", "Receptions", "receptions", None, "Receptions", "x Receptions"),
    "WR_rec_yds": ("WR", "Rec Yds", "receiving_yards", "WR rec yds tough-matchup weight", "Receiving Yards", "x Rec yds"),
    "TE_rec": ("TE", "Receptions", "receptions", None, "Receptions", "x Receptions"),
    "TE_rec_yds": ("TE", "Rec Yds", "receiving_yards", "TE rec yds tough-matchup weight", "Receiving Yards", "x Rec yds"),
}
CHIPS = ["x Pass yds", "x Rush yds", "x Receptions", "x Rec yds"]
HEADER = ["Player", "Team", "Pos", "Opp", "Games"] + CHIPS + ["D " + c[2:] for c in CHIPS] + ["Opp SOS " + c[2:] for c in CHIPS] + ["Sheet factor " + c[2:] for c in CHIPS] + ["Projection Week", "Note"]


def num(x):
    try:
        return float(str(x).replace(",", "").replace("%", ""))
    except Exception:
        return None


def vals(path):
    d = json.load(open(path))
    return d["values"] if isinstance(d, dict) else d


def fit(rows, k, pa, pb, teams, iters=300):
    """rows: (off, dfn, y). returns raw b (a==1), a, b as dicts keyed by team"""
    ti = {t: i for i, t in enumerate(teams)}; n = len(teams)
    if not rows:
        return {t: 1.0 for t in teams}, {t: 1.0 for t in teams}, {t: 1.0 for t in teams}
    L = sum(r[2] for r in rows) / len(rows)
    if L <= 0:
        return {t: 1.0 for t in teams}, {t: 1.0 for t in teams}, {t: 1.0 for t in teams}
    Yd = [0.0] * n; Yo = [0.0] * n; nd = [0.0] * n; C = [[0.0] * n for _ in range(n)]
    for o, d, y in rows:
        Yd[ti[d]] += y / L; Yo[ti[o]] += y / L; nd[ti[d]] += 1; C[ti[o]][ti[d]] += 1
    PA = [pa.get(t, 1.0) for t in teams]; PB = [pb.get(t, 1.0) for t in teams]
    raw = [(Yd[j] + k * 1.0) / (nd[j] + k) for j in range(n)]       # sheet-style prior of 1
    a = [1.0] * n; b = [1.0] * n
    for _ in range(iters):
        bn = [(Yd[j] + k * PB[j]) / (sum(C[i][j] * a[i] for i in range(n)) + k) for j in range(n)]
        an = [(Yo[i] + k * PA[i]) / (sum(C[i][j] * bn[j] for j in range(n)) + k) for i in range(n)]
        delta = max(max(abs(x - y) for x, y in zip(bn, b)), max(abs(x - y) for x, y in zip(an, a)))
        a, b = an, bn
        if delta < 1e-10: break
    return dict(zip(teams, raw)), dict(zip(teams, a)), dict(zip(teams, b))


def prior_factors(csv_path, stat):
    """last season's final two-way factors (full REG season, k=K, prior 1)"""
    pos, _, col, *_ = STATS[stat]
    tot = {}
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("season_type") != "REG": continue
            t = TEAMFIX.get(r["team"], r["team"]); o = TEAMFIX.get(r["opponent_team"], r["opponent_team"])
            key = (int(r["week"]), t, o)
            tot.setdefault(key, 0.0)
            if r.get("position_group") == pos:
                tot[key] += num(r.get(col)) or 0.0
    teams = sorted({k[1] for k in tot})
    rows = [(t, o, y) for (w, t, o), y in tot.items()]
    _, a, b = fit(rows, K, {}, {}, teams)
    return a, b, teams


def main():
    args = sys.argv[1:]
    IN = args[args.index("--in") + 1] if "--in" in args else "in"
    OUT = args[args.index("--out") + 1] if "--out" in args else "out"
    os.makedirs(OUT, exist_ok=True)
    settings = vals(os.path.join(IN, "settings.json"))
    week = int(args[args.index("--week") + 1]) if "--week" in args else int(num(settings[1][1]))
    prodw = {}
    for r in settings:
        if r and len(r) > 1:
            for st, (_, _, _, label, _, _) in STATS.items():
                if label and str(r[0]).startswith(label): prodw[st] = num(r[1]) or 0.0
    found = [st for st in STATS if STATS[st][3] and st in prodw]
    print(f"sheet one-sided weights found for {len(found)} of 5 stats: " + ", ".join(f"{st}={prodw[st]}" for st in found)
          + ("" if len(found) == 5 else "  ** WARNING: 'AUTO - Settings' labels changed - a missing weight is treated as 0 and the SOS factor would be applied on top of the sheet's; fix the label before publishing **"))
    gl = vals(os.path.join(IN, "gamelog.json")); h = gl[0]; ci = {k: h.index(k) for k in h}
    log = [r for r in gl[1:] if r and num(r[0]) is not None and num(r[0]) < week and len(r) > ci["Rec Yds"]]
    teams = sorted({r[ci["Team"]] for r in log} | {r[ci["Opponent"]] for r in log})
    teams = [t for t in teams if t and t != "BYE"]
    prior_csv = os.path.join(IN, f"stats_player_week_{PRIOR_SEASON}.csv")
    if not os.path.exists(prior_csv):
        url = f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{PRIOR_SEASON}.csv"
        print("downloading", url); urllib.request.urlretrieve(url, prior_csv)
    n_sheet = week - 1          # the sheet's n in fs = (n r + 4)/(n + 4)
    out = {}                     # stat -> {b_sos, r_sheet(opp->factor), per-player}
    for st, (pos, col, _, label, market, chip) in STATS.items():
        pa_, pb_, _ = prior_factors(prior_csv, st)
        pa = {t: 1 + RHO * (pa_.get(t, 1.0) - 1) for t in teams}; pb = {t: 1 + RHO * (pb_.get(t, 1.0) - 1) for t in teams}
        # team-game totals from the sheet's own game log (every team-week in the log counts, 0 if no row at the position)
        tg = {}
        for r in log:
            key = (int(num(r[0])), r[ci["Team"]], r[ci["Opponent"]])
            if key[2] in ("", "BYE") or key[1] in ("", "BYE"): continue
            tg.setdefault(key, 0.0)
            if r[ci["Pos"]] == pos: tg[key] += num(r[ci[col]]) or 0.0
        rows = [(t, o, y) for (w, t, o), y in tg.items()]
        _, a, b = fit(rows, K, pa, pb, teams)
        # the sheet's factor: r = AVERAGEIFS(stat, opp=d, pos) / AVERAGEIFS(stat, pos) over PLAYER rows, fs=(n r+4)/(n+4), 1+w min(0, fs-1)
        prow = [r for r in log if r[ci["Pos"]] == pos]
        lg = sum(num(r[ci[col]]) or 0.0 for r in prow) / max(1, len(prow))
        sheet = {}
        for d in teams:
            rr = [num(r[ci[col]]) or 0.0 for r in prow if r[ci["Opponent"]] == d]
            rt = (sum(rr) / len(rr)) / lg if rr and lg > 0 else 1.0
            fs = (n_sheet * rt + 4) / (n_sheet + 4)
            sheet[d] = 1 + prodw.get(st, 0.0) * min(0.0, fs - 1)
        # per player
        per = {}
        for r in log:
            if r[ci["Pos"]] != pos: continue
            p = per.setdefault(r[ci["Player"]], {"m": 0, "sumy": 0.0, "S": 0.0})
            o = r[ci["Opponent"]]
            if o in b: p["m"] += 1; p["sumy"] += num(r[ci[col]]) or 0.0; p["S"] += b[o]
        out[st] = {"b": b, "a": a, "sheet": sheet, "per": per, "pos": pos, "market": market, "chip": chip}
    # one row per model player (projection tabs) with this week's opponent
    rows_out = []; stats_by_pos = {}
    for st, v in out.items(): stats_by_pos.setdefault(v["pos"], []).append(st)
    for fn, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
        try: pv = vals(os.path.join(IN, fn))
        except Exception: continue
        for r in pv[1:]:
            if not r or not r[0]: continue
            name, team, opp = r[0], r[1] if len(r) > 1 else "", r[2] if len(r) > 2 else ""
            mult = {c: 1.0 for c in CHIPS}; D_ = {c: "" for c in CHIPS}; F_ = {c: "" for c in CHIPS}; O_ = {c: "" for c in CHIPS}; games = 0
            for st in stats_by_pos[pos]:
                v = out[st]; p = v["per"].get(name); c = v["chip"]
                m = p["m"] if p else 0; games = max(games, m)
                D = (m + WD * (p["S"] - m)) / m if p and m > 0 else 1.0
                fopp = v["b"].get(opp, 1.0) if opp and opp != "BYE" else 1.0
                new = (1.0 / D) * (1 + WF * min(0.0, fopp - 1))
                old = v["sheet"].get(opp, 1.0) if opp and opp != "BYE" else 1.0
                mult[c] = new / old if old > 0 else 1.0
                D_[c] = round(D, 4); F_[c] = round(fopp, 4); O_[c] = round(old, 4)
            rows_out.append([name, team, pos, opp, games] + [round(mult[c], 4) for c in CHIPS] + [D_[c] for c in CHIPS] + [F_[c] for c in CHIPS] + [O_[c] for c in CHIPS] + [week, ""])
    note = (f"week {week}: K={K} RHO={RHO} WD={WD} WF={WF}; two-way IPF defense factors from 'AUTO - Player Game Log' weeks < {week}, "
            f"prior = {PRIOR_SEASON} nflverse final factors; multiplier = (1/D) x (1 + WF min(0, b[opp]-1)) / sheet factor; "
            f"sheet weights {json.dumps({k: prodw.get(k, 0) for k in STATS})}")
    if rows_out: rows_out[0][-1] = note
    json.dump({"range": f"'AUTO - SOS Adjust'!A2:W{1 + max(len(rows_out), 1)}", "values": rows_out}, open(os.path.join(OUT, "sos_values.json"), "w"))
    json.dump({"header": HEADER, "rows": rows_out, "week": week, "factors": {st: {"b": v["b"], "a": v["a"], "sheet": v["sheet"]} for st, v in out.items()}},
              open(os.path.join(OUT, "sos_debug.json"), "w"), indent=0)
    ms = [m for r in rows_out for m in r[5:9] if m != 1.0]
    print(f"wrote {OUT}/sos_values.json: {len(rows_out)} players for week {week}; multipliers {min(ms):.3f}-{max(ms):.3f} "
          f"(mean {sum(ms)/len(ms):.3f}); below 0.95: {sum(1 for m in ms if m < 0.95)}, above 1.05: {sum(1 for m in ms if m > 1.05)}")
    for st, v in out.items():
        b = v["b"]; s = sorted(b, key=b.get)
        print(f"  {st:12s} toughest {', '.join(f'{t} {b[t]:.2f}' for t in s[:3])} | softest {', '.join(f'{t} {b[t]:.2f}' for t in s[-3:])}")


if __name__ == "__main__":
    main()
