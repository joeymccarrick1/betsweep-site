"""The Premier League board graded match by match: lock, grade, record.

Owner's standing rule for anything new: it starts "tracked, not a lead" - nothing becomes a pick until it has been graded. The /epl/ page went
up 11/22 with model numbers only; this is the grading it has to earn its picks with. The same three steps as the NBA's (sports/nba/grade.py),
run inside the feeds-sports job on every run, after the board is written or carried forward (sports/epl/publish.py main):

  LOCK    When a match's kickoff has passed, its numbers - the result chances, each side's expected goals, and every player row of the two
          clubs - are copied out of the LAST BOARD BUILT BEFORE KICKOFF and never touched again (epl/locks/<kickoff date>.json). That board
          is normally a few minutes old and carries the confirmed elevens. With no board from before kickoff in reach the match is marked
          MISSED and is never graded: a number written down after kickoff is not a projection.
  GRADE   In two parts, because the two answers arrive at different times.
          The match, as soon as ESPN's mirrored fixture list calls it final: home / draw / away, over 2.5, both to score and each side's
          goals, scored for the model and for "every match alike" - the same model given two average sides, which is what you would say
          knowing nothing about the clubs. A match ESPN calls postponed or abandoned is set aside, not graded. A knockout match
          that went to extra time or penalties was a draw at ninety minutes and is graded as one, on the result alone (grade_match).
          The players, when the data set has the match (hours later, sometimes the next day): ONLY PLAYERS WHO STARTED, because every
          player number on the board is "if he starts" - chance to score, chance of an assist, shots, shots on target, the shot ladders
          and his minutes, each beside his own season average over the same minutes. Players who came on or did not play are counted,
          not graded. If the data set and ESPN disagree on the score the players are left ungraded and the run says so.
  RECORD  epl/record.json keeps one row of sums per gameweek and the totals, which are always the sum of the rows. epl/graded-gwNN.json
          keeps the last few gameweeks match by match and player by player. A league without gameweeks gives each match the Tuesday its
          week starts on as its round (20261124: sports/soccer/publish.py week_key), and everything here works the same.

The other soccer leagues (sports/soccer/publish.py) are graded by this same code, each in its own folder with its own record
(run(..., sport="bun")); there the players' results come from the job's own season file, usually in the same run as the final.

The branch these files live on is rebuilt from nothing on every run of the job, so the job copies them forward before anything else
(.github/feeds_sports.py carry()). Nothing here needs pandas: plain files in, plain files out, so it can be tested anywhere.
"""
import datetime as dt
import glob
import json
import math
import os
import re

FORMAT = 1
EDGES = (0.2, 0.4, 0.6, 0.8)                 # five bands of stated chance for a match's chances and the shot ladders: under 20%, 20-40, 40-60, 60-80, 80 and up
GOAL_EDGES = (0.05, 0.10, 0.20, 0.30)        # a player's chance to score or assist sits low: under 5%, 5-10, 10-20, 20-30, 30 and up
MATCH_CHANCES = ("home", "draw", "away", "over15", "over25", "over35", "btts")
THREE = ("home", "draw", "away")
REGULAR = 3                                  # starts in the club's last five that make a player "a regular" before the elevens are posted (the page's rule)
MIN_BASE_MINUTES = 270                       # a season average needs three matches' worth of minutes behind it
KEEP_LOCK_DAYS = 10                          # a lock still not fully graded after this many days is dropped (a postponement, results that never came)
KEEP_ROUND_FILES = 4                         # match-by-match files kept
VOID = ("postponed", "canceled", "cancelled", "abandoned")
BEYOND = re.compile(r"\b(aet|pens?|penalties|extra time)\b")        # ESPN's "AET", "FT-Pens", "After Extra Time", "After Penalties" (and not "suspended")


