"""Tonight's NBA board as one JSON file for the site build (owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl. I
want each sport to basically look exactly like everything we've built for NFL."; the same hour: prices - "I will upgrade but start
without prices"; the data jobs - "Yes add them").

Runs in the feeds-sports job (pandas lives there, not in the hourly site build): history from sportsdataverse, who is out and tonight's
state from the ESPN mirror the same job wrote a moment earlier. The site build (build_nba.py, plain Python) only draws what is here.

    python -m sports.nba.publish --feeds out --out out            # in the job
    BS_SPORTS_DATA=sports/_data python -m sports.nba.publish --out /tmp/x [--day 2026-11-22] [--feeds DIR]

What the file says and how each part is decided:
  day        the Central-time day being shown: a day runs 4 AM to 4 AM, so a late West-coast game stays on "tonight"
  games      tip, teams, venue, the model's team points (the model's own team total; the market's is used once prices are stored),
             ESPN's posted line when the mirror carries one (named by its provider - this is NOT FanDuel), state and score from the mirror
  players    minutes and points / rebounds / assists / threes from sports.nba.model, and the chance of each X+ rung
  who plays  everyone who played in the team's last game, PLUS a rotation player who sat it out (played 3 of the 9 before at 15+
             minutes a night) and is not listed Out or doubtful now, MINUS anyone the injury report lists as Out or whose note says
             doubtful. A questionable or probable player stays in, flagged - the NFL site's rule. The first real run (11/22) brought
             35 players "back" without the minutes bar: end-of-bench players who simply had not been used, each taking minutes from
             the rotation when the team's 240 were shared out.
             With no injury report in reach the list is last game's and the file says so ("injuries": false).
  defense    what each opponent allows to guards / forwards / centers, ranked 1 (allows the most) to 30
Nothing here is a pick: there are no prices to compare with yet, and the numbers are being graded first ("tracked, not a lead").
"""
import argparse, datetime as dt, glob, json, os, sys, urllib.request
import numpy as np
import pandas as pd
from . import data as ND, model as NM, slate as SL, positions as PS
from ..core import dist as D, legboard as LB

# the shape of board.json. build_nba.py (the page) refuses a board whose number it does not know, so the page and the file can never be half a version apart:
# raise it here and there together when a field the page reads is renamed or changes meaning.
FORMAT = 2

STAT_NAMES = {"pts": "Points", "reb": "Rebounds", "ast": "Assists", "fg3": "Threes"}
RUNGS = SL.RUNGS
CT = dt.timezone(dt.timedelta(hours=-6))   # standard time covers the whole season's winter; the day boundary is 4 AM, so an hour of DST cannot move a game to another day


def _ct_now():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/Chicago"))
    except Exception:
        return dt.datetime.now(CT)


def fetch(folder, seasons=(2026, 2027)):
    """The history files, downloaded when the folder does not hold them (the job starts empty every run)."""
    os.makedirs(folder, exist_ok=True)
    want = [(f"nba_player_box_{s}.csv", ND.SOURCES["player_box"].format(season=s)) for s in seasons] + [(f"nba_schedule_{max(seasons)}.csv", ND.SOURCES["schedule"].format(season=max(seasons)))]
    for name, url in want:
        p = os.path.join(folder, name)
        if os.path.exists(p) and os.path.getsize(p) > 10000:
            continue
        with urllib.request.urlopen(url, timeout=120) as r, open(p, "wb") as f:
            f.write(r.read())
    return folder


def _j(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def _r(x, n=1):
    return None if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))) else round(float(x), n)


