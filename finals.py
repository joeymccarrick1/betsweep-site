#!/usr/bin/env python3
"""finals.py - what the build already knows about this week's FINISHED games, for the Live page.

Why (found 11/17): once the build held a final score for every game that had kicked off, the Live page stopped asking ESPN for anything.
It then graded every leg against a 0-0 score and an empty box score - winners showed as dead, "My week" read 0-5 for five legs that had
all won, and those losses were saved into the reader's season record. The page now refuses to settle a leg without real numbers
(build_live.py), and this module hands it the real numbers the build has on hand, so a finished game needs no ESPN call at all:

  in/games.csv                       nflverse schedule: final scores
  in/stats_player_week_<season>.csv  nflverse player stat lines per game
  in/snap_counts_<season>.csv        who was on the field (a man with no stat line either played and did nothing, or did not play)

build() returns {gid: {"sc": {TEAM: points, TEAM: points}, "box": {leg player name: [pass yds, pass TD, INT, rush yds, rush TD, receptions,
rec yds, rec TD, completions, pass attempts, carries, targets]}, "dnp": [leg player names who did not play]}} for the games that are final.
"box" and "dnp" are only given when the stat file can be trusted for that game: both teams have rows AND the points the file credits to
each team's players add up to that team's final score (touchdowns, field goals, extra points, two-point tries, safeties). A game that
fails the check gets its score only, and the page falls back to ESPN for the box score. Never guessed: a player the files cannot place
is left out, and the page shows his leg as not graded yet.

Not in these files: who scored the first touchdown, and a player's longest reception. The page asks ESPN for those when a reader is
looking at such a leg.

refresh() - the hourly build keeps one copy of the nflverse files per day (actions/cache), so a game that ended since that copy was made
is missing from it. When a final game of this week has no stat rows (or no snap rows), try once for a newer copy; a failed download
changes nothing.
"""
import csv, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import social_grade as SG

FIELDS = ("pass", "ptd", "int", "rush", "rtd", "rec", "recy", "ctd", "cmp", "patt", "ratt", "tgt")
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download/"


def _final_teams(IN, season, week):
    """the teams of this week's games that have a final score in in/games.csv"""
    out = []
    try:
        with open(os.path.join(IN, "games.csv"), newline="") as f:
            for r in csv.DictReader(f):
                if str(r.get("season")) != str(season) or r.get("game_type") != "REG" or str(r.get("week")) != str(week): continue
                if r.get("home_score") in ("", None, "NA") or r.get("away_score") in ("", None, "NA"): continue
                out += [SG.team(r["home_team"]), SG.team(r["away_team"])]
    except Exception: pass
    return out


def _teams_in(path, week, team_col, type_col):
    have = set()
    try:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                if r.get(type_col, "REG") == "REG" and str(r.get("week")) == str(week): have.add(SG.team(r.get(team_col)))
    except Exception: pass
    return have


def refresh(IN, season, week, min_age=1200, log=print):
    """Try for newer nflverse copies when a final game of this week is missing from the ones on hand. Returns the names that were replaced."""
    done = []; teams = _final_teams(IN, season, week)
    if not teams: return done
    for name, rel, team_col, type_col, must in ((f"stats_player_week_{season}.csv", f"stats_player/stats_player_week_{season}.csv", "team", "season_type", "player_display_name"),
                                                (f"snap_counts_{season}.csv", f"snap_counts/snap_counts_{season}.csv", "team", "game_type", "offense_snaps")):
        path = os.path.join(IN, name)
        if os.path.exists(path):
            if all(t in _teams_in(path, week, team_col, type_col) for t in teams): continue          # nothing missing
            if time.time() - os.path.getmtime(path) < min_age: continue                             # just fetched: nflverse has not published it yet
        tmp = path + ".part"
        try:
            subprocess.run(["curl", "-fsSL", "--max-time", "90", "-o", tmp, NFLVERSE + rel], check=True, stderr=subprocess.DEVNULL)
            with open(tmp, newline="") as f: head = f.readline()
            if must not in head or os.path.getsize(tmp) < (os.path.getsize(path) * 0.9 if os.path.exists(path) else 1000): raise ValueError("the download does not look like the file")
            os.replace(tmp, path); done.append(name)
        except Exception as e:
            log(f"note: finals: no newer {name} ({type(e).__name__}) - using the copy on hand")
            try: os.remove(tmp)
            except Exception: pass
    if done: log("finals: fetched a newer " + " and ".join(done) + " (a finished game was missing from the daily copy)")
    return done


def build(IN, week, games, legs, season=2026, log=print):
    """games: the page's game dicts (gid = the two teams, sorted, joined by '-'); legs: every leg the page can track (pl, tm, g, gl)."""
    F = SG.Finals(IN, season); out = {}; week = int(week); notes = []
    known = {k for (_, k, _) in F.stats} | {k for (_, k, _) in F.snaps}
    by_game = {}
    for l in legs:
        if l.get("gl") or not l.get("pl") or not l.get("g"): continue
        by_game.setdefault(l["g"], {})[l["pl"]] = l.get("tm")
    for g in games:
        gid = g["gid"]; fg = F.game(week, gid)
        if not fg: continue
        rec = {"sc": {fg["a"]: int(fg["sa"]), fg["h"]: int(fg["sh"])}}
        both = (fg["a"], fg["h"])
        if any((week, t) not in F.statteams for t in both):
            out[gid] = rec; notes.append(f"{gid}: no stat lines yet"); continue
        off = [t for t in both if int(round(F.points.get((week, t), 0))) != rec["sc"][t]]
        if off:
            out[gid] = rec; notes.append(f"{gid}: the stat file's points for {'/'.join(off)} do not add up to the final score - box left to ESPN"); continue
        box, dnp = {}, []
        for pl, tm in sorted(by_game.get(gid, {}).items()):
            r = F.player(pl, {"tm": tm}, week, fg)
            if isinstance(r, dict): box[pl] = [int(r.get(k, 0)) if float(r.get(k, 0)).is_integer() else r.get(k, 0) for k in FIELDS]
            elif r == "dnp" and SG.pkey(pl) in known: dnp.append(pl)      # "did not play" only for a name these files know from another week: a name they spell differently is left ungraded, never voided
        rec["box"] = box
        if dnp: rec["dnp"] = dnp
        out[gid] = rec
    n = sum(1 for v in out.values() if "box" in v)
    log(f"finals: {len(out)} finished game(s) this week, {n} with a trusted box score" + ("; " + "; ".join(notes) if notes else ""))
    return out


if __name__ == "__main__":
    import json
    IN = os.path.join(HERE, "in"); D = json.load(open(os.path.join(HERE, "out", "builder_data.json")))
    if "--refresh" in sys.argv: refresh(IN, 2026, D["week"])
    fb = build(IN, D["week"], D["games"], D["legs"])
    for gid, v in fb.items(): print(gid, v["sc"], len(v.get("box", {})), "players", v.get("dnp", []))
