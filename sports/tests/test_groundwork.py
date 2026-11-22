"""Checks for the multi-sport groundwork. Run:  python -m sports.tests.test_groundwork   (no data files needed)

The important ones are the leak tests: change what happened in a game and its own projection must not move.
"""
import numpy as np
import pandas as pd
from sports.core import odds as O, baseline as B, budget as BG, dist as D, ratings as R, legboard as LB, oddsapi as OA, metrics as M


def test_odds():
    assert abs(O.implied(-110) - 0.5238) < 1e-4 and abs(O.implied(150) - 0.4) < 1e-9
    assert O.american(0.75) == -300 and O.american(0.25) == 300 and O.american(1.0) is None
    a, b = O.devig(O.implied(-110), O.implied(-110))
    assert abs(a - 0.5) < 1e-9 and abs(a + b - 1) < 1e-9
    assert abs(O.blend(0.7, 0.5) - 0.6) < 1e-9 and O.blend(0.7, None) == 0.7
    assert O.parlay_american([-300, -300, -250, -200]) == 273          # four favourites near the Daily Sweep's price range


def test_prior_features_ignore_the_current_game():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"p": np.repeat(np.arange(5), 12), "x": rng.poisson(10, 60).astype(float)})
    a = (B.prior_mean(df, "p", "x"), B.prior_roll_mean(df, "p", "x", 4), B.prior_count(df, "p"))
    df2 = df.copy()
    df2.loc[df2.index[-1], "x"] = 999.0
    b = (B.prior_mean(df2, "p", "x"), B.prior_roll_mean(df2, "p", "x", 4), B.prior_count(df2, "p"))
    for u, v in zip(a, b):
        assert np.allclose(u.fillna(-1), v.fillna(-1))
    assert pd.isna(a[0].iloc[0]) and a[2].iloc[0] == 0
    assert abs(a[0].iloc[2] - df["x"].iloc[:2].mean()) < 1e-9


def test_budget():
    base = pd.Series([34.0, 30.0, 28.0, 20.0, 12.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0])
    grp = pd.Series(["short"] * 5 + ["full"] * 9)
    adj = BG.rebalance(base, grp, 240.0, c=1.0)
    assert abs(adj[grp == "short"].sum() - 240) < 1e-6 and abs(adj[grp == "full"].sum() - 240) < 1e-6
    assert (adj[grp == "short"] > base[grp == "short"]).all() and (adj[grp == "full"] < base[grp == "full"]).all()
    capped = BG.rebalance(base, grp, 240.0, c=1.0, cap=38.0)
    assert capped.max() <= 38.0 + 1e-9 and (capped >= 0).all()
    half = BG.rebalance(base, grp, 240.0, c=0.5)
    assert abs(half[grp == "short"].sum() - (124 + 0.5 * 116)) < 1e-6
    f = BG.scale_to_total(pd.Series([10.0, 10.0]), pd.Series(["g", "g"]), 30.0, u=0.5)
    assert np.allclose(f, 1.25)


def test_hit_chances():
    lines = np.arange(1, 40)
    p = D.p_at_least(lines, np.full(len(lines), 18.0), "qp", phi=3.5)
    assert (np.diff(p) <= 1e-12).all() and 0 < p[-1] < p[0] <= 1
    assert abs(D.p_at_least(20, 18.0, "qp", phi=1.000001) - D.p_at_least(20, 18.0, "poisson")) < 1e-3
    assert abs(D.p_at_least(19.5, 18.0, "poisson") - D.p_at_least(20, 18.0, "poisson")) < 1e-12        # 19.5 and '20+' are the same bet
    rng = np.random.default_rng(3)
    mean = rng.uniform(4, 30, 20000)
    r = mean / (2.6 - 1.0)
    y = rng.negative_binomial(r, r / (r + mean))
    assert abs(D.fit_phi(y, mean) - 2.6) < 0.1
    mk = D.soccer_markets(1.6, 1.1, rho=-0.1)
    assert abs(mk["home"] + mk["draw"] + mk["away"] - 1) < 1e-9 and mk["home"] > mk["away"] and 0 < mk["btts"] < 1 and mk["over15"] > mk["over25"] > mk["over35"]


