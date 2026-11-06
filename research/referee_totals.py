"""research/referee_totals.py (owner 11/6 idea 5): do referee crews move game totals? Walk-forward: for each game, the referee's shrunk average
(total points - closing total) over all his PRIOR games (sum / (n + 30)), then the over/under record by that number's band. Also the same for
margin vs spread (home cover). Usage: python3 research/referee_totals.py <games.csv>"""
import csv, sys, collections
G = [g for g in csv.DictReader(open(sys.argv[1])) if g.get("referee") and g.get("total_line") not in ("", "NA") and g.get("home_score") not in ("", "NA") and g["game_type"] == "REG"]
G.sort(key=lambda g: (g["season"], int(g["week"])))
hist = collections.defaultdict(list); rows = []
for g in G:
    tot = float(g["home_score"]) + float(g["away_score"]); tl = float(g["total_line"]); r = tot - tl
    h = hist[g["referee"]]
    if len(h) >= 16: rows.append((int(g["season"]), sum(h) / (len(h) + 30), r, len(h)))
    if int(g["season"]) < 2026: h.append(r)
def rec(xs): o = sum(1 for x in xs if x[2] > 0); u = sum(1 for x in xs if x[2] < 0); return f"{o}-{u} ({o / max(1, o + u):.1%} over, n={o + u})"
for lab, lo, hi in (("crew avg <= -1.5", -99, -1.5), ("-1.5..-0.5", -1.5, -0.5), ("-0.5..+0.5", -0.5, 0.5), ("+0.5..+1.5", 0.5, 1.5), ("crew avg >= +1.5", 1.5, 99)):
    for per, a, b in (("2015-2020", 2015, 2020), ("2021-2025", 2021, 2025), ("2026", 2026, 2026)):
        xs = [x for x in rows if lo <= x[1] < hi and a <= x[0] <= b]
        print(f"{lab:18s} {per}: {rec(xs)}")
