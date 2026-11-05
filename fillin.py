"""Replacement starters with no game log (the Hurts -> McKee case).

The projection tabs only know players with a 2026 game log, so when a starter is ruled out and his replacement has never
played this season, the sheet's QB succession picks the next QB on file (Andy Dalton for PHI in Week 6) and carries the
team's fill-in projection on HIS row - while FanDuel prices the real starter, who the site then cannot see.

Convention (sheet side, 'AUTO - Weekly Availability'): one row for the real starter with
    B player (FanDuel spelling)  C team  D pos  E CLEARED  G Forced Role = STARTER  H Replacement For = <ruled-out starter>
Site side (this module): that player takes over the stand-in's row - same projection, renamed, tagged FILL-IN STARTER - on the
boards, Fantasy and DFS pages, and the builder prices his FanDuel lines from that projection with a normal spread
(pass yards SD = 87, the 2026 QB game-to-game SD; anytime TD from the fill-in TD rate). Every such leg carries a risk flag,
so it never enters a best parlay or quick build. Nothing is invented: the numbers are the sheet's own fill-in projection.
"""
import json, os, math

PASS_SD = 87.0     # SD of a QB's single-game passing yards (2026 game log, 171 QB games)
RUSH_SD = 14.0

def _num(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return None

def load(IN, week):
    """[{player, team, pos, for, standin, proj:{pass, ptd, int, rush, rtd}}] for every Forced Role = STARTER row whose player has no projection row."""
    out = []
    try: av = json.load(open(os.path.join(IN, "avail.json")))["values"]
    except Exception: return out
    tabs = {"QB": "proj_qb.json", "RB": "proj_rb.json", "WR": "proj_wr.json", "TE": "proj_te.json"}
    for r in av[1:]:
        r = r + [""] * (13 - len(r))
        if str(r[0]) != str(week) or r[6].strip().upper() != "STARTER" or not r[1]: continue
        pos = r[3].strip().upper(); team = r[2].strip()
        if pos != "QB": continue   # only QBs have a fill-in projection on the sheet today
        try: v = json.load(open(os.path.join(IN, tabs[pos])))["values"]
        except Exception: continue
        h = v[0]; idx = {c: i for i, c in enumerate(h)}
        rows = [x for x in v[1:] if x and len(x) > 1 and x[1] == team]
        if any(x[0] == r[1] for x in rows): continue   # he has his own row: nothing to do
        # the stand-in: the team row the sheet currently treats as the starter (AUTO QB SUCCESSION / fill-in), not the ruled-out man
        cand = [x for x in rows if x[0] != r[7].strip() and len(x) > idx.get("Fill-in Pass Yds", 999)]
        if not cand: continue
        def g(x, c): return _num(x[idx[c]]) if c in idx and idx[c] < len(x) else None
        cand.sort(key=lambda x: -(g(x, "Fill-in Pass Yds") or 0))
        s = cand[0]
        out.append({"player": r[1].strip(), "team": team, "pos": pos, "for": r[7].strip(), "standin": s[0],
                    "proj": {"pass": g(s, "Fill-in Pass Yds") or g(s, "Proj Pass Yds") or 0, "ptd": g(s, "Fill-in Pass TD") or g(s, "Proj Pass TD") or 0,
                             "int": g(s, "Fill-in INT") or 0, "rush": g(s, "Fill-in Rush Yds") or g(s, "Proj Rush Yds") or 0, "rtd": g(s, "Fill-in Rush TD") or g(s, "Proj Rush TD") or 0},
                    "note": f"Replacement starter for {r[7].strip()}: no 2026 game log, so this is the sheet's fill-in projection (team environment, carried on {s[0]}'s row) - not his own history."})
    return out

def by_standin(fills): return {f["standin"]: f for f in fills}

def _phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))

def prob(f, market, line):
    """Model chance for one of his FanDuel lines, or None for markets the fill-in projection cannot price."""
    p = f["proj"]
    if market == "Passing Yards" and p["pass"]: return min(0.99, max(0.01, 1 - _phi((line - 0.5 - p["pass"]) / PASS_SD)))
    if market == "Rushing Yards" and p["rush"] is not None: return min(0.99, max(0.01, 1 - _phi((line - 0.5 - p["rush"]) / RUSH_SD)))
    if market == "Anytime TD": return min(0.99, max(0.01, 1 - math.exp(-(p["rtd"] or 0))))
    return None