def when(s):
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
    """whole or not at all"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), separators=(",", ":"))
    os.replace(tmp, path)


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def regular(p):
    """the page's own rule: in the confirmed eleven, or - before it is posted - three or more starts in his club's last five"""
    return p.get("xi") == "start" or (p.get("xi") is None and (p.get("starts5") or 0) >= REGULAR)


def season_average(p):
    """What one start has brought him this season, whoever the opponent: his season totals scaled to the minutes the model gives him when
    he starts. None when he has played too little for an average to mean anything."""
    mins, sm, tot = p.get("mins") or 0, p.get("start_min") or 0, p.get("tot") or {}
    if mins < MIN_BASE_MINUTES or not sm:
        return None
    f = sm / mins
    g, a = (tot.get("goals") or 0) * f, (tot.get("assists") or 0) * f
    return {"p_goal": round(1 - math.exp(-g), 4), "p_assist": round(1 - math.exp(-a), 4),
            "shots": round((tot.get("shots") or 0) * f, 2), "sot": round((tot.get("sot") or 0) * f, 2)}


def slim(p):
    """what is kept of a board player at the lock: enough to grade him and to show the result"""
    return {"id": str(p.get("id")), "name": p.get("name"), "team": p.get("team"), "pos": p.get("pos"), "xi": p.get("xi"), "starts5": p.get("starts5"),
            "reg": bool(regular(p)), "start_min": p.get("start_min"), "p_goal": p.get("p_goal"), "p_assist": p.get("p_assist"), "shots": p.get("shots"), "sot": p.get("sot"),
            "ladder": {k: [[r[0], r[1]] for r in ((p.get("ladder") or {}).get(k) or [])] for k in ("shots", "sot")},
            "base": season_average(p), "tag": ((p.get("status") or {}).get("tag") or "")}


def lock(locks, boards, now, known=()):
    """locks: {day: {"day", "matches": {match id: {...}}}} (changed in place). boards: [(where it came from, board)] - every board in reach, the
    newest first (its kickoff time is the one believed). known: ids the record already holds, never locked twice.
    Each match whose kickoff has passed and that has no entry yet gets one: locked from the latest board built before its kickoff, or missed.
    Returns [(day, match id, "locked" | "missed")] for what this call added."""
    done, seen = [], {}
    for src, b in boards:
        if not isinstance(b, dict):
            continue
        for m in b.get("matches") or []:
            if m.get("id") and when(m.get("ko")):
                seen.setdefault(str(m["id"]), m)
    have = {mid for e in locks.values() for mid in e["matches"]} | set(known)
    for mid, m in sorted(seen.items(), key=lambda kv: (str(kv[1].get("ko")), kv[0])):
        ko = when(m.get("ko"))
        if ko > now or mid in have:
            continue
        best = None
        for src, b in boards:
            built = when((b or {}).get("built")) if isinstance(b, dict) else None
            if not built or built >= ko:
                continue
            mm = next((x for x in b.get("matches") or [] if str(x.get("id")) == mid), None)
            ps = [slim(p) for p in b.get("players") or [] if str(p.get("match")) == mid]
            if mm and ps and (best is None or built > best[0]):
                best = (built, src, ps, b, mm)
        day = ko.strftime("%Y-%m-%d")
        entry = locks.setdefault(day, {"day": day, "matches": {}})
        head = {"id": mid, "espn": m.get("espn"), "key": m.get("key"), "gw": m.get("gw"), "ko": m.get("ko"), "home": m.get("home"), "away": m.get("away"),
                "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        if best:
            built, src, ps, b, mm = best
            entry["matches"][mid] = dict(head, board_built=b.get("built"), source=src, minutes_before_ko=round((ko - built).total_seconds() / 60),
                                         p=mm.get("p"), xg=mm.get("xg"), scores=mm.get("scores"), shots=mm.get("shots"), line=mm.get("line"),
                                         lineups=bool(mm.get("lineups")), base=b.get("base"), players=ps)
            done.append((day, mid, "locked"))
        else:
            entry["matches"][mid] = dict(head, missed=True, why="no board built before kickoff was in reach")
            done.append((day, mid, "missed"))
    return done


def final_score(ev):
    """ESPN's word on a match: None while it is not over, "void" when it will not be played as scheduled, else {"home", "away"} -
    with "beyond": True when it was settled in extra time or on penalties, so the score shown is not a ninety-minute score"""
    if not ev:
        return None
    det = str(ev.get("detail") or "").strip().lower()
    if det.startswith(VOID):
        return "void"
    if ev.get("state") != "post" or not ev.get("done"):
        return None
    t = {x.get("ha"): x for x in ev.get("teams") or []}
    try:
        fs = {"home": int(t["home"]["score"]), "away": int(t["away"]["score"])}
    except Exception:
        return None
    if BEYOND.search(det):
        fs["beyond"] = True      # a knockout match that went to extra time or penalties (the MLS playoffs): see grade_match
    return fs


def _imp(ml):
    """an American price as the chance it implies, the book's cut still in it; None for anything that is not a price"""
    if isinstance(ml, bool) or not isinstance(ml, (int, float)) or abs(ml) < 100:
        return None
    return 100.0 / (ml + 100.0) if ml > 0 else -ml / (-ml + 100.0)


