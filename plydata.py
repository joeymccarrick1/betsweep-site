#!/usr/bin/env python3
"""plydata.py - one per-player view of the season for the Players, Usage and Who Benefits pages (owner 10/30: "I love all of these
let's try and do them all"). Nothing here changes a projection; it only re-reads what the build already has.

Sources (all already on disk after Steps 2-3):
  in/stats_player_week_<season>.csv   nflverse weekly player stats (downloaded by build_snaps.py / build_trade.py; re-downloaded here if
                                      missing) - targets, carries, yards, TDs, target share, PPR points
  in/snap_counts_<season>.csv         nflverse snap counts (offense_pct per player-week; build_snaps.py)
  in/injuries_<season>.csv            nflverse weekly injury report (build_snaps.py)
  out/builder_data.json               this week's priced legs (build_builder.py): lines, prices, model %, flags, matchup ranks

    P = load(HERE)
    P.week                  this week's number (the builder's)
    P.players               {key: {"name","pos","team","games":[row...],"legs":[...],"status":(report, practice, injury)|None,"slug"}}
    P.team_weeks[team]      sorted weeks the team has played (final games in the stats file)
    P.usage(key, weeks)     averages over the given weeks the player PLAYED: snap%, targets, carries, tgt share, carry share, ppr
    P.slug(name)            url slug used by /player/<slug>/
Keys are "<normalized name>|<team>" so two players with one name on different teams stay apart. A traded player keeps one key per
team; the page uses the current team (the most recent game, or this week's leg team).
"""
import csv, json, os, re, collections, urllib.request

POS = ("QB", "RB", "WR", "TE")
TEAM = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}

def norm(s):
    s = re.sub(r"\.", "", str(s)).strip(); s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s, flags=re.I); return re.sub(r"\s+", " ", s).lower()

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")

def _t(x): x = str(x or "").strip(); return TEAM.get(x, x)

def _f(x):
    try: return float(x)
    except Exception: return 0.0

def _csv(path, url=None):
    if not os.path.exists(path) and url:
        try: urllib.request.urlretrieve(url, path)
        except Exception as e: print(f"warn: could not download {os.path.basename(path)}: {e}"); return []
    if not os.path.exists(path): return []
    with open(path, newline="") as fh: return list(csv.DictReader(fh))

