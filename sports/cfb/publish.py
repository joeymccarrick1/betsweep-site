"""College football: the postseason board the site will draw (conference title games, bowls, the playoff), as one file - cfb/board.json.

Owner 11/22: college football means "Post season game lines". 11/23 1:10 AM: "get to work on the next thing which I suppose is college
football". Game lines only: Tennessee does not allow bets on individual college athletes.

THE BOOK LEADS HERE, on the evidence (sports/backtests/RESULTS.md, 2026, 751 games): DraftKings' spread missed the final margin by 11.89
points on average, our rating by 13.29; taking the rating's side against the spread went 352-389. So every game shows the posted line
first - what it implies each side scores - and our rating beside it as a second opinion that is tracked, never a pick.

Where the numbers come from:
  the line, kickoff, site, ranks, records   ESPN's scoreboard, from the feeds-sports job's own mirror (cfb/scoreboard.json). The line is the
                                             book ESPN names (DraftKings); the spread there is the home side's (negative = home favored).
  every final score this season             sportsdataverse's public ESPN schedule file, one small CSV fetched on every run, plus any final
                                             in the mirror that the file does not have yet
  our rating                                sports/cfb/model.py, unchanged from the 11/15 groundwork: the schedule-adjusted grid on points
                                             (league x home x OFFENSE[team] x DEFENSE-ALLOWED[opponent]) -> each side's expected points

Which games: the ones ESPN marks as postseason, or names as a championship, bowl or playoff game. A game whose teams are not decided yet
is listed by name, date and site, with no numbers.

    python3 -m sports.cfb.publish --feeds DIR --out DIR [--data DIR] [--now ISO]
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess

import numpy as np
import pandas as pd
from scipy import stats

from ..core import ratings as R
from . import data as CD, model as CM

FORMAT = 1
POSTSEASON = re.compile(r"championship|bowl|playoff|semifinal|quarterfinal|first round|national", re.I)
TEST = {"season": 2026, "games": 751, "book_miss": 11.89, "model_miss": 13.29, "book_total_miss": 12.25, "model_total_miss": 12.87,
        "ats": [352, 389], "checked": "2026-11-15"}        # sports/backtests/RESULTS.md, quoted on the page so the reader knows which number to trust


def when(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def ct(ts):
    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo("America/Chicago")
    except Exception:
        z = dt.timezone(dt.timedelta(hours=-6))
    d = ts.astimezone(z)
    return f"{d.strftime('%a')} {d.month}/{d.day} {d.strftime('%I:%M %p').lstrip('0')}"


def season_of(now):
    return now.year if now.month >= 7 else now.year - 1


def fetch(folder, season):
    """this season's schedule file, fetched fresh (it is small); a copy that cannot be refreshed is used as it is"""
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"cfb_schedule_{season}.csv")
    tmp = dest + ".new"
    try:
        r = subprocess.run(["curl", "-sSLf", "--max-time", "120", "-o", tmp, CD.SOURCES["schedule"].format(season=season)], timeout=150)
        if r.returncode == 0 and os.path.getsize(tmp) > 20000:
            os.replace(tmp, dest)
            return "fetched"
    except Exception:
        pass
    return "kept the copy on disk" if os.path.exists(dest) else "missing"


def games_frame(folder, season, events):
    """every final this season: the schedule file, plus finals the mirror has that the file does not (the file can be a day behind)"""
    g = CD.load_games([season], folder)
    have = set(g["game_id"].astype(str))
    add = []
    for e in events or []:
        if e.get("state") != "post" or not e.get("done") or str(e.get("id")) in have:
            continue
        t = {x.get("ha"): x for x in e.get("teams") or []}
        try:
            add.append({"season": season, "week": e.get("week"), "season_type": e.get("stype"), "date": pd.Timestamp(when(e["date"])).tz_convert(None), "game_id": int(e["id"]),
                        "neutral": bool(e.get("neutral")), "home_id": int(t["home"]["id"]), "away_id": int(t["away"]["id"]), "home_team": t["home"].get("name"),
                        "away_team": t["away"].get("name"), "home_score": float(t["home"]["score"]), "away_score": float(t["away"]["score"])})
        except Exception:
            continue
    if add:
        g = pd.concat([g, pd.DataFrame(add)], ignore_index=True).sort_values(["date", "game_id"], kind="stable").reset_index(drop=True)
    return g, len(add)


def abbreviations(folder, season, events):
    """{team id: short code} for the lists of past results - from the schedule file and the mirror (best effort: a team without one keeps its name)"""
    out = {}
    try:
        raw = pd.read_csv(os.path.join(folder, f"cfb_schedule_{season}.csv"), usecols=["home_id", "away_id", "home_abbreviation", "away_abbreviation"], low_memory=False)
        for side in ("home", "away"):
            out.update({int(i): str(a) for i, a in zip(raw[side + "_id"], raw[side + "_abbreviation"]) if pd.notna(i) and pd.notna(a)})
    except Exception:
        pass
    for e in events or []:
        for x in e.get("teams") or []:
            try:
                if x.get("abbr") and str(x["abbr"]).upper() != "TBD":
                    out[int(x["id"])] = str(x["abbr"])
            except Exception:
                continue
    return out


