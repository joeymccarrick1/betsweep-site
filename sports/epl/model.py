"""Premier League baseline, same steps as the NFL build.

Team level (this is the scripts / team-points layer):
  the grid (core.ratings) on a blend of expected goals and real goals -> each side's goal rate for the match ->
  every score's chance -> home / draw / away, over-under, both teams to score.
  For the NFL the book's spread and total beat our own formula, so once FanDuel prices are stored the same test decides whether
  these goal rates or the market's lead; either way the player layer below takes the goal rates as an input.

Player level (props):
  minutes when he starts x his per-90 rates (season, pulled toward last season) x the matchup (what this opponent allows, home/away)
  -> expected goals -> chance to score; shots and shots on target the same way.
"""
import numpy as np
import pandas as pd
from ..core import ratings as R, dist as D, baseline as B

PROMOTED_2025 = [40, 13, 20]      # promoted into 2024-25 (Ipswich, Leicester, Southampton): the first season on disk has no season before it
PARAMS = {                        # picked on 2025-26 by `backtest.py --tune` (log in backtests/epl.json), then checked on 2026-27
    "xg_blend": 0.5,              # share of expected goals (vs real goals) in what the grid is fitted to
    "half_life": 240.0,           # days for a match to count half as much
    "k_games": 2.0,               # games of prior mixed into every team rating
    "rho": -0.12,                 # low-score correction (0-0, 1-0, 0-1, 1-1); the edge of the range tried, re-test with more seasons
    "k_rate_min": 1200.0,         # minutes of last season's per-90 rate mixed into a player's rate
    "w_env": 1.0,                 # how much of the opponent/home factor reaches the player number
    "start_min_k": 1.0,           # starts of prior mixed into 'minutes when he starts'
}


def team_index(m):
    codes = sorted(set(m["home_team"].dropna().astype(int)) | set(m["away_team"].dropna().astype(int)))
    return {c: i for i, c in enumerate(codes)}


def promoted_sets(m):
    """Clubs in each season that were not in the previous one."""
    out = {}
    seasons = sorted(m["season"].unique())
    for s in seasons:
        cur = set(m.loc[m["season"] == s, "home_team"].astype(int))
        prev = set(m.loc[m["season"] == s - 1, "home_team"].astype(int))
        out[s] = set(PROMOTED_2025) if not prev else cur - prev
    return out


def promoted_prior(tg, idx, promoted, before_season, y):
    """Average offense / defense factor of promoted clubs in their first season, from seasons before `before_season` only."""
    os_, ds_ = [], []
    for s, clubs in promoted.items():
        if s >= before_season:
            continue
        x = tg[tg["season"] == s]
        if x.empty:
            continue
        g = R.fit_grid(x["team"].map(idx), x["opp"].map(idx), y[x.index], len(idx), home=x["home"], k_games=2.0)
        os_ += [g["O"][idx[c]] for c in clubs if c in idx]
        ds_ += [g["D"][idx[c]] for c in clubs if c in idx]
    return (float(np.mean(os_)), float(np.mean(ds_))) if os_ else (0.85, 1.15)


def walk_forward(m, tg, seasons, params=None, stat="goals"):
    """Rate every match in `seasons` using only matches from earlier days. Returns one row per match with both sides' expected number."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    idx = team_index(m)
    prom = promoted_sets(m)
    y = (P["xg_blend"] * tg["xg"] + (1 - P["xg_blend"]) * tg["goals"]) if stat == "goals" else tg[stat].astype(float)
    day = tg["date"].dt.normalize()
    t_i, o_i = tg["team"].map(idx).values, tg["opp"].map(idx).values
    rows = []
    todo = m[m["season"].isin(seasons)].copy()
    todo["day"] = todo["date"].dt.normalize()
    for season in seasons:
        po, pd_ = np.ones(len(idx)), np.ones(len(idx))
        o0, d0 = promoted_prior(tg, idx, prom, season, y)
        for c in prom.get(season, ()):
            if c in idx:
                po[idx[c]], pd_[idx[c]] = o0, d0
        for dday, grp in todo[todo["season"] == season].groupby("day", sort=True):
            past = (day < dday).values
            if past.sum() < 40:
                continue
            w = R.decay_weights((dday - day[past]).dt.days.values, P["half_life"])
            g = R.fit_grid(t_i[past], o_i[past], y.values[past], len(idx), home=tg["home"].values[past], w=w, k_games=P["k_games"], prior_o=po, prior_d=pd_)
            for _, r in grp.iterrows():
                h, a = idx[int(r["home_team"])], idx[int(r["away_team"])]
                rows.append({"match_id": r["match_id"], "season": season, "date": r["date"], "home_team": int(r["home_team"]), "away_team": int(r["away_team"]),
                             "lam_home": R.expect(g, h, a, 1), "lam_away": R.expect(g, a, h, -1), "L": g["L"], "H": g["H"],
                             "o_home": g["O"][h], "d_home": g["D"][h], "o_away": g["O"][a], "d_away": g["D"][a]})
    return pd.DataFrame(rows)


def add_markets(wf, rho):
    mk = [D.soccer_markets(a, b, rho) for a, b in zip(wf["lam_home"], wf["lam_away"])]
    return pd.concat([wf.reset_index(drop=True), pd.DataFrame(mk)], axis=1)


def ratings_table(m, tg, params=None, asof=None):
    """Today's grid: every club's attack and defence factor (the EPL version of the offense-vs-defense tabs)."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    idx = team_index(m)
    asof = pd.Timestamp(asof) if asof is not None else tg["date"].max() + pd.Timedelta(days=1)
    season = int(tg["season"].max())
    y = P["xg_blend"] * tg["xg"] + (1 - P["xg_blend"]) * tg["goals"]
    po, pd_ = np.ones(len(idx)), np.ones(len(idx))
    o0, d0 = promoted_prior(tg, idx, promoted_sets(m), season, y)
    for c in promoted_sets(m).get(season, ()):
        if c in idx:
            po[idx[c]], pd_[idx[c]] = o0, d0
    past = (tg["date"] < asof).values
    w = R.decay_weights((asof - tg["date"][past]).dt.days.values, P["half_life"])
    g = R.fit_grid(tg["team"].map(idx).values[past], tg["opp"].map(idx).values[past], y.values[past], len(idx), home=tg["home"].values[past], w=w,
                   k_games=P["k_games"], prior_o=po, prior_d=pd_)
    cur = sorted(set(m.loc[m["season"] == season, "home_team"].astype(int)))
    t = pd.DataFrame({"team": cur, "attack": [g["O"][idx[c]] for c in cur], "defence_allowed": [g["D"][idx[c]] for c in cur]})
    t["goals_for_vs_avg_opp"] = g["L"] * t["attack"]
    t["goals_against_vs_avg_opp"] = g["L"] * t["defence_allowed"]
    return t.sort_values("attack", ascending=False).reset_index(drop=True), g