def market(line):
    """the posted three-way price as chances with the book's cut taken out evenly (each implied chance divided by their sum):
    {"home", "draw", "away", "hold"} - plus "over25" when the posted total is 2.5 and both sides of it are priced. None unless all
    three prices are there. Owner 11/24 ("Yes."): the posted price is the bar the model has to beat."""
    line = line or {}
    q = {k: _imp(line.get(k + "_ml")) for k in THREE}
    if any(v is None for v in q.values()):
        return None
    s = sum(q.values())
    if not (1.0 <= s <= 1.35):                       # three prices that do not add up to a book's cut are not a market (a stale or half-posted line)
        return None
    out = {k: q[k] / s for k in THREE}; out["hold"] = s - 1.0
    o, u = _imp(line.get("over")), _imp(line.get("under"))
    if line.get("total") == 2.5 and o is not None and u is not None and 1.0 <= o + u <= 1.25:
        out["over25"] = o / (o + u)
    return out


def bucket(p, edges):
    return sum(1 for e in edges if p >= e)


def empty():
    z = lambda n: [[0, 0, 0.0] for _ in range(n)]            # per band: how many chances were stated, how many happened, the sum of what was stated
    ev = lambda: {"n": 0, "brier": 0.0, "base": 0.0, "hit": 0}
    ch = lambda: {"n": 0, "hit": 0, "exp": 0.0, "bn": 0, "brier": 0.0, "base": 0.0}
    ct = lambda: {"n": 0, "model": 0.0, "base": 0.0, "err": 0.0}
    return {"matches": 0, "pmatches": 0,
            "res": {"n": 0, "brier": 0.0, "base": 0.0, "ll": 0.0, "bll": 0.0, "top": 0, "btop": 0},
            "o25": ev(), "btts": ev(), "goals": ct(), "cal": z(len(EDGES) + 1),
            # 11/24, against the posted price (market()), on the matches that had one at the lock: the price's miss score and the model's on those same matches
            "mkt": {"n": 0, "price": 0.0, "model": 0.0, "pll": 0.0, "mll": 0.0, "ptop": 0, "mtop": 0, "on": 0, "oprice": 0.0, "omodel": 0.0},
            "pl": {"n": 0, "sub": 0, "dnp": 0, "reg": 0, "reg_start": 0, "goal": ch(), "assist": ch(), "shots": ct(), "sot": ct(),
                   "min": {"n": 0, "abs": 0.0, "err": 0.0},
                   "cal": {"goal": z(len(GOAL_EDGES) + 1), "assist": z(len(GOAL_EDGES) + 1), "shots": z(len(EDGES) + 1), "sot": z(len(EDGES) + 1)}}}


def add(a, b):
    """a += b, over the sums only (a row's gameweek and ids are not sums and are left alone)"""
    for k, v in b.items():
        if k not in a:
            continue
        if isinstance(v, dict) and isinstance(a[k], dict):
            add(a[k], v)
        elif isinstance(v, list) and isinstance(a[k], list) and k != "ids" and k != "pids":
            for i, row in enumerate(v):
                if i < len(a[k]):
                    for j, x in enumerate(row):
                        a[k][i][j] += x
        elif num(v) and num(a[k]) and k != "gw":
            a[k] += v
    return a


def norm(row):
    """a stored row, with every sum this version knows (a row written by an older version gains the new ones at zero)"""
    r = add(empty(), row)
    r["gw"] = row.get("gw"); r["ids"] = list(row.get("ids") or []); r["pids"] = list(row.get("pids") or [])
    return r


def rounded(x):
    if isinstance(x, float):
        return round(x, 4)
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [rounded(v) for v in x]
    return x


