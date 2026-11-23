"""The Premier League board for the /epl/ preview: the coming matches as the feeds-sports job writes them (epl/board.json).

Owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl. I want each sport to basically look exactly like everything
we've built for NFL."; 9:32 PM, with the NBA boards, grader and Stock Market up: "Get to what's next".

What goes in, and from where:
  matches, goals, expected goals, shots, every player's minutes and shots   the public FPL-Elo-Insights data set (sports/epl/data.py), cloned here
  kickoff times, venues, scores, the posted line, confirmed line-ups         ESPN, from this job's own mirror (epl/scoreboard.json, epl/lineups.json)
  who is injured, suspended or doubtful                                       the official Fantasy Premier League list, same mirror (epl/fpl.json)
The data set is a community one, so every fixture is checked against ESPN before it is written: a match ESPN does not list for those
two clubs within a day is left off the board and named in "checks"; ESPN's kickoff time is the one shown.

The model is the 11/15 groundwork (sports/epl/model.py), unchanged:
  teams    an attack and a defence factor for every club, fitted on a blend of expected goals and real goals with older matches counting
           less -> each side's goal rate for this match -> every score's chance -> home / draw / away, totals, both teams to score
  players  minutes when he starts x his per-90 rates (this season, pulled toward last season's) x what this opponent allows and where the
           match is -> chance to score, chance of an assist, shots, shots on target. EVERY PLAYER NUMBER IS "IF HE STARTS": the model does
           not pick line-ups. When ESPN posts the confirmed eleven (about an hour before kickoff) each player is marked in it or not.

A PREVIEW's numbers: no bookmaker price is read or compared (ESPN's posted line is carried as posted, with the book named).

    python3 -m sports.epl.publish --feeds DIR --out DIR [--data DIR] [--now ISO]
"""
import argparse, datetime as dt, json, math, os, re, subprocess, unicodedata
import numpy as np
import pandas as pd
from . import data as ED, model as EM
from ..core import ratings as R, dist as D

FORMAT = 1
REPO = ED.REPO
AHEAD_DAYS = 8                     # matches kicking off within this many days are on the board
ESPN_ABBR = {"MUN": "MAN", "MCI": "MNC"}       # Fantasy Premier League short name -> ESPN's, where they differ
POS = {"Goalkeeper": "GK", "Defender": "DEF", "Midfielder": "MID", "Forward": "FWD", "GK": "GK", "DEF": "DEF", "MID": "MID", "FWD": "FWD", "GKP": "GK"}
FPL_POS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
STATUS = {"i": "Out", "s": "Suspended", "u": "Out", "n": "Out"}        # 'd' (doubtful) is read with its chance of playing


def fetch(folder):
    """the data set, cloned shallow beside the other sports' files; an existing copy is brought up to date (best effort: a copy that cannot be updated is used as it is)"""
    dest = os.path.join(folder, "fplei")
    if not os.path.isdir(os.path.join(dest, ".git")):
        os.makedirs(folder, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", REPO, dest], check=True, timeout=240)
    else:
        if subprocess.run(["git", "-C", dest, "fetch", "-q", "--depth", "1", "origin"], timeout=240).returncode == 0:
            subprocess.run(["git", "-C", dest, "reset", "-q", "--hard", "FETCH_HEAD"], timeout=120)
    r = subprocess.run(["git", "-C", dest, "log", "-1", "--format=%H %cI"], capture_output=True, text=True)
    sha, _, when = (r.stdout.strip() + " ").partition(" ")
    return {"sha": sha[:10], "when": when.strip()}


def plain(s):
    """a name for matching: no accents, no punctuation, lower case"""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).strip()


