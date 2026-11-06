"""simdef.py - "vs similar defenses" for every player this week (owner 11/6: "I want us to utilize the similar defenses").

Same split as the Game previews (build_dossier.py): this week's opponent's defensive profile (pass / rush yards allowed, yards per play,
sacks, takeaways - earlier weeks only, z-scored, weighted distance) -> the 3 past opponents of the player's team that look most like it ->
the player's main stat in those games vs his season average. QB pass yds, RB rush yds, WR/TE rec yds.

How it is used (owner decision, 11/6): a visible chip on every leg, and the TIEBREAKER for best-bet / listed-parlay picks among legs that
already qualify on edge - it never changes a probability. Tested 2024-26 it did not predict results (research/similar_def.py: players 20%+
above their average vs similar defenses hit FanDuel overs 46.5% vs 56.7% priced), so it is graded every Tuesday (research/simdef_grade.py
via legsnaps) and the tiebreaker comes off if it keeps losing (RUNBOOK).
"""
import csv, os, math, collections, statistics as st
STAT = {"QB": "passing_yards", "RB": "rushing_yards", "WR": "receiving_yards", "TE": "receiving_yards"}
KEYS = ("pyd", "ryd", "ypp", "sk", "to"); WT = {"pyd": 1.0, "ryd": 1.0, "ypp": 0.8, "sk": 0.6, "to": 0.4}
FIX = {"LAR": "LA", "WSH": "WAS"}
def _f(x):
    try: return float(x or 0)
    except Exception: return 0.0
def T(t): return FIX.get(t, t)
def load(IN, WEEK, season=2026):
    """-> {(player, team): {"pct": .41, "n": 3, "opps": ["CLE", ...], "near": 61.3, "season": 43.5, "opp": "BAL"}}"""
    OFF = {}
    for r in csv.DictReader(open(os.path.join(IN, f"stats_team_week_{season}.csv"))):
        if r.get("season_type", "REG") != "REG" or int(r["week"]) >= WEEK: continue
        OFF[(T(r["team"]), int(r["week"]))] = {"opp": T(r["opponent_team"]), "pyd": _f(r["passing_yards"]) - _f(r.get("sack_yards_lost")), "ryd": _f(r["rushing_yards"]),
            "plays": _f(r["attempts"]) + _f(r["carries"]) + _f(r["sacks_suffered"]), "sk": _f(r["sacks_suffered"]),
            "to": _f(r["passing_interceptions"]) + _f(r.get("sack_fumbles_lost")) + _f(r.get("rushing_fumbles_lost")) + _f(r.get("receiving_fumbles_lost"))}
    DG = collections.defaultdict(list)
    for (t, w), l in OFF.items(): DG[l["opp"]].append(l)
    PROF = {d: {"pyd": st.mean(x["pyd"] for x in ls), "ryd": st.mean(x["ryd"] for x in ls), "ypp": sum(x["pyd"] + x["ryd"] for x in ls) / max(1, sum(x["plays"] for x in ls)),
                "sk": st.mean(x["sk"] for x in ls), "to": st.mean(x["to"] for x in ls)} for d, ls in DG.items() if len(ls) >= 3}
    if len(PROF) < 16: return {}
    MU = {k: st.mean(PROF[d][k] for d in PROF) for k in KEYS}; SD = {k: st.pstdev([PROF[d][k] for d in PROF]) or 1 for k in KEYS}
    Z = {d: {k: (PROF[d][k] - MU[k]) / SD[k] for k in KEYS} for d in PROF}
    dist = lambda a, b: math.sqrt(sum(WT[k] * (Z[a][k] - Z[b][k]) ** 2 for k in KEYS))
    OPP = {}
    for g in csv.DictReader(open(os.path.join(IN, "games.csv"))):
        if g["season"] == str(season) and g["week"] == str(WEEK) and g["game_type"] == "REG":
            OPP[T(g["home_team"])] = T(g["away_team"]); OPP[T(g["away_team"])] = T(g["home_team"])
    PG = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(IN, f"stats_player_week_{season}.csv"))):
        if r.get("season_type") != "REG" or r.get("position") not in STAT or int(r["week"]) >= WEEK: continue
        PG[(r["player_display_name"], T(r["team"]))].append((int(r["week"]), T(r["opponent_team"]), _f(r[STAT[r["position"]]]), r["position"]))
    out = {}
    for (pl, tm), gs in PG.items():
        opp = OPP.get(tm)
        if not opp or opp not in Z or len(gs) < 3: continue
        s = st.mean(g[2] for g in gs); pos = gs[-1][3]
        if s < (120 if pos == "QB" else 15): continue
        past = [g for g in gs if g[1] in Z and g[1] != opp]
        if len(past) < 3: continue
        near = sorted(past, key=lambda g: dist(opp, g[1]))[:3]
        v = st.mean(g[2] for g in near)
        out[(pl, tm)] = {"pct": round((v - s) / s, 3), "n": len(near), "cons": sum(1 for g in near if g[2] > s), "opps": [g[1] for g in near], "near": round(v, 1), "season": round(s, 1), "opp": opp, "pos": pos}
    return out
MAIN = {"QB": ("Passing Yards",), "RB": ("Rushing Yards", "Rush Attempts"), "WR": ("Receiving Yards", "Receptions", "Longest Reception"), "TE": ("Receiving Yards", "Receptions", "Longest Reception")}
def for_leg(SD, pl, tm, market):
    """The split when the leg's market is (or moves with) the player's main stat, else None."""
    x = SD.get((pl, T(tm)))
    if not x: return None
    m = str(market).replace("Under ", "")
    return x if m in MAIN.get(x["pos"], ()) else None
