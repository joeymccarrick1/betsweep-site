"""research/qb_form.py (owner 11/6, Ravens rookie QB / Jaguars hot streak): vs the closing market (games.csv spread_line, total_line).
(1) Team scoring vs its implied team total when its QB is making one of his first 3 career starts (from games.csv qb names, 2006+).
(2) Covers by recent form: team's average margin vs the spread over its previous 3 games."""
import csv, sys, collections, statistics as st
G = [g for g in csv.DictReader(open(sys.argv[1])) if g["game_type"] == "REG" and g.get("spread_line") not in ("", "NA") and g.get("home_score") not in ("", "NA") and g.get("total_line") not in ("", "NA")]
G.sort(key=lambda g: (int(g["season"]), int(g["week"])))
starts = collections.Counter(); res = collections.defaultdict(list); ats = collections.defaultdict(list); form = collections.defaultdict(list)
for g in G:
    hs, as_, sp, tl = float(g["home_score"]), float(g["away_score"]), float(g["spread_line"]), float(g["total_line"])   # spread_line = home favoured by
    for side, qb, pts, imp, cov in (("home", g["home_qb_name"], hs, tl / 2 + sp / 2, (hs - as_) - sp), ("away", g["away_qb_name"], as_, tl / 2 - sp / 2, (as_ - hs) + sp)):
        tm = g[side + "_team"]; n = starts[qb]
        per = "2006-15" if int(g["season"]) <= 2015 else "2016-25" if int(g["season"]) <= 2025 else "2026"
        if qb and int(g["season"]) >= 2006: res[(per, "first 3 starts" if n < 3 else "veteran")].append((pts - imp, cov))
        f = form[tm][-3:]
        if len(f) == 3 and int(g["season"]) >= 2006:
            a = st.mean(f); b = "hot (+7 ATS avg)" if a >= 7 else "cold (-7)" if a <= -7 else "middle"
            ats[(per, b)].append(cov)
        starts[qb] += 1; form[tm].append(cov)
    if g["week"] == "1": pass
for k in sorted(res):
    xs = res[k]; print(k, f"n={len(xs)} pts vs implied {st.mean(x[0] for x in xs):+.2f}  cover {sum(1 for x in xs if x[1] > 0) / max(1, sum(1 for x in xs if x[1] != 0)):.1%}")
for k in sorted(ats):
    xs = ats[k]; w = sum(1 for x in xs if x > 0); l = sum(1 for x in xs if x < 0); print(k, f"{w}-{l} ({w / max(1, w + l):.1%})")
