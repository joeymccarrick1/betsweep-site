"""College football data.

History: sportsdataverse's public releases - ESPN schedules with final scores (one small CSV a season) and cfbfastR play-by-play
(one ~500 MB CSV a season, with DraftKings' spread and total for each game, each team's pregame Elo, and the passer / rusher / receiver
on every play). The play-by-play is boiled down once into three small tables that are cached next to it.
Live and deeper stats (to be wired later): ESPN's college-football scoreboard / summary, and the CollegeFootballData API
(free key: 1,000 calls a month; lines from several books, SP+ ratings, returning production, official player box scores).

Two things to know before any player number is published:
  - rushing yards here come from rush plays only; the official box score also charges sacks to the quarterback, so quarterback
    rushing must be read from the box score, not from this table;
  - Tennessee does not allow bets on individual college athletes, so in Tennessee only the game lines are bettable.
"""
import os
import numpy as np
import pandas as pd

RELEASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
SOURCES = {
    "schedule": RELEASE + "/espn_cfb_schedules/cfb_schedule_{season}.csv",
    "pbp": RELEASE + "/cfbfastR_cfb_pbp/play_by_play_{season}.csv",
    "live_scoreboard": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80",
    "live_summary": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={event_id}",
    "cfbd_api": "https://api.collegefootballdata.com",
}
ODDS_API_SPORT = "americanfootball_ncaaf"
ODDS_API_MARKETS = ["h2h", "spreads", "totals", "alternate_spreads", "alternate_totals", "team_totals"]   # player props exist but are not legal in TN
PBP_COLS = ["period", "play_text", "game_id", "week", "pos_team", "def_pos_team", "home", "away", "play_type", "rush", "pass", "completion", "target", "rush_td", "pass_td", "sack", "int",
            "rush_player_id", "rush_player", "rush_yds", "completion_player_id", "completion_player", "completion_yds", "reception_player_id", "reception_player",
            "reception_yds", "target_player_id", "incompletion_player_id", "interception_thrown_player_id", "touchdown_player_id",
            "spread", "over_under", "provider", "home_team_pregame_elo", "away_team_pregame_elo", "home_team_division", "away_team_division"]


def data_dir():
    return os.environ.get("BS_SPORTS_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_data"))


def load_games(seasons, folder=None):
    """Finished games with final scores (FBS teams' games, including the ones against lower-division opponents)."""
    folder = folder or data_dir()
    g = pd.concat([pd.read_csv(os.path.join(folder, f"cfb_schedule_{s}.csv"), low_memory=False) for s in seasons], ignore_index=True)
    g = g[g["status"].eq("STATUS_FINAL") & g["home_score"].notna() & g["away_score"].notna()].copy()
    g["date"] = pd.to_datetime(g["game_date"], utc=True).dt.tz_localize(None)
    g["neutral"] = g["neutral_site"].astype(str).str.lower().eq("true")
    keep = ["season", "week", "season_type", "date", "game_id", "neutral", "home_id", "away_id", "home_team", "away_team", "home_score", "away_score"]
    return g[keep].drop_duplicates("game_id").sort_values(["date", "game_id"], kind="stable").reset_index(drop=True)


