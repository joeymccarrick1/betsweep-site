#!/usr/bin/env python3
"""offranks.py - OFFENSIVE stat ranks per team, the mirror of 'AUTO - Defensive Stat Matchup Ranks' (owner 10/29: "I'd like to also see the
teams offensive rankings in each stat for each player whenever we look at defensive matchups").

Same 15 columns as the defense tab (QB Pass Yds ... TE Receptions), same two windows (season to date, and last 3 weeks W-3..W-1), per team
game, but grouped by the player's OWN team instead of the opponent, and rank 1 = PRODUCES the most. Built from in/gamelog.json
('AUTO - Player Game Log', already read in Step 2 for the SOS step), weeks before the projection week only.

    load(IN, WEEK) -> {"season": {team: [15 ranks]}, "l3": {team: [15 ranks]}, "cols": [...15 names], "pg": {"season": {team: [15 per-game values]}, ...}}
    rank(OR, team, col, window="season") -> int | None
    side_by_side(team, opp, col, OR, DR) -> (off_rank, def_rank)   helper for the pages

check(IN, WEEK) recomputes the DEFENSE side with the same code and compares it to in/ranks.json, so a definition drift shows up in the build log.
"""
import json, os

COLS = ["QB Pass Yds", "QB Rush Yds", "RB Rush Yds", "RB Rec Yds", "WR Rec Yds", "TE Rec Yds", "QB Pass TD", "QB Rush TD", "RB Rush TD",
        "RB Rec TD", "WR Rec TD", "TE Rec TD", "RB Receptions", "WR Receptions", "TE Receptions"]
# column -> (position, game-log stat column)
SRC = {"QB Pass Yds": ("QB", "Pass Yds"), "QB Rush Yds": ("QB", "Rush Yds"), "RB Rush Yds": ("RB", "Rush Yds"), "RB Rec Yds": ("RB", "Rec Yds"),
       "WR Rec Yds": ("WR", "Rec Yds"), "TE Rec Yds": ("TE", "Rec Yds"), "QB Pass TD": ("QB", "Pass TD"), "QB Rush TD": ("QB", "Rush TD"),
       "RB Rush TD": ("RB", "Rush TD"), "RB Rec TD": ("RB", "Rec TD"), "WR Rec TD": ("WR", "Rec TD"), "TE Rec TD": ("TE", "Rec TD"),
       "RB Receptions": ("RB", "Receptions"), "WR Receptions": ("WR", "Receptions"), "TE Receptions": ("TE", "Receptions")}
ALIAS = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}

def _num(x):
    try: return float(x)
    except Exception: return 0.0

def _rows(IN):
    d = json.load(open(os.path.join(IN, "gamelog.json"))); v = d["values"] if isinstance(d, dict) else d
    h = {c: i for i, c in enumerate(v[0])}
    out = []
    for r in v[1:]:
        if not r or len(r) < len(v[0]) - 2: continue
        try: wk = int(float(r[h["Week"]]))
        except Exception: continue
        t = ALIAS.get(str(r[h["Team"]]).strip(), str(r[h["Team"]]).strip()); o = ALIAS.get(str(r[h["Opponent"]]).strip(), str(r[h["Opponent"]]).strip())
        out.append((wk, t, o, str(r[h["Pos"]]).strip(), {c: _num(r[h[c]]) if h.get(c) is not None and h[c] < len(r) else 0.0 for c in ("Pass Yds", "Rush Yds", "Pass TD", "Rush TD", "Rec Yds", "Rec TD", "Receptions")}))
    return out

def _ranks(rows, weeks, side):
    """side 'off' groups by team, 'def' by opponent. Per team game; rank 1 = most (min rank for ties, like RANK in Sheets)."""
    tot, games = {}, {}
    for wk, t, o, pos, s in rows:
        if wk not in weeks: continue
        k = t if side == "off" else o
        if not k: continue
        games.setdefault(k, set()).add(wk)
        a = tot.setdefault(k, [0.0] * len(COLS))
        for i, c in enumerate(COLS):
            p, st = SRC[c]
            if pos == p: a[i] += s[st]
    pg = {k: [a / max(1, len(games[k])) for a in v] for k, v in tot.items()}
    rk = {k: [0] * len(COLS) for k in pg}
    for i in range(len(COLS)):
        vals = sorted((pg[k][i] for k in pg), reverse=True)
        for k in pg: rk[k][i] = 1 + sum(1 for x in vals if x > pg[k][i] + 1e-9)
    return rk, pg

def load(IN, WEEK):
    rows = _rows(IN); WEEK = int(WEEK)
    s_rk, s_pg = _ranks(rows, set(range(1, WEEK)), "off")
    l_rk, l_pg = _ranks(rows, set(range(max(1, WEEK - 3), WEEK)), "off")
    return {"season": s_rk, "l3": l_rk, "cols": COLS, "pg": {"season": s_pg, "l3": l_pg}, "week": WEEK}

def rank(OR, team, col, window="season"):
    if not OR or col not in COLS: return None
    t = ALIAS.get(team, team); r = (OR.get(window) or {}).get(t)
    return r[COLS.index(col)] if r else None

def check(IN, WEEK):
    """Recompute the DEFENSE ranks with this code and compare to the sheet's tab: returns (cells compared, cells matching, max |diff|)."""
    rows = _rows(IN); WEEK = int(WEEK)
    mine, _ = _ranks(rows, set(range(1, WEEK)), "def")
    d = json.load(open(os.path.join(IN, "ranks.json"))); v = d["values"] if isinstance(d, dict) else d
    hdr = v[0][1:]; n = ok = 0; mx = 0
    for r in v[1:]:
        if not r or str(r[0]).startswith("LAST 3"): break
        t = ALIAS.get(str(r[0]).strip(), str(r[0]).strip())
        if t in ("Defense", "") or t not in mine: continue
        for j, c in enumerate(hdr):
            if c not in COLS or j + 1 >= len(r): continue
            try: sheet = int(float(r[j + 1]))
            except Exception: continue
            n += 1; dv = abs(sheet - mine[t][COLS.index(c)]); ok += dv == 0; mx = max(mx, dv)
    return n, ok, mx

if __name__ == "__main__":
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in")
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    OR = load(IN, W); print("teams", len(OR["season"]), "GB", dict(zip(COLS, OR["season"].get("GB", []))))
    print("defense self-check (cells, exact, max diff):", check(IN, W))
