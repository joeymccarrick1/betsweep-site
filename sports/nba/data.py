"""NBA data. History: sportsdataverse's public ESPN box-score releases (one CSV per season, refreshed daily).
Live (to be wired in a GitHub Action, same host the NFL feeds already use): ESPN scoreboard / summary / injuries."""
import os
import pandas as pd

RELEASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
SOURCES = {
    "player_box": RELEASE + "/espn_nba_player_boxscores/player_box_{season}.csv",     # season = year the season ends (2027 = 2026-27)
    "team_box": RELEASE + "/espn_nba_team_boxscores/team_box_{season}.csv",
    "schedule": RELEASE + "/espn_nba_schedules/nba_schedule_{season}.csv",
    "live_scoreboard": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "live_summary": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}",
    "live_injuries": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries",
}
ODDS_API_SPORT = "basketball_nba"
ODDS_API_MARKETS = ["player_points", "player_rebounds", "player_assists", "player_threes", "player_points_rebounds_assists",
                    "player_points_alternate", "player_rebounds_alternate", "player_assists_alternate", "player_threes_alternate",
                    "player_points_rebounds_assists_alternate", "h2h", "spreads", "totals"]
EXHIBITION = {"STARS", "STRIPES", "WORLD", "EAST", "WEST", "USA"}
STATS = {"pts": "points", "reb": "rebounds", "ast": "assists", "fg3": "three_point_field_goals_made",
         "stl": "steals", "blk": "blocks", "tov": "turnovers"}
GROUP = {"G": "G", "PG": "G", "SG": "G", "F": "F", "SF": "F", "PF": "F", "C": "C"}


def data_dir():
    return os.environ.get("BS_SPORTS_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_data"))


def load(seasons, folder=None):
    """One row per player per game (played or listed as did-not-play), regular season only, in time order."""
    folder = folder or data_dir()
    d = pd.concat([pd.read_csv(os.path.join(folder, f"nba_player_box_{s}.csv"), low_memory=False) for s in seasons], ignore_index=True)
    d = d[(d["season_type"] == 2) & ~d["team_abbreviation"].isin(EXHIBITION) & ~d["opponent_team_abbreviation"].isin(EXHIBITION)].copy()
    d["date"] = pd.to_datetime(d["game_date"])
    dnp = d["did_not_play"].astype(str).str.lower().eq("true")
    d["min"] = pd.to_numeric(d["minutes"], errors="coerce").fillna(0.0)
    d["played"] = (~dnp) & (d["min"] > 0)
    for k, c in STATS.items():
        d[k] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    d["fga"] = pd.to_numeric(d["field_goals_attempted"], errors="coerce").fillna(0.0)
    d["fta"] = pd.to_numeric(d["free_throws_attempted"], errors="coerce").fillna(0.0)
    d["grp"] = d["athlete_position_abbreviation"].map(GROUP).fillna("F")
    d["home"] = d["home_away"].astype(str).str.lower().eq("home")
    d["tg"] = d["game_id"].astype(str) + "|" + d["team_id"].astype(str)          # team-game key
    keep = ["season", "date", "game_id", "tg", "athlete_id", "athlete_display_name", "team_id", "team_abbreviation",
            "opponent_team_id", "opponent_team_abbreviation", "home", "grp", "starter", "played", "reason", "min",
            "team_score", "opponent_team_score", "fga", "fta"] + list(STATS)
    d = d[keep].rename(columns={"athlete_display_name": "player", "team_abbreviation": "team", "opponent_team_abbreviation": "opp",
                                "opponent_team_id": "opp_id"})
    return d.sort_values(["date", "game_id", "team_id", "athlete_id"], kind="stable").reset_index(drop=True)
