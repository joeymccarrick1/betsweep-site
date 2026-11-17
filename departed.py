#!/usr/bin/env python3
"""departed.py - targets that left a team with a traded player (11/17).

Why. The Colts traded Keenan Allen (SF) and Josh Downs (KC) before Week 10: 115 targets in nine games. Nobody on the Colts was
"out", so nothing on the site knew the room had emptied - the sheet handed no targets to the players left (fixed there the same
day: tab 'AUTO - Departed Targets'), the flags said nothing, and the Under of the day was Jonathan Taylor under 3.5 catches on a
team that had just lost its two top targets and was an 11.5-point underdog. FanDuel's lines knew: seven of the week's twenty
biggest model-vs-FanDuel gaps were Colts pass catchers.

load(in_dir, week) reads the game log and the three projection tabs from the sheet mirror and returns, per OLD team, the players
whose team on the projection tabs is now a different one, with the same bar the sheet uses for a key absentee (2+ games and 3.3+
targets a game for the old team):
    {"IND": [{"pl": "Keenan Allen", "pos": "WR", "now": "SF", "g": 8, "tg": 58, "per": 5.8}, ...]}
"per" = his targets for the old team / that team's games so far - the share of the team's weekly targets that left with him.
per_team(dep) -> {"IND": 11.5}. Used by flags.py (the "Fill-in volume" flag) and under_day.py (no catch / receiving-yard under on a
team whose targets are up for grabs).
"""
import json, os

KEY_G, KEY_TG = 2, 3.3

def _vals(in_dir, name):
    try:
        d = json.load(open(os.path.join(in_dir, name)))
        return d.get("values", d) if isinstance(d, dict) else d
    except Exception:
        return []

def load(in_dir="in", week=None):
    now = {}
    for tab in ("proj_wr.json", "proj_te.json", "proj_rb.json"):
        for r in _vals(in_dir, tab)[1:]:
            if len(r) > 1 and r[0] and r[1]: now.setdefault(str(r[0]).strip(), str(r[1]).strip())
    gl = _vals(in_dir, "gamelog.json")
    if not gl or not now: return {}
    H = {h: i for i, h in enumerate(gl[0])}
    need = ("Week", "Player", "Team", "Pos", "Targets")
    if any(k not in H for k in need): return {}
    def num(x):
        try: return float(x)
        except (TypeError, ValueError): return 0.0
    agg, team_weeks = {}, {}
    for r in gl[1:]:
        if len(r) <= max(H[k] for k in need): continue
        w = int(num(r[H["Week"]]))
        if not w or (week is not None and w >= int(week)): continue
        pl, tm, pos = str(r[H["Player"]]).strip(), str(r[H["Team"]]).strip(), str(r[H["Pos"]]).strip()
        if not pl or not tm: continue
        team_weeks.setdefault(tm, set()).add(w)
        if pos not in ("WR", "TE", "RB"): continue
        a = agg.setdefault((pl, tm, pos), [0, 0.0]); a[0] += 1; a[1] += num(r[H["Targets"]])
    out = {}
    for (pl, tm, pos), (g, tg) in agg.items():
        cur = now.get(pl)
        if not cur or cur == tm or g < KEY_G or tg / g < KEY_TG: continue
        out.setdefault(tm, []).append({"pl": pl, "pos": pos, "now": cur, "g": g, "tg": int(round(tg)), "per": round(tg / max(1, len(team_weeks.get(tm, ()))), 2)})
    for tm in out: out[tm].sort(key=lambda d: -d["per"])
    return out

def per_team(dep):
    return {tm: round(sum(d["per"] for d in ds), 2) for tm, ds in (dep or {}).items()}

if __name__ == "__main__":
    import sys
    d = load(sys.argv[1] if len(sys.argv) > 1 else "in", sys.argv[2] if len(sys.argv) > 2 else None)
    for tm, ds in sorted(d.items()): print(tm, per_team(d)[tm], ", ".join(f'{x["pl"]} ({x["pos"]}, now {x["now"]}: {x["tg"]} targets in {x["g"]} games)' for x in ds))
    if not d: print("no departed key targets")
