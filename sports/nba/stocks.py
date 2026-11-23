"""The NBA Stock Market's numbers: who is rising and who is falling in fantasy points, and the minutes behind it.

Owner 11/22: "I want each sport to basically look exactly like everything we've built for NFL." The NFL Stock Market compares a player's
last few games with the ones before; this is the same question for the NBA, asked of games instead of weeks.

Written by the feeds-sports job beside the board (nba/stocks.json); the page is drawn from the file in plain Python (build_nba_stocks.py),
so the hourly site build needs no pandas.

  fantasy points   FanDuel's NBA scoring: points 1, rebounds 1.2, assists 1.5, steals 3, blocks 3, turnovers -1
  recent           his last 5 games played
  before           the up-to-10 games played before those (at least 3, or he is not listed)
  move             recent average minus the average before
  rising           up 6.0 or more AND averaging 22+ over the recent games (a real fantasy player now, not a bench player's good week)
  falling          down 6.0 or more AND averaged 22+ before (he was one)
                   (6.0: five games against ten is a noisy comparison - a starter's fantasy points swing about 9 or 10 from game to game - and at 4.0 a
                   quarter of the league was "rising" on 11/22; at 6.0 it was 48 of 279, two thirds of them with minutes up by 2 or more)
A player is listed with 8+ games played this season and a rotation role (15+ minutes a game on the season, or 18+ over the recent games).
"""
import datetime as dt
import pandas as pd
from . import data as ND

FORMAT = 1
SCORING = {"pts": 1.0, "reb": 1.2, "ast": 1.5, "stl": 3.0, "blk": 3.0, "tov": -1.0}
SCORING_TEXT = "FanDuel scoring: points 1, rebounds 1.2, assists 1.5, steals 3, blocks 3, turnovers -1"
RECENT, PRIOR, MIN_PRIOR, MIN_GAMES = 5, 10, 3, 8
MOVE, FLOOR = 6.0, 22.0
KEEP = 15                      # team games of each player kept in the file
COLS = ["d", "opp", "min", "pts", "reb", "ast", "fg3", "stl", "blk", "tov", "fp"]


def fantasy(frame):
    return sum(frame[k] * w for k, w in SCORING.items())


def build(d, now=None):
    """d: the frame of data.load() - one row per player per game. Returns the file as a dict."""
    now = now or dt.datetime.now(dt.timezone.utc)
    cur = d[d["season"] == d["season"].max()].copy()
    cur["fp"] = fantasy(cur)
    players = []
    for pid, g in cur.groupby("athlete_id", sort=False):
        pl = g[g["played"]]
        if len(pl) < MIN_GAMES:
            continue
        rec, pri = pl.iloc[-RECENT:], pl.iloc[-(RECENT + PRIOR):-RECENT]
        if len(pri) < MIN_PRIOR:
            continue
        smin, rmin, pmin = float(pl["min"].mean()), float(rec["min"].mean()), float(pri["min"].mean())
        if smin < 15 and rmin < 18:
            continue
        r, p = float(rec["fp"].mean()), float(pri["fp"].mean())
        move = r - p
        last = g.iloc[-1]                                   # his latest listing, played or not: the team he is with now
        rows = []
        for _, x in g.iloc[-KEEP:].iterrows():
            day = f"{x['date'].month}/{x['date'].day}"
            opp = ("" if x["home"] else "@") + str(x["opp"])
            if x["played"]:
                rows.append([day, opp, int(round(x["min"])), int(x["pts"]), int(x["reb"]), int(x["ast"]), int(x["fg3"]), int(x["stl"]), int(x["blk"]), int(x["tov"]), round(float(x["fp"]), 1)])
            else:
                why = str(x["reason"]) if isinstance(x["reason"], str) and x["reason"].strip() else "did not play"
                rows.append([day, opp, None, why.strip().capitalize()[:40]])
        sat = int((~g.iloc[-RECENT:]["played"]).sum())      # of his team's last five games he was listed for, how many he sat out
        players.append({"id": str(int(pid)), "name": str(last["player"]), "team": str(last["team"]), "grp": str(last["grp"]), "gp": int(len(pl)),
                        "fp": round(float(pl["fp"].mean()), 1), "min": round(smin, 1), "r": round(r, 1), "p": round(p, 1), "d": round(move, 1),
                        "rmin": round(rmin, 1), "pmin": round(pmin, 1), "nr": int(len(rec)), "np": int(len(pri)), "sat": sat,
                        "dir": "up" if (move >= MOVE and r >= FLOOR) else ("dn" if (move <= -MOVE and p >= FLOOR) else ""),
                        "avg": {k: round(float(pl[k].mean()), 1) for k in ("pts", "reb", "ast", "fg3", "stl", "blk", "tov")},
                        "ravg": {k: round(float(rec[k].mean()), 1) for k in ("pts", "reb", "ast", "fg3", "stl", "blk", "tov")},
                        "g": rows})
    players.sort(key=lambda x: (-x["r"], x["name"]))
    through = cur["date"].max()
    return {"sport": "nba", "format": FORMAT, "built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "season": int(cur["season"].max()), "data_through": through.strftime("%Y-%m-%d"),
            "scoring": SCORING_TEXT, "rule": {"recent": RECENT, "before": PRIOR, "move": MOVE, "floor": FLOOR, "games": MIN_GAMES}, "cols": COLS, "players": players}


def main():
    import argparse, json, os
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--data")
    a = ap.parse_args()
    d = ND.load([2027], a.data or ND.data_dir())
    s = build(d)
    os.makedirs(os.path.join(a.out, "nba"), exist_ok=True)
    json.dump(s, open(os.path.join(a.out, "nba", "stocks.json"), "w"), separators=(",", ":"))
    print(f"nba stocks: {len(s['players'])} players through {s['data_through']}, {sum(1 for p in s['players'] if p['dir'] == 'up')} rising, {sum(1 for p in s['players'] if p['dir'] == 'dn')} falling")


if __name__ == "__main__":
    main()
