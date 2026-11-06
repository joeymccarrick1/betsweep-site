"""research/insurance_shift.py (owner 11/6, fantasy insurance card): how much does a player's fantasy day move when his main prop goes over?
For every player-season (2024-26 REG, 6+ games of real volume) the "line" is his own median of the stat (a coin-flip line, like a main
prop). Reported per position: mean PPR points when over the line minus his season mean, as a share of his mean (so it scales to any
player), and the same for scoring a TD. Feeds the win-chance-if-it-hits number on the Fantasy page."""
import csv, statistics as st, collections, json
STAT = {"QB": "passing_yards", "RB": "rushing_yards", "WR": "receiving_yards", "TE": "receiving_yards"}
rows = collections.defaultdict(list)
for yr in (2024, 2025, 2026):
    for r in csv.DictReader(open(f"/tmp/gt9/in/stats_player_week_{yr}.csv")):
        if r.get("season_type") != "REG" or r.get("position") not in STAT: continue
        try: pts = float(r["fantasy_points_ppr"] or 0); v = float(r[STAT[r["position"]]] or 0); td = float(r["rushing_tds"] or 0) + float(r["receiving_tds"] or 0)
        except Exception: continue
        rows[(yr, r["player_display_name"], r["position"])].append((v, pts, td))
out = {}
for pos in STAT:
    up, dn, tup, n, nt = [], [], [], 0, 0
    for (yr, nm, p), g in rows.items():
        if p != pos or len(g) < 6: continue
        mean = st.mean(x[1] for x in g)
        if mean < (12 if pos == "QB" else 6): continue
        med = st.median(x[0] for x in g)
        o = [x[1] for x in g if x[0] > med]; u = [x[1] for x in g if x[0] <= med]
        if o and u: up.append((st.mean(o) - mean) / mean); dn.append((st.mean(u) - mean) / mean); n += 1
        t = [x[1] for x in g if x[2] >= 1]
        if t and len(t) < len(g): tup.append((st.mean(t) - mean) / mean); nt += 1
    out[pos] = {"over": round(st.mean(up), 3), "under": round(st.mean(dn), 3), "td": round(st.mean(tup), 3), "n": n, "nt": nt}
    print(pos, out[pos])
json.dump(out, open("/home/claude/work/gp/research/insurance_shift.json", "w"), indent=1)