def grade_match(lk, fs):
    """one locked match against its final score -> (sums, what happened).
    Every chance on the board is for ninety minutes. A knockout match that went to extra time or penalties (fs["beyond"]) was level at
    ninety - it could not have gone on otherwise - so it is graded as the draw it was, on home / draw / away alone: the ninety-minute
    score is not known from the final, so its totals, both-to-score and goals are left out (and run() leaves its players out)."""
    S = empty(); S["matches"] = 1
    h, a = fs["home"], fs["away"]
    beyond = bool(fs.get("beyond"))
    out = "draw" if beyond else ("home" if h > a else ("away" if a > h else "draw"))
    hap = {"home": out == "home", "draw": out == "draw", "away": out == "away", "over15": h + a >= 2, "over25": h + a >= 3, "over35": h + a >= 4, "btts": h >= 1 and a >= 1}
    p = lk.get("p") or {}; bp = (lk.get("base") or {}).get("p") or {}
    ok = lambda q, ks: all(num(q.get(k)) for k in ks)
    if ok(p, THREE) and ok(bp, THREE):
        R = S["res"]; R["n"] = 1
        R["brier"] = sum((p[k] - hap[k]) ** 2 for k in THREE); R["base"] = sum((bp[k] - hap[k]) ** 2 for k in THREE)
        R["ll"] = -math.log(max(p[out], 1e-6)); R["bll"] = -math.log(max(bp[out], 1e-6))
        R["top"] = int(max(THREE, key=lambda k: p[k]) == out); R["btop"] = int(max(THREE, key=lambda k: bp[k]) == out)
    mk = market(lk.get("line"))
    if mk and ok(p, THREE):                          # a three-way price is a ninety-minute price, so a match that went beyond is graded here as its draw too
        M = S["mkt"]; M["n"] = 1
        M["price"] = sum((mk[k] - hap[k]) ** 2 for k in THREE); M["model"] = sum((p[k] - hap[k]) ** 2 for k in THREE)
        M["pll"] = -math.log(max(mk[out], 1e-6)); M["mll"] = -math.log(max(p[out], 1e-6))
        M["ptop"] = int(max(THREE, key=lambda k: mk[k]) == out); M["mtop"] = int(max(THREE, key=lambda k: p[k]) == out)
        if not beyond and "over25" in mk and ok(p, ("over25",)):
            M["on"] = 1; M["oprice"] = (mk["over25"] - hap["over25"]) ** 2; M["omodel"] = (p["over25"] - hap["over25"]) ** 2
    for key, k in (("o25", "over25"), ("btts", "btts")):
        if not beyond and ok(p, (k,)) and ok(bp, (k,)):
            S[key] = {"n": 1, "brier": (p[k] - hap[k]) ** 2, "base": (bp[k] - hap[k]) ** 2, "hit": int(hap[k])}
    for k in (THREE if beyond else MATCH_CHANCES):
        if ok(p, (k,)):
            c = S["cal"][bucket(p[k], EDGES)]; c[0] += 1; c[1] += int(hap[k]); c[2] += p[k]
    xg = lk.get("xg") or {}; bx = (lk.get("base") or {}).get("xg") or {}
    for side, got in (("home", h), ("away", a)):
        if not beyond and ok(xg, (side,)) and ok(bx, (side,)):
            G = S["goals"]; G["n"] += 1; G["model"] += abs(xg[side] - got); G["base"] += abs(bx[side] - got); G["err"] += got - xg[side]
    info = {"result": out, "final": {"home": h, "away": a}}
    if beyond: info["beyond"] = True
    return S, info


