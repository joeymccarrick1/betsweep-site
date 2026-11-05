"""Build dynasty age curves and rookie-pick values from nflverse data.

Usage: python3 -I build.py <data_dir> <out_dir> <weekly_2025_csv>
"""
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date

DATA, OUT, WEEKLY_2025 = sys.argv[1], sys.argv[2], sys.argv[3]
POS = ["QB", "RB", "WR", "TE"]
SEASONS = list(range(2012, 2026))
MIN_GAMES = 8
AGES = list(range(21, 39))
# "fantasy relevant" floor on this-season ppg for the primary curve (see RESEARCH.md)
PPG_FLOOR = {"QB": 8.0, "RB": 4.0, "WR": 4.0, "TE": 3.0}
TOP_N = {"QB": 12, "TE": 12, "RB": 24, "WR": 24}
SHRINK_K = 40  # pseudo-count toward the quadratic fit


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------- seasons
# seasons[season][player_id] = dict(pos, games, pts, targets, carries)
seasons = {}
for s in SEASONS:
    d = {}
    if s == 2025:
        agg = {}
        with open(WEEKLY_2025, newline="") as fh:
            for r in csv.DictReader(fh):
                if r["season_type"] != "REG":
                    continue
                a = agg.setdefault(r["player_id"], {"pos": r["position"], "games": 0, "pts": 0.0, "targets": 0, "carries": 0})
                a["games"] += 1
                a["pts"] += f(r["fantasy_points_ppr"])
                a["targets"] += int(f(r["targets"]))
                a["carries"] += int(f(r["carries"]))
        d = agg
    else:
        with open(f"{DATA}/stats_player_reg_{s}.csv", newline="") as fh:
            for r in csv.DictReader(fh):
                d[r["player_id"]] = {"pos": r["position"], "games": int(f(r["games"])), "pts": f(r["fantasy_points_ppr"]),
                                     "targets": int(f(r["targets"])), "carries": int(f(r["carries"]))}
    for v in d.values():
        v["ppg"] = v["pts"] / v["games"] if v["games"] else 0.0
    seasons[s] = d

# ---------------------------------------------------------------- rosters -> birth dates
birth = {}
for s in SEASONS:
    with open(f"{DATA}/roster_{s}.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            g, b = r.get("gsis_id", ""), r.get("birth_date", "")
            if g and b and g not in birth:
                try:
                    y, m, dd = (int(t) for t in b.split("-"))
                    birth[g] = date(y, m, dd)
                except ValueError:
                    pass


def age_in(season, pid):
    b = birth.get(pid)
    if not b:
        return None
    # age on Sept 1 of the season
    return int(((date(season, 9, 1) - b).days) / 365.25)


# ---------------------------------------------------------------- age curves
# pair rows: (pos, age_next, ppg_this, ppg_next)
pairs = defaultdict(list)          # (pos) -> list of (age_next, ppg0, ppg1)
attr = defaultdict(lambda: defaultdict(lambda: [0, 0]))        # pos -> age_next -> [played_next, total]
attr_rel = defaultdict(lambda: defaultdict(lambda: [0, 0]))    # same, relevance filtered
missing_birth = 0
for s in SEASONS[:-1]:
    nxt = seasons[s + 1]
    for pid, v in seasons[s].items():
        p = v["pos"]
        if p not in POS or v["games"] < MIN_GAMES:
            continue
        a = age_in(s + 1, pid)
        if a is None:
            missing_birth += 1
            continue
        if a not in AGES:
            continue
        w = nxt.get(pid)
        played = bool(w and w["games"] >= MIN_GAMES)
        attr[p][a][1] += 1
        attr[p][a][0] += played
        rel = v["ppg"] >= PPG_FLOOR[p]
        if rel:
            attr_rel[p][a][1] += 1
            attr_rel[p][a][0] += played
        if played:
            pairs[p].append((a, v["ppg"], w["ppg"], rel))


def trimmed_mean(xs, trim=0.1):
    xs = sorted(xs)
    k = int(len(xs) * trim)
    core = xs[k:len(xs) - k] if len(xs) - 2 * k > 0 else xs
    return sum(core) / len(core)


def wquad_fit(ages, ys, ws):
    """Weighted least squares quadratic y = a + b*age + c*age^2 (solve normal equations)."""
    S = [[0.0] * 3 for _ in range(3)]
    T = [0.0] * 3
    for a, y, w in zip(ages, ys, ws):
        x = [1.0, a, a * a]
        for i in range(3):
            T[i] += w * x[i] * y
            for j in range(3):
                S[i][j] += w * x[i] * x[j]
    # gaussian elimination
    M = [S[i] + [T[i]] for i in range(3)]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(M[r][i]))
        M[i], M[piv] = M[piv], M[i]
        for r in range(3):
            if r != i:
                fac = M[r][i] / M[i][i]
                M[r] = [M[r][c] - fac * M[i][c] for c in range(4)]
    return [M[i][3] / M[i][i] for i in range(3)]


