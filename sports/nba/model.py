"""NBA baseline, built the way the NFL sheet builds its projections:

  1. baseline     minutes (season + last-5, pulled toward last season early) x per-minute rates (season, pulled toward last season)
  2. team budget  the active players' minutes are fitted to the 240 a team has to give - this is the fill-in / vacated-opportunity step
  3. matchup      what this opponent allows to guards / forwards / centers vs the league (the offense-vs-defense grid)
  4. team total   the active players' expected points (rebounds, assists, threes) are moved toward what the team should total
  5. hit chance   projection -> chance of each 'X+' line (negative binomial, spread fitted on past errors)

Every number for a game uses only games before it. Weights are picked on one season and checked on the next (promote only if better).
"""
import numpy as np
import pandas as pd
from ..core import baseline as B
from ..core import budget as BG
from ..core import dist as D

STATS = ["pts", "reb", "ast", "fg3", "stl", "blk", "tov"]
TEAM_MIN = 241.0          # 240 plus the average overtime
PARAMS = {                # picked on 2025-26 by `backtest.py --tune` (log in backtests/nba.json), then checked on 2026-27
    "w_recent_min": 0.75, # weight on the last-5 minutes vs the season average (NFL: "Last-4 weight")
    "k_min": 0.0,         # games of last season's minutes mixed in early (0: last season's role did not help once he has played)
    "k_rate": 150.0,      # minutes of last season's per-minute rate mixed in early
    "w_recent_rate": 0.15,# weight on the last-10 per-minute rate
    "c_budget": 0.75,     # share of the team-minutes gap handed out (NFL: missing-starter transfer)
    "cap_min": 38.0,
    "k_def": 1000.0,      # group-minutes of league average mixed into each defense's allowed rate
    "w_match": {"pts": 0.5, "reb": 0.5, "ast": 0.5, "fg3": 0.5, "stl": 0.5, "blk": 0.75, "tov": 0.75},
    "u_total": {"pts": 0.5, "reb": 0.25, "ast": 0.75, "fg3": 0.25, "stl": 0.0, "blk": 0.5, "tov": 0.5},
    "k_team": 8.0,        # games of league average mixed into a team's own totals
    "debut_min": 10.0,    # minutes assumed for a player with no history at all (he still uses up team minutes)
}
PHI = {"pts": 3.57, "reb": 1.36, "ast": 1.24, "fg3": 1.21}   # spread per stat (variance = phi x projection), fitted on 2025-26 errors


def _prev_season(pl):
    """Last season's per-game minutes and per-minute rates for every player, keyed to the season they inform."""
    g = pl.groupby(["athlete_id", "season"], sort=False)
    t = g[["min"] + STATS].sum()
    t["gp"] = g.size()
    t = t.reset_index()
    out = pd.DataFrame({"athlete_id": t["athlete_id"], "season": t["season"] + 1, "prev_gp": t["gp"], "prev_min": t["min"] / t["gp"],
                        "prev_minutes": t["min"]})
    for s in STATS:
        out["prev_rate_" + s] = t[s] / t["min"].where(t["min"] > 0)
    return out


def _group_rates(pl):
    """League per-minute rate by position group for the previous season (the prior for a player with no NBA history)."""
    g = pl.groupby(["season", "grp"], sort=False)[["min"] + STATS].sum().reset_index()
    out = pd.DataFrame({"season": g["season"] + 1, "grp": g["grp"]})
    for s in STATS:
        out["lg_prev_rate_" + s] = g[s] / g["min"]
    return out


