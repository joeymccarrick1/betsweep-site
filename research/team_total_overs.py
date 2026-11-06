"""research/team_total_overs.py (owner 11/6, Ravens TNF): do player overs on teams the market expects to score little underperform their
FanDuel price? Graded frozen legs (legsnaps, Latest Snapshot) Weeks 6-9 (Week 9 graded from nflverse stats when the sheet is pending),
implied team total = total/2 +- spread/2 from games.csv. Hit rate vs the price's implied % by team-total band, overs only."""
import csv, json, sys, collections
v = json.load(open(sys.argv[1]))["values"]; H = {c: i for i, c in enumerate(v[0])}
G = {}
for g in csv.DictReader(open(sys.argv[2])):
    if g["season"] != "2026" or g.get("total_line") in ("", "NA") or g.get("spread_line") in ("", "NA"): continue
    tl, sp = float(g["total_line"]), float(g["spread_line"])
    G[(int(g["week"]), g["home_team"])] = tl / 2 + sp / 2; G[(int(g["week"]), g["away_team"])] = tl / 2 - sp / 2
S = {}
if len(sys.argv) > 3:
    for r in csv.DictReader(open(sys.argv[3])): S[(int(r["week"]), r["player_display_name"])] = r
COL = {"Receiving Yards": "receiving_yards", "Receptions": "receptions", "Rushing Yards": "rushing_yards", "Passing Yards": "passing_yards"}
st = collections.defaultdict(lambda: [0, 0, 0.0, 0.0])
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE": continue
    wk = int(float(r[0])); m = r[H["Market"]]; res = r[H["Result"]]
    if m not in COL and m != "Anytime TD": continue
    if res not in ("HIT", "MISS"):
        s = S.get((wk, r[H["Player"]]))
        if not s: continue
        act = float(s["rushing_tds"] or 0) + float(s["receiving_tds"] or 0) if m == "Anytime TD" else float(s[COL[m]] or 0)
        res = "HIT" if act >= float(r[H["Line (X+)"]]) else "MISS"
    tt = G.get((wk, r[H["Team"]].replace("LAR", "LA")))
    if tt is None: continue
    try: bk = float(r[H["Book implied %"]]); o = float(r[H["FanDuel odds"]])
    except Exception: continue
    band = "team total < 19" if tt < 19 else "19-22.5" if tt < 22.5 else "22.5-26" if tt < 26 else "26+"
    dec = 1 + o / 100 if o > 0 else 1 + 100 / -o
    for key in ((band, "all overs"), (band, m)):
        x = st[key]; x[0] += 1; x[1] += res == "HIT"; x[2] += bk; x[3] += (dec - 1) if res == "HIT" else -1
for k in sorted(st):
    n, h, b, u = st[k]
    if n >= 40: print(f"{k[0]:16s} {k[1]:16s} n={n:4d} hit {h / n:.1%} vs price {b / n:.1%}  ROI {u / n:+.1%}")