def _digest(season, folder):
    """Read one season of play-by-play once and cache the three small tables the model needs."""
    out = {k: os.path.join(folder, f"cfb_{k}_{season}.csv") for k in ("lines", "team_stats", "player_games")}
    if all(os.path.exists(f) for f in out.values()):
        return out
    d = pd.read_csv(os.path.join(folder, f"cfb_pbp_{season}.csv"), usecols=lambda c: c in PBP_COLS, low_memory=False)
    # the source repeats some plays (about 2.6% of 2025 rows, concentrated in a few games): one copy of each play text per team per period
    dup = d["play_text"].notna() & d.duplicated(["game_id", "period", "pos_team", "play_text"], keep="first")
    d = d[~dup].copy()
    d.drop_duplicates("game_id")[["game_id", "spread", "over_under", "provider", "home_team_pregame_elo", "away_team_pregame_elo", "home", "away",
                                  "home_team_division", "away_team_division"]].to_csv(out["lines"], index=False)
    for c in ("rush_yds", "completion_yds", "reception_yds"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    key = ["game_id", "week", "pos_team", "def_pos_team"]
    att = d["completion_player_id"].notna() | d["incompletion_player_id"].notna() | d["interception_thrown_player_id"].notna()
    t = d.assign(pass_yds=d["completion_yds"].fillna(0), rush_yds_=d["rush_yds"].fillna(0), carries=d["rush_player_id"].notna().astype(int), att=att.astype(int),
                 plays=((d["rush"] == 1) | (d["pass"] == 1)).astype(int)).groupby(key, sort=False)[["pass_yds", "rush_yds_", "carries", "att", "plays"]].sum().reset_index()
    t.rename(columns={"rush_yds_": "rush_yds"}).to_csv(out["team_stats"], index=False)
    frames = []
    r = d[d["rush_player_id"].notna()]
    frames.append(r.groupby(key + ["rush_player_id", "rush_player"], sort=False).agg(rush_yds=("rush_yds", "sum"), carries=("rush_yds", "size"), rush_td=("rush_td", "sum")).reset_index()
                  .rename(columns={"rush_player_id": "player_id", "rush_player": "player"}))
    c = d[d["reception_player_id"].notna()]
    frames.append(c.groupby(key + ["reception_player_id", "reception_player"], sort=False).agg(rec_yds=("reception_yds", "sum"), rec=("reception_yds", "size"), rec_td=("pass_td", "sum")).reset_index()
                  .rename(columns={"reception_player_id": "player_id", "reception_player": "player"}))
    tg = d[d["target_player_id"].notna()]
    frames.append(tg.groupby(key + ["target_player_id"], sort=False).size().rename("targets").reset_index().rename(columns={"target_player_id": "player_id"}))
    q = d[d["completion_player_id"].notna()]
    frames.append(q.groupby(key + ["completion_player_id", "completion_player"], sort=False).agg(pass_yds=("completion_yds", "sum"), comp=("completion_yds", "size"), pass_td=("pass_td", "sum")).reset_index()
                  .rename(columns={"completion_player_id": "player_id", "completion_player": "player"}))
    inc = pd.concat([d.loc[d["incompletion_player_id"].notna(), key + ["incompletion_player_id"]].rename(columns={"incompletion_player_id": "player_id"}),
                     d.loc[d["interception_thrown_player_id"].notna(), key + ["interception_thrown_player_id"]].rename(columns={"interception_thrown_player_id": "player_id"})])
    frames.append(inc.groupby(key + ["player_id"], sort=False).size().rename("inc").reset_index())
    p = None
    for f in frames:
        f["player_id"] = f["player_id"].astype("int64")
        p = f if p is None else p.merge(f, on=key + ["player_id"] + (["player"] if "player" in f.columns and "player" in p.columns else []), how="outer")
    for cnum in ("rush_yds", "carries", "rush_td", "rec_yds", "rec", "rec_td", "targets", "pass_yds", "comp", "pass_td", "inc"):
        p[cnum] = p[cnum].fillna(0)
    p["pass_att"] = p["comp"] + p["inc"]
    p.drop(columns=["inc"]).to_csv(out["player_games"], index=False)
    return out


def load_lines(seasons, folder=None):
    """DraftKings' spread (home side; negative = home favoured) and total for each game, plus each team's pregame Elo."""
    folder = folder or data_dir()
    return pd.concat([pd.read_csv(_digest(s, folder)["lines"]).assign(season=s) for s in seasons], ignore_index=True)


def load_team_stats(seasons, folder=None):
    folder = folder or data_dir()
    return pd.concat([pd.read_csv(_digest(s, folder)["team_stats"]).assign(season=s) for s in seasons], ignore_index=True)


def load_player_games(seasons, folder=None):
    folder = folder or data_dir()
    return pd.concat([pd.read_csv(_digest(s, folder)["player_games"]).assign(season=s) for s in seasons], ignore_index=True)
