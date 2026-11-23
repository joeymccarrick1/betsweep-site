"""Soccer beyond the Premier League: one board per league - bun/, lal/, sea/, mls/ board.json - in the Premier League board's own format.

Owner 11/23 1:10 AM: "get to building Bundesliga, La Liga, Serie A, and MLS. We'd have NFL, College Football, NBA and Soccer (with these
different leagues)." The 11/15 groundwork said the grid and the player code are league-neutral; this is that, on ESPN's data.

Where the numbers come from - all of it the feeds-sports job's own mirror of ESPN (.github/feeds_sports.py on main):
  <league>/season.json      every finished match of the season: the score, each side's shots, and a line for every player who took the
                            field (started, minutes, goals, assists, shots, shots on target)
  <league>/scoreboard.json  the coming fixtures with kickoff, site and ESPN's posted home / draw / away and total prices (the book is named)
  <league>/lineups.json     confirmed elevens, about an hour before kickoff

The model is the Premier League's, with one honest difference: there are NO EXPECTED GOALS for these leagues. Where the Premier League
grid is fitted on a blend of expected goals and goals, this one is fitted on a blend of goals and a SHOT-BASED STAND-IN: a shot on target
counts three times a shot off target, scaled so the league's stand-in total equals its goals. Players the same way. That is weaker
evidence than expected goals, and the page says so; the grading (sports/epl/grade.py, per league) is what will say whether it holds.
No injury list is read for these leagues yet: nobody is marked out, and the page says that too.

    python3 -m sports.soccer.publish --feeds DIR --out DIR [--now ISO] [--only bun,lal] [--no-grade]
"""
import argparse
import collections
import datetime as dt
import json
import math
import os

import numpy as np

from ..core import dist as D, ratings as R
from ..epl import grade as G

FORMAT = 1
LEAGUES = collections.OrderedDict((("bun", "Bundesliga"), ("lal", "La Liga"), ("sea", "Serie A"), ("mls", "MLS")))
AHEAD_DAYS = 8
PARAMS = {
    "shot_blend": 0.5,       # share of the shot-based stand-in (vs real goals) in what the grid is fitted to - the Premier League's own split
    "sot_weight": 3.0,       # a shot on target counts this many times a shot off target in the stand-in
    "half_life": 240.0,      # days for a match to count half as much
    "k_games": 2.0,          # games of prior mixed into every club's rating
    "rho": -0.12,            # low-score correction, as the Premier League's
    "k_rate_min": 900.0,     # minutes of the position's average rate mixed into a player's rate (ten matches)
    "start_min_k": 1.0,      # starts of prior mixed into 'minutes when he starts'
}
POS = {"G": "GK"}            # ESPN's formation places -> the four the page shows; everything else by its letters below


def position(code):
    c = str(code or "").upper()
    if c in ("G", "GK"): return "GK"
    if c == "SUB" or not c: return None
    head = c.split("-")[0]
    if head in ("F", "CF", "LF", "RF", "ST", "S"): return "FWD"
    if head in ("CD", "LB", "RB", "CB", "D", "LWB", "RWB", "SW"): return "DEF"
    return "MID"                                         # LM, RM, CM, DM, AM, M ...


