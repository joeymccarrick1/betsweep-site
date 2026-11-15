"""FanDuel prices from The Odds API, for any sport - the Python twin of FanDuelOdds.gs (the NFL pull that runs in the sheet).

Same calls, same fields: the free events list, then one /events/{id}/odds call per game with bookmakers=fanduel, includeLinks and
includeSids, so every rung comes back with its price and its betslip ids. Cost per game = the number of markets that come back
(up to 10 bookmakers count as one region). Nothing here runs on a schedule yet and it has not been run against the live API from
this branch: the key lives in the sheet's script properties, and the 20,000-credit plan is already used by the NFL pulls
(about 580 credits a day). `parse_event` is tested against a hand-made response in tests/.
"""
import json
import re
import urllib.parse
import urllib.request
from .legboard import norm_name

BASE = "https://api.the-odds-api.com/v4"
# Odds API market key -> (board market name, stat key in the model). X+ rung = round(point + 0.5), as in the NFL pull.
NBA = {"player_points": ("Points", "pts"), "player_points_alternate": ("Points", "pts"), "player_rebounds": ("Rebounds", "reb"),
       "player_rebounds_alternate": ("Rebounds", "reb"), "player_assists": ("Assists", "ast"), "player_assists_alternate": ("Assists", "ast"),
       "player_threes": ("Threes Made", "fg3"), "player_threes_alternate": ("Threes Made", "fg3"),
       "player_points_rebounds_assists": ("Pts + Reb + Ast", "pra"), "player_points_rebounds_assists_alternate": ("Pts + Reb + Ast", "pra")}
EPL = {"player_goal_scorer_anytime": ("Anytime Goalscorer", "goal"), "player_shots": ("Shots", "shots"), "player_shots_alternate": ("Shots", "shots"),
       "player_shots_on_target": ("Shots on Target", "sot"), "player_shots_on_target_alternate": ("Shots on Target", "sot"), "player_assists": ("Assist", "assist")}
GAME_LINES = ["h2h", "spreads", "totals"]
SPORT_KEYS = {"nba": "basketball_nba", "cfb": "americanfootball_ncaaf", "epl": "soccer_epl"}


def _qs(url, name):
    m = re.search(r"[?&]" + re.escape(name) + r"=([^&#]+)", str(url or ""))
    return urllib.parse.unquote(m.group(1)) if m else ""


def parse_event(event_json, market_map, book="fanduel"):
    """One /events/{id}/odds response -> price rows: key, player, market, X+ line, price, side, betslip ids, game, start."""
    d = event_json
    game = f"{d.get('away_team', '')} @ {d.get('home_team', '')}"
    rows, seen = [], set()
    for b in d.get("bookmakers") or []:
        if b.get("key") != book:
            continue
        for m in b.get("markets") or []:
            if m.get("key") not in market_map:
                continue
            name, stat = market_map[m["key"]]
            for o in m.get("outcomes") or []:
                side = o.get("name") or ""
                player = o.get("description") or (side if side not in ("Over", "Under", "Yes", "No") else "")
                price = o.get("price")
                if not player or price is None:
                    continue
                pt = o.get("point")
                if pt is None:                       # yes / no markets (anytime goalscorer): keep the Yes side, as the NFL pull does for touchdowns
                    if side == "No":
                        continue
                    x, side_out = 1, "Over"
                else:
                    if side not in ("Over", "Under"):
                        continue
                    x, side_out = int(round(float(pt) + 0.5)), side
                key = f"{norm_name(player)}|{name}|{x}|{side_out}"
                if key in seen:
                    continue
                seen.add(key)
                link = o.get("link") or ""
                rows.append({"key": f"{norm_name(player)}|{name}|{x}", "player": player, "market": name, "stat": stat, "line": x, "side": side_out,
                             "price": int(price), "market_id": _qs(link, "marketId") or m.get("sid") or "", "selection_id": _qs(link, "selectionId") or o.get("sid") or "",
                             "link": link, "game": game, "event_id": d.get("id", ""), "commence_time": d.get("commence_time", ""), "last_update": m.get("last_update", "")})
    return rows


def fetch_events(sport, api_key, timeout=30):
    """The events list (free)."""
    with urllib.request.urlopen(f"{BASE}/sports/{SPORT_KEYS.get(sport, sport)}/events?apiKey={api_key}", timeout=timeout) as r:
        return json.load(r)


def fetch_event_odds(sport, event_id, markets, api_key, books="fanduel", timeout=30):
    """One game's prices. Returns (json, credits_left)."""
    q = urllib.parse.urlencode({"apiKey": api_key, "bookmakers": books, "markets": ",".join(markets), "oddsFormat": "american", "includeLinks": "true", "includeSids": "true"})
    with urllib.request.urlopen(f"{BASE}/sports/{SPORT_KEYS.get(sport, sport)}/events/{event_id}/odds?{q}", timeout=timeout) as r:
        return json.load(r), r.headers.get("x-requests-remaining")


def monthly_credits(games_per_day, markets_per_game, pulls_per_day, days=30):
    """Rough monthly cost of a pull plan: one credit per market that comes back, per game, per pull."""
    return int(round(games_per_day * markets_per_game * pulls_per_day * days))
