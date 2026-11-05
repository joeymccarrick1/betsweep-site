#!/usr/bin/env python3
"""build_snaps.py - refresh rows for the Sheet tab 'AUTO - Snap Trends' from nflverse snap counts.

Usage:  python3 build_snaps.py            (week = 'boards.json' projection week; season 2026)
Reads  in/proj_qb.json, proj_rb.json, proj_wr.json, proj_te.json (to spell names the way the model does)
Downloads https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_<season>.csv
Writes out/snaps_values.json = {"range": "'AUTO - Snap Trends'!A3:I<n>", "values": [[...], ...]} and out/snaps_meta.txt
  Columns: Player | Team | Pos | Games | Season snap % | Last-2 snap % | Last game snap % | Trend (L2 - season) | Signal
  Only regular-season games with week < projection week; QB/RB/WR/TE with 3+ games. Column J (factor) is an
  ARRAYFORMULA already in the tab, driven by 'AUTO - Settings'!B267:B277 - do not overwrite it.
The caller clears 'AUTO - Snap Trends'!A2:I700 (keep J2, the factor ARRAYFORMULA, and K2/L2) and writes these values, then puts the week in K2 and a stamp in L2.
"""
import json, os, re, csv, io, sys, datetime, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
boards = vals("boards.json"); WEEK = int(sys.argv[1]) if len(sys.argv) > 1 else int(float(boards[1][1])); SEASON = 2026
def norm(s):
    s = re.sub(r"\.", "", str(s)).strip(); s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s, flags=re.I); return re.sub(r"\s+", " ", s).lower()
model = {}
for fn, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
    try:
        for r in vals(fn)[1:]:
            if r and r[0]: model.setdefault((norm(r[0]), pos), (r[0], r[1]))
    except Exception as e: print("warn:", fn, e)
url = f"https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{SEASON}.csv"
dst = os.path.join(IN, f"snap_counts_{SEASON}.csv")
try:
    urllib.request.urlretrieve(url, dst)
except Exception as e:
    if not os.path.exists(dst): sys.exit(f"snap counts download failed: {e}")
    print("warn: download failed, using cached file", e)
# injury reports (nflverse): injweeks.py uses them to set aside games shaped by an injury - the hurt player's own limited games and his
# teammates' fill-in games while he is back this week - so a hobbled starter is not a "SNAPS DOWN" (which also cuts his projection
# through column J) and the backup who filled in is not a "SNAPS UP". Owner 2026-10-22 (TreVeyon Henderson / Corey Kiner).
inj_dst = os.path.join(IN, f"injuries_{SEASON}.csv")
try: urllib.request.urlretrieve(f"https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{SEASON}.csv", inj_dst)
except Exception as e: print("warn: injury report download failed" + (", using cached file" if os.path.exists(inj_dst) else " - no injury weeks set aside"), e)
sys.path.insert(0, HERE)
import injweeks as INJ
IW = INJ.load(IN, WEEK, SEASON)
rows = {}
with open(dst, newline="") as f:
    for r in csv.DictReader(f):
        if r["game_type"] != "REG" or r["position"] not in ("QB", "RB", "WR", "TE"): continue
        try: wk = int(r["week"]); pct = float(r["offense_pct"])
        except Exception: continue
        if wk >= WEEK: continue
        rows.setdefault((norm(r["player"]), r["position"]), []).append((wk, pct, r["player"], r["team"]))
out = []
for (key, pos), g in rows.items():
    g.sort(); n = len(g)
    if n < 3: continue
    name, team = model.get((key, pos), (g[-1][2], g[-1][3]))
    excl = set()
    # FIRST GAMES BACK (owner OK 10/23): an injury-limited game among his last two games played, in a real role (median snap share >= 25%, as injweeks.py)
    # -> 'RETURN' in column M; the J factor multiplies by 'AUTO - Settings'!B278 (0.935). nflverse 2019-25 backtest: players right after an
    # injury-limited game produced 0.937 (train 2019-22) / 0.938 (test 2023-25) of their all-games average relative to players without one (0.927 / 0.933 with a 50% snap floor);
    # the projection tabs average all games, so ~0.935 is the matching factor (test MAE 28.24 -> 27.80 yds).
    ret = ""
    if IW:
        _lim = set(IW.limited(g[-1][2], g[-1][3]))
        _last2 = {x[0] for x in g[-2:]}
        _med = sorted(x[1] for x in g)[len(g) // 2]
        if _lim & _last2 and _med >= 0.25 and pos in ("RB", "WR", "TE"): ret = "RETURN"   # backtested on RB / WR / TE only
    if IW:
        excl = set(IW.limited(g[-1][2], g[-1][3])) | set(IW.fill(g[-1][2], g[-1][3], pos))
        g2 = [x for x in g if x[0] not in excl]
        if excl & {x[0] for x in g} and len(g2) >= 2: g = g2; n = len(g)
        else: excl = set()
    season = sum(x[1] for x in g) / n; l2 = (g[-1][1] + g[-2][1]) / 2; last = g[-1][1]; trend = l2 - season
    sig = "SNAPS DOWN" if trend <= -0.10 else "SNAPS UP" if trend >= 0.10 else "STABLE"
    if excl: sig += " (injury wks " + ",".join(str(w) for w in sorted(excl)) + " set aside)"
    out.append([name, team, pos, n, round(season, 3), round(l2, 3), round(last, 3), round(trend, 3), sig, ret])
    NX = globals().get("NX", 0) + (1 if excl else 0); globals()["NX"] = NX
out.sort(key=lambda r: (["QB", "RB", "WR", "TE"].index(r[2]), r[0]))
json.dump({"range": f"'AUTO - Snap Trends'!A2:I{1 + len(out)}", "values": [r[:9] for r in out]}, open(os.path.join(OUT, "snaps_values.json"), "w"))
# column M (first games back) is a separate write - K2/L2 hold the week and stamp, so A:M cannot go in one range
json.dump({"range": f"'AUTO - Snap Trends'!M2:M700", "values": [[r[9]] for r in out] + [[""]] * (699 - len(out))}, open(os.path.join(OUT, "snaps_return.json"), "w"))
print(f"first games back (column M = RETURN, J x Settings B278): {sum(1 for r in out if r[9])} players: " + ", ".join(r[0] for r in out if r[9]))
stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
open(os.path.join(OUT, "snaps_meta.txt"), "w").write(f"week={WEEK}\nrows={len(out)}\nK2={WEEK}\nL2={stamp} nflverse snap_counts weeks 1-{WEEK-1}; offense_pct; QB/RB/WR/TE with 3+ games; names as the model spells them. Factor (J) = 1 + w(pos) x Trend when Trend <= threshold AND last game <= season + guard, floored; 1 otherwise. Settings B267:B277.\n")
down = [r for r in out if r[8].startswith("SNAPS DOWN")]
print(f"wrote out/snaps_values.json: {len(out)} rows for week {WEEK} ({len(down)} SNAPS DOWN, {sum(1 for r in out if r[8].startswith('SNAPS UP'))} SNAPS UP; {globals().get('NX', 0)} players with injury-shaped weeks set aside); matched to model names: {sum(1 for r in out if (norm(r[0]), r[2]) in model)}")
