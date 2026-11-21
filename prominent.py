"""prominent.py - who counts as a big name for the news push (owner 11/20: "push notifications about prominent players being out or
released"). From this season's game log: every quarterback with 4+ starts (15+ attempts), and the top 30 backs, 40 receivers and 14
tight ends by fantasy points a game (4+ games). Season-long on purpose: a player who is released drops out of this week's projections,
and he still has to be on the list for the release to be noticed.   build(values) -> [{"n", "tm", "pos", "ppg"}]"""
TOP = {"RB": 30, "WR": 40, "TE": 14}


def build(values):
    h = {k: i for i, k in enumerate(values[0])}; P = {}
    for r in values[1:]:
        if not r or not str(r[0]).isdigit(): continue
        g = lambda k: r[h[k]] if h[k] < len(r) else ""
        try: fp = float(g("Fantasy Pts") or 0); att = float(g("Pass Att") or 0)
        except Exception: continue
        p = P.setdefault(g("Player"), {"n": g("Player"), "pos": g("Pos"), "tm": g("Team"), "w": 0, "g": 0, "fp": 0.0, "st": 0})
        if int(r[0]) >= p["w"]: p["w"] = int(r[0]); p["tm"] = g("Team")
        p["g"] += 1; p["fp"] += fp; p["st"] += 1 if att >= 15 else 0
    out = [p for p in P.values() if p["pos"] == "QB" and p["st"] >= 4]
    for pos, n in TOP.items():
        out += sorted([p for p in P.values() if p["pos"] == pos and p["g"] >= 4], key=lambda p: -p["fp"] / p["g"])[:n]
    return [{"n": p["n"], "tm": p["tm"], "pos": p["pos"], "ppg": round(p["fp"] / p["g"], 1)} for p in sorted(out, key=lambda p: p["n"])]


if __name__ == "__main__":
    import json, os, sys
    v = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "in", "gamelog.json")))["values"]; L = build(v)
    print(len(L), [p["n"] for p in L if p["n"] in ("Kenneth Walker III", "Daniel Jones", "Michael Carter", "James Cook")])