class Season:
    def __init__(self, HERE, season=2026):
        IN, OUT = os.path.join(HERE, "in"), os.path.join(HERE, "out")
        NV = "https://github.com/nflverse/nflverse-data/releases/download"
        try: self.B = json.load(open(os.path.join(OUT, "builder_data.json")))
        except Exception: self.B = {"week": 0, "legs": [], "games": []}
        self.week = int(self.B.get("week") or 0)
        stats = _csv(os.path.join(IN, f"stats_player_week_{season}.csv"), f"{NV}/stats_player/stats_player_week_{season}.csv")
        snaps = _csv(os.path.join(IN, f"snap_counts_{season}.csv"), f"{NV}/snap_counts/snap_counts_{season}.csv")
        inj = _csv(os.path.join(IN, f"injuries_{season}.csv"), f"{NV}/injuries/injuries_{season}.csv")
        self.snap = {}
        for r in snaps:
            if r.get("game_type", "REG") != "REG": continue
            self.snap[(norm(r["player"]), _t(r["team"]), int(r["week"]))] = _f(r["offense_pct"])
        # team totals per week (for shares we compute ourselves: carry share; nflverse gives target share already)
        self.team_weeks = collections.defaultdict(set); tcar = collections.Counter(); ttgt = collections.Counter()
        self.opp = {}
        rows = [r for r in stats if r.get("season_type", "REG") == "REG"]
        for r in rows:
            t, w = _t(r["team"]), int(r["week"]); self.team_weeks[t].add(w); self.opp[(t, w)] = _t(r["opponent_team"])
            tcar[(t, w)] += _f(r["carries"]); ttgt[(t, w)] += _f(r["targets"])
        self.team_weeks = {t: sorted(v) for t, v in self.team_weeks.items()}
        self.players = {}
        for r in rows:
            if r["position"] not in POS: continue
            t, w = _t(r["team"]), int(r["week"]); nm = r["player_display_name"]; k = norm(nm) + "|" + t
            p = self.players.setdefault(k, {"name": nm, "pos": r["position"], "team": t, "games": [], "legs": [], "status": None, "id": r["player_id"]})
            sp = self.snap.get((norm(nm), t, w))
            p["games"].append({"w": w, "opp": _t(r["opponent_team"]), "snap": sp, "tgt": _f(r["targets"]), "rec": _f(r["receptions"]),
                               "recy": _f(r["receiving_yards"]), "car": _f(r["carries"]), "rush": _f(r["rushing_yards"]),
                               "pass": _f(r["passing_yards"]), "att": _f(r["attempts"]), "ptd": _f(r["passing_tds"]),
                               "td": _f(r["rushing_tds"]) + _f(r["receiving_tds"]), "int": _f(r["passing_interceptions"]),
                               "ts": _f(r["target_share"]) if r.get("target_share") not in ("", "NA", None) else (_f(r["targets"]) / ttgt[(t, w)] if ttgt[(t, w)] else 0.0),
                               "cs": (_f(r["carries"]) / tcar[(t, w)]) if tcar[(t, w)] else 0.0,
                               "ppr": _f(r["fantasy_points_ppr"]), "long": 0.0})
        for p in self.players.values(): p["games"].sort(key=lambda g: g["w"])
        # this week's report
        self.inj = {}
        for r in inj:
            if int(r.get("week") or 0) != self.week or r.get("game_type", "REG") != "REG": continue
            self.inj[(norm(r["full_name"]), _t(r["team"]))] = (r.get("report_status") or "", r.get("practice_status") or "", r.get("report_primary_injury") or "")
        # the model's own availability tab ('AUTO - Weekly Availability', in/avail.json) wins: it carries IR / released / ruled-out
        # players the weekly report does not, and it is what the projections use. OUT -> "Out", DOUBTFUL -> "Doubtful", QUESTIONABLE ->
        # "Questionable"; CLEARED / ACTIVE clear a stale report line.
        self.avail = {}
        try:
            av = json.load(open(os.path.join(IN, "avail.json")))["values"]; h = {c: i for i, c in enumerate(av[0])}
            for r in av[1:]:
                r = list(r) + [""] * (len(av[0]) - len(r))
                if str(r[h["Projection Week"]]).strip() != str(self.week): continue
                a = str(r[h["Availability"]]).strip().upper(); k = (norm(r[h["Player"]]), _t(r[h["Team"]]))
                why = str(r[h.get("Reason / Injury", 9)]).strip(); prac = str(r[h.get("Practice Participation", 12)]).strip()
                if a in ("OUT", "DOUBTFUL", "QUESTIONABLE"):
                    self.inj[k] = (a.title(), prac, why); self.avail[k] = a.title()
                elif a in ("CLEARED", "ACTIVE", "PLAYING"):
                    self.inj.pop(k, None)
        except Exception as e:
            print("note: availability tab not read:", e)
        # attach this week's legs (player props only) and statuses
        by = collections.defaultdict(list)
        for l in self.B.get("legs", []):
            if l.get("pos") in POS and l.get("pl"): by[(norm(l["pl"]), _t(l.get("tm")))].append(l)
        self.legname = {}
        for (n, t), ls in by.items():
            k = n + "|" + t
            if k not in self.players:   # traded / first game for the team: match on name alone if it is unique
                cands = [kk for kk in self.players if kk.split("|")[0] == n]
                if len(cands) == 1:
                    old = self.players.pop(cands[0]); old["team"] = t; self.players[k] = old
                else:
                    self.players[k] = {"name": ls[0]["pl"], "pos": ls[0]["pos"], "team": t, "games": [], "legs": [], "status": None, "id": ""}
            self.players[k]["legs"] = ls; self.players[k]["name"] = ls[0]["pl"]; self.legname[k] = ls[0]["pl"]
        for k, p in self.players.items():
            p["status"] = self.inj.get((k.split("|")[0], p["team"]))
        # slugs: name, or name-team when two players share a name
        cnt = collections.Counter(slugify(p["name"]) for p in self.players.values())
        for k, p in self.players.items():
            s = slugify(p["name"]); p["slug"] = s if cnt[s] == 1 else f"{s}-{p['team'].lower()}"
        self.games = {g["gid"]: g for g in self.B.get("games", []) if g.get("gid")}

    def game_of(self, team):
        for g in self.games.values():
            if team in (g.get("a"), g.get("b")): return g
        return None

    def played(self, key, weeks=None):
        p = self.players[key]; gs = [g for g in p["games"] if (weeks is None or g["w"] in weeks)]
        return gs

    def usage(self, key, weeks):
        gs = self.played(key, set(weeks))
        if not gs: return None
        n = len(gs); sn = [g["snap"] for g in gs if g["snap"] is not None]
        return {"n": n, "snap": (sum(sn) / len(sn)) if sn else None, "tgt": sum(g["tgt"] for g in gs) / n, "car": sum(g["car"] for g in gs) / n,
                "ts": sum(g["ts"] for g in gs) / n, "cs": sum(g["cs"] for g in gs) / n, "ppr": sum(g["ppr"] for g in gs) / n,
                "recy": sum(g["recy"] for g in gs) / n, "rush": sum(g["rush"] for g in gs) / n, "rec": sum(g["rec"] for g in gs) / n}

def load(HERE, season=2026):
    return Season(HERE, season)

if __name__ == "__main__":
    P = load(os.path.dirname(os.path.abspath(__file__)))
    withlegs = sum(1 for p in P.players.values() if p["legs"])
    print(f"week {P.week}: {len(P.players)} players, {withlegs} with legs this week, {len(P.inj)} on this week's report")
