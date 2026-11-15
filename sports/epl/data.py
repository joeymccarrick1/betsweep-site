"""Premier League data.

History and week-to-week: the public FPL-Elo-Insights repo (github.com/olbauday/FPL-Elo-Insights): every match with goals, xG, shots,
corners and cards, and every player's minutes, shots, shots on target, xG and xA, refreshed several times a day. It is a community
data set, so the live build should also read the two primary sources it is assembled from before anything is published:
  - the official Fantasy Premier League API (fixtures, minutes, xG, injury flags and 'chance of playing')
  - ESPN's soccer scoreboard / summary (same host the NFL feeds use), league code eng.1
Player ids change every season in FPL; `player_code` is the one that stays the same.
"""
import glob, os
import numpy as np
import pandas as pd

REPO = "https://github.com/olbauday/FPL-Elo-Insights"
SOURCES = {
    "history": REPO,
    "fpl_bootstrap": "https://fantasy.premierleague.com/api/bootstrap-static/",
    "fpl_fixtures": "https://fantasy.premierleague.com/api/fixtures/",
    "live_scoreboard": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
    "live_summary": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/summary?event={event_id}",
}
ODDS_API_SPORT = "soccer_epl"
ODDS_API_MARKETS = ["h2h", "totals", "btts", "double_chance", "draw_no_bet", "alternate_totals", "team_totals",
                    "player_goal_scorer_anytime", "player_shots", "player_shots_on_target", "player_shots_alternate",
                    "player_shots_on_target_alternate", "player_assists", "player_to_receive_card"]
SEASONS = {2025: "2024-2025", 2026: "2025-2026", 2027: "2026-2027"}      # season = year it ends, like the NBA files


def data_dir():
    return os.environ.get("BS_SPORTS_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_data"))


def _root(folder=None):
    return os.path.join(folder or data_dir(), "fplei", "data")


def _gw_files(root, season_dir, name):
    pat = (os.path.join(root, season_dir, name, "GW*", name + ".csv") if season_dir == "2024-2025"
           else os.path.join(root, season_dir, "By Tournament", "Premier League", "GW*", name + ".csv"))
    return sorted(glob.glob(pat), key=lambda f: int(f.split("GW")[-1].split(os.sep)[0]))


def load_matches(folder=None):
    """One row per Premier League match (played or still to come), every season on disk."""
    root = _root(folder)
    out = []
    for season, sd in SEASONS.items():
        if sd == "2024-2025":
            f = os.path.join(root, sd, "matches", "matches.csv")
            m = pd.read_csv(f) if os.path.exists(f) else None
        else:
            fs = _gw_files(root, sd, "matches")
            m = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True) if fs else None
        if m is None:
            continue
        out.append(m.assign(season=season))
    m = pd.concat(out, ignore_index=True).copy()
    m["date"] = pd.to_datetime(m["kickoff_time"], utc=True, format="mixed").dt.tz_localize(None)
    m["finished"] = m["finished"].astype(str).str.lower().eq("true")
    ren = {"home_expected_goals_xg": "home_xg", "away_expected_goals_xg": "away_xg", "home_total_shots": "home_shots", "away_total_shots": "away_shots",
           "home_shots_on_target": "home_sot", "away_shots_on_target": "away_sot"}
    m = m.rename(columns=ren)
    for c in ["home_team", "away_team", "home_score", "away_score", "home_xg", "away_xg", "home_shots", "away_shots", "home_sot", "away_sot",
              "home_corners", "away_corners", "home_yellow_cards", "away_yellow_cards", "home_team_elo", "away_team_elo", "gameweek"]:
        m[c] = pd.to_numeric(m[c], errors="coerce")
    keep = ["season", "gameweek", "date", "match_id", "finished", "home_team", "away_team", "home_score", "away_score", "home_xg", "away_xg",
            "home_shots", "away_shots", "home_sot", "away_sot", "home_corners", "away_corners", "home_yellow_cards", "away_yellow_cards",
            "home_team_elo", "away_team_elo"]
    m = m[keep].drop_duplicates("match_id").sort_values(["date", "match_id"], kind="stable").reset_index(drop=True)
    m["home_team"] = m["home_team"].astype("Int64")
    m["away_team"] = m["away_team"].astype("Int64")
    return m


def load_teams(folder=None):
    root = _root(folder)
    out = {}
    for season, sd in SEASONS.items():
        f = os.path.join(root, sd, "teams", "teams.csv") if sd == "2024-2025" else os.path.join(root, sd, "teams.csv")
        if os.path.exists(f):
            t = pd.read_csv(f)
            for _, r in t.iterrows():
                out[int(r["code"])] = {"name": r["name"], "short": r["short_name"]}
    return out