def grid(m, tg, stat, asof):
    """today's attack / defence grid for one stat, fitted exactly as model.ratings_table fits goals"""
    P = EM.PARAMS
    idx = EM.team_index(m)
    season = int(tg["season"].max())
    y = (P["xg_blend"] * tg["xg"] + (1 - P["xg_blend"]) * tg["goals"]) if stat == "goals" else tg[stat].astype(float)
    po, pd_ = np.ones(len(idx)), np.ones(len(idx))
    prom = EM.promoted_sets(m)
    o0, d0 = EM.promoted_prior(tg, idx, prom, season, y)
    for c in prom.get(season, ()):
        if c in idx:
            po[idx[c]], pd_[idx[c]] = o0, d0
    past = ((tg["date"] < asof) & y.notna()).values
    w = R.decay_weights((asof - tg["date"][past]).dt.days.values, P["half_life"])
    g = R.fit_grid(tg["team"].map(idx).values[past], tg["opp"].map(idx).values[past], y.values[past], len(idx), home=tg["home"].values[past], w=w,
                   k_games=P["k_games"], prior_o=po, prior_d=pd_)
    return g, idx


def ranks(values, low_is_best=False):
    """{key: rank} with 1 the highest value (or the lowest when low_is_best)"""
    order = sorted(values, key=lambda k: values[k] if low_is_best else -values[k])
    return {k: i + 1 for i, k in enumerate(order)}


def ct(ts):
    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo("America/Chicago")
    except Exception:
        z = dt.timezone(dt.timedelta(hours=-6))
    d = ts.astimezone(z)
    return f"{d.strftime('%a')} {d.month}/{d.day} {d.strftime('%I:%M %p').lstrip('0')}"


