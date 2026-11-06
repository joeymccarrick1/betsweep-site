"""Unders on popular players (owner 11/5 fade question). FanDuel's main line per player-market-week (frozen ladder rung priced closest to
-110, within -170..+150) from legsnaps (graded weeks); "star" = line in the top quarter of that market that week (the big names the public
bets). Prints over hit rate star vs rest per market and per week; an under at ~-110 needs the over to hit under 47.6%.
Usage: python3 -I research/star_unders.py <legsnaps.json> [out.json]
"""
import sys, json, collections
v = json.load(open(sys.argv[1]))["values"]; H = {c: i for i, c in enumerate(v[0])}
def imp(o): return 100 / (o + 100) if o > 0 else -o / (-o + 100)
best = {}
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
    try: o = float(r[H["FanDuel odds"]]); ln = float(r[H["Line (X+)"]]); w = int(float(r[0]))
    except Exception: continue
    m = r[H["Market"]]
    if m not in ("Receiving Yards", "Receptions", "Rushing Yards", "Passing Yards") or not (-170 <= o <= 150) or (0 <= o < 100): continue
    k = (w, r[H["Player"]], m); d = abs(imp(o) - 0.5238)
    if k not in best or d < best[k][0]: best[k] = (d, ln, r[H["Result"]] == "HIT", o)
by = collections.defaultdict(list)
for (w, pl, m), (d, ln, hit, o) in best.items(): by[(w, m)].append((ln, hit, o, pl))
agg = collections.defaultdict(lambda: [0, 0]); per = collections.defaultdict(lambda: [0, 0])
for (w, m), xs in by.items():
    xs.sort(key=lambda x: -x[0]); cut = max(1, len(xs) // 4)
    for i, (ln, hit, o, pl) in enumerate(xs):
        grp = "star" if i < cut else "rest"
        for key in ((m, grp), ("ALL", grp)): agg[key][0] += int(hit); agg[key][1] += 1
        per[(w, grp)][0] += int(hit); per[(w, grp)][1] += 1
out = {}
for key in sorted(agg):
    h, n = agg[key]; out[f"{key[0]}|{key[1]}"] = [h, n]
    print(f"{key[0]:16s} {key[1]:4s}: overs {h}-{n-h} ({h/n*100:.1f}%) -> unders {n-h}-{h} ({(n-h)/n*100:.1f}%)")
for key in sorted(per): h, n = per[key]; print(f"  week {key[0]} {key[1]}: overs {h}/{n} ({h/n*100:.0f}%)")
if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w"))