age_curves = {"meta": {
    "source": "nflverse stats_player_reg_<season>.csv 2012-2024 + stats_player_week_2025.csv (REG weeks aggregated); birth dates from nflverse roster_<season>.csv",
    "seasons_paired": "2012->2013 ... 2024->2025 (13 transitions)",
    "min_games_each_season": MIN_GAMES,
    "age_definition": "integer age on Sept 1 of the season being projected (the NEXT season of each pair)",
    "ppg_floor_this_season_for_primary_curve": PPG_FLOOR,
    "ratio_definition": "ppg_next / ppg_this for players with >= 8 games in both seasons",
    "fields": {
        "raw[age].n": "number of player-season pairs in cell (relevance-filtered)",
        "raw[age].median": "median of individual ratios (primary statistic)",
        "raw[age].trimmed_mean": "10% two-sided trimmed mean of ratios",
        "raw[age].ratio_of_means": "sum(ppg_next)/sum(ppg_this): production-weighted ratio",
        "raw[age].n_all / median_all": "same without the ppg floor (every >=8 game player)",
        "smoothed[age]": "n-weighted 3-age centered rolling median of raw medians",
        "quadratic[age]": "weighted quadratic fit of log(median) vs age, exp'd",
        "yoy_multiplier[age]": "RECOMMENDED: smoothed shrunk toward quadratic with weight smoothed_n/(smoothed_n+40); clipped to [0.55, 1.20]; forced non-increasing beyond the oldest age with raw n >= 10",
        "cumulative_peak1[age]": "product of yoy_multiplier from age 21, normalised so the max = 1.0",
        "survival[age].p_play_next": "P(>= 8 games next season | >= 8 games this season), unconditional on production",
        "survival[age].p_play_next_relevant": "same but this-season ppg >= floor (use this with yoy_multiplier)",
        "survival[age].n / n_relevant": "denominators",
        "survival[age].p_play_next_relevant_smoothed": "RECOMMENDED survival: pooled counts over ages a-1..a+1, relevance-filtered (n_relevant_pooled3 is its denominator)",
    },
    "missing_birth_date_player_seasons_dropped": missing_birth,
}}

for p in POS:
    rows = pairs[p]
    raw = {}
    for a in AGES:
        cell = [(p0, p1) for (aa, p0, p1, rel) in rows if aa == a and rel]
        cell_all = [(p0, p1) for (aa, p0, p1, rel) in rows if aa == a]
        entry = {"n": len(cell), "n_all": len(cell_all)}
        if cell:
            rs = [p1 / p0 for p0, p1 in cell]
            entry["median"] = round(statistics.median(rs), 4)
            entry["trimmed_mean"] = round(trimmed_mean(rs), 4)
            entry["ratio_of_means"] = round(sum(p1 for _, p1 in cell) / sum(p0 for p0, _ in cell), 4)
            entry["mean_ppg_this"] = round(sum(p0 for p0, _ in cell) / len(cell), 2)
        if cell_all:
            rs = [p1 / p0 for p0, p1 in cell_all if p0 > 0]
            entry["median_all"] = round(statistics.median(rs), 4) if rs else None
        raw[a] = entry
    # smoothing: n-weighted rolling over ages a-1..a+1 (weighted mean of medians)
    smoothed, sm_n = {}, {}
    for a in AGES:
        num = den = 0.0
        for b in (a - 1, a, a + 1):
            e = raw.get(b)
            if e and e.get("median") is not None:
                num += e["n"] * e["median"]
                den += e["n"]
        sm_n[a] = int(den)
        smoothed[a] = round(num / den, 4) if den else None
    # quadratic fit on log median, weight n (cells with n >= 5)
    fa = [a for a in AGES if raw[a].get("median") and raw[a]["n"] >= 5]
    coef = wquad_fit(fa, [math.log(raw[a]["median"]) for a in fa], [raw[a]["n"] for a in fa])
    quad = {a: round(math.exp(coef[0] + coef[1] * a + coef[2] * a * a), 4) for a in AGES}
    # recommended: shrink the rolling median toward the quadratic fit with weight n/(n+SHRINK_K),
    # then force non-increasing beyond the oldest age with raw n >= 10 (no extrapolated rebounds)
    rec = {}
    last_reliable = max(a for a in AGES if raw[a]["n"] >= 10)
    for a in AGES:
        if smoothed[a] is None:
            v = quad[a]
        else:
            wgt = sm_n[a] / (sm_n[a] + SHRINK_K)
            v = wgt * smoothed[a] + (1 - wgt) * quad[a]
        v = min(1.20, max(0.55, v))
        if a > last_reliable:
            v = min(v, rec[a - 1])
        rec[a] = round(v, 4)
    cum, c = {}, 1.0
    for a in AGES:
        if a > AGES[0]:
            c *= rec[a]
        cum[a] = c
    peak = max(cum.values())
    cum = {a: round(v / peak, 4) for a, v in cum.items()}
    surv = {}
    for a in AGES:
        t, tr = attr[p][a], attr_rel[p][a]
        # pooled 3-age window (a-1..a+1) on the relevance-filtered counts
        pk = sum(attr_rel[p][b][0] for b in (a - 1, a, a + 1))
        pn = sum(attr_rel[p][b][1] for b in (a - 1, a, a + 1))
        surv[a] = {"n": t[1], "p_play_next": round(t[0] / t[1], 4) if t[1] else None,
                   "n_relevant": tr[1], "p_play_next_relevant": round(tr[0] / tr[1], 4) if tr[1] else None,
                   "n_relevant_pooled3": pn, "p_play_next_relevant_smoothed": round(pk / pn, 4) if pn else None}
    age_curves[p] = {
        "n_pairs_relevant": sum(1 for r in rows if r[3]), "n_pairs_all": len(rows),
        "quadratic_coef_log_ratio": [round(x, 6) for x in coef],
        "raw": raw, "smoothed": smoothed, "smoothed_n": sm_n, "quadratic": quad,
        "yoy_multiplier": rec, "cumulative_peak1": cum, "survival": surv,
    }

