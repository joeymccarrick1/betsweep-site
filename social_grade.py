#!/usr/bin/env python3
"""social_grade.py - grade Social posts for the record (alpha plan step 2, 11/16).

Reads open, ungraded posts with the site's public key, grades each from the same finals the receipts use (nflverse weekly player
stats + the schedule's final scores; snap counts tell "played and did nothing" from "did not play"), and - only with --write AND
FEED_GRADE_SECRET in the environment - records the results through the database's feed_grade(). Without both it is a dry run: it
reads, reports and changes nothing. The secret is never printed.

A post is graded only when the result is certain:
  lost   one leg missed (whatever the other legs did)                units -1
  won    every leg hit                                                units = profit on one unit at the posted price
  push   every leg pushed                                             units 0
  left   anything else - a game not final, stats not published yet, a player who did not play (the book voids that leg and
         re-prices the slip at a price this job does not know), a First TD or longest-reception leg, a market it does not know.
         Left posts are reported with the reason and picked up again on the next run. Nothing is guessed.

  python3 social_grade.py                       dry run against the live database, files from ./in
  python3 social_grade.py --fetch               download fresh nflverse files into ./in first (the scheduled job does)
  python3 social_grade.py --write               record results (needs FEED_GRADE_SECRET)
  python3 social_grade.py --check               does the database accept FEED_GRADE_SECRET? (sends an empty list; writes nothing)
  python3 social_grade.py --probe               read-only: which Social scripts the database has had, and how much is in it (counts only)
  python3 social_grade.py --posts FILE.json     grade posts from a file instead of the database (tests)
"""
import argparse, csv, json, math, os, re, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ALIAS = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download/"
YARDS = {"Passing Yards": ("pass",), "Rushing Yards": ("rush",), "Receiving Yards": ("recy",), "Receptions": ("rec",), "Rush + Rec Yards": ("rush", "recy")}


def pkey(n):
    """the same name key the promo grader uses (home._pkey)"""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", str(n).lower().replace(".", "")))).strip()
def team(x): x = str(x or "").upper().strip(); return ALIAS.get(x, x)
def jsround(x): return math.floor(float(x) + 0.5)          # the page rounds lines with Math.round; Python's round() rounds halves to even
def num(x):
    try: return float(x or 0)
    except Exception: return 0.0