def team_games(m):
    """Two rows per finished match: what each side produced and allowed."""
    f = m[m["finished"]]
    rows = []
    for side, other, s in (("home", "away", 1), ("away", "home", -1)):
        rows.append(pd.DataFrame({
            "season": f["season"], "date": f["date"], "match_id": f["match_id"], "team": f[side + "_team"].astype(int), "opp": f[other + "_team"].astype(int),
            "home": s, "goals": f[side + "_score"], "xg": f[side + "_xg"], "shots": f[side + "_shots"], "sot": f[side + "_sot"],
            "corners": f[side + "_corners"], "cards": f[side + "_yellow_cards"], "goals_against": f[other + "_score"]}))
    return pd.concat(rows, ignore_index=True).sort_values(["date", "match_id", "home"], kind="stable").reset_index(drop=True)


def load_player_matches(m, folder=None):
    """One row per player per match he appeared in, with his team worked out for that week."""
    root = _root(folder)
    out = []
    for season, sd in SEASONS.items():
        fs = _gw_files(root, sd, "playermatchstats")
        if not fs:
            continue
        season_players = pd.read_csv(os.path.join(root, sd, "players", "players.csv") if sd == "2024-2025" else os.path.join(root, sd, "players.csv"))
        for f in fs:
            p = pd.read_csv(f)
            wk = os.path.join(os.path.dirname(f), "players.csv")
            pl = pd.read_csv(wk) if (sd != "2024-2025" and os.path.exists(wk)) else season_players
            pl = pl.drop_duplicates("player_id")[["player_id", "player_code", "web_name", "team_code", "position"]]
            p = p.merge(pl, on="player_id", how="left")
            miss = p["team_code"].isna()
            if miss.any():       # not in this week's list: fall back to the season list
                fb = season_players.drop_duplicates("player_id").set_index("player_id")
                for c in ["player_code", "web_name", "team_code", "position"]:
                    p.loc[miss, c] = p.loc[miss, "player_id"].map(fb[c])
            p["season"] = season
            out.append(p)
    p = pd.concat(out, ignore_index=True)
    for c in ["minutes_played", "goals", "assists", "total_shots", "shots_on_target", "xg", "xa", "start_min"]:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p.merge(m[["match_id", "date", "home_team", "away_team", "finished"]], on="match_id", how="inner")
    p = p[p["finished"] & (p["minutes_played"].fillna(0) > 0) & p["player_code"].notna()].copy()
    tc = p["team_code"].astype(float)
    is_home = tc == p["home_team"].astype(float)
    is_away = tc == p["away_team"].astype(float)
    p = p[is_home | is_away].copy()                                        # a mid-season mover listed under his new club is dropped for the old games
    p["team"] = p["team_code"].astype(int)
    p["opp"] = np.where(p["team"] == p["home_team"].astype(int), p["away_team"].astype(int), p["home_team"].astype(int))
    p["home"] = np.where(p["team"] == p["home_team"].astype(int), 1, -1)
    p["started"] = p["start_min"].eq(0) if "start_min" in p.columns else False
    # the 2025-26 files mark almost everyone as starting at minute 0; where a season's flags do not give 10-11 starters a side,
    # fall back to the eleven with the most minutes for that side (agrees with the true flag on about 97% of rows in the seasons that have it)
    rank = p.groupby(["match_id", "team_code"], sort=False)["minutes_played"].rank(method="first", ascending=False)
    per_side = p.groupby(["season", "match_id", "team_code"], sort=False)["started"].transform("sum")
    ok_share = per_side.between(10, 11).groupby(p["season"]).transform("mean")
    p["started_flag_ok"] = ok_share >= 0.9
    p["started"] = np.where(p["started_flag_ok"], p["started"], rank <= 11)
    p = p.rename(columns={"minutes_played": "min", "total_shots": "shots", "shots_on_target": "sot", "web_name": "player"})
    for c in ["goals", "assists", "shots", "sot", "xg", "xa"]:
        p[c] = p[c].fillna(0.0)                                             # the source leaves a blank where a player had none
    p["player_code"] = p["player_code"].astype(int)
    keep = ["season", "date", "match_id", "player_code", "player", "position", "team", "opp", "home", "started", "min", "goals", "assists", "shots", "sot", "xg", "xa"]
    return p[keep].sort_values(["date", "match_id", "team", "player_code"], kind="stable").reset_index(drop=True)