with open(f"{OUT}/age_curves.json", "w") as fh:
    json.dump(age_curves, fh, indent=1)

# ---------------------------------------------------------------- rookie values
# positional rank by ppg among >= 8 game players per season
rank = {}
for s in SEASONS:
    rank[s] = {}
    for p in POS:
        lst = sorted(((v["ppg"], pid) for pid, v in seasons[s].items() if v["pos"] == p and v["games"] >= MIN_GAMES), reverse=True)
        for i, (_, pid) in enumerate(lst):
            rank[s][pid] = (p, i + 1)

drafted = []
with open(f"{DATA}/draft_picks.csv", newline="") as fh:
    for r in csv.DictReader(fh):
        s = int(r["season"])
        if 2012 <= s <= 2022 and r["position"] in POS:
            drafted.append((s, int(r["round"]), int(r["pick"]), r["gsis_id"], r["position"]))

no_gsis = sum(1 for d in drafted if not d[3])


def bucket(rnd, pick):
    if rnd == 1:
        return "R1_pick_1-10" if pick <= 10 else ("R1_pick_11-20" if pick <= 20 else "R1_pick_21-32")
    return None


recs = []
for s, rnd, pick, gid, p in drafted:
    best_ppg, best_rank, hit, hit_any_year = 0.0, None, False, []
    for y in (s, s + 1, s + 2):
        rk = rank[y].get(gid)
        if rk and rk[0] == p:
            v = seasons[y][gid]
            if v["ppg"] > best_ppg:
                best_ppg = v["ppg"]
            if best_rank is None or rk[1] < best_rank:
                best_rank = rk[1]
            if rk[1] <= TOP_N[p]:
                hit = True
                hit_any_year.append(y - s + 1)
    recs.append({"season": s, "round": rnd, "pick": pick, "gsis_id": gid, "pos": p,
                 "best_ppg": best_ppg, "best_rank": best_rank, "hit": hit, "qualified": best_rank is not None,
                 "first_hit_year": min(hit_any_year) if hit_any_year else None})