def _defense(pl, k_def):
    """What each defense has allowed per minute to each position group before this game, vs the league before this date."""
    a = pl.groupby(["season", "date", "game_id", "opp_id", "grp"], sort=False)[["min"] + STATS].sum().reset_index()
    a = a.sort_values(["date", "game_id"], kind="stable").reset_index(drop=True)
    key = ["season", "opp_id", "grp"]
    cm = B.prior_sum(a, key, "min")
    lg = a.groupby(["season", "grp", "date"], sort=False)[["min"] + STATS].sum().reset_index().sort_values("date", kind="stable")
    lgm = lg.groupby(["season", "grp"], sort=False)["min"].cumsum() - lg["min"]
    for s in STATS:
        lg["lg_" + s] = (lg.groupby(["season", "grp"], sort=False)[s].cumsum() - lg[s]) / lgm.where(lgm > 0)
    a = a.merge(lg[["season", "grp", "date"] + ["lg_" + s for s in STATS]], on=["season", "grp", "date"], how="left")
    out = a[["game_id", "opp_id", "grp"]].copy()
    for s in STATS:
        cs = B.prior_sum(a, key, s)
        lgr = a["lg_" + s]
        out["def_" + s] = ((cs + k_def * lgr) / (cm + k_def) / lgr.where(lgr > 0)).fillna(1.0)
    return out


def _team_totals(pl, k_team):
    """What each team should total tonight: league average x its own offense factor x the opponent's allowed factor (the grid)."""
    t = pl.groupby(["season", "date", "game_id", "tg", "team_id", "opp_id"], sort=False)[STATS].sum().reset_index()
    t = t.sort_values(["date", "game_id"], kind="stable").reset_index(drop=True)
    n_off = B.prior_count(t, ["season", "team_id"])
    n_def = B.prior_count(t, ["season", "opp_id"])
    lg = t.groupby(["season", "date"], sort=False)[STATS].agg(["sum", "size"])
    out = t[["tg"]].copy()
    for s in STATS:
        l = lg[s].reset_index().sort_values("date", kind="stable")
        cs = l.groupby("season", sort=False)["sum"].cumsum() - l["sum"]
        cn = l.groupby("season", sort=False)["size"].cumsum() - l["size"]
        l["lg"] = cs / cn.where(cn > 0)
        lgv = t[["season", "date"]].merge(l[["season", "date", "lg"]], on=["season", "date"], how="left")["lg"]
        off = (B.prior_sum(t, ["season", "team_id"], s) + k_team * lgv) / (n_off + k_team)
        dfn = (B.prior_sum(t, ["season", "opp_id"], s) + k_team * lgv) / (n_def + k_team)
        out["team_" + s] = (off * dfn / lgv.where(lgv > 0))
    return out


