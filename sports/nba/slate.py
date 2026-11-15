"""Tonight's NBA board from the baseline: every active player's projection and the chance of each FanDuel-style 'X+' rung.

Who is active is an input. Until the injury feed is wired, the default is 'everyone who played in the team's last game', with `out`
and `back` lists to correct it by hand - so a board built this way is a pipeline check, not a set of picks.
"""
import numpy as np
import pandas as pd
from . import data as ND, model as NM
from ..core import legboard as LB, dist as D

MARKETS = {"pts": "Points", "reb": "Rebounds", "ast": "Assists", "fg3": "Threes Made"}
RUNGS = {"pts": [10, 15, 20, 25, 30, 35, 40], "reb": [4, 6, 8, 10, 12, 14], "ast": [2, 4, 6, 8, 10, 12], "fg3": [1, 2, 3, 4, 5, 6]}


def games_on(schedule, day):
    """Games tipping off on a US calendar day (Central time)."""
    s = schedule.copy()
    s["tip"] = pd.to_datetime(s["date"], utc=True).dt.tz_convert("America/Chicago")
    x = s[s["tip"].dt.strftime("%Y-%m-%d") == str(day)]
    return x[["game_id", "tip", "home_id", "home_abbreviation", "away_id", "away_abbreviation", "home_display_name", "away_display_name"]]


def build(d, schedule, day, out=(), back=(), params=None, min_proj_minutes=12.0):
    """Returns (board rows in the leg-board columns, the projection table)."""
    out_n = {LB.norm_name(x) for x in out}
    back_n = {LB.norm_name(x) for x in back}
    season = int(d["season"].max())
    cur = d[d["season"] == season]
    games = games_on(schedule, day)
    new = []
    for _, g in games.iterrows():
        for tid, oid, home in ((g["home_id"], g["away_id"], True), (g["away_id"], g["home_id"], False)):
            t = cur[(cur["team_id"] == tid) & (cur["date"] < pd.Timestamp(day))]
            if t.empty:
                continue
            last_game = t["game_id"].iloc[-1]
            recent = t[t["game_id"].isin(t["game_id"].drop_duplicates().tail(10))]
            act = t[(t["game_id"] == last_game) & t["played"]]
            extra = recent[recent["played"] & recent["player"].map(LB.norm_name).isin(back_n)].drop_duplicates("athlete_id", keep="last")
            ros = pd.concat([act, extra]).drop_duplicates("athlete_id", keep="last")
            ros = ros[~ros["player"].map(LB.norm_name).isin(out_n)]
            opp_abbr = g["away_abbreviation"] if home else g["home_abbreviation"]
            for _, r in ros.iterrows():
                row = {c: 0.0 for c in ["min", "fga", "fta"] + list(ND.STATS)}
                row.update({"season": season, "date": pd.Timestamp(day), "game_id": int(g["game_id"]), "tg": f"{int(g['game_id'])}|{int(tid)}", "athlete_id": r["athlete_id"],
                            "player": r["player"], "team_id": tid, "team": r["team"], "opp_id": oid, "opp": opp_abbr, "home": home, "grp": r["grp"], "starter": np.nan,
                            "played": True, "reason": "", "team_score": np.nan, "opponent_team_score": np.nan})
                new.append(row)
    if not new:
        return [], pd.DataFrame()
    full = pd.concat([d[d["date"] < pd.Timestamp(day)], pd.DataFrame(new)], ignore_index=True)
    p = NM.project(full, params)
    p = p[(p["date"] == pd.Timestamp(day)) & p["has_base"] & (p["proj_min"] >= min_proj_minutes)].copy()
    tips = {int(g["game_id"]): g for _, g in games.iterrows()}
    rows = []
    for _, r in p.iterrows():
        g = tips[int(r["game_id"])]
        game = f"{g['away_display_name']} @ {g['home_display_name']}"
        kick = g["tip"].strftime("%a %m/%d %-I:%M %p")
        warn = []
        if r["n"] < 5:
            warn.append("Fewer than 5 games this season")
        if r["proj_min"] > r["base_min"] * 1.10:
            warn.append(f"Minutes raised {r['proj_min'] - r['base_min']:+.1f}: team is short-handed")
        if r["proj_min"] < r["base_min"] * 0.92:
            warn.append(f"Minutes trimmed {r['proj_min'] - r['base_min']:+.1f}: rotation is fuller than his recent games")
        for s, name in MARKETS.items():
            for L in RUNGS[s]:
                pr = float(D.p_at_least(L, r["proj_" + s], "qp", phi=NM.PHI[s]))
                if 0.05 <= pr <= 0.95:
                    rows.append(LB.row(r["player"], name, L, r["team"], r["opp"], r["proj_" + s], None if pd.isna(r["avg_" + s]) else r["avg_" + s], int(r["n"]), pr, game, kick,
                                       warnings="; ".join(warn)))
    return rows, p
