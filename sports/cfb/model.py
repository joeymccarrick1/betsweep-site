"""College football baseline.

Game lines first (the only college markets that can be bet in Tennessee):
  the schedule-adjusted grid (core.ratings) on points -> each side's expected points -> margin and total -> compared with the book.
  Uneven schedules are the whole problem in college football, so the plain offense-average / defense-allowed grid is not enough here;
  the adjusted grid is the same idea with the opponents accounted for. Teams outside FBS are pooled into one 'lower division' team.

Player layer (for states that allow college props, and for content): season + last-3 baseline x the opponent's adjusted
pass / rush defense factor, as in the NFL build.
"""
import numpy as np
import pandas as pd
from scipy import stats
from ..core import ratings as R, baseline as B

LOWER = -1
PARAMS = {                 # picked on 2025 by `backtest.py --tune` (log in backtests/cfb.json), then checked on 2026
    "half_life": 150.0,    # days for a game to count half as much (the shortest tried: recent form mattered most)
    "k_games": 1.0,        # games of prior mixed into every team rating
    "cap": 80.0,           # points above this are trimmed before rating
    "sd_margin": 15.95,    # spread of final margins around the expected margin (for win / cover chances)
    "w_recent": 0.15,      # player layer: weight on the last-3 average vs the season average
    "w_match": 0.25,       # player layer: how much of the opponent's defense factor is applied
}


def fbs_sets(g, min_games=6):
    """Teams with a full schedule in a season = FBS; everyone else is pooled as 'lower division'."""
    out = {}
    for s, x in g.groupby("season"):
        c = pd.concat([x["home_id"], x["away_id"]]).value_counts()
        out[int(s)] = set(c[c >= min_games].index.astype(int))
    return out


def team_rows(g, fbs):
    """Two rows per game: points scored by each side."""
    rows = []
    for side, other, s in (("home", "away", 1), ("away", "home", -1)):
        rows.append(pd.DataFrame({"season": g["season"].values, "date": g["date"].values, "game_id": g["game_id"].values,
                                  "team": g[side + "_id"].astype(int).values, "opp": g[other + "_id"].astype(int).values,
                                  "home": np.where(g["neutral"].values, 0, s), "pts": g[side + "_score"].astype(float).values}))
    t = pd.concat(rows, ignore_index=True)
    for c in ("team", "opp"):
        t[c] = [v if v in fbs.get(int(s), ()) else LOWER for v, s in zip(t[c], t["season"])]
    return t.sort_values(["date", "game_id", "home"], kind="stable").reset_index(drop=True)


def walk_forward(g, seasons, params=None):
    """Rate every game in `seasons` from games on earlier days only. One row per game: expected points for both sides."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    fbs = fbs_sets(g)
    t = team_rows(g, fbs)
    codes = sorted(set(t["team"]) | set(t["opp"]) | {LOWER})
    idx = {c: i for i, c in enumerate(codes)}
    ti, oi = t["team"].map(idx).values, t["opp"].map(idx).values
    y = t["pts"].clip(upper=P["cap"]).values
    day = t["date"].dt.normalize()
    po, pd_ = np.ones(len(idx)), np.ones(len(idx))
    out = []
    todo = g[g["season"].isin(seasons)].copy()
    todo["day"] = todo["date"].dt.normalize()
    for dday, grp in todo.groupby("day", sort=True):
        past = (day < dday).values
        w = R.decay_weights((dday - day[past]).dt.days.values, P["half_life"])
        gr = R.fit_grid(ti[past], oi[past], y[past], len(idx), home=t["home"].values[past], w=w, k_games=P["k_games"], prior_o=po, prior_d=pd_)
        for _, r in grp.iterrows():
            s = int(r["season"])
            h = idx[int(r["home_id"]) if int(r["home_id"]) in fbs[s] else LOWER]
            a = idx[int(r["away_id"]) if int(r["away_id"]) in fbs[s] else LOWER]
            hs = 0 if r["neutral"] else 1
            out.append({"game_id": r["game_id"], "season": s, "week": r["week"], "date": r["date"], "home_team": r["home_team"], "away_team": r["away_team"],
                        "fbs_both": (h != idx[LOWER]) and (a != idx[LOWER]), "exp_home": R.expect(gr, h, a, hs), "exp_away": R.expect(gr, a, h, -hs),
                        "home_score": r["home_score"], "away_score": r["away_score"]})
    o = pd.DataFrame(out)
    o["model_margin"] = o["exp_home"] - o["exp_away"]
    o["model_total"] = o["exp_home"] + o["exp_away"]
    o["margin"] = o["home_score"] - o["away_score"]
    o["total"] = o["home_score"] + o["away_score"]
    o["p_home_win"] = stats.norm.sf(0, loc=o["model_margin"], scale=P["sd_margin"])
    return o


def ratings_table(g, params=None, top=None):
    """Today's grid: offense and defense factor for every FBS team this season."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    fbs = fbs_sets(g)
    t = team_rows(g, fbs)
    codes = sorted(set(t["team"]) | set(t["opp"]) | {LOWER})
    idx = {c: i for i, c in enumerate(codes)}
    asof = t["date"].max() + pd.Timedelta(days=1)
    w = R.decay_weights((asof - t["date"]).dt.days.values, P["half_life"])
    gr = R.fit_grid(t["team"].map(idx).values, t["opp"].map(idx).values, t["pts"].clip(upper=P["cap"]).values, len(idx), home=t["home"].values, w=w, k_games=P["k_games"])
    season = int(g["season"].max())
    names = pd.concat([g.loc[g["season"] == season, ["home_id", "home_team"]].rename(columns={"home_id": "id", "home_team": "name"}),
                       g.loc[g["season"] == season, ["away_id", "away_team"]].rename(columns={"away_id": "id", "away_team": "name"})]).drop_duplicates("id").set_index("id")["name"]
    cur = sorted(fbs[season])
    tab = pd.DataFrame({"team": [names.get(c, str(c)) for c in cur], "offense": [gr["O"][idx[c]] for c in cur], "defense_allowed": [gr["D"][idx[c]] for c in cur]})
    tab["points_for_vs_avg"] = gr["L"] * tab["offense"]
    tab["points_against_vs_avg"] = gr["L"] * tab["defense_allowed"]
    tab["net_vs_avg"] = tab["points_for_vs_avg"] - tab["points_against_vs_avg"]
    tab = tab.sort_values("net_vs_avg", ascending=False).reset_index(drop=True)
    return (tab.head(top) if top else tab), gr