def fit(g):
    """the grid as model.ratings_table fits it, kept with its team index so any two teams can be asked about"""
    P = CM.PARAMS
    fbs = CM.fbs_sets(g)
    t = CM.team_rows(g, fbs)
    codes = sorted(set(t["team"]) | set(t["opp"]) | {CM.LOWER})
    idx = {c: i for i, c in enumerate(codes)}
    asof = t["date"].max() + pd.Timedelta(days=1)
    w = R.decay_weights((asof - t["date"]).dt.days.values, P["half_life"])
    gr = R.fit_grid(t["team"].map(idx).values, t["opp"].map(idx).values, t["pts"].clip(upper=P["cap"]).values, len(idx), home=t["home"].values, w=w, k_games=P["k_games"])
    return gr, idx, fbs


def ranks(vals, low_is_first=False):
    """{key: [rank, value]} - rank 1 = the highest value (or the lowest, for points allowed)"""
    order = sorted(vals, key=lambda k: vals[k], reverse=not low_is_first)
    return {k: [i + 1, round(float(vals[k]), 2)] for i, k in enumerate(order)}


def build(folder, feeds, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    season = season_of(now)
    try:
        sb = json.load(open(os.path.join(feeds, "cfb", "scoreboard.json"), encoding="utf-8"))
    except Exception:
        sb = None
    events = (sb or {}).get("events") or []
    checks = []
    if sb is None:
        checks.append("ESPN's scoreboard was not in reach: no games can be listed")
    g, added = games_frame(folder, season, events)
    gr, idx, fbs = fit(g)
    cur = fbs.get(season, set())
    L, H, sd = float(gr["L"]), float(gr["H"]), float(CM.PARAMS["sd_margin"])
    code = lambda tid: idx[tid if tid in cur else CM.LOWER]
    off = ranks({t: L * gr["O"][idx[t]] for t in cur})
    dfn = ranks({t: L * gr["D"][idx[t]] for t in cur}, low_is_first=True)
    net = ranks({t: L * (gr["O"][idx[t]] - gr["D"][idx[t]]) for t in cur})
    cs = g[g["season"] == season]
    ab = abbreviations(folder, season, events)

    def team_block(x):
        tid = int(x["id"])
        mine = cs[(cs["home_id"] == tid) | (cs["away_id"] == tid)].sort_values("date")
        rows = []
        for _, r in mine.iterrows():
            home = int(r["home_id"]) == tid
            pf, pa = (r["home_score"], r["away_score"]) if home else (r["away_score"], r["home_score"])
            oid = int(r["away_id"] if home else r["home_id"])
            rows.append({"d": str((r["date"] - pd.Timedelta(hours=6)).date()), "opp": ab.get(oid) or str(r["away_team"] if home else r["home_team"]), "ha": "vs" if (home or r["neutral"]) else "at", "home": bool(home and not r["neutral"]),
                         "pf": int(pf), "pa": int(pa), "res": "W" if pf > pa else ("L" if pf < pa else "T")})
        n = len(rows)
        streak = 0
        for r in reversed(rows):
            if r["res"] == (rows[-1]["res"] if rows else None):
                streak += 1
            else:
                break
        return {"id": str(tid), "abbr": x.get("abbr"), "name": x.get("name"), "short": x.get("short") or x.get("abbr"), "color": x.get("color"), "alt": x.get("alt"),
                "rank": x.get("rank"), "record": x.get("record"), "games": n, "fbs": tid in cur,
                "ppg": round(sum(r["pf"] for r in rows) / n, 1) if n else None, "papg": round(sum(r["pa"] for r in rows) / n, 1) if n else None,
                "off": off.get(tid), "def": dfn.get(tid), "net": net.get(tid), "streak": (rows[-1]["res"] + str(streak)) if rows else None, "last": rows[-5:][::-1]}

    games, tbd, teams = [], [], {}
    for e in sorted(events, key=lambda e: (str(e.get("date")), str(e.get("id")))):
        notes = [str(n) for n in (e.get("note") or []) if n]
        if e.get("stype") != 3 and not any(POSTSEASON.search(n) for n in notes):
            continue
        ko = when(e.get("date"))
        if not ko:
            continue
        t = {x.get("ha"): x for x in e.get("teams") or []}
        name = notes[0] if notes else (e.get("name") or "Postseason game")
        head = {"id": str(e.get("id")), "name": name, "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "koct": ct(ko), "venue": e.get("venue"), "neutral": bool(e.get("neutral")), "tv": e.get("tv") or []}
        known = [x for x in t.values() if x and str(x.get("abbr") or "").upper() not in ("TBD", "") and str(x.get("id") or "").lstrip("-").isdigit() and int(x["id"]) > 0]
        if len(known) < 2 or "home" not in t or "away" not in t:
            tbd.append(dict(head, known=[x.get("abbr") for x in known]))
            continue
        hid, aid = int(t["home"]["id"]), int(t["away"]["id"])
        hs = 0 if e.get("neutral") else 1
        eh, ea = float(R.expect(gr, code(hid), code(aid), hs)), float(R.expect(gr, code(aid), code(hid), -hs))
        model = {"home": round(eh, 1), "away": round(ea, 1), "margin": round(eh - ea, 1), "total": round(eh + ea, 1), "p_home": round(float(stats.norm.sf(0, loc=eh - ea, scale=sd)), 4)}
        o = e.get("odds") or {}
        line = mkt = None
        if isinstance(o.get("spread"), (int, float)) and isinstance(o.get("total"), (int, float)):
            sp, tot = float(o["spread"]), float(o["total"])
            line = {"by": "DraftKings" if str(o.get("by")).replace(" ", "").lower() == "draftkings" else o.get("by"), "details": o.get("details"), "spread": sp, "total": tot}
            mkt = {"home": round((tot - sp) / 2, 1), "away": round((tot + sp) / 2, 1), "margin": round(-sp, 1), "total": tot, "p_home": round(float(stats.norm.sf(0, loc=-sp, scale=sd)), 4)}
        elif o.get("details") or isinstance(o.get("total"), (int, float)):
            line = {"by": o.get("by"), "details": o.get("details"), "spread": o.get("spread"), "total": o.get("total")}
        for side in ("home", "away"):
            teams[t[side]["abbr"]] = team_block(t[side])
        if hid not in cur or aid not in cur:
            checks.append(f"{name}: a team with too few games this season to rate on its own is rated as an average lower-division side")
        sc = None
        if e.get("state") in ("in", "post"):
            try:
                sc = {"home": int(t["home"]["score"]), "away": int(t["away"]["score"])}
            except Exception:
                sc = None
        games.append(dict(head, key=f"{t['away']['abbr']}-{t['home']['abbr']}", home=t["home"]["abbr"], away=t["away"]["abbr"], state=e.get("state"), detail=e.get("detail"), score=sc,
                          stype=e.get("stype"), week=e.get("week"), line=line, mkt=mkt, model=model,
                          gap=({"margin": round(model["margin"] - mkt["margin"], 1), "total": round(model["total"] - mkt["total"], 1)} if mkt else None)))
    last = cs["date"].max() if len(cs) else None
    return {"sport": "cfb", "format": FORMAT, "built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "season": season, "data_through": str(last)[:10] if last is not None else None,
            "played": int(len(cs)), "from_mirror": added, "espn_at": (sb or {}).get("mirrored"), "home_edge": round(H, 3), "league_points": round(L, 2), "sd_margin": sd, "n_teams": len(cur),
            "test": TEST, "checks": checks, "games": games, "tbd": tbd, "teams": teams}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--feeds", required=True); ap.add_argument("--out", required=True); ap.add_argument("--data"); ap.add_argument("--now")
    ap.add_argument("--prev", help="the branch as the last run left it (default: prev/ beside --out, where the feeds-sports job puts it)")
    ap.add_argument("--site", help="a checkout of the live site, for the board it has published (default: the folder --out is in)")
    ap.add_argument("--no-grade", action="store_true", help="write the board only: no lock, no grading (local work)")
    a, _ = ap.parse_known_args()
    now = when(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    folder = a.data or CD.data_dir()
    how = fetch(folder, season_of(now))
    b = build(folder, a.feeds, now)
    b["schedule_file"] = how
    path = os.path.join(a.out, "cfb", "board.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(b, open(path + ".tmp", "w"), separators=(",", ":")); os.replace(path + ".tmp", path)
    print(f"cfb board: {len(b['games'])} postseason game(s) with both teams known ({sum(1 for x in b['games'] if x['mkt'])} with a posted line), {len(b['tbd'])} still to be decided; "
          f"{b['played']} finals this season through {b['data_through']} ({b['from_mirror']} from the mirror; schedule file {how}); {b['n_teams']} teams rated; "
          f"{len(b['checks'])} check note(s){': ' + ' | '.join(b['checks'])[:300] if b['checks'] else ''}; {os.path.getsize(path) // 1024} KB")
    if not a.no_grade:
        # lock and grade (sports/cfb/grade.py), on every run. The board is already written, so nothing here can cost it.
        try:
            from . import grade as G
            root = os.path.dirname(os.path.abspath(a.out))
            rd = lambda p: G.load(p)
            boards = [("the feed", b), ("the feed, one run earlier", rd(os.path.join(a.prev or os.path.join(root, "prev"), "cfb", "board.json"))),
                      ("the published page", rd(os.path.join(a.site or root, "cfb", "board.json")))]
            G.run(os.path.join(a.out, "cfb"), boards, scoreboard=rd(os.path.join(a.feeds, "cfb", "scoreboard.json")), now=now)
        except Exception as e:
            print(f"cfb grade: FAILED ({type(e).__name__}: {e}) - the board above is unaffected")


if __name__ == "__main__":
    main()