def grade_players(lk, act):
    """one locked match's player rows against who played and what they did -> (sums, rows). act: {"players": {id: {min, started, g, a, sh, sot}}}"""
    S = empty(); S["pmatches"] = 1
    P, rows = S["pl"], []
    got = {str(k): v for k, v in (act.get("players") or {}).items()}
    for p in lk.get("players") or []:
        a = got.get(str(p.get("id")))
        started, reg = bool(a and a.get("started")), bool(p.get("reg"))
        P["reg"] += int(reg); P["reg_start"] += int(reg and started)
        row = {"id": p.get("id"), "name": p.get("name"), "team": p.get("team"), "pos": p.get("pos"), "reg": reg, "xi": p.get("xi"), "started": started}
        if not started:
            P["sub" if a else "dnp"] += 1
            rows.append(dict(row, got=({"min": a.get("min")} if a else None)))
            continue
        P["n"] += 1
        base = p.get("base") or None
        did = {"goal": int((a.get("g") or 0) >= 1), "assist": int((a.get("a") or 0) >= 1)}
        for key, pk in (("goal", "p_goal"), ("assist", "p_assist")):
            q = p.get(pk)
            if not num(q):
                continue
            T, y = P[key], did[key]
            T["n"] += 1; T["hit"] += y; T["exp"] += q
            c = P["cal"][key][bucket(q, GOAL_EDGES)]; c[0] += 1; c[1] += y; c[2] += q
            if base and num(base.get(pk)):
                T["bn"] += 1; T["brier"] += (q - y) ** 2; T["base"] += (base[pk] - y) ** 2
        for key, ak in (("shots", "sh"), ("sot", "sot")):
            q, v = p.get(key), a.get(ak) or 0
            if not num(q):
                continue
            for k, pr in ((p.get("ladder") or {}).get(key) or []):
                c = P["cal"][key][bucket(pr, EDGES)]; c[0] += 1; c[1] += int(v >= k); c[2] += pr
            if base and num(base.get(key)):
                T = P[key]; T["n"] += 1; T["model"] += abs(q - v); T["base"] += abs(base[key] - v); T["err"] += v - q
        sm, mn = p.get("start_min"), a.get("min")
        if num(sm) and num(mn):
            P["min"]["n"] += 1; P["min"]["abs"] += abs(sm - mn); P["min"]["err"] += mn - sm
        rows.append(dict(row, got={"min": a.get("min"), "g": a.get("g") or 0, "a": a.get("a") or 0, "sh": a.get("sh") or 0, "sot": a.get("sot") or 0},
                         said={"p_goal": p.get("p_goal"), "p_assist": p.get("p_assist"), "shots": p.get("shots"), "sot": p.get("sot"), "min": sm}, base=base))
    return S, rows


def wanted(folder):
    """the match ids whose player results are still to come: locked, not missed or set aside, and not yet graded player by player"""
    done = set((load(os.path.join(folder, "record.json")) or {}).get("pgraded") or {})
    out = []
    for f in sorted(glob.glob(os.path.join(folder, "locks", "*.json"))):
        for mid, lk in ((load(f) or {}).get("matches") or {}).items():
            if not lk.get("missed") and not lk.get("void") and not lk.get("beyond") and mid not in done:
                out.append(mid)
    return sorted(out)