def summarise(group):
    n = len(group)
    if not n:
        return {"n": 0}
    hits = [g for g in group if g["hit"]]
    q = [g for g in group if g["qualified"]]
    return {
        "n": n,
        "hit_rate": round(len(hits) / n, 4),
        "n_hits": len(hits),
        "share_with_any_8game_season": round(len(q) / n, 4),
        "mean_best_ppg_all": round(sum(g["best_ppg"] for g in group) / n, 2),
        "mean_best_ppg_if_qualified": round(sum(g["best_ppg"] for g in q) / len(q), 2) if q else None,
        "mean_best_ppg_if_hit": round(sum(g["best_ppg"] for g in hits) / len(hits), 2) if hits else None,
        "median_best_ppg_all": round(statistics.median(g["best_ppg"] for g in group), 2),
        "p25_best_ppg_all": round(sorted(g["best_ppg"] for g in group)[n // 4], 2),
        "p75_best_ppg_all": round(sorted(g["best_ppg"] for g in group)[(3 * n) // 4], 2),
        "hit_in_year1_share": round(sum(1 for g in hits if g["first_hit_year"] == 1) / n, 4),
    }


rookie = {"meta": {
    "source": "nflverse draft_picks.csv (round, pick, gsis_id, position) joined to seasonal PPR stats",
    "draft_classes": "2012-2022 (so every class has 3 full seasons through 2024/2025)",
    "window": "first 3 seasons: draft year, +1, +2",
    "hit_definition": "a season with >= 8 games ranked top-12 (QB, TE) or top-24 (RB, WR) by PPR ppg among >= 8 game players at that position",
    "best_ppg": "max PPR ppg across the window's >= 8 game seasons; 0 if no such season",
    "fields": {
        "hit_rate": "share of drafted players who produced a hit season in the window",
        "share_with_any_8game_season": "share who played >= 8 games in at least one of the 3 seasons",
        "mean_best_ppg_all": "mean of best ppg with non-qualifiers counted as 0 (expected value for pricing)",
        "mean_best_ppg_if_qualified": "mean best ppg among players with at least one >= 8 game season",
        "mean_best_ppg_if_hit": "mean best ppg among hits",
        "hit_in_year1_share": "share of all drafted players who hit already in the draft season",
    },
    "draftees_without_gsis_id_dropped": no_gsis,
    "top_n": TOP_N,
}}
for p in POS:
    pr = [r for r in recs if r["pos"] == p]
    by_round = {f"R{k}": summarise([r for r in pr if r["round"] == k]) for k in range(1, 8)}
    by_bucket = {b: summarise([r for r in pr if bucket(r["round"], r["pick"]) == b]) for b in ("R1_pick_1-10", "R1_pick_11-20", "R1_pick_21-32")}
    rookie[p] = {"n_drafted": len(pr), "all_rounds": summarise(pr), "by_round": by_round, "round1_by_pick": by_bucket,
                 "day2_R2-3": summarise([r for r in pr if r["round"] in (2, 3)]),
                 "day3_R4-7": summarise([r for r in pr if r["round"] >= 4])}
# all positions by round (useful for generic pick pricing)
rookie["ALL_OFFENSE_SKILL"] = {"by_round": {f"R{k}": summarise([r for r in recs if r["round"] == k]) for k in range(1, 8)},
                               "round1_by_pick": {b: summarise([r for r in recs if bucket(r["round"], r["pick"]) == b]) for b in ("R1_pick_1-10", "R1_pick_11-20", "R1_pick_21-32")}}

with open(f"{OUT}/rookie_values.json", "w") as fh:
    json.dump(rookie, fh, indent=1)

# hits list for README sanity
with open(f"{OUT}/scripts/_rookie_records.json", "w") as fh:
    json.dump(recs, fh)

# ---------------------------------------------------------------- print tables
print("AGE CURVES")
for p in POS:
    c = age_curves[p]
    print(f"\n{p}  pairs relevant={c['n_pairs_relevant']} all={c['n_pairs_all']}")
    print("age   n  median  trim  ratioMeans  smooth(n)  quad  REC  cum   surv_rel(n)  surv_all(n)  surv_sm(n)")
    for a in AGES:
        r = c["raw"][a]; s = c["survival"][a]
        print(f"{a:3d} {r['n']:4d} {r.get('median', float('nan')):6.3f} {r.get('trimmed_mean', float('nan')):6.3f} {r.get('ratio_of_means', float('nan')):6.3f}"
              f"   {c['smoothed'][a] if c['smoothed'][a] is not None else float('nan'):6.3f}({c['smoothed_n'][a]:3d}) {c['quadratic'][a]:6.3f} {c['yoy_multiplier'][a]:6.3f} {c['cumulative_peak1'][a]:5.3f}"
              f"   {s['p_play_next_relevant'] if s['p_play_next_relevant'] is not None else float('nan'):5.3f}({s['n_relevant']:3d}) {s['p_play_next'] if s['p_play_next'] is not None else float('nan'):5.3f}({s['n']:3d}) {s['p_play_next_relevant_smoothed'] if s['p_play_next_relevant_smoothed'] is not None else float('nan'):5.3f}({s['n_relevant_pooled3']:3d})")
print("\nROOKIES")
for p in POS + ["ALL_OFFENSE_SKILL"]:
    print(f"\n{p}")
    for k, v in list(rookie[p]["by_round"].items()) + list(rookie[p]["round1_by_pick"].items()):
        print(f"  {k:14s} n={v['n']:3d} hit={v.get('hit_rate')} q={v.get('share_with_any_8game_season')} bestppg_all={v.get('mean_best_ppg_all')} if_q={v.get('mean_best_ppg_if_qualified')} if_hit={v.get('mean_best_ppg_if_hit')} y1={v.get('hit_in_year1_share')}")
