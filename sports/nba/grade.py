"""The NBA board graded night by night: lock, grade, record.

Owner's standing rule for anything new: it starts "tracked, not a lead" - nothing becomes a pick until it has been graded. The /nba/ page went up
11/22 with model numbers only; this is the grading that page has to earn its picks with.

Three steps, all run inside the feeds-sports job after the board is written (sports/nba/publish.py main), every run:

  LOCK    When a game's tip time has passed, its players' numbers are copied out of the LAST BOARD BUILT BEFORE THE TIP and never touched again
          (nba/locks/<day>.json). The boards in reach are the feed's previous board (last run, at most half an hour old) and the one the site
          has published. If no board built before the tip is in reach - the job was down, or the page did not exist yet - the game is marked
          MISSED and is never graded: a number written down after the ball went up is not a projection.
  GRADE   When a locked game's box score is final (nba/box-<id>.json from the mirror), every locked player is compared with what he did:
          the model's number and his season average, each against the result, for points, rebounds, assists, threes; minutes; and every rung
          of his chance ladders against whether he reached it. A locked player who did not play is counted on his own line (the board said he
          would play), not in the averages.
  RECORD  nba/record.json keeps one row of sums per night and the totals, which are always the sum of the rows. nba/graded-<day>.json keeps
          the player-by-player result of the last few nights.

The branch these files live on is rebuilt from nothing on every run of the job, so the job copies them forward before anything else
(.github/feeds_sports.py carry()). Nothing here needs pandas: plain files in, plain files out, so it can be tested anywhere.
"""
import datetime as dt
import glob
import json
import os

FORMAT = 1
STATS = ("pts", "reb", "ast", "fg3")
BOX = {"pts": "PTS", "reb": "REB", "ast": "AST"}             # fg3 is the makes in "3PT": "2-8"
EDGES = (0.2, 0.4, 0.6, 0.8)                                   # five buckets of stated chance: under 20%, 20-40, 40-60, 60-80, 80 and up
KEEP_LOCK_DAYS = 6                                             # a lock not graded within this many days is dropped (postponed game, box never came)
KEEP_NIGHT_FILES = 4                                           # player-by-player files kept