class Finals:
    """final scores, player stat lines and snap rows for one season, keyed by week"""
    def __init__(self, IN, season=None):
        self.games, self.stats, self.statteams, self.snaps, self.snapteams = {}, {}, set(), {}, set()
        with open(os.path.join(IN, "games.csv"), newline="") as f: rows = list(csv.DictReader(f))
        self.season = int(season or max(int(r["season"]) for r in rows if r.get("game_type") == "REG" and r.get("home_score") not in ("", None, "NA")))
        for r in rows:
            if int(r["season"]) != self.season or r.get("game_type") != "REG" or r.get("home_score") in ("", None, "NA") or r.get("away_score") in ("", None, "NA"): continue
            a, h = team(r["away_team"]), team(r["home_team"])
            self.games.setdefault(int(r["week"]), {})[frozenset((a, h))] = {"a": a, "h": h, "sa": num(r["away_score"]), "sh": num(r["home_score"])}
        p = os.path.join(IN, f"stats_player_week_{self.season}.csv")
        if os.path.exists(p):
            with open(p, newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("season_type", "REG") != "REG" or not r.get("player_display_name"): continue
                    w, t = int(r["week"]), team(r.get("team") or r.get("recent_team"))
                    self.stats[(w, pkey(r["player_display_name"]), t)] = {"pass": num(r.get("passing_yards")), "ptd": num(r.get("passing_tds")), "rush": num(r.get("rushing_yards")), "rtd": num(r.get("rushing_tds")),
                                                                         "rec": num(r.get("receptions")), "recy": num(r.get("receiving_yards")), "ctd": num(r.get("receiving_tds"))}
                    self.statteams.add((w, t))
        p = os.path.join(IN, f"snap_counts_{self.season}.csv")
        if os.path.exists(p):
            with open(p, newline="") as f:
                for r in csv.DictReader(f):
                    if r.get("game_type", "REG") != "REG" or not r.get("player"): continue
                    w, t = int(r["week"]), team(r.get("team"))
                    k = (w, pkey(r["player"]), t); self.snaps[k] = self.snaps.get(k, 0) + num(r.get("offense_snaps")) + num(r.get("st_snaps")); self.snapteams.add((w, t))

    def game(self, week, gid):
        ts = [team(x) for x in str(gid or "").split("-")]
        return self.games.get(week, {}).get(frozenset(ts)) if len(ts) == 2 else None

    def player(self, name, leg, week, g):
        """his stat line in THIS game: a dict / 'dnp' / ('unknown', why). The player must be on one of the two teams in the leg's game,
        so two players who share a name are never mixed up."""
        k = pkey(name); both = (g["a"], g["h"]); have = [t for t in both if (week, k, t) in self.stats]
        if len(have) == 2: have = [t for t in have if t == team(leg.get("tm"))]
        if len(have) == 1: return self.stats[(week, k, have[0])]
        if any((week, t) not in self.statteams for t in both): return ("unknown", "stats not published yet")
        played = [t for t in both if self.snaps.get((week, k, t), 0) > 0]
        if played: return {"pass": 0.0, "ptd": 0.0, "rush": 0.0, "rtd": 0.0, "rec": 0.0, "recy": 0.0, "ctd": 0.0}     # on the field, nothing in the box
        if any((week, t) not in self.snapteams for t in both): return ("unknown", "snap counts not published yet")
        return "dnp"


def grade_leg(l, week, F):
    """'hit' / 'miss' / 'push' / ('unknown', why) - the page's gradeLeg() for a finished week, minus its guesses"""
    m = str(l.get("m") or "")
    if m.startswith("Under "):                                # unders: the other side of the (X+1)+ over
        r = grade_leg(dict(l, m=m[6:], ln=math.floor(num(l.get("ln"))) + 1), week, F)
        return {"hit": "miss", "miss": "hit"}.get(r, r) if isinstance(r, str) else r
    g = F.game(week, l.get("g"))
    if not g: return ("unknown", "game not final")
    if l.get("gl"):
        x = l["gl"]; ln = num(l.get("ln")); tot = g["sa"] + g["sh"]
        if x.get("k") != "M":
            if tot == ln: return "push"
            return "hit" if (tot > ln) == (str(x.get("side")).upper() == "OVER") else "miss"
        s = team(x.get("side"))
        if s not in (g["a"], g["h"]): return ("unknown", "game line names a team that is not in the game")
        d = (g["sa"] - g["sh"] if s == g["a"] else g["sh"] - g["sa"]) + (0 if m == "Moneyline" else ln)
        return "hit" if d > 0 else "push" if d == 0 else "miss"
    if m == "First TD": return ("unknown", "first-touchdown legs are not graded by this job")
    if m == "Longest Reception": return ("unknown", "longest-reception legs are not graded by this job")
    names = [n.strip() for n in re.split(r"\s+or\s+", str(l.get("pl") or "")) if n.strip()] if m == "Either TD" else [str(l.get("pl") or "")]
    rows = [F.player(n, l, week, g) for n in names]
    tds = lambda r: r["rtd"] + r["ctd"]
    if m == "Either TD":
        if any(isinstance(r, dict) and tds(r) >= 1 for r in rows): return "hit"
        bad = [r for r in rows if not isinstance(r, dict)]
        return "miss" if not bad else ("unknown", "did not play (the book voids the leg)") if "dnp" in bad else bad[0]
    r = rows[0]
    if r == "dnp": return ("unknown", "did not play (the book voids the leg)")
    if not isinstance(r, dict): return r
    if m == "Passing TDs": return "hit" if r["ptd"] >= jsround(num(l.get("ln"))) else "miss"
    if m.endswith("TD"): return "hit" if tds(r) >= (2 if m == "2+ TD" else 3 if m == "3+ TD" else 1) else "miss"
    if m in YARDS: return "hit" if sum(r[c] for c in YARDS[m]) >= jsround(num(l.get("ln"))) else "miss"
    return ("unknown", "a market this job does not grade: " + m[:40])


def grade_post(p, F):
    """(result, units, why_left)"""
    try: week = int(p.get("week"))
    except Exception: return (None, None, "no week on the post")
    res = [grade_leg(l, week, F) for l in (p.get("legs") or []) if isinstance(l, dict)]
    if not res: return (None, None, "no legs")
    if "miss" in res: return ("lost", -1.0, None)
    if all(r == "hit" for r in res):
        o = p.get("fd_odds")
        if not o or abs(o) < 100: return (None, None, "no price on the post")
        return ("won", round(o / 100.0 if o > 0 else 100.0 / abs(o), 2), None)
    if all(r == "push" for r in res): return ("push", 0.0, None)
    why = sorted({r[1] for r in res if isinstance(r, tuple)} | ({"a leg pushed (the book re-prices the slip)"} if "push" in res else set()))
    return (None, None, "; ".join(why))


# ---- the database, through its public REST address --------------------------------------------------------------------------------
def _cfg():
    sys.path.insert(0, HERE)
    import account
    return account.SUPABASE_URL, account.SUPABASE_ANON

def rest(path, params=None, body=None, head=False, prefer=None):
    url, key = _cfg(); u = url + "/rest/v1/" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    hd = {"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if prefer: hd["Prefer"] = prefer
    req = urllib.request.Request(u, data=json.dumps(body).encode() if body is not None else None, headers=hd, method="HEAD" if head else "POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read(); return {"ok": True, "data": json.loads(raw) if raw else None, "range": r.headers.get("Content-Range")}
    except urllib.error.HTTPError as e:
        try: msg = json.loads(e.read() or b"{}").get("message") or ""
        except Exception: msg = ""
        return {"ok": False, "status": e.code, "error": str(msg)[:200]}
    except Exception as e:
        return {"ok": False, "status": 0, "error": type(e).__name__ + ": " + str(e)[:160]}

def count(table, params):
    r = rest(table, dict(params, select="*"), head=True, prefer="count=exact")
    try: return int(str(r.get("range")).split("/")[-1]) if r["ok"] else None
    except Exception: return None

def probe():
    """read-only: what the database has, in counts and yes/no only"""
    r0 = rest("feed_posts", {"select": "id", "limit": 1})
    if not r0["ok"]: return {"reachable": False, "error": f"HTTP {r0.get('status')}: {r0.get('error')}"}     # say nothing about the rest: unknown is not "no"
    out = {"reachable": True}
    out["v3_people_and_grades"] = rest("feed_posts", {"select": "id,result,units,tails,rx", "limit": 1})["ok"]
    out["v4_usernames_and_avatars"] = rest("feed_profiles", {"select": "user_id,emoji,handle_changed_at", "limit": 1})["ok"]
    out["open_posts"] = count("feed_posts", {"status": "eq.open"})
    out["graded_posts"] = count("feed_posts", {"status": "eq.open", "result": "not.is.null"}) if out["v3_people_and_grades"] else None
    out["profiles"] = count("feed_profiles", {}) if out["v3_people_and_grades"] else None
    out["tails"] = count("feed_tails", {}) if out["v3_people_and_grades"] else None
    out["reactions"] = count("feed_reactions", {}) if out["v3_people_and_grades"] else None
    out["follows"] = count("feed_follows", {}) if out["v3_people_and_grades"] else None
    r = rest("feed_posts", {"select": "week", "status": "eq.open", "limit": 1000})
    if r["ok"]:
        by = {}
        for x in r["data"] or []: by[x.get("week")] = by.get(x.get("week"), 0) + 1
        out["open_posts_by_week"] = {str(k): by[k] for k in sorted(by, key=lambda v: (v is None, v))}
    return out

def check_secret(secret):
    """does the database accept this secret? An empty list of results is sent, so nothing can be written either way."""
    if not secret: return (False, "FEED_GRADE_SECRET is not set in this run")
    r = rest("rpc/feed_grade", body={"p_secret": secret, "p_rows": []})
    if r["ok"]: return (True, "the database accepted the secret; nothing was written (an empty list was sent)")
    if r.get("status") == 0: return (False, f"could not reach the database ({r.get('error')})")
    return (False, f"the database REFUSED the secret (HTTP {r.get('status')}: {r.get('error')}) - the value in GitHub is not the one in the database")

def fetch(IN, season):
    import subprocess
    for name, path in (("games.csv", "schedules/games.csv"), (f"stats_player_week_{season}.csv", f"stats_player/stats_player_week_{season}.csv"), (f"snap_counts_{season}.csv", f"snap_counts/snap_counts_{season}.csv")):
        tmp = os.path.join(IN, name + ".part")
        try:
            subprocess.run(["curl", "-fsSL", "--max-time", "120", "-o", tmp, NFLVERSE + path], check=True)
            if os.path.getsize(tmp) > 1000: os.replace(tmp, os.path.join(IN, name))
        except Exception as e:
            print(f"note: could not download {name} ({type(e).__name__}); using the copy on hand" if os.path.exists(os.path.join(IN, name)) else f"note: could not download {name} and there is no copy on hand")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in", dest="IN", default=os.path.join(HERE, "in")); ap.add_argument("--season", type=int); ap.add_argument("--week", type=int)
    ap.add_argument("--posts"); ap.add_argument("--fetch", action="store_true"); ap.add_argument("--write", action="store_true"); ap.add_argument("--probe", action="store_true")
    ap.add_argument("--check", action="store_true", help="only ask the database whether it accepts FEED_GRADE_SECRET (sends an empty list; writes nothing)")
    ap.add_argument("--detail", action="store_true", help="print every leg with its grade and the numbers behind it (legs only - no usernames, titles or ids of people)")
    a = ap.parse_args(); S = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if a.check:
        ok, msg = check_secret(os.environ.get("FEED_GRADE_SECRET") or ""); S["secret_ok"] = ok; S["result"] = msg
        print(msg); print("SOCIALGRADE " + json.dumps(S, separators=(",", ":"))); return 0 if ok else 1
    if a.probe:
        S["probe"] = probe(); print("SOCIALGRADE " + json.dumps(S, separators=(",", ":"))); return 0 if S["probe"].get("reachable") else 1
    if a.fetch:
        os.makedirs(a.IN, exist_ok=True)
        season = a.season
        if not season:
            try: season = Finals(a.IN).season
            except Exception: season = time.gmtime().tm_year - (1 if time.gmtime().tm_mon < 3 else 0)
        fetch(a.IN, season)
    F = Finals(a.IN, a.season); S["season"] = F.season; S["weeks_with_finals"] = sorted(F.games)
    if a.posts: posts = json.load(open(a.posts))
    else:
        # newest first, so old posts that can never be graded (a First TD leg, a man who did not play) cannot crowd new ones out of the 1,000
        q = {"select": "id,week,legs,fd_odds,last_ko", "status": "eq.open", "result": "is.null", "last_ko": "lt." + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "order": "id.desc", "limit": 1000}
        if a.week: q["week"] = f"eq.{a.week}"
        r = rest("feed_posts", q)
        if not r["ok"]:
            S["result"] = ("the database has not had sql/social_v3.sql (no result column); nothing to do" if "result" in r.get("error", "") else f"could not read posts (HTTP {r.get('status')}: {r.get('error')})")
            print(S["result"]); print("SOCIALGRADE " + json.dumps(S, separators=(",", ":"))); return 0 if "result" in r.get("error", "") else 1
        posts = r["data"] or []
    if a.week: posts = [p for p in posts if p.get("week") == a.week]
    rows, left = [], {}
    for p in posts:
        res, units, why = grade_post(p, F)
        if a.detail:
            print(f"post {p.get('id')} wk{p.get('week')} {len(p.get('legs') or [])} leg(s) at {p.get('fd_odds')}: {res or 'LEFT - ' + str(why)}")
            for l in p.get("legs") or []:
                try:
                    wk = int(p.get("week")); lr = grade_leg(l, wk, F); g = F.game(wk, l.get("g")); had = ""
                    if g and l.get("gl"): had = f"final {g['a']} {g['sa']:.0f} {g['h']} {g['sh']:.0f}"
                    elif g and isinstance(lr, str):
                        prs = [F.player(n.strip(), l, wk, g) for n in re.split(r"\s+or\s+", str(l.get("pl") or ""))]      # not "rows": that is the list of results being built
                        had = " / ".join(", ".join(f"{k} {v:g}" for k, v in x.items() if v) or "zero in every counted stat" if isinstance(x, dict) else str(x) for x in prs)
                    print(f"    {lr if isinstance(lr, str) else 'unknown: ' + lr[1]:8} {l.get('pl')} | {l.get('m')} | {l.get('ln')} | {l.get('g')}" + (f"   [{had}]" if had else ""))
                except Exception as e: print("    (could not explain this leg:", type(e).__name__, ")")
        if res: rows.append({"id": p["id"], "result": res, "units": units})
        else: left.setdefault(why, []).append(p.get("id"))
    S.update(posts=len(posts), won=sum(r["result"] == "won" for r in rows), lost=sum(r["result"] == "lost" for r in rows), push=sum(r["result"] == "push" for r in rows),
             left=sum(len(v) for v in left.values()), left_why={k: len(v) for k, v in sorted(left.items())})
    print(f"{len(posts)} ungraded post(s) read; graded {len(rows)}: {S['won']} won, {S['lost']} lost, {S['push']} push; left {S['left']}")
    for k, v in sorted(left.items()): print(f"  left ({len(v)}): {k}  [post ids {', '.join(str(i) for i in v[:12])}{' ...' if len(v) > 12 else ''}]")
    secret = os.environ.get("FEED_GRADE_SECRET") or ""
    if a.posts: S["result"] = "graded from a file; nothing written"; S["rows"] = rows
    elif not a.write or not secret:
        S["result"] = "dry run: nothing written" + ("" if a.write is False else " (FEED_GRADE_SECRET is not set)")
    elif not rows: S["result"] = "nothing to write"
    else:
        n = 0; ok = True
        for i in range(0, len(rows), 200):
            r = rest("rpc/feed_grade", body={"p_secret": secret, "p_rows": rows[i:i + 200]})
            if not r["ok"]: ok = False; S["result"] = f"feed_grade refused the write (HTTP {r.get('status')}: {r.get('error')}); {n} row(s) written before that"; break
            n += int(r["data"] or 0)
        if ok: S["result"] = f"wrote {n} of {len(rows)} result(s)"
        S["written"] = n
    print(S["result"]); print("SOCIALGRADE " + json.dumps(S, separators=(",", ":")))
    return 0 if not S["result"].startswith("feed_grade refused") else 1

if __name__ == "__main__": sys.exit(main())