def test_grid_recovers_known_teams():
    rng = np.random.default_rng(7)
    n = 20
    o_true, d_true, L, H = np.exp(rng.normal(0, 0.25, n)), np.exp(rng.normal(0, 0.2, n)), 1.4, 1.12
    o_true, d_true = o_true / o_true.mean(), d_true / d_true.mean()
    team, opp, home, y = [], [], [], []
    for rep in range(8):
        for i in range(n):
            for j in range(n):
                if i != j:
                    for a, b, s in ((i, j, 1), (j, i, -1)):
                        team.append(a); opp.append(b); home.append(s); y.append(rng.poisson(L * H ** s * o_true[a] * d_true[b]))
    g = R.fit_grid(team, opp, y, n, home=home, k_games=1.0)
    assert np.corrcoef(g["O"], o_true)[0, 1] > 0.97 and np.corrcoef(g["D"], d_true)[0, 1] > 0.95
    assert abs(g["H"] - H) < 0.02 and abs(R.expect(g, 0, 1, 1) - L * H * o_true[0] * d_true[1]) / (L * H * o_true[0] * d_true[1]) < 0.12
    # a team with no games keeps its prior
    g2 = R.fit_grid(team, opp, y, n + 1, home=home, k_games=2.0, prior_o=np.r_[np.ones(n), 0.8], prior_d=np.r_[np.ones(n), 1.2])
    assert abs(g2["O"][n] - 0.8) < 1e-9 and abs(g2["D"][n] - 1.2) < 1e-9


def test_names_and_board_row():
    assert LB.norm_name("Kelly Oubre Jr.") == "kelly oubre" and LB.norm_name("Luka Dončić") == "luka doncic" and LB.norm_name("De'Aaron Fox") == "deaaron fox"
    r = LB.row("Test Player", "Points", 20, "AAA", "BBB", 22.4, 21.0, 12, 0.62, "BBB @ AAA", "Sun 11/15 6:00 PM", fd_odds=-150)
    d = dict(zip(LB.HEADER, r))
    assert len(r) == len(LB.HEADER) and d["Book implied %"] == 0.6 and abs(d["Model hit % (history-adjusted)"] - 0.61) < 1e-9 and abs(d["Edge"] - 0.01) < 1e-9
    r2 = dict(zip(LB.HEADER, LB.row("Test Player", "Points", 20, "AAA", "BBB", 22.4, None, 3, 0.62, "g", "k")))
    assert r2["FanDuel odds"] == "" and r2["Edge"] == "" and r2["Fair odds"] == "-163"


def test_price_parser_matches_the_nfl_pull():
    ev = {"id": "abc", "home_team": "Boston Celtics", "away_team": "Dallas Mavericks", "commence_time": "2026-11-15T23:00:00Z", "bookmakers": [
        {"key": "draftkings", "markets": [{"key": "player_points", "outcomes": [{"name": "Over", "description": "Jayson Tatum", "price": -105, "point": 27.5}]}]},
        {"key": "fanduel", "markets": [
            {"key": "player_points", "sid": "42.100", "last_update": "t", "outcomes": [
                {"name": "Over", "description": "Jayson Tatum", "price": -112, "point": 26.5, "link": "https://sportsbook.fanduel.com/addToBetslip?marketId=42.100&selectionId=777"},
                {"name": "Under", "description": "Jayson Tatum", "price": -108, "point": 26.5, "sid": "778"}]},
            {"key": "player_points_alternate", "sid": "42.200", "outcomes": [{"name": "Over", "description": "Jayson Tatum", "price": -340, "point": 19.5, "sid": "901"},
                                                                         {"name": "Over", "description": "Jayson Tatum", "price": 180, "point": 29.5, "sid": "902"}]},
            {"key": "not_a_market_we_use", "outcomes": [{"name": "Over", "description": "X", "price": 100, "point": 1.5}]}]}]}
    rows = OA.parse_event(ev, OA.NBA)
    by = {(r["line"], r["side"]): r for r in rows}
    assert len(rows) == 4 and all(r["key"].startswith("jayson tatum|Points|") for r in rows)
    assert by[(27, "Over")]["price"] == -112 and by[(27, "Over")]["market_id"] == "42.100" and by[(27, "Over")]["selection_id"] == "777"
    assert by[(27, "Under")]["selection_id"] == "778" and by[(20, "Over")]["price"] == -340 and by[(30, "Over")]["market_id"] == "42.200"
    soc = {"id": "m1", "home_team": "Arsenal", "away_team": "Chelsea", "bookmakers": [{"key": "fanduel", "markets": [
        {"key": "player_goal_scorer_anytime", "outcomes": [{"name": "Yes", "description": "Bukayo Saka", "price": 150}, {"name": "No", "description": "Bukayo Saka", "price": -200}]},
        {"key": "player_shots_on_target", "outcomes": [{"name": "Over", "description": "Bukayo Saka", "price": -130, "point": 0.5}]}]}]}
    r2 = OA.parse_event(soc, OA.EPL)
    assert {(r["market"], r["line"], r["price"]) for r in r2} == {("Anytime Goalscorer", 1, 150), ("Shots on Target", 1, -130)}
    assert OA.monthly_credits(7, 10, 3) == 6300