def when(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def central(ts):
    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo("America/Chicago")
    except Exception:
        z = dt.timezone(dt.timedelta(hours=-6))
    return ts.astimezone(z)


def ct(ts):
    d = central(ts)
    return f"{d.strftime('%a')} {d.month}/{d.day} {d.strftime('%I:%M %p').lstrip('0')}"


def week_key(ts):
    """These leagues have no gameweek number in ESPN's feed, so a match's round is the week it is played in: Tuesday to Monday on the
    Central clock - a weekend and its Monday night together, a midweek round with the weekend after it - named by its Tuesday as a
    number (20261124). The grader keeps one row of sums a round (sports/epl/grade.py), the page calls it 'Week of Nov 24'."""
    d = central(ts).date()
    return int((d - dt.timedelta(days=(d.weekday() - 1) % 7)).strftime("%Y%m%d"))


def load(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def pois_at_least(k, mean):
    if mean <= 0: return 0.0
    return 1.0 - sum(math.exp(-mean) * mean ** i / math.factorial(i) for i in range(k))


def ranks(vals, low_is_first=False):
    order = sorted(vals, key=lambda k: vals[k], reverse=not low_is_first)
    return {k: i + 1 for i, k in enumerate(order)}


def build(lg, feeds, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    P = PARAMS
    A = load(os.path.join(feeds, lg, "season.json")) or {}
    sb = load(os.path.join(feeds, lg, "scoreboard.json")) or {}
    lu = load(os.path.join(feeds, lg, "lineups.json")) or {}
    checks = []
    fin = sorted(((mid, m) for mid, m in (A.get("matches") or {}).items() if m.get("h") and m.get("a") and m.get("hs") is not None and m.get("as") is not None and when(m.get("d"))),
                 key=lambda kv: (kv[1]["d"], kv[0]))
    if len(fin) < 30:
        raise ValueError(f"{lg}: only {len(fin)} finished matches on file - too few to rate a league")
    tinfo = {str(t["id"]): t for t in A.get("teams") or []}
    ab = lambda tid: (tinfo.get(str(tid)) or {}).get("abbr") or str(tid)

    # ---- the shot-based stand-in for expected goals: scaled so its league total equals the goals scored in the same matches
    sot = off = goals = 0.0
    for _, m in fin:
        st = m.get("st") or {}
        for side, gs in ((m["h"], m["hs"]), (m["a"], m["as"])):
            s = st.get(side) or {}
            if s.get("sh") is not None and s.get("sot") is not None:
                sot += s["sot"]; off += max(0.0, s["sh"] - s["sot"]); goals += gs
    k_off = goals / (P["sot_weight"] * sot + off) if (sot + off) > 0 else 0.0
    k_sot = P["sot_weight"] * k_off
    proxy = lambda sh, so: k_sot * so + k_off * max(0.0, sh - so)

    # ---- the grid: two rows a match (what each side produced), newest matches weighing most
    ids = sorted({m["h"] for _, m in fin} | {m["a"] for _, m in fin})
    idx = {t: i for i, t in enumerate(ids)}
    asof = now + dt.timedelta(days=0)
    rows = []                                               # team, opp, home(+1/-1), goals-blend, shots (or None), days ago
    for mid, m in fin:
        st = m.get("st") or {}
        days = max(0.0, (asof - when(m["d"])).total_seconds() / 86400)
        for me, other, s, gs in ((m["h"], m["a"], 1, m["hs"]), (m["a"], m["h"], -1, m["as"])):
            x = st.get(me) or {}
            has = x.get("sh") is not None and x.get("sot") is not None
            y = (P["shot_blend"] * proxy(x["sh"], x["sot"]) + (1 - P["shot_blend"]) * gs) if has else float(gs)
            rows.append((idx[me], idx[other], s, y, (x["sh"] if has else None), days))
    T = np.array([r[0] for r in rows]); O = np.array([r[1] for r in rows]); S = np.array([r[2] for r in rows], dtype=float)
    w = R.decay_weights(np.array([r[5] for r in rows]), P["half_life"])
    gg = R.fit_grid(T, O, np.array([r[3] for r in rows]), len(idx), home=S, w=w, k_games=P["k_games"])
    hs_ = np.array([r[4] is not None for r in rows])
    gs = R.fit_grid(T[hs_], O[hs_], np.array([r[4] for r in rows if r[4] is not None], dtype=float), len(idx), home=S[hs_], w=w[hs_], k_games=P["k_games"])
    L, H = float(gg["L"]), float(gg["H"])
    att = {t: L * float(gg["O"][idx[t]]) for t in ids}; dfn = {t: L * float(gg["D"][idx[t]]) for t in ids}
    sf = {t: float(gs["L"] * gs["O"][idx[t]]) for t in ids}; sa = {t: float(gs["L"] * gs["D"][idx[t]]) for t in ids}
    r_att, r_def, r_sf, r_sa = ranks(att), ranks(dfn, True), ranks(sf), ranks(sa, True)

    # ---- the coming matches: ESPN's fixtures from three hours ago to AHEAD_DAYS ahead (an empty week: the next round, whenever it is)
    events = [e for e in sb.get("events") or [] if when(e.get("date"))]
    if not events: checks.append("ESPN's fixture list was not in reach: no match can be listed")
    lo, hi = now - dt.timedelta(hours=3), now + dt.timedelta(days=AHEAD_DAYS)
    coming = [e for e in events if lo <= when(e["date"]) <= hi and e.get("state") in ("pre", "in", "post")]
    if not coming:
        later = [e for e in events if when(e["date"]) >= lo]
        if later:
            d0 = min(when(e["date"]) for e in later); coming = [e for e in later if when(e["date"]) <= d0 + dt.timedelta(days=4)]
    lineups = {str(x.get("id")): x for x in lu.get("matches") or []}
    matches, on = [], collections.OrderedDict()
    for e in sorted(coming, key=lambda e: (e["date"], e["id"])):
        t = {x.get("ha"): x for x in e.get("teams") or []}
        if "home" not in t or "away" not in t:
            continue
        if str(e.get("detail", "")).lower().startswith(("postponed", "canceled", "cancelled", "abandoned")):
            checks.append(f"{t['home'].get('abbr')} v {t['away'].get('abbr')}: ESPN says {e.get('detail')}: left off the board"); continue
        hc, ac = str(t["home"].get("id")), str(t["away"].get("id"))
        if hc not in idx or ac not in idx:
            checks.append(f"{t['home'].get('abbr')} v {t['away'].get('abbr')}: a side with no finished match this season cannot be rated: left off the board"); continue
        ko = when(e["date"])
        h, a = idx[hc], idx[ac]
        lh, la = float(R.expect(gg, h, a, 1)), float(R.expect(gg, a, h, -1))
        mk = D.soccer_markets(lh, la, P["rho"]); sm = D.scoreline_matrix(lh, la, P["rho"])
        top = sorted(((float(sm[i, j]), f"{i}-{j}") for i in range(6) for j in range(6)), reverse=True)[:5]
        hab, aab = t["home"].get("abbr") or ab(hc), t["away"].get("abbr") or ab(ac)
        Lx = lineups.get(str(e["id"]))
        mid = str(e["id"])
        matches.append({"id": mid, "espn": mid, "key": f"{hab}-{aab}", "gw": week_key(ko), "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "koct": ct(ko), "home": hab, "away": aab, "venue": e.get("venue"),
                        "state": e.get("state") or "pre", "detail": e.get("detail"),
                        "score": ({"home": t["home"].get("score"), "away": t["away"].get("score")} if e.get("state") in ("in", "post") else None),
                        "line": e.get("odds"), "xg": {"home": round(lh, 2), "away": round(la, 2)}, "p": {k: round(float(v), 4) for k, v in mk.items()},
                        "scores": [[s, round(p, 4)] for p, s in top], "shots": {"home": round(float(R.expect(gs, h, a, 1)), 1), "away": round(float(R.expect(gs, a, h, -1)), 1)},
                        "lineups": bool(Lx and Lx.get("posted"))})
        for code, abbr, opp, home, tt in ((hc, hab, ac, True, t["home"]), (ac, aab, hc, False, t["away"])):
            info = tinfo.get(code) or {}
            on.setdefault(code, {"abbr": abbr, "name": info.get("short") or tt.get("short") or info.get("name") or abbr, "color": tt.get("color") or info.get("color"), "alt": tt.get("alt") or info.get("alt"),
                                 "record": tt.get("record"), "form": tt.get("form"), "matches": []})["matches"].append((mid, opp, home))

    # ---- players: every line of the season, per player; his club is the one he last played for
    byp = collections.defaultdict(list)                     # player id -> [(date, match id, team, opp, home, pos, started, min, g, a, sh, sot)]
    posmin = collections.defaultdict(lambda: [0.0] * 6)     # position -> [min, goals, assists, shots, sot, stand-in]
    for mid, m in fin:
        for p in m.get("p") or []:
            tid, pid, name, pos, st_, mn, g, a_, sh, so = p[:10]
            home = tid == m["h"]
            byp[pid].append((m["d"], mid, tid, m["a"] if home else m["h"], home, pos, bool(st_), mn, g, a_, sh, so, name))
    place = {}
    for pid, rs in byp.items():
        c = collections.Counter(position(r[5]) for r in rs if r[6] and position(r[5]))
        place[pid] = c.most_common(1)[0][0] if c else None
    for pid, rs in byp.items():
        if place[pid]:
            z = posmin[place[pid]]
            for r in rs:
                z[0] += r[7]; z[1] += r[8]; z[2] += r[9]; z[3] += r[10]; z[4] += r[11]; z[5] += proxy(r[10], r[11])
    pos90 = {k: [90.0 * v / z[0] if z[0] else 0.0 for v in z[1:]] for k, z in posmin.items()}        # goals, assists, shots, sot, stand-in per 90
    allz = [sum(z[i] for z in posmin.values()) for i in range(6)]
    any90 = [90.0 * v / allz[0] if allz[0] else 0.0 for v in allz[1:]]
    last5 = {}
    for code in on:
        mine = [mid for mid, m in fin if code in (m["h"], m["a"])]
        last5[code] = set(mine[-5:])
    xi_by = {}
    for mm in matches:
        Lx = lineups.get(mm["id"])
        if Lx and Lx.get("posted"):
            for t in Lx.get("teams") or []:
                xi_by[(mm["id"], t.get("abbr"))] = ({str(p.get("id")) for p in t.get("xi") or []}, {str(p.get("id")) for p in t.get("bench") or []})
    players = []
    for pid, rs in byp.items():
        rs.sort(key=lambda r: (r[0], r[1]))
        code = rs[-1][2]
        if code not in on:
            continue
        mine = [r for r in rs if r[2] == code]
        l5 = [r for r in mine if r[1] in last5[code]]
        starts5, min5 = sum(1 for r in l5 if r[6]), sum(r[7] for r in l5)
        if starts5 < 1 and min5 < 45:
            continue
        pos = place.get(pid) or "MID"
        prior = pos90.get(pos) or any90
        mins = sum(r[7] for r in mine)
        tot = [sum(r[i] for r in mine) for i in (8, 9, 10, 11)]                       # goals, assists, shots, sot
        px = sum(proxy(r[10], r[11]) for r in mine)
        rate = lambda total, pr: 90.0 * (total + P["k_rate_min"] * pr / 90.0) / (mins + P["k_rate_min"])
        r90 = {"goals": rate(tot[0], prior[0]), "assists": rate(tot[1], prior[1]), "shots": rate(tot[2], prior[2]), "sot": rate(tot[3], prior[3]), "xg": rate(px, prior[4])}
        st_rows = [r for r in mine if r[6]]
        start_min = (sum(r[7] for r in st_rows) + P["start_min_k"] * 82.0) / (len(st_rows) + P["start_min_k"])
        frac = start_min / 90.0
        name = " ".join(str(mine[-1][12] or "").split()) or f"Player {pid}"          # ESPN's names come with stray spaces now and then
        short = name if len(name) <= 18 else (name.split(" ")[-1] if " " in name else name)
        recent = []
        for r in mine[-5:]:
            d = when(r[0])
            recent.append([f"{d.month}/{d.day}", ("" if r[4] else "@") + ab(r[3]), int(r[7]), int(r[8]), int(r[9]), int(r[10]), int(r[11]), bool(r[6])])
        T_ = on[code]
        for mid, opp, home in T_["matches"]:
            eg = (H if home else 1.0 / H) * float(gg["D"][idx[opp]])
            es = (float(gs["H"]) if home else 1.0 / float(gs["H"])) * float(gs["D"][idx[opp]])
            xg = frac * (0.7 * r90["xg"] + 0.3 * r90["goals"]) * eg
            sh, so = frac * r90["shots"] * es, frac * r90["sot"] * es
            xi = None
            if (mid, T_["abbr"]) in xi_by:
                start, bench = xi_by[(mid, T_["abbr"])]
                xi = "start" if pid in start else ("bench" if pid in bench else "no")
            players.append({"id": str(pid), "name": short, "full": name, "team": T_["abbr"], "opp": on[opp]["abbr"], "match": mid, "home": bool(home), "pos": pos,
                            "apps5": len(l5), "starts5": starts5, "apps": len(mine), "starts": len(st_rows), "mins": int(mins), "start_min": round(start_min),
                            "xg": round(xg, 3), "p_goal": round(1.0 - math.exp(-xg), 4), "p_goal2": round(1.0 - math.exp(-xg) * (1 + xg), 4),
                            "p_assist": round(1.0 - math.exp(-frac * r90["assists"] * eg), 4), "shots": round(sh, 2), "sot": round(so, 2),
                            "ladder": {"shots": [[k, round(pois_at_least(k, sh), 4)] for k in (1, 2, 3, 4)], "sot": [[k, round(pois_at_least(k, so), 4)] for k in (1, 2, 3)]},
                            "per90": {k: round(v, 3) for k, v in r90.items()},
                            "tot": {"goals": int(tot[0]), "assists": int(tot[1]), "shots": int(tot[2]), "sot": int(tot[3]), "xg": round(px, 2)}, "status": None, "xi": xi, "recent": recent})
    players.sort(key=lambda p: (p["match"], p["team"], -p["p_goal"], p["name"]))

    teams = {}
    for code, T_ in on.items():
        mine = [(mid, m) for mid, m in fin if code in (m["h"], m["a"])]
        last = None
        if mine:
            mid, m = mine[-1]; d = when(m["d"]); home = m["h"] == code
            last = f"{d.month}/{d.day} {'v' if home else 'at'} {ab(m['a'] if home else m['h'])}, {m['hs'] if home else m['as']}-{m['as'] if home else m['hs']}"
        teams[T_["abbr"]] = {"name": T_["name"], "code": code, "espn": T_["abbr"], "color": T_["color"], "alt": T_["alt"], "record": T_["record"], "form": T_["form"],
                             "att": [r_att[code], round(att[code], 2)], "def": [r_def[code], round(dfn[code], 2)], "shots_for": [r_sf[code], round(sf[code], 1)], "shots_against": [r_sa[code], round(sa[code], 1)],
                             "out": [], "doubt": [], "last": last}
    bh, ba = L * H, L / H
    base = {"xg": {"home": round(bh, 2), "away": round(ba, 2)}, "p": {k: round(float(v), 4) for k, v in D.soccer_markets(bh, ba, P["rho"]).items()}}
    withp = sum(1 for _, m in fin if m.get("p"))
    return {"sport": lg, "league": LEAGUES.get(lg, lg), "format": FORMAT, "built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "season": None, "gameweeks": [],
            "data_through": when(fin[-1][1]["d"]).strftime("%Y-%m-%d"), "played": len(fin), "with_players": withp, "fpl_at": None, "espn_at": sb.get("mirrored"), "lineups_at": lu.get("mirrored"),
            "home_edge": round(H, 3), "league_goals": round(L, 3), "n_clubs": len(ids), "base": base, "no_availability": True,
            "standin": {"on_target": round(k_sot, 4), "off_target": round(k_off, 4)}, "checks": checks, "matches": matches, "teams": teams, "players": players}


def actuals(A, want):
    """what the season file has for these matches, for the grading: the final score and every player who played. A match is handed over only
    with at least 20 starters on file."""
    out = {}
    for mid in want or ():
        m = (A.get("matches") or {}).get(str(mid))
        if not m or not m.get("p") or m.get("hs") is None:
            continue
        if sum(1 for p in m["p"] if p[4]) < 20:
            continue
        out[str(mid)] = {"final": {"home": int(m["hs"]), "away": int(m["as"])},
                         "players": {str(p[1]): {"min": int(p[5]), "started": bool(p[4]), "g": int(p[6]), "a": int(p[7]), "sh": int(p[8]), "sot": int(p[9])} for p in m["p"]}}
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--feeds", required=True); ap.add_argument("--out", required=True); ap.add_argument("--now"); ap.add_argument("--only")
    ap.add_argument("--prev"); ap.add_argument("--site"); ap.add_argument("--no-grade", action="store_true")
    a, _ = ap.parse_known_args()
    now = when(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    root = os.path.dirname(os.path.abspath(a.out))
    for lg in ([x for x in a.only.split(",") if x] if a.only else list(LEAGUES)):
        gdir = os.path.join(a.out, lg); path = os.path.join(gdir, "board.json")
        pb = load(os.path.join(a.prev or os.path.join(root, "prev"), lg, "board.json"))
        try:
            b = build(lg, a.feeds, now)
            os.makedirs(gdir, exist_ok=True)
            json.dump(b, open(path + ".tmp", "w"), separators=(",", ":")); os.replace(path + ".tmp", path)
            print(f"{lg} board: {len(b['matches'])} matches, {len(b['players'])} player rows, {b['n_clubs']} clubs, {b['played']} finished matches through {b['data_through']} "
                  f"({b['with_players']} with player lines); line-ups posted for {sum(1 for x in b['matches'] if x['lineups'])}; {len(b['checks'])} check note(s){': ' + ' | '.join(b['checks'])[:300] if b['checks'] else ''}; "
                  f"{os.path.getsize(path) // 1024} KB")
        except Exception as e:
            print(f"{lg} board: FAILED ({type(e).__name__}: {e})")
            if pb and not os.path.exists(path):
                os.makedirs(gdir, exist_ok=True); json.dump(pb, open(path, "w"), separators=(",", ":")); print(f"{lg} board: kept the last run's")
            b = pb
        if a.no_grade or not b:
            continue
        try:                                                # lock and grade, as the Premier League's: the board is already written, so nothing here can cost it
            A = load(os.path.join(a.feeds, lg, "season.json")) or {}
            boards = [("the feed", b), ("the feed, one run earlier", pb), ("the published page", load(os.path.join(a.site or root, SITE_FOLDER.get(lg, lg), "board.json")))]
            G.run(gdir, boards, scoreboard=load(os.path.join(a.feeds, lg, "scoreboard.json")), actuals=actuals(A, G.wanted(gdir)), now=now, sport=lg)
        except Exception as e:
            print(f"{lg} grade: FAILED ({type(e).__name__}: {e}) - the board is written, the record is as the last run left it")


SITE_FOLDER = {"bun": "bundesliga", "lal": "laliga", "sea": "seriea", "mls": "mls"}      # where each league's page lives on the site

if __name__ == "__main__":
    main()