def run(folder, boards, scoreboard=None, actuals=None, now=None, say=print, sport="epl"):
    """folder: the epl/ folder of the branch being built (locks/, record.json, graded-gwNN.json).
    boards: [(source, board)] in reach, the newest first. scoreboard: ESPN's mirrored fixture list ({"events": [...]}).
    actuals: {match id: {"final": {"home", "away"}, "players": {id: {min, started, g, a, sh, sot}}}} for the matches the data set has.
    Never raises on bad data: a file it cannot read is left exactly as it is."""
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lock_dir = os.path.join(folder, "locks")
    locks = {}
    for f in sorted(glob.glob(os.path.join(lock_dir, "*.json"))):
        d = load(f)
        if isinstance(d, dict) and d.get("day") and isinstance(d.get("matches"), dict):
            locks[d["day"]] = d
    rec_path = os.path.join(folder, "record.json")
    rec = load(rec_path)
    readable = not (rec is None and os.path.exists(rec_path))
    if not isinstance(rec, dict):
        rec = {"format": FORMAT, "sport": sport, "since": None, "rounds": []}
    for k in ("graded", "pgraded", "missed", "void", "beyond"):
        if not isinstance(rec.get(k), dict):
            rec[k] = {}
    # ---- lock (always: a kickoff does not wait for a record that cannot be read)
    new = lock(locks, boards, now, set(rec["graded"]) | set(rec["missed"]))
    if not readable:
        for day, entry in locks.items():
            if entry["matches"]:
                save(os.path.join(lock_dir, f"{day}.json"), entry)
        say(f"{sport} grade: record.json is there but cannot be read - left as it is, nothing graded this run (locked {sum(1 for x in new if x[2] == 'locked')})")
        return {"new": new, "graded": [], "players": [], "void": [], "notes": [], "record": None}
    # ---- grade
    rounds = {r.get("gw"): norm(r) for r in rec.get("rounds") or [] if isinstance(r, dict)}
    events = {str(e.get("id")): e for e in (scoreboard or {}).get("events") or []}
    graded_now, players_now, void_now, notes = [], [], [], []
    for day, entry in sorted(locks.items()):
        for mid, lk in sorted(entry["matches"].items()):
            if lk.get("missed"):
                rec["missed"].setdefault(mid, day)
                continue
            if lk.get("void"):
                continue
            gw = lk.get("gw") if isinstance(lk.get("gw"), int) else 0
            rf = os.path.join(folder, f"graded-gw{gw:02d}.json")
            head = {"key": lk.get("key"), "ko": lk.get("ko"), "home": lk.get("home"), "away": lk.get("away"), "board_built": lk.get("board_built"), "source": lk.get("source"),
                    "minutes_before_ko": lk.get("minutes_before_ko"), "lineups": lk.get("lineups"), "p": lk.get("p"), "xg": lk.get("xg"), "base": lk.get("base")}
            if mid not in rec["graded"]:
                ev = events.get(str(lk.get("espn")))
                fs = final_score(ev)
                if fs == "void":
                    lk["void"] = True; lk["why"] = f"ESPN: {ev.get('detail')}"
                    rec["void"][mid] = day; void_now.append(mid)
                    continue
                if not fs:
                    continue
                S, info = grade_match(lk, fs)
                r = rounds.setdefault(gw, dict(empty(), gw=gw, ids=[], pids=[]))
                add(r, S); r["ids"].append(mid)
                rec["graded"][mid] = day
                rec["since"] = min(x for x in (rec.get("since"), day) if x)
                lk["final"] = info["final"]; lk["result"] = info["result"]
                rd = load(rf) or {"gw": gw, "matches": {}}
                rd["matches"][mid] = dict(head, final=info["final"], result=info["result"], rows=None)
                if info.get("beyond"):
                    lk["beyond"] = True; rec["beyond"][mid] = day; rd["matches"][mid]["beyond"] = True
                save(rf, rd)
                graded_now.append(mid)
            if mid in rec["graded"] and mid not in rec["pgraded"] and not lk.get("beyond") and actuals and mid in actuals:
                act, fin = actuals[mid], lk.get("final")
                af = act.get("final")
                if fin and af and (af.get("home"), af.get("away")) != (fin.get("home"), fin.get("away")):
                    notes.append(f"{lk.get('key')}: ESPN's final is {fin.get('home')}-{fin.get('away')}, the data set's {af.get('home')}-{af.get('away')} - players left ungraded")
                    continue
                S, rows = grade_players(lk, act)
                r = rounds.setdefault(gw, dict(empty(), gw=gw, ids=[], pids=[]))
                add(r, S); r["pids"].append(mid)
                rec["pgraded"][mid] = day
                rd = load(rf) or {"gw": gw, "matches": {}}
                rd["matches"].setdefault(mid, dict(head, final=fin, result=lk.get("result"), rows=None))["rows"] = rows
                save(rf, rd)
                players_now.append((mid, S["pl"]["n"], S["pl"]["sub"], S["pl"]["dnp"]))
    if graded_now or players_now or void_now or new or not os.path.exists(rec_path):
        rec["rounds"] = [rounded(rounds[g]) for g in sorted(rounds, key=lambda g: (g is None, g or 0))]
        total = empty()
        for r in rec["rounds"]:
            add(total, r)
        rec["total"] = rounded(total)
        rec["updated"] = stamp
        # ids are kept three weeks: by then a match's lock is long gone and it cannot come round again
        keep_from = (now - dt.timedelta(days=21)).strftime("%Y-%m-%d")
        for k in ("graded", "pgraded", "missed", "void", "beyond"):
            rec[k] = {m: d for m, d in rec[k].items() if d >= keep_from}
        live = [(mid, lk) for e in locks.values() for mid, lk in e["matches"].items() if not lk.get("missed") and not lk.get("void")]
        rec["waiting"] = sum(1 for mid, lk in live if mid not in rec["graded"])
        rec["pwaiting"] = sum(1 for mid, lk in live if mid in rec["graded"] and mid not in rec["pgraded"] and not lk.get("beyond"))
        save(rec_path, rec)
    # ---- write the locks back; drop the old ones
    cut = (now - dt.timedelta(days=KEEP_LOCK_DAYS)).strftime("%Y-%m-%d")
    for day, entry in locks.items():
        f = os.path.join(lock_dir, f"{day}.json")
        if day < cut:
            if os.path.exists(f):
                os.remove(f)
        elif entry["matches"]:
            save(f, entry)
    for f in sorted(glob.glob(os.path.join(folder, "graded-gw*.json")))[:-KEEP_ROUND_FILES]:
        os.remove(f)
    t = rec.get("total") or empty()
    say(f"{sport} grade: locked {sum(1 for x in new if x[2] == 'locked')}, missed {sum(1 for x in new if x[2] == 'missed')}, graded {len(graded_now)} match(es)"
        + (f" ({', '.join(graded_now)})" if graded_now else "")
        + f", players of {len(players_now)}" + (f" ({', '.join(f'{m}: {n} starters, {s} came on, {d} did not play' for m, n, s, d in players_now)})" if players_now else "")
        + (f", set aside {len(void_now)}" if void_now else "")
        + f"; record: {t['matches']} matches, players of {t['pmatches']}; waiting {rec.get('waiting', 0)} for a final, {rec.get('pwaiting', 0)} for player results"
        + (" | " + " | ".join(notes) if notes else ""))
    return {"new": new, "graded": graded_now, "players": players_now, "void": void_now, "notes": notes, "record": rec}