def _toy_nba(seed=5):
    rng = np.random.default_rng(seed)
    rows, gid = [], 0
    teams = list(range(1, 7))
    for season in (2026, 2027):
        day = pd.Timestamp(f"{season - 1}-10-20")
        for rnd in range(14):
            order = rng.permutation(teams)
            for a, b in zip(order[::2], order[1::2]):
                gid += 1
                for t, o, home in ((a, b, True), (b, a, False)):
                    for k in range(9):
                        mins = max(0.0, rng.normal(34 - 3 * k, 4))
                        played = bool(rng.random() > 0.08)
                        rows.append({"season": season, "date": day, "game_id": gid, "tg": f"{gid}|{t}", "athlete_id": t * 100 + k, "player": f"P{t}_{k}", "team_id": t, "team": f"T{t}",
                                     "opp_id": o, "opp": f"T{o}", "home": home, "grp": "GFC"[k % 3], "starter": k < 5, "played": played and mins > 0, "reason": "",
                                     "min": mins if played else 0.0, "team_score": 110, "opponent_team_score": 108, "fga": 0.0, "fta": 0.0,
                                     "pts": float(rng.poisson(0.5 * mins)) if played else 0.0, "reb": float(rng.poisson(0.18 * mins)) if played else 0.0,
                                     "ast": float(rng.poisson(0.12 * mins)) if played else 0.0, "fg3": float(rng.poisson(0.05 * mins)) if played else 0.0,
                                     "stl": 0.0, "blk": 0.0, "tov": 0.0})
            day += pd.Timedelta(days=2)
    return pd.DataFrame(rows).sort_values(["date", "game_id", "team_id", "athlete_id"], kind="stable").reset_index(drop=True)


def test_nba_projection_does_not_see_the_game_it_projects():
    from sports.nba import model as NM
    d = _toy_nba()
    last = d["date"].max()
    p1 = NM.project(d)
    d2 = d.copy()
    m = (d2["date"] == last) & d2["played"]
    for c in ("min", "pts", "reb", "ast", "fg3"):
        d2.loc[m, c] = d2.loc[m, c] * 3 + 7            # a different night in every box score; the same players active
    p2 = NM.project(d2)
    a, b = p1[p1["date"] == last], p2[p2["date"] == last]
    assert len(a) > 20 and np.allclose(a[["proj_min", "proj_pts", "proj_reb", "proj_ast", "proj_fg3"]].fillna(-1), b[["proj_min", "proj_pts", "proj_reb", "proj_ast", "proj_fg3"]].fillna(-1))
    assert not np.allclose(a["pts"], b["pts"])
    tot = p1[p1["has_base"]].groupby("tg")["proj_min"].sum()
    assert tot.max() <= 260 and tot.median() > 200          # a team's projected minutes stay near the 240 it has to give