def when(s):
    """an ISO time from the feeds ("2026-11-23T01:30Z", "...+00:00") as an aware datetime, or None"""
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def load(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    """written whole or not at all: a half-written record would be carried forward for ever"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), separators=(",", ":"))
    os.replace(tmp, path)


def slim(p):
    """what is kept of a board player at the lock: enough to grade him and to show the result"""
    return {"id": str(p.get("id")), "name": p.get("name"), "team": p.get("team"), "opp": p.get("opp"), "grp": p.get("grp"), "min": p.get("min"),
            "proj": {k: (p.get("proj") or {}).get(k) for k in STATS}, "avg": {k: (p.get("avg") or {}).get(k) for k in STATS},
            "ladder": {k: [[r[0], r[1]] for r in ((p.get("ladder") or {}).get(k) or [])] for k in STATS},
            "tag": ((p.get("status") or {}).get("tag") or "")}


def lock(locks, boards, now):
    """locks: {day: {"day", "games": {gid: {...}}}} (changed in place). boards: [(where it came from, board)] - every board in reach.
    Each game whose tip has passed and that has no entry yet gets one: locked from the latest board built before its tip, or missed.
    Returns [(day, gid, "locked" | "missed")] for what this call added."""
    done = []
    games = {}
    for src, b in boards:
        if not b or not isinstance(b, dict) or not b.get("day"):
            continue
        for g in b.get("games") or []:
            games.setdefault((b["day"], str(g.get("id"))), g)
    for (day, gid), g in sorted(games.items()):
        tip = when(g.get("tip"))
        entry = locks.setdefault(day, {"day": day, "games": {}})
        if not tip or tip > now or gid in entry["games"]:
            continue
        best = None
        for src, b in boards:
            built = when((b or {}).get("built"))
            if not b or b.get("day") != day or not built or built >= tip:
                continue
            ps = [slim(p) for p in b.get("players") or [] if str(p.get("game")) == gid]
            if ps and (best is None or built > best[0]):
                best = (built, src, ps, b)
        head = {"key": g.get("key"), "tip": g.get("tip"), "home": g.get("home"), "away": g.get("away"), "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        if best:
            built, src, ps, b = best
            gg = next((x for x in b.get("games") or [] if str(x.get("id")) == gid), {})
            entry["games"][gid] = dict(head, board_built=b.get("built"), source=src, minutes_before_tip=round((tip - built).total_seconds() / 60),
                                       proj=gg.get("proj"), line=gg.get("line"), players=ps)
            done.append((day, gid, "locked"))
        else:
            entry["games"][gid] = dict(head, missed=True, why="no board built before the tip was in reach")
            done.append((day, gid, "missed"))
    return done


def actual(row):
    """a box-score line as {"min", "pts", "reb", "ast", "fg3"}, or None when he did not play"""
    s = (row or {}).get("s") or {}
    try:
        mins = int(float(s.get("MIN")))
    except Exception:
        mins = 0
    if not row or row.get("dnp") or mins <= 0:
        return None
    out = {"min": mins}
    try:
        for k, col in BOX.items():
            out[k] = int(float(s[col]))
        out["fg3"] = int(str(s["3PT"]).split("-")[0])
    except Exception:
        return None
    return out


def bucket(p):
    return sum(1 for e in EDGES if p >= e)


def empty():
    return {"games": 0, "players": 0, "dnp": 0, "stats": {k: {"n": 0, "model": 0.0, "base": 0.0, "err": 0.0} for k in STATS}, "min": {"n": 0, "abs": 0.0, "err": 0.0},
            "cal": {k: [[0, 0, 0.0] for _ in range(len(EDGES) + 1)] for k in STATS}}


def add(a, b):
    """a += b, for two blocks of sums shaped like empty()"""
    for k in ("games", "players", "dnp"):
        a[k] += b[k]
    for k in STATS:
        for f in ("n", "model", "base", "err"):
            a["stats"][k][f] += b["stats"][k][f]
        for i, row in enumerate(b["cal"][k]):
            for j in range(3):
                a["cal"][k][i][j] += row[j]
    for f in ("n", "abs", "err"):
        a["min"][f] += b["min"][f]
    return a


def grade_game(lg, box):
    """One locked game against its final box score -> (sums shaped like empty(), player rows).
    A player-stat counts only when the lock has both the model's number and his season average, so the two are always compared on the same players."""
    by = {str(r.get("id")): r for r in box.get("players") or []}
    S = empty(); S["games"] = 1
    rows = []
    for p in lg.get("players") or []:
        a = actual(by.get(str(p["id"])))
        row = {"id": p["id"], "name": p["name"], "team": p["team"], "min": [p.get("min"), a["min"] if a else None], "tag": p.get("tag") or ""}
        if a is None:
            S["dnp"] += 1
            row["dnp"] = True
            rows.append(row)
            continue
        S["players"] += 1
        if isinstance(p.get("min"), (int, float)):
            S["min"]["n"] += 1; S["min"]["abs"] += abs(p["min"] - a["min"]); S["min"]["err"] += p["min"] - a["min"]
        for k in STATS:
            m, base = (p.get("proj") or {}).get(k), (p.get("avg") or {}).get(k)
            row[k] = [m, base, a[k]]
            if isinstance(m, (int, float)) and isinstance(base, (int, float)):
                st = S["stats"][k]
                st["n"] += 1; st["model"] += abs(m - a[k]); st["base"] += abs(base - a[k]); st["err"] += m - a[k]
            for L, pr in (p.get("ladder") or {}).get(k) or []:
                if isinstance(pr, (int, float)) and isinstance(L, (int, float)):
                    c = S["cal"][k][bucket(pr)]
                    c[0] += 1; c[1] += 1 if a[k] >= L else 0; c[2] += pr
        rows.append(row)
    return S, rows


def rounded(S):
    """sums with the float noise taken off, so a record that is added up twice reads the same"""
    for k in STATS:
        for f in ("model", "base", "err"):
            S["stats"][k][f] = round(S["stats"][k][f], 4)
        for row in S["cal"][k]:
            row[2] = round(row[2], 4)
    for f in ("abs", "err"):
        S["min"][f] = round(S["min"][f], 4)
    return S


def run(folder, boards, now=None, say=print):
    """folder: the nba/ folder of the branch being built (board.json, box-*.json, locks/, record.json, graded-*.json).
    boards: [(source, board)] in reach besides nothing else - the caller passes the previous feed board and the published one.
    Never raises on bad data: a file it cannot read is left exactly as it is."""
    now = now or dt.datetime.now(dt.timezone.utc)
    lock_dir = os.path.join(folder, "locks")
    locks = {}
    for f in sorted(glob.glob(os.path.join(lock_dir, "*.json"))):
        d = load(f)
        if isinstance(d, dict) and d.get("day") and isinstance(d.get("games"), dict):
            locks[d["day"]] = d
    # ---- lock
    new = lock(locks, boards, now)
    # ---- grade
    rec_path = os.path.join(folder, "record.json")
    rec = load(rec_path)
    if rec is None and os.path.exists(rec_path):
        say("nba grade: record.json is there but cannot be read - left as it is, nothing graded this run")
        rec = False
    if rec is None:
        rec = {"format": FORMAT, "sport": "nba", "since": None, "nights": [], "graded": {}, "missed": {}}
    graded_now = []
    if rec:
        nights = {n["day"]: n for n in rec.get("nights") or []}
        for day, entry in sorted(locks.items()):
            for gid, lg in sorted(entry["games"].items()):
                if lg.get("missed"):
                    rec.setdefault("missed", {}).setdefault(gid, day)
                    continue
                if gid in rec.get("graded", {}):
                    continue
                box = load(os.path.join(folder, f"box-{gid}.json"))
                if not box or not box.get("done") or box.get("state") != "post":
                    continue
                S, rows = grade_game(lg, box)
                n = nights.setdefault(day, dict(empty(), day=day, ids=[]))
                add(n, S); n["ids"].append(gid)
                rec.setdefault("graded", {})[gid] = day
                nf = os.path.join(folder, f"graded-{day}.json")
                night = load(nf) or {"day": day, "games": {}}
                night["games"][gid] = {"key": lg.get("key"), "tip": lg.get("tip"), "board_built": lg.get("board_built"), "source": lg.get("source"),
                                       "final": {t.get("abbr"): t.get("score") for t in box.get("teams") or []}, "proj": lg.get("proj"), "rows": rows}
                save(nf, night)
                graded_now.append((day, gid, S["players"], S["dnp"]))
        if graded_now or new or not os.path.exists(rec_path):
            rec["nights"] = [rounded(nights[d]) for d in sorted(nights)]
            total = empty()
            for n in rec["nights"]:
                add(total, n)
            rec["total"] = rounded(total)
            rec["since"] = rec["nights"][0]["day"] if rec["nights"] else None
            rec["updated"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            # only the last two weeks of ids are kept: older games' locks are long gone, they cannot be graded twice
            keep_from = (now - dt.timedelta(days=14)).strftime("%Y-%m-%d")
            rec["graded"] = {g: d for g, d in rec.get("graded", {}).items() if d >= keep_from}
            rec["missed"] = {g: d for g, d in rec.get("missed", {}).items() if d >= keep_from}
            rec["waiting"] = sum(1 for e in locks.values() for g, lg in e["games"].items() if not lg.get("missed") and g not in rec["graded"])
            save(rec_path, rec)
    # ---- write the locks back; drop the old ones
    cut = (now - dt.timedelta(days=KEEP_LOCK_DAYS)).strftime("%Y-%m-%d")
    for day, entry in locks.items():
        f = os.path.join(lock_dir, f"{day}.json")
        if day < cut:
            if os.path.exists(f): os.remove(f)
        elif entry["games"]:
            save(f, entry)
    for f in sorted(glob.glob(os.path.join(folder, "graded-*.json")))[:-KEEP_NIGHT_FILES]:
        os.remove(f)
    t = (rec or {}).get("total") or empty()
    say(f"nba grade: locked {sum(1 for x in new if x[2] == 'locked')}, missed {sum(1 for x in new if x[2] == 'missed')}, graded {len(graded_now)} game(s) this run"
        + (f" ({', '.join(f'{g}: {p} players, {d} did not play' for _, g, p, d in graded_now)})" if graded_now else "")
        + f"; record: {t['games']} games, {t['players']} player-games")
    return {"new": new, "graded": graded_now, "record": rec or None}


def summary(rec):
    """the record as the page shows it: mean misses, or None while nothing is graded"""
    t = (rec or {}).get("total")
    if not t or not t.get("players"):
        return None
    out = {"since": rec.get("since"), "nights": len(rec.get("nights") or []), "games": t["games"], "players": t["players"], "dnp": t["dnp"], "stats": {}}
    for k in STATS:
        s = t["stats"][k]
        if s["n"]:
            out["stats"][k] = {"n": s["n"], "model": s["model"] / s["n"], "base": s["base"] / s["n"], "bias": s["err"] / s["n"]}
    if t["min"]["n"]:
        out["min"] = {"n": t["min"]["n"], "mae": t["min"]["abs"] / t["min"]["n"], "bias": t["min"]["err"] / t["min"]["n"]}
    return out