def summary(rec):
    """the record as the page shows it: mean scores and misses, or None while no match is graded"""
    t = (rec or {}).get("total")
    if not isinstance(t, dict) or not t.get("matches"):
        return None
    t = add(empty(), t)
    div = lambda a, b: (a / b) if b else None
    ev = lambda s: ({"n": s["n"], "model": s["brier"] / s["n"], "base": s["base"] / s["n"], "hit": s["hit"]} if s["n"] else None)
    out = {"since": rec.get("since"), "rounds": len(rec.get("rounds") or []), "matches": t["matches"], "pmatches": t["pmatches"],
           "res": ({"n": t["res"]["n"], "model": t["res"]["brier"] / t["res"]["n"], "base": t["res"]["base"] / t["res"]["n"], "top": t["res"]["top"], "btop": t["res"]["btop"]} if t["res"]["n"] else None),
           "o25": ev(t["o25"]), "btts": ev(t["btts"]),
           "goals": ({"n": t["goals"]["n"], "model": t["goals"]["model"] / t["goals"]["n"], "base": t["goals"]["base"] / t["goals"]["n"], "bias": t["goals"]["err"] / t["goals"]["n"]} if t["goals"]["n"] else None),
           "pl": None}
    M = t["mkt"]
    out["mkt"] = ({"n": M["n"], "price": M["price"] / M["n"], "model": M["model"] / M["n"], "ptop": M["ptop"], "mtop": M["mtop"],
                   "o25": ({"n": M["on"], "price": M["oprice"] / M["on"], "model": M["omodel"] / M["on"]} if M["on"] else None)} if M["n"] else None)
    P = t["pl"]
    if P["n"]:
        ch = lambda s: {"n": s["n"], "hit": s["hit"], "exp": s["exp"], "bn": s["bn"], "model": div(s["brier"], s["bn"]), "base": div(s["base"], s["bn"])}
        ct = lambda s: ({"n": s["n"], "model": s["model"] / s["n"], "base": s["base"] / s["n"], "bias": s["err"] / s["n"]} if s["n"] else None)
        out["pl"] = {"n": P["n"], "sub": P["sub"], "dnp": P["dnp"], "reg": P["reg"], "reg_start": P["reg_start"], "goal": ch(P["goal"]), "assist": ch(P["assist"]),
                     "shots": ct(P["shots"]), "sot": ct(P["sot"]), "min": ({"n": P["min"]["n"], "mae": P["min"]["abs"] / P["min"]["n"], "bias": P["min"]["err"] / P["min"]["n"]} if P["min"]["n"] else None)}
    return out
