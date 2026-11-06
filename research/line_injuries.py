"""research/line_injuries.py (owner 11/6 idea 4): does losing offensive-line or secondary STARTERS move what offenses do?
Starter = 70%+ of his unit's snaps over his previous 3 games played (nflverse snap_counts). Out = final report status Out / Doubtful
(nflverse injuries). For each team-week (2022-25 REG): OL starters out -> the team's rushing yards, sacks taken, passing yards vs its own
season average without that week; DB (CB/S) starters out -> the opponent's passing yards vs the opponent's own average.
Usage: python3 research/line_injuries.py <dir with inj_Y.csv, team_Y.csv, snap_Y.csv>"""
import csv, sys, os, collections, statistics as st
D = sys.argv[1]; OL = {"T", "G", "C", "OT", "OG", "OL"}; DB = {"CB", "S", "FS", "SS", "DB"}
res = collections.defaultdict(list)
for y in (2022, 2023, 2024, 2025):
    snaps = collections.defaultdict(list)   # (team, player) -> [(week, off%, def%, pos)]
    for r in csv.DictReader(open(os.path.join(D, f"snap_{y}.csv"))):
        if r["game_type"] != "REG": continue
        try: snaps[(r["team"], r["player"])].append((int(r["week"]), float(r["offense_pct"] or 0), float(r["defense_pct"] or 0), r["position"]))
        except Exception: pass
    starter = collections.defaultdict(set)   # (team, week) -> {(name, unit)}
    for (tm, pl), xs in snaps.items():
        xs.sort()
        for w in range(2, 19):
            prev = [x for x in xs if x[0] < w][-3:]
            if len(prev) < 2: continue
            pos = prev[-1][3]
            if pos in OL and st.mean(x[1] for x in prev) >= 0.7: starter[(tm, w)].add((pl.lower(), "OL"))
            if pos in DB and st.mean(x[2] for x in prev) >= 0.7: starter[(tm, w)].add((pl.lower(), "DB"))
    out = collections.Counter()
    for r in csv.DictReader(open(os.path.join(D, f"inj_{y}.csv"))):
        if r["game_type"] != "REG" or r["report_status"] not in ("Out", "Doubtful"): continue
        w = int(r["week"]); nm = r["full_name"].lower()
        for (pl, unit) in starter.get((r["team"], w), ()):
            if pl == nm: out[(r["team"], w, unit)] += 1
    T = {}
    for r in csv.DictReader(open(os.path.join(D, f"team_{y}.csv"))):
        if r.get("season_type", "REG") != "REG": continue
        T[(r["team"], int(r["week"]))] = (r["opponent_team"], float(r["rushing_yards"] or 0), float(r["sacks_suffered"] or 0), float(r["passing_yards"] or 0))
    byteam = collections.defaultdict(list)
    for (tm, w), v in T.items(): byteam[tm].append((w, v))
    def avg(tm, w, i):
        xs = [v[i] for ww, v in byteam[tm] if ww != w]; return st.mean(xs) if xs else None
    for (tm, w), v in T.items():
        n_ol = out.get((tm, w, "OL"), 0); opp = v[0]; n_db = out.get((opp, w, "DB"), 0)
        k = "OL 0" if n_ol == 0 else "OL 1" if n_ol == 1 else "OL 2+"
        res[(k, "rush")].append(v[1] - avg(tm, w, 1)); res[(k, "sacks")].append(v[2] - avg(tm, w, 2)); res[(k, "pass")].append(v[3] - avg(tm, w, 3))
        k2 = "opp DB 0" if n_db == 0 else "opp DB 1" if n_db == 1 else "opp DB 2+"
        res[(k2, "pass")].append(v[3] - avg(tm, w, 3))
for k in ("OL 0", "OL 1", "OL 2+"):
    print(k, " | ".join(f"{s} {st.mean(res[(k, s)]):+.1f} (n={len(res[(k, s)])}, se {st.pstdev(res[(k, s)]) / len(res[(k, s)]) ** .5:.1f})" for s in ("rush", "sacks", "pass")))
for k in ("opp DB 0", "opp DB 1", "opp DB 2+"):
    xs = res[(k, "pass")]; print(k, f"pass yds {st.mean(xs):+.1f} (n={len(xs)}, se {st.pstdev(xs) / len(xs) ** .5:.1f})")
