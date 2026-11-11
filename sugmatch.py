"""sugmatch.py - the suggested legs near -110, shared by Beat the model (build_beat.py) and the Parlay Builder (build_builder.py).

Owner 11/11 8:20 AM: "suggested legs around -110 that we can scroll through to build our five. Include percentage and position ranking in
that stat vs defensive matchup in that stat for each leg"; 8:28 AM: "Having this same best legs where you can scroll and add to parlay on
the parlay builder page would be cool".

pick(legs, IN, week) -> [[slip key, pos, [[stat, offense rank, defense rank], ...]], ...], the model's most likely first.
Rules: player props priced -125 to +100; one rung per player + market (the side is in the market name), the one nearest -110; model 50% or
better; the row must have the matchup pair. Offense rank = his team's rank at his position in that stat (offranks.py, 1 = produces the
most); defense rank = the opponent's rank against that position (the sheet's defense tab, 1 = allows the most) - the builder's own pill.
An under uses its stat's ranks; Rush + Rec carries two pairs; Longest Reception uses receiving yards; TD legs use the position's TD column.
"""
import json, os, math
LO, HI = -125, 100

def key(pl, m, ln): return f"{pl}|{m}|{int(math.floor((float(ln) if ln is not None else 1) + 0.5))}"
def stat_cols(pos, m):
    m = m[6:] if m.startswith("Under ") else m
    if m == "Passing Yards" and pos == "QB": return [("pass yds", "QB Pass Yds")]
    if m == "Passing TDs" and pos == "QB": return [("pass TDs", "QB Pass TD")]
    if m == "Rushing Yards" and pos in ("QB", "RB"): return [("rush yds", f"{pos} Rush Yds")]
    if m in ("Receiving Yards", "Longest Reception") and pos in ("RB", "WR", "TE"): return [("rec yds", f"{pos} Rec Yds")]
    if m == "Receptions" and pos in ("RB", "WR", "TE"): return [("catches", f"{pos} Receptions")]
    if m == "Rush + Rec Yards" and pos == "RB": return [("rush yds", "RB Rush Yds"), ("rec yds", "RB Rec Yds")]
    if m in ("Anytime TD", "First TD", "2+ TD"): return [("rush TDs", f"{pos} Rush TD")] if pos in ("QB", "RB") else ([("rec TDs", f"{pos} Rec TD")] if pos in ("WR", "TE") else [])
    return []
def _imp(o): return (-o / (-o + 100.0)) if o < 0 else 100.0 / (o + 100.0)

def pick(legs, IN, week):
    DRK, DCOL = {}, {}
    try:
        d = json.load(open(os.path.join(IN, "ranks.json"))); rr = d["values"] if isinstance(d, dict) else d
        DCOL = {c: i for i, c in enumerate(rr[0][1:])}
        for r in rr[1:]:
            if r and str(r[0]).startswith("LAST 3"): break
            if not r or r[0] in ("Defense", ""): continue
            try: DRK[r[0]] = [int(float(x)) if str(x).strip() != "" else None for x in r[1:16]]
            except Exception: pass
    except Exception as e: print("note: defense ranks unavailable:", e)
    try:
        import offranks as ORK; OR = ORK.load(IN, week)
    except Exception as e: ORK = OR = None; print("note: offense ranks unavailable:", e)
    def matchup(pos, tm, opp, m):
        out = []
        for lab, c in stat_cols(pos, m):
            o = ORK.rank(OR, tm, c) if OR else None
            dd = (DRK.get(opp) or [None] * 15)[DCOL[c]] if c in DCOL else None
            if o is not None and dd is not None: out.append([lab, o, dd])
        return out
    best = {}
    for l in legs:
        o, p = l.get("o"), l.get("p")
        if l.get("gl") or o is None or p is None or not (LO <= o <= HI) or p < 0.5 or l.get("pos") not in ("QB", "RB", "WR", "TE"): continue
        fam = (l["pl"], l["m"]); rk = (abs(_imp(o) - _imp(-110)), -p)
        if fam not in best or rk < best[fam][0]: best[fam] = (rk, l)
    out = []
    for _, l in best.values():
        mu = matchup(l["pos"], l.get("tm", ""), l.get("opp", ""), l["m"])
        if mu: out.append((l["p"], [key(l["pl"], l["m"], l.get("ln", 1)), l["pos"], mu]))
    return [x for _, x in sorted(out, key=lambda t: -t[0])]