def player_projections(pm, wf_goals, wf_shots, params=None):
    """pm = data.load_player_matches(...). One row per appearance with the projection built from earlier matches only."""
    P = dict(PARAMS)
    if params:
        P.update(params)
    p = pm.copy().reset_index(drop=True)
    ps = ["player_code", "season"]
    p["n_app"] = B.prior_count(p, ps)
    cmin = B.prior_sum(p, ps, "min")
    g = p.groupby(ps, sort=False)
    tot = g[["min", "xg", "goals", "shots", "sot", "assists", "xa"]].sum().reset_index()
    prev = pd.DataFrame({"player_code": tot["player_code"], "season": tot["season"] + 1, "prev_min": tot["min"]})
    for s in ["xg", "goals", "shots", "sot", "xa", "assists"]:
        prev["prev90_" + s] = 90.0 * tot[s] / tot["min"].where(tot["min"] > 0)
    p = p.merge(prev, on=ps, how="left")
    pos = p.groupby(["season", "position"], sort=False)[["min", "xg", "goals", "shots", "sot", "xa", "assists"]].sum().reset_index()
    posr = pd.DataFrame({"season": pos["season"] + 1, "position": pos["position"]})
    for s in ["xg", "goals", "shots", "sot", "xa", "assists"]:
        posr["pos90_" + s] = 90.0 * pos[s] / pos["min"]
    p = p.merge(posr, on=["season", "position"], how="left")
    for s in ["xg", "goals", "shots", "sot", "xa", "assists"]:
        prior = p["prev90_" + s].where(p["prev_min"].fillna(0) >= 450, p["pos90_" + s])
        p["r90_" + s] = 90.0 * (B.prior_sum(p, ps, s) + P["k_rate_min"] * prior / 90.0) / (cmin + P["k_rate_min"])
        p["avg_" + s] = B.prior_sum(p, ps, s) / p["n_app"].where(p["n_app"] > 0)                       # benchmark: per-appearance average
    # minutes when he starts
    st = p["started"].fillna(False).astype(bool)
    smin = (p["min"] * st).groupby([p["player_code"], p["season"]], sort=False).cumsum() - p["min"] * st
    sn = st.astype(float).groupby([p["player_code"], p["season"]], sort=False).cumsum() - st.astype(float)
    p["n_start"] = sn
    p["start_min"] = (smin + P["start_min_k"] * 82.0) / (sn + P["start_min_k"])
    # matchup: what the opponent allows and where the match is, from the walk-forward grid
    def env(wf, name):
        a = wf[["match_id", "home_team", "H", "d_away"]].rename(columns={"home_team": "team", "d_away": "d_opp"}); a["hs"] = a["H"]
        b = wf[["match_id", "away_team", "H", "d_home"]].rename(columns={"away_team": "team", "d_home": "d_opp"}); b["hs"] = 1.0 / b["H"]
        e = pd.concat([a, b], ignore_index=True)
        e[name] = e["hs"] * e["d_opp"]
        return e[["match_id", "team", name]]
    p = p.merge(env(wf_goals, "env_goals"), on=["match_id", "team"], how="left").merge(env(wf_shots, "env_shots"), on=["match_id", "team"], how="left")
    eg = np.power(p["env_goals"].fillna(1.0), P["w_env"])
    es = np.power(p["env_shots"].fillna(1.0), P["w_env"])
    frac = p["start_min"] / 90.0
    p["proj_xg"] = frac * (0.7 * p["r90_xg"] + 0.3 * p["r90_goals"]) * eg
    p["p_goal"] = 1.0 - np.exp(-p["proj_xg"])
    p["proj_shots"] = frac * p["r90_shots"] * es
    p["proj_sot"] = frac * p["r90_sot"] * es
    p["proj_xa"] = frac * (0.7 * p["r90_xa"] + 0.3 * p["r90_assists"]) * eg
    p["p_assist"] = 1.0 - np.exp(-p["proj_xa"])
    p["base_xg"] = frac * (0.7 * p["r90_xg"] + 0.3 * p["r90_goals"])        # no matchup
    p["base_shots"] = frac * p["r90_shots"]
    return p