def _toy_league(seed=11, n=8):
    rng = np.random.default_rng(seed)
    rows, mid = [], 0
    for season in (2025, 2026):
        day = pd.Timestamp(f"{season - 1}-08-15")
        for rnd in range(2 * (n - 1)):
            order = rng.permutation(n)
            for a, b in zip(order[::2], order[1::2]):
                mid += 1
                hs, as_ = rng.poisson(1.6), rng.poisson(1.2)
                rows.append({"season": season, "gameweek": rnd + 1, "date": day + pd.Timedelta(hours=15), "match_id": f"m{mid}", "finished": True, "home_team": int(a + 1), "away_team": int(b + 1),
                             "home_score": hs, "away_score": as_, "home_xg": 1.5, "away_xg": 1.1, "home_shots": 13, "away_shots": 11, "home_sot": 5, "away_sot": 4,
                             "home_corners": 5, "away_corners": 4, "home_yellow_cards": 2, "away_yellow_cards": 2, "home_team_elo": np.nan, "away_team_elo": np.nan})
            day += pd.Timedelta(days=7)
    m = pd.DataFrame(rows)
    m["home_team"] = m["home_team"].astype("Int64"); m["away_team"] = m["away_team"].astype("Int64")
    return m


def test_epl_rating_does_not_see_the_match_it_rates():
    from sports.epl import data as ED, model as EM
    m = _toy_league()
    wf1 = EM.walk_forward(m, ED.team_games(m), [2026])
    m2 = m.copy()
    last_day = m2["date"].max().normalize()
    sel = m2["date"].dt.normalize() == last_day
    m2.loc[sel, ["home_score", "away_score", "home_xg", "away_xg"]] = [9, 0, 6.0, 0.1]
    wf2 = EM.walk_forward(m2, ED.team_games(m2), [2026])
    a = wf1[wf1["date"].dt.normalize() == last_day].sort_values("match_id")
    b = wf2[wf2["date"].dt.normalize() == last_day].sort_values("match_id")
    assert len(a) == 4 and np.allclose(a[["lam_home", "lam_away"]], b[["lam_home", "lam_away"]])
    mk = EM.add_markets(wf1, -0.1)
    assert np.allclose(mk["home"] + mk["draw"] + mk["away"], 1.0)


def test_cfb_rating_does_not_see_the_game_it_rates():
    from sports.cfb import model as CM
    rng = np.random.default_rng(2)
    rows, gid = [], 0
    for season in (2025, 2026):
        day = pd.Timestamp(f"{season}-09-01")
        for wk in range(10):
            order = rng.permutation(12)
            for a, b in zip(order[::2], order[1::2]):
                gid += 1
                rows.append({"season": season, "week": wk + 1, "season_type": 2, "date": day + pd.Timedelta(hours=18), "game_id": gid, "neutral": False, "home_id": int(a + 1), "away_id": int(b + 1),
                             "home_team": f"H{a}", "away_team": f"A{b}", "home_score": float(rng.poisson(30)), "away_score": float(rng.poisson(24))})
            day += pd.Timedelta(days=7)
    g = pd.DataFrame(rows)
    w1 = CM.walk_forward(g, [2026])
    g2 = g.copy()
    sel = g2["date"] == g2["date"].max()
    g2.loc[sel, ["home_score", "away_score"]] = [77.0, 0.0]
    w2 = CM.walk_forward(g2, [2026])
    a, b = w1[w1["date"] == g["date"].max()].sort_values("game_id"), w2[w2["date"] == g["date"].max()].sort_values("game_id")
    assert len(a) == 6 and np.allclose(a[["exp_home", "exp_away"]], b[["exp_home", "exp_away"]])
    assert CM.fbs_sets(g)[2026] == set(range(1, 13))


def test_metrics():
    assert abs(M.brier([1, 0], [0.8, 0.2]) - 0.04) < 1e-12 and M.mae([1, 2, 3], [1, 2, 5]) == 2 / 3
    assert M.rps_1x2([1.0], [0.0], [0.0], ["H"]) == 0.0 and M.rps_1x2([0.0], [0.0], [1.0], ["H"]) == 1.0
    assert abs(M.logloss_1x2([0.5], [0.3], [0.2], ["D"]) + np.log(0.3)) < 1e-12


if __name__ == "__main__":
    import sys
    tests = [(k, v) for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in tests:
        try:
            fn(); print("ok  ", name)
        except Exception as e:                      # noqa: BLE001 - a plain runner: show which check failed and keep going
            failed += 1; print("FAIL", name, "-", repr(e)[:300])
    print(f"{len(tests) - failed} of {len(tests)} checks passed")
    sys.exit(1 if failed else 0)