def project(d, params=None):
    """d = nba.data.load(...). Returns one row per player-game that was played, with the projection and each step's number."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    pl = d[d["played"]].copy().reset_index(drop=True)
    ps = ["athlete_id", "season"]
    pl["n"] = B.prior_count(pl, ps)
    cmin = B.prior_sum(pl, ps, "min")
    pl["season_min"] = cmin / pl["n"].where(pl["n"] > 0)
    pl["last5_min"] = B.prior_roll_mean(pl, ps, "min", 5)
    pl = pl.merge(_prev_season(pl), on=ps, how="left").merge(_group_rates(pl), on=["season", "grp"], how="left")

    # 1. baseline minutes and per-minute rates
    cur = B.blend(pl["season_min"], pl["last5_min"], P["w_recent_min"])
    base = (cur.fillna(0.0) * pl["n"] + P["k_min"] * pl["prev_min"]) / (pl["n"] + P["k_min"])
    pl["base_min"] = base.where(pl["prev_min"].notna(), cur)
    last10_min = B.prior_roll_sum(pl, ps, "min", 10)
    for s in STATS:
        prior = pl["prev_rate_" + s].where(pl["prev_minutes"].fillna(0) >= 200, pl["lg_prev_rate_" + s])
        rate = (B.prior_sum(pl, ps, s) + P["k_rate"] * prior) / (cmin + P["k_rate"])
        rate = rate.where(prior.notna(), B.prior_sum(pl, ps, s) / cmin.where(cmin > 0))
        if P["w_recent_rate"] > 0:
            recent = B.prior_roll_sum(pl, ps, s, 10) / last10_min.where(last10_min > 0)
            rate = B.blend(rate, recent, P["w_recent_rate"])
        pl["rate_" + s] = rate
        pl["avg_" + s] = (B.prior_sum(pl, ps, s) / pl["n"].where(pl["n"] > 0))       # benchmark: plain season average
        pl["l10_" + s] = B.prior_roll_mean(pl, ps, s, 10)                             # benchmark: last-10 average
    pl["has_base"] = pl["base_min"].notna()

    # 2. team minutes budget across the players who are active tonight
    filled = pl["base_min"].fillna(P["debut_min"])
    pl["proj_min"] = BG.rebalance(filled, pl["tg"], TEAM_MIN, c=P["c_budget"], cap=P["cap_min"]).where(pl["has_base"])
    pl["team_base_min"] = filled.groupby(pl["tg"], sort=False).transform("sum")

    # 3. matchup, 4. team total
    pl = pl.merge(_defense(pl, P["k_def"]), on=["game_id", "opp_id", "grp"], how="left")
    pl = pl.merge(_team_totals(pl, P["k_team"]), on="tg", how="left")
    for s in STATS:
        f = np.power(pl["def_" + s].clip(0.7, 1.4).fillna(1.0), P["w_match"].get(s, 0.0))
        raw = pl["proj_min"] * pl["rate_" + s] * f
        pl["pre_" + s] = raw
        if P["u_total"].get(s, 0.0) > 0:
            exp = raw.fillna(filled * pl["rate_" + s].fillna(0.0))
            raw = raw * BG.scale_to_total(exp, pl["tg"], pl["team_" + s], u=P["u_total"][s])
        pl["proj_" + s] = raw
        pl["base_" + s] = pl["base_min"] * pl["rate_" + s]                           # step 1 only (no budget, matchup, total)
    pl["proj_pra"] = pl["proj_pts"] + pl["proj_reb"] + pl["proj_ast"]
    pl["pra"] = pl["pts"] + pl["reb"] + pl["ast"]
    return pl


LADDERS = {"pts": [10, 15, 20, 25, 30], "reb": [4, 6, 8, 10, 12], "ast": [2, 4, 6, 8, 10], "fg3": [1, 2, 3, 4, 5]}


def hit_chances(proj, stat, phi=None, lines=None):
    """Chance of each 'X+' line for one stat (columns p_<line>)."""
    lines = lines or LADDERS[stat]
    phi = phi or PHI[stat]
    return pd.DataFrame({f"p_{L}": D.p_at_least(L, proj.values, "qp", phi=phi) for L in lines}, index=proj.index)


def defense_grid(d, season=None):
    """Today's defense-vs-position grid (the NBA version of 'AUTO - Defense vs Position Ranks'): what each team has allowed per minute
    to guards / forwards / centers this season vs the league, and its rank (1 = allows the most)."""
    pl = d[d["played"]]
    season = int(season or pl["season"].max())
    x = pl[pl["season"] == season]
    a = x.groupby(["opp", "grp"])[["min"] + STATS].sum()
    lg = x.groupby("grp")[["min"] + STATS].sum()
    rows = []
    for (team, grp), r in a.iterrows():
        row = {"defense": team, "vs": {"G": "Guards", "F": "Forwards", "C": "Centers"}[grp]}
        for s in ("pts", "reb", "ast", "fg3"):
            row[s + "_vs_league"] = (r[s] / r["min"]) / (lg.loc[grp, s] / lg.loc[grp, "min"])
        rows.append(row)
    t = pd.DataFrame(rows)
    for s in ("pts", "reb", "ast", "fg3"):
        t[s + "_rank"] = t.groupby("vs")[s + "_vs_league"].rank(ascending=False, method="min").astype(int)
    return t.sort_values(["vs", "pts_rank"]).reset_index(drop=True)