# ---- player layer ----
PLAYER_STATS = {"pass_yds": ("pass_yds", 120.0), "rush_yds": ("rush_yds", 35.0), "rec_yds": ("pass_yds", 25.0), "rec": ("pass_yds", 2.0)}   # stat -> (defense grid it uses, season-average floor to be graded)


def defense_factors(ts, g, params=None):
    """Opponent-adjusted pass-yards and rush-yards allowed factor for every defense before each game (season to date only)."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    t = ts.merge(g[["game_id", "date"]], on="game_id", how="inner").sort_values(["date", "game_id"], kind="stable").reset_index(drop=True)
    out = []
    for season, x in t.groupby("season", sort=True):
        cnt = pd.concat([x["pos_team"], x["def_pos_team"]]).value_counts() / 2.0
        keep = set(cnt[cnt >= 5].index)
        team = x["pos_team"].where(x["pos_team"].isin(keep), "LOWER")
        opp = x["def_pos_team"].where(x["def_pos_team"].isin(keep), "LOWER")
        codes = sorted(set(team) | set(opp))
        idx = {c: i for i, c in enumerate(codes)}
        ti, oi, day = team.map(idx).values, opp.map(idx).values, x["date"].dt.normalize()
        for dday in sorted(day.unique()):
            past = (day < dday).values
            now = (day == dday).values
            row = {"game_id": x["game_id"].values[now], "pos_team": x["pos_team"].values[now]}
            for stat in ("pass_yds", "rush_yds"):
                if past.sum() >= 60:
                    gr = R.fit_grid(ti[past], oi[past], x[stat].clip(lower=0).values[past], len(idx), k_games=3.0)
                    row["def_" + stat] = gr["D"][oi[now]]
                else:
                    row["def_" + stat] = np.ones(now.sum())
            out.append(pd.DataFrame(row))
    return pd.concat(out, ignore_index=True)


def player_projections(pg, ts, g, params=None):
    """One row per player-game with a baseline from his earlier games this season and the opponent factor."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    p = pg.merge(g[["game_id", "date"]], on="game_id", how="inner").sort_values(["date", "game_id", "pos_team", "player_id"], kind="stable").reset_index(drop=True)
    p = p.merge(defense_factors(ts, g, P), on=["game_id", "pos_team"], how="left")
    ps = ["player_id", "season"]
    p["n"] = B.prior_count(p, ps)
    for stat, (grid, _) in PLAYER_STATS.items():
        avg = B.prior_mean(p, ps, stat)
        l3 = B.prior_roll_mean(p, ps, stat, 3)
        base = B.blend(avg, l3, P["w_recent"])
        p["avg_" + stat] = avg
        p["base_" + stat] = base
        p["proj_" + stat] = base * np.power(p["def_" + grid].clip(0.6, 1.6).fillna(1.0), P["w_match"])
    return p
