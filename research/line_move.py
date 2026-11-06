"""Follow the line move (owner 11/5 fade question): for each 2026 game in 'AUTO - Model Calls Archive' (calls.json), FanDuel's spread / total at
our FIRST freeze vs our LAST freeze before kickoff. If the spread moved 1+ pt (total 1.5+), bet WITH the move at the LAST number (what you
could actually bet when you noticed) and grade on the final score; also grade the last-freeze number vs nflverse's closing line (CLV).
Usage: python3 -I research/line_move.py <calls.json> <games.csv> [out.json]
"""
import sys, json, csv
v = json.load(open(sys.argv[1]))["values"]; H = {c: i for i, c in enumerate(v[0])}
fin = {}
for g in csv.DictReader(open(sys.argv[2])):
    if g["season"] == "2026" and g["home_score"] not in ("", "NA"):
        fin[(g["week"], frozenset([g["home_team"], g["away_team"]]))] = g
def num(x):
    try: return float(x)
    except Exception: return None
by = {}
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    sp, tot = num(r[H["FD spread (A)"]]), num(r[H["FD total"]])
    if sp is None: continue
    by.setdefault((r[0], r[H["A"]], r[H["B"]]), []).append((r[H["Frozen at (CT)"]], sp, tot))
res = {"spread": [0, 0, 0], "total": [0, 0, 0], "games": 0, "moved_sp": [], "moved_tot": []}
for (w, a, b), xs in by.items():
    g = fin.get((str(w), frozenset([a, b])))
    if not g: continue
    xs.sort(); f, l = xs[0], xs[-1]; res["games"] += 1
    hs, as_ = float(g["home_score"]), float(g["away_score"]); ma = (hs - as_) if g["home_team"] == a else (as_ - hs); tt = hs + as_
    mv = l[1] - f[1]   # spread for A: negative move = toward A
    if abs(mv) >= 1:
        side_a = mv < 0; cov = ma + l[1]
        if cov != 0:
            win = (cov > 0) == side_a; res["spread"][0 if win else 1] += 1
            res["moved_sp"].append([w, a, b, f[1], l[1], ma, "W" if win else "L"])
        else: res["spread"][2] += 1
    if f[2] is not None and l[2] is not None and abs(l[2] - f[2]) >= 1.5:
        up = l[2] > f[2]; d = tt - l[2]
        if d != 0:
            win = (d > 0) == up; res["total"][0 if win else 1] += 1; res["moved_tot"].append([w, a, b, f[2], l[2], tt, "W" if win else "L"])
        else: res["total"][2] += 1
pc = lambda x: f"{x[0]}-{x[1]}" + (f" ({x[0]/(x[0]+x[1])*100:.0f}%)" if x[0] + x[1] else "")
print(f"2026 games with 2+ freezes and a final: {res['games']}; spreads that moved 1+ between our first and last freeze, bet with the move at the last number: {pc(res['spread'])}; totals moved 1.5+: {pc(res['total'])}")
for x in res["moved_sp"]: print("  sp", x)
for x in res["moved_tot"]: print("  tot", x)
if len(sys.argv) > 3: json.dump(res, open(sys.argv[3], "w"))