def build(folder, feeds=None, day=None, now=None):
    now = now or _ct_now()
    season = 2027
    d = ND.load([2026, 2027], folder)
    sched = pd.read_csv(os.path.join(folder, f"nba_schedule_{season}.csv"), low_memory=False)
    sched = sched[sched["season_type"] == 2] if "season_type" in sched.columns else sched
    if day is None:
        day = (now - dt.timedelta(hours=4)).date()
        for _ in range(8):                      # a day with no games (Thanksgiving, Christmas Eve): the next day that has some
            if len(SL.games_on(sched, day)):
                break
            day = day + dt.timedelta(days=1)
    day = pd.Timestamp(day).date()
    games = SL.games_on(sched, day)
    cur = d[d["season"] == season]

    # ---- the ESPN mirror: who is out, and where tonight's games stand
    sb = _j(os.path.join(feeds, "nba", "scoreboard.json")) if feeds else None
    inj = _j(os.path.join(feeds, "nba", "injuries.json")) if feeds else None
    depth = _j(os.path.join(feeds, "nba", "depth.json")) if feeds else None      # ESPN's depth charts: the five positions (sports/nba/positions.py)
    ev = {str(e.get("id")): e for e in ((sb or {}).get("events") or [])}
    name_of = {}
    for _, g in games.iterrows():
        name_of[g["home_display_name"]] = g["home_abbreviation"]; name_of[g["away_display_name"]] = g["away_abbreviation"]
    listed = {}                                   # team abbreviation -> {normalised name: line}
    for x in ((inj or {}).get("injuries") or []):
        ab = name_of.get(x.get("team"))
        if ab:
            listed.setdefault(ab, {})[LB.norm_name(x.get("name"))] = x
    have_inj = inj is not None and bool((inj or {}).get("injuries"))
    def tag(x):
        """Out / Doubtful / Questionable / Probable / Day-to-day, from ESPN's status, its fantasy tag and the words of its own note."""
        st, fs, note = str(x.get("status") or "").strip().lower(), str(x.get("fs") or "").upper(), str(x.get("note") or "").lower()
        if st in ("out", "out for season", "suspension", "suspended") or fs in ("OUT", "OFS", "SUSP"): return "Out"
        for w, t in (("doubtful", "Doubtful"), ("questionable", "Questionable"), ("probable", "Probable")):
            if w in note: return t
        return "Day-to-day"
    is_out = lambda x: tag(x) in ("Out", "Doubtful")

    out_names, back_names, out_rows, back_by = [], [], {}, {}
    for _, g in games.iterrows():
        for tid, ab in ((g["home_id"], g["home_abbreviation"]), (g["away_id"], g["away_abbreviation"])):
            t = cur[(cur["team_id"] == tid) & (cur["date"] < pd.Timestamp(day))]
            lines = listed.get(ab, {})
            out_rows[ab] = [{"name": x.get("name"), "tag": tag(x), "note": (x.get("type") or ""), "why": (x.get("note") or "")[:200], "ret": x.get("ret")} for x in lines.values() if is_out(x)]
            out_names += [x.get("name") for x in lines.values() if is_out(x)]
            if t.empty or not have_inj:
                continue
            gids = list(t["game_id"].drop_duplicates())
            last, before = gids[-1], gids[-10:-1]
            played_last = set(t[(t["game_id"] == last) & t["played"]]["athlete_id"])
            prev = t[t["game_id"].isin(before) & t["played"]]
            cnt = prev.groupby("athlete_id")["game_id"].nunique()
            mpg = prev.groupby("athlete_id")["min"].mean()
            for aid, n in cnt.items():
                if aid in played_last or n < 3 or mpg.get(aid, 0) < 15:
                    continue
                nm = prev[prev["athlete_id"] == aid]["player"].iloc[-1]
                line = lines.get(LB.norm_name(nm))
                if line is not None and is_out(line):
                    continue
                back_names.append(nm); back_by.setdefault(ab, []).append(nm)

    rows, p = SL.build(d, sched, day, out=out_names, back=back_names)
    grid = NM.defense_grid(d, season)
    dgrid = {}
    for _, r in grid.iterrows():
        dgrid.setdefault(r["defense"], {})[r["vs"][0]] = {s: [int(r[s + "_rank"]), _r(r[s + "_vs_league"], 3)] for s in ("pts", "reb", "ast", "fg3")}

    # last five games' lines for each player on the board (the page shows them under his numbers)
    recent = {}
    if len(p):
        ids = set(p["athlete_id"])
        h = cur[cur["athlete_id"].isin(ids) & cur["played"] & (cur["date"] < pd.Timestamp(day))]
        for aid, x in h.groupby("athlete_id"):
            recent[aid] = [[r["date"].strftime("%m/%d"), r["opp"], int(round(r["min"])), int(r["pts"]), int(r["reb"]), int(r["ast"]), int(r["fg3"])] for _, r in x.tail(5).iterrows()]

    G, T, P = [], {}, []
    for _, g in games.iterrows():
        gid = str(int(g["game_id"])); e = ev.get(gid) or {}
        home, away = g["home_abbreviation"], g["away_abbreviation"]
        proj = {}
        for ab in (home, away):
            x = p[p["team"] == ab] if len(p) else p
            proj[ab] = _r(x["team_pts"].iloc[0], 1) if len(x) and "team_pts" in x.columns and pd.notna(x["team_pts"].iloc[0]) else None
        sc = {t.get("abbr"): t.get("score") for t in (e.get("teams") or [])}
        look = {t.get("abbr"): t for t in (e.get("teams") or [])}
        row = sched[sched["game_id"] == g["game_id"]].iloc[0]
        G.append({"id": gid, "key": f"{away}-{home}", "tip": g["tip"].isoformat(), "tipct": g["tip"].strftime("%a %-m/%d %-I:%M %p"), "home": home, "away": away,
                  "home_name": g["home_display_name"], "away_name": g["away_display_name"], "venue": (row.get("venue_full_name") if isinstance(row.get("venue_full_name"), str) else None),
                  "proj": proj, "state": e.get("state"), "detail": e.get("detail"), "score": ({home: sc.get(home), away: sc.get(away)} if e.get("state") in ("in", "post") else None),
                  "line": e.get("odds") if (e.get("odds") or {}).get("details") or (e.get("odds") or {}).get("total") else None})
        for tid, ab, opp in ((g["home_id"], home, away), (g["away_id"], away, home)):
            t = cur[(cur["team_id"] == tid) & (cur["date"] < pd.Timestamp(day))]
            last = t["date"].max() if len(t) else None
            T[ab] = {"name": g["home_display_name"] if ab == home else g["away_display_name"], "opp": opp, "home": ab == home, "games": int(t["game_id"].nunique()),
                     "rest": (None if last is None or pd.isna(last) else int((pd.Timestamp(day) - last).days)), "out": out_rows.get(ab, []), "back": sorted(back_by.get(ab, [])), "opp_def": dgrid.get(opp, {}),
                     "color": (look.get(ab) or {}).get("color"), "alt": (look.get(ab) or {}).get("alt"), "record": (look.get(ab) or {}).get("record"), "short": (look.get(ab) or {}).get("short")}
    if len(p):
        for _, r in p.sort_values(["team", "proj_min"], ascending=[True, False]).iterrows():
            line = (listed.get(r["team"], {}) or {}).get(LB.norm_name(r["player"]))
            warn = []
            if r["n"] < 5: warn.append("Fewer than 5 games this season")
            if r["proj_min"] > r["base_min"] * 1.10: warn.append(f"Minutes raised {r['proj_min'] - r['base_min']:+.1f}: his team is short-handed")
            if r["proj_min"] < r["base_min"] * 0.92: warn.append(f"Minutes trimmed {r['proj_min'] - r['base_min']:+.1f}: the rotation is fuller than in his recent games")
            lad = {}
            for s in STAT_NAMES:
                lad[s] = [[L, _r(float(D.p_at_least(L, r["proj_" + s], "qp", phi=NM.PHI[s])), 3)] for L in RUNGS[s]]
                lad[s] = [x for x in lad[s] if x[1] is not None and 0.05 <= x[1] <= 0.95]
            P.append({"id": str(int(r["athlete_id"])), "name": r["player"], "team": r["team"], "opp": r["opp"], "game": str(int(r["game_id"])), "grp": r["grp"],
                      "pos": PS.slot(depth, r["team"], str(int(r["athlete_id"])), r["grp"]), "n": int(r["n"]),
                      "min": _r(r["proj_min"]), "base_min": _r(r["base_min"]),
                      "proj": {s: _r(r["proj_" + s]) for s in STAT_NAMES}, "avg": {s: _r(r["avg_" + s]) for s in STAT_NAMES}, "l10": {s: _r(r["l10_" + s]) for s in STAT_NAMES},
                      "pra": _r(r["proj_pra"]), "ladder": lad, "warn": warn, "recent": recent.get(r["athlete_id"], []),
                      "status": (None if line is None else {"tag": tag(line), "why": (line.get("note") or "")[:200]})})
    through = cur["date"].max()
    return {"sport": "nba", "format": FORMAT, "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "day": str(day), "day_label": pd.Timestamp(day).strftime("%a %-m/%d"), "season": "2026-27",
            "data_through": None if pd.isna(through) else through.strftime("%Y-%m-%d"), "injuries": bool(have_inj), "injuries_at": (inj or {}).get("mirrored"), "scoreboard_at": (sb or {}).get("mirrored"),
            "positions_at": ((depth or {}).get("mirrored") if (depth or {}).get("teams") else None),      # when ESPN's depth charts were read; None = the rows have no five-position
            "back": sorted(set(back_names)), "stats": STAT_NAMES, "games": G, "teams": T, "players": P}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--feeds"); ap.add_argument("--out", required=True); ap.add_argument("--day"); ap.add_argument("--data")
    ap.add_argument("--prev", help="the branch as the last run left it (default: prev/ beside --out, where the feeds-sports job puts it)")
    ap.add_argument("--site", help="a checkout of the live site, for the board it has published (default: the folder --out is in)")
    ap.add_argument("--no-grade", action="store_true", help="write the board only: no lock, no grading (local work)")
    a = ap.parse_args()
    folder = fetch(a.data or ND.data_dir())
    b = build(folder, a.feeds, a.day)
    os.makedirs(os.path.join(a.out, "nba"), exist_ok=True)
    json.dump(b, open(os.path.join(a.out, "nba", "board.json"), "w"), separators=(",", ":"))
    print(f"nba board {b['day']}: {len(b['games'])} games, {len(b['players'])} players, data through {b['data_through']}, injuries {'from the mirror' if b['injuries'] else 'NOT in reach (the players of each last game)'}, "
          f"out {sum(len(t['out']) for t in b['teams'].values())}, back {len(b['back'])}; {os.path.getsize(os.path.join(a.out, 'nba', 'board.json')) // 1024} KB")
    # ---- the nightly grading (sports/nba/grade.py): lock each game's numbers at tip, grade them when its box score is final, keep the record.
    # It can never take the board down with it: any failure is printed and the board stands, the grading files as the last run left them.
    if not a.no_grade:
        try:
            from . import grade as G
            root = os.path.dirname(os.path.abspath(a.out))   # in the job: the workspace - main checked out at its top, the branch's last state in prev/
            boards = [("the feed", b), ("the feed, one run earlier", G.load(os.path.join(a.prev or os.path.join(root, "prev"), "nba", "board.json"))),
                      ("the published page", G.load(os.path.join(a.site or root, "nba", "board.json")))]
            G.run(os.path.join(a.out, "nba"), boards)
        except Exception as e:
            print(f"nba grade: FAILED and skipped ({type(e).__name__}: {e}) - the board is written; locks and record are as the last run left them")
    # ---- the Stock Market's numbers (sports/nba/stocks.py). Same rule: a failure is printed and the last run's file is kept.
    sk_path = os.path.join(a.out, "nba", "stocks.json")
    try:
        from . import stocks as NS
        s = NS.build(ND.load([2027], folder), depth=(_j(os.path.join(a.feeds, "nba", "depth.json")) if a.feeds else None))
        json.dump(s, open(sk_path + ".tmp", "w"), separators=(",", ":")); os.replace(sk_path + ".tmp", sk_path)
        print(f"nba stocks: {len(s['players'])} players through {s['data_through']}, {sum(1 for p in s['players'] if p['dir'] == 'up')} rising, {sum(1 for p in s['players'] if p['dir'] == 'dn')} falling")
    except Exception as e:
        last = os.path.join(a.prev or os.path.join(os.path.dirname(os.path.abspath(a.out)), "prev"), "nba", "stocks.json")
        kept = os.path.exists(last) and not os.path.exists(sk_path)
        if kept:
            import shutil; shutil.copy(last, sk_path)
        print(f"nba stocks: FAILED and skipped ({type(e).__name__}: {e})" + (" - the last run's file is kept" if kept else ""))


if __name__ == "__main__":
    main()