def when(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def load_feed(feeds, name):
    try:
        return json.load(open(os.path.join(feeds, "epl", name), encoding="utf-8"))
    except Exception:
        return None


def pois_at_least(k, mean):
    """chance of k or more from a Poisson count"""
    if mean <= 0:
        return 0.0
    return float(1.0 - sum(math.exp(-mean) * mean ** i / math.factorial(i) for i in range(k)))


def build(folder, feeds=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    nown = pd.Timestamp(now).tz_convert(None)
    m = ED.load_matches(folder)
    names = ED.load_teams(folder)
    tg = ED.team_games(m)
    pm = ED.load_player_matches(m, folder)
    season = int(m["season"].max())
    short = lambda code: names.get(int(code), {}).get("short", str(code))
    checks = []

    # ---- the mirror: ESPN's fixtures and line-ups, the Fantasy Premier League list
    sb = load_feed(feeds, "scoreboard.json") if feeds else None
    lu = load_feed(feeds, "lineups.json") if feeds else None
    fpl = load_feed(feeds, "fpl.json") if feeds else None
    events = (sb or {}).get("events") or []
    if not events: checks.append("ESPN's fixture list was not in reach: kickoff times are the data set's and no match could be confirmed")
    if not fpl: checks.append("the Fantasy Premier League list was not in reach: nobody is marked injured, suspended or doubtful")
    ev_by = {}
    for e in events:
        ab = {t.get("ha"): t for t in e.get("teams") or []}
        if "home" in ab and "away" in ab:
            ev_by.setdefault((ab["home"]["abbr"], ab["away"]["abbr"]), []).append(e)
    lineups = {str(x.get("id")): x for x in (lu or {}).get("matches") or []}

    # ---- which matches: not finished in the data set, kicking off from three hours ago to AHEAD_DAYS ahead
    cur = m[m["season"] == season]
    up = cur[(~cur["finished"]) & cur["date"].notna() & (cur["date"] >= nown - pd.Timedelta(hours=3)) & (cur["date"] <= nown + pd.Timedelta(days=AHEAD_DAYS))]
    if up.empty:                                          # an international break: the next round, whenever it is
        nxt = cur[(~cur["finished"]) & cur["date"].notna() & (cur["date"] >= nown - pd.Timedelta(hours=3))]
        if not nxt.empty:
            d0 = nxt["date"].min(); up = nxt[nxt["date"] <= d0 + pd.Timedelta(days=4)]
    gg, idx = grid(m, tg, "goals", nown)
    gs, _ = grid(m, tg, "shots", nown)
    clubs = sorted(set(cur["home_team"].dropna().astype(int)))
    att = {c: float(gg["L"] * gg["O"][idx[c]]) for c in clubs}; dfn = {c: float(gg["L"] * gg["D"][idx[c]]) for c in clubs}
    sf = {c: float(gs["L"] * gs["O"][idx[c]]) for c in clubs}; sa = {c: float(gs["L"] * gs["D"][idx[c]]) for c in clubs}
    r_att, r_def, r_sf, r_sa = ranks(att), ranks(dfn, True), ranks(sf), ranks(sa, True)

    matches, wf_g, wf_s, teams_on = [], [], [], {}
    for _, r in up.sort_values(["date", "match_id"]).iterrows():
        hc, ac = int(r["home_team"]), int(r["away_team"])
        hs, as_ = short(hc), short(ac)
        he, ae = ESPN_ABBR.get(hs, hs), ESPN_ABBR.get(as_, as_)
        ko = r["date"].tz_localize("UTC").to_pydatetime()
        e = None
        if events:
            cand = [x for x in ev_by.get((he, ae), []) if when(x.get("date")) and abs((when(x["date"]) - ko).total_seconds()) <= 36 * 3600]
            e = min(cand, key=lambda x: abs((when(x["date"]) - ko).total_seconds())) if cand else None
            if e is None:
                checks.append(f"{hs} v {as_} ({ko.strftime('%m/%d')}) is in the data set but ESPN lists no such match within a day: left off the board")
                continue
            if str(e.get("detail", "")).lower().startswith(("postponed", "canceled", "cancelled", "abandoned")):
                checks.append(f"{hs} v {as_}: ESPN says {e.get('detail')}: left off the board")
                continue
            ek = when(e["date"])
            if abs((ek - ko).total_seconds()) > 3600:
                checks.append(f"{hs} v {as_}: the data set has kickoff {ko.strftime('%m/%d %H:%M')} UTC, ESPN {ek.strftime('%m/%d %H:%M')} UTC - ESPN's is shown")
            ko = ek
        h, a = idx[hc], idx[ac]
        lh, la = float(R.expect(gg, h, a, 1)), float(R.expect(gg, a, h, -1))
        mk = D.soccer_markets(lh, la, EM.PARAMS["rho"])
        sm = D.scoreline_matrix(lh, la, EM.PARAMS["rho"])
        top = sorted(((float(sm[i, j]), f"{i}-{j}") for i in range(6) for j in range(6)), reverse=True)[:5]
        et = {t.get("ha"): t for t in (e or {}).get("teams") or []}
        L = lineups.get(str((e or {}).get("id")))
        posted = bool(L and L.get("posted"))
        mid = str(r["match_id"])
        matches.append({"id": mid, "espn": str(e["id"]) if e else None, "key": f"{hs}-{as_}", "gw": int(r["gameweek"]) if pd.notna(r["gameweek"]) else None,
                        "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "koct": ct(ko), "home": hs, "away": as_, "venue": (e or {}).get("venue"),
                        "state": (e or {}).get("state") or "pre", "detail": (e or {}).get("detail"), "score": ({"home": et["home"].get("score"), "away": et["away"].get("score")} if e and (e.get("state") in ("in", "post")) else None),
                        "line": (e or {}).get("odds"), "xg": {"home": round(lh, 2), "away": round(la, 2)}, "p": {k: round(float(v), 4) for k, v in mk.items()},
                        "scores": [[s, round(p, 4)] for p, s in top], "shots": {"home": round(float(R.expect(gs, h, a, 1)), 1), "away": round(float(R.expect(gs, a, h, -1)), 1)},
                        "lineups": posted})
        row = {"match_id": r["match_id"], "home_team": hc, "away_team": ac, "H": gg["H"], "d_home": gg["D"][h], "d_away": gg["D"][a]}
        wf_g.append(row); wf_s.append(dict(row, H=gs["H"], d_home=gs["D"][h], d_away=gs["D"][a]))
        for code, sh_, opp, home, tt in ((hc, hs, as_, True, et.get("home")), (ac, as_, hs, False, et.get("away"))):
            teams_on.setdefault(code, {"abbr": sh_, "espn": ESPN_ABBR.get(sh_, sh_), "name": names.get(code, {}).get("name", sh_), "color": (tt or {}).get("color"), "alt": (tt or {}).get("alt"),
                                       "record": (tt or {}).get("record"), "form": (tt or {}).get("form"), "matches": []})["matches"].append(mid)

    # ---- availability: the Fantasy Premier League list, by the player code that stays the same from season to season
    fp = {int(x["code"]): x for x in (fpl or {}).get("players") or [] if x.get("code") is not None}

    def status(code):
        x = fp.get(int(code))
        if not x: return None
        s, nx = x.get("status"), x.get("next")
        if s in STATUS: return {"tag": STATUS[s], "why": x.get("news") or ""}
        if s == "d":
            if nx is not None and nx <= 25: return {"tag": "Out", "why": x.get("news") or ""}
            return {"tag": f"{nx}%" if nx is not None else "Doubt", "why": x.get("news") or ""}
        return None

    # ---- players: everyone with a part in his club's last five matches, projected for each coming match AS IF HE STARTS
    cs = pm[pm["season"] == season]
    last5 = {c: list(tg[(tg["season"] == season) & (tg["team"] == c)].sort_values("date")["match_id"].tail(5)) for c in teams_on}
    club_now = cs.sort_values("date").groupby("player_code")["team"].last()
    if fp:                                                # the official list knows a transfer before the match files do
        code_of = {t["short"]: int(t["code"]) for t in (fpl or {}).get("teams") or []}
        for pc, x in fp.items():
            if pc in club_now.index and x.get("team") in code_of:
                club_now.loc[pc] = code_of[x["team"]]
    synth, meta = [], {}
    for code, T in teams_on.items():
        mine = cs[(cs["team"] == code) & cs["player_code"].map(lambda pc: club_now.get(pc) == code)]
        l5 = mine[mine["match_id"].isin(last5[code])]
        role = l5.groupby("player_code").agg(apps5=("min", "size"), starts5=("started", "sum"), min5=("min", "sum"))
        tot = mine.groupby("player_code").agg(apps=("min", "size"), starts=("started", "sum"), mins=("min", "sum"), goals=("goals", "sum"), assists=("assists", "sum"), shots=("shots", "sum"), sot=("sot", "sum"), xg=("xg", "sum"))
        for pc, rr in role.iterrows():
            if rr["starts5"] < 1 and rr["min5"] < 45:
                continue
            base = mine[mine["player_code"] == pc].iloc[-1]
            t = tot.loc[pc]
            rec = [[f"{x['date'].month}/{x['date'].day}", ("" if x["home"] == 1 else "@") + short(x["opp"]), int(x["min"]), int(x["goals"]), int(x["assists"]), int(x["shots"]), int(x["sot"]), bool(x["started"])]
                   for _, x in mine[mine["player_code"] == pc].tail(5).iterrows()]
            x = fp.get(int(pc)) or {}
            meta[int(pc)] = {"name": str(base["player"]), "full": (f"{x.get('first', '')} {x.get('last', '')}".strip() or str(base["player"])), "pos": POS.get(str(base["position"]), FPL_POS.get(x.get("pos"), str(base["position"])[:3].upper())),
                             "apps5": int(rr["apps5"]), "starts5": int(rr["starts5"]), "apps": int(t["apps"]), "starts": int(t["starts"]), "mins": int(t["mins"]),
                             "tot": {"goals": int(t["goals"]), "assists": int(t["assists"]), "shots": int(t["shots"]), "sot": int(t["sot"]), "xg": round(float(t["xg"]), 2)}, "recent": rec}
            for mid in T["matches"]:
                mm = next(x for x in matches if x["id"] == mid)
                row = up[up["match_id"].astype(str) == mid].iloc[0]
                opp = int(row["away_team"]) if int(row["home_team"]) == code else int(row["home_team"])
                synth.append({"season": season, "date": row["date"], "match_id": row["match_id"], "player_code": int(pc), "player": str(base["player"]), "position": base["position"], "team": code, "opp": opp,
                              "home": 1 if int(row["home_team"]) == code else -1, "started": False, "min": 0.0, "goals": 0.0, "assists": 0.0, "shots": 0.0, "sot": 0.0, "xg": 0.0, "xa": 0.0, "_new": True})
    players = []
    if synth:
        ext = pd.concat([pm.assign(_new=False), pd.DataFrame(synth)], ignore_index=True)
        ext = ext.sort_values(["date", "_new"], kind="stable").reset_index(drop=True)
        pr = EM.player_projections(ext, pd.DataFrame(wf_g), pd.DataFrame(wf_s))
        pr = pr[pr["_new"].astype(bool)]
        xi_by = {}
        for mm in matches:
            L = lineups.get(str(mm["espn"])) if mm["espn"] else None
            if L and L.get("posted"):
                for t in L.get("teams") or []:
                    xi_by[(mm["id"], t.get("abbr"))] = ({plain(p["name"]) for p in t.get("xi") or []}, {plain(p["name"]) for p in t.get("bench") or []})
        for _, r in pr.iterrows():
            pc = int(r["player_code"]); mt = meta[pc]; T = teams_on[int(r["team"])]
            if (status(pc) or {}).get("tag") in ("Out", "Suspended"):
                continue                                  # listed out or suspended: he is on his club's list, and has no numbers
            mid = str(r["match_id"])
            xg, sh, so = float(r["proj_xg"]), float(r["proj_shots"]), float(r["proj_sot"])
            xi = None
            if (mid, T["espn"]) in xi_by:
                start, bench = xi_by[(mid, T["espn"])]
                me = {plain(mt["full"]), plain(mt["name"])}
                last = plain(mt["full"]).split(" ")[-1] if plain(mt["full"]) else ""
                hit = lambda group: bool(me & group) or (bool(last) and sum(1 for n in group if n.split(" ")[-1] == last) == 1 and len(last) > 3)
                xi = "start" if hit(start) else ("bench" if hit(bench) else "no")
            players.append({"id": str(pc), "name": mt["name"], "full": mt["full"], "team": T["abbr"], "opp": short(r["opp"]), "match": mid, "home": bool(r["home"] == 1), "pos": mt["pos"],
                            "apps5": mt["apps5"], "starts5": mt["starts5"], "apps": mt["apps"], "starts": mt["starts"], "mins": mt["mins"], "start_min": round(float(r["start_min"])),
                            "xg": round(xg, 3), "p_goal": round(float(r["p_goal"]), 4), "p_goal2": round(1.0 - math.exp(-xg) * (1 + xg), 4), "p_assist": round(float(r["p_assist"]), 4),
                            "shots": round(sh, 2), "sot": round(so, 2),
                            "ladder": {"shots": [[k, round(pois_at_least(k, sh), 4)] for k in (1, 2, 3, 4)], "sot": [[k, round(pois_at_least(k, so), 4)] for k in (1, 2, 3)]},
                            "per90": {k: (round(float(r["r90_" + k]), 3) if pd.notna(r["r90_" + k]) else None) for k in ("goals", "xg", "shots", "sot", "assists")},
                            "tot": mt["tot"], "status": status(pc), "xi": xi, "recent": mt["recent"]})
    players.sort(key=lambda p: (p["match"], p["team"], -p["p_goal"], p["name"]))

    # ---- each club: where it ranks, who is out
    teams = {}
    for code, T in teams_on.items():
        mine = [x for pc, x in fp.items() if (x.get("team") == T["abbr"])] if fp else []
        out, doubt = [], []
        for x in mine:
            if (x.get("min") or 0) < 180 and (x.get("starts") or 0) < 2:
                continue                                  # a player with no real part this season is not news
            st = status(x["code"])
            if not st: continue
            row = {"name": x.get("name"), "pos": FPL_POS.get(x.get("pos"), ""), "tag": st["tag"], "why": st["why"], "starts": x.get("starts"), "mins": x.get("min")}
            (out if st["tag"] in ("Out", "Suspended") else doubt).append(row)
        out.sort(key=lambda o: -(o["mins"] or 0)); doubt.sort(key=lambda o: -(o["mins"] or 0))
        lastg = tg[(tg["season"] == season) & (tg["team"] == code)].sort_values("date").tail(1)
        teams[T["abbr"]] = {"name": T["name"], "code": code, "espn": T["espn"], "color": T["color"], "alt": T["alt"], "record": T["record"], "form": T["form"],
                            "att": [r_att[code], round(att[code], 2)], "def": [r_def[code], round(dfn[code], 2)], "shots_for": [r_sf[code], round(sf[code], 1)], "shots_against": [r_sa[code], round(sa[code], 1)],
                            "out": out, "doubt": doubt,
                            "last": (f"{lastg.iloc[0]['date'].month}/{lastg.iloc[0]['date'].day} {'v' if lastg.iloc[0]['home'] == 1 else 'at'} {short(lastg.iloc[0]['opp'])}, {int(lastg.iloc[0]['goals'])}-{int(lastg.iloc[0]['goals_against'])}" if len(lastg) else None)}
    done = cur[cur["finished"]]
    gws = sorted({x["gw"] for x in matches if x["gw"] is not None})
    return {"sport": "epl", "format": FORMAT, "built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "season": season, "gameweeks": gws,
            "data_through": done["date"].max().strftime("%Y-%m-%d") if len(done) else None, "played": int(len(done)),
            "fpl_at": (fpl or {}).get("mirrored"), "espn_at": (sb or {}).get("mirrored"), "lineups_at": (lu or {}).get("mirrored"),
            "home_edge": round(float(gg["H"]), 3), "league_goals": round(float(gg["L"]), 3), "n_clubs": len(clubs),
            "checks": checks, "matches": matches, "teams": teams, "players": players}


KEEP_MINUTES = 100                 # a board younger than this is carried forward, unless a kickoff is near (the confirmed elevens)


def keep_last(prev_board, now):
    """(True, why) when the last run's board is good enough to carry forward: built less than KEEP_MINUTES ago and no match on it
    kicks off within KEEP_MINUTES or kicked off in the last half hour. The job runs four times an hour; the data set changes a few
    times a day, and cloning it every run would be 96 clones a day for nothing."""
    built = when((prev_board or {}).get("built"))
    if not prev_board or prev_board.get("format") != FORMAT or not built or not prev_board.get("matches"):
        return False, "no board from the last run"
    age = (now - built).total_seconds() / 60
    if age >= KEEP_MINUTES:
        return False, f"the last board is {age:.0f} minutes old"
    for mm in prev_board["matches"]:
        ko = when(mm.get("ko"))
        if ko and -30 <= (ko - now).total_seconds() / 60 <= KEEP_MINUTES:
            return False, f"{mm.get('key')} kicks off at {mm.get('koct')}: the confirmed elevens are due"
    return True, f"the last board is {age:.0f} minutes old and no kickoff is near"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--feeds"); ap.add_argument("--out", required=True); ap.add_argument("--data"); ap.add_argument("--now")
    ap.add_argument("--prev"); ap.add_argument("--always", action="store_true", help="build even when the last run's board is fresh")
    a, _ = ap.parse_known_args()
    path = os.path.join(a.out, "epl", "board.json")
    last = os.path.join(a.prev or os.path.join(os.path.dirname(os.path.abspath(a.out)), "prev"), "epl", "board.json")
    try: pb = json.load(open(last, encoding="utf-8"))
    except Exception: pb = None
    keep, why = keep_last(pb, when(a.now) if a.now else dt.datetime.now(dt.timezone.utc))
    if keep and not a.always:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(pb, open(path + ".tmp", "w"), separators=(",", ":")); os.replace(path + ".tmp", path)
        print(f"epl board: kept from the last run - {why}")
        return
    folder = a.data or ED.data_dir()
    src = fetch(folder)
    now = when(a.now) if a.now else None
    b = build(folder, a.feeds, now)
    b["data_commit"] = src
    os.makedirs(os.path.join(a.out, "epl"), exist_ok=True)
    json.dump(b, open(path + ".tmp", "w"), separators=(",", ":")); os.replace(path + ".tmp", path)
    print(f"epl board: {len(b['matches'])} matches (gameweek {', '.join(map(str, b['gameweeks'])) or '?'}), {len(b['players'])} player rows, {len(b['teams'])} clubs, data through {b['data_through']} "
          f"({b['played']} matches played; data set {src['sha']} {src['when'][:16]}); line-ups posted for {sum(1 for x in b['matches'] if x['lineups'])}; "
          f"{len(b['checks'])} check note(s){': ' + ' | '.join(b['checks'])[:300] if b['checks'] else ''}; {os.path.getsize(path) // 1024} KB")


if __name__ == "__main__":
    main()
