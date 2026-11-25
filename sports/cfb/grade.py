"""College football's postseason board graded game by game: lock, grade, record.

Owner's standing rule for anything new: it starts "tracked, not a lead" - nothing becomes a pick until it has been graded. The /cfb/ page went
up 11/23 with the posted line leading and our rating beside it; this is the grading that says, game by game, which of the two was closer.
Wanted before the conference title games on 12/4 (owner 11/24: "Yes please work on this"). The same three steps as the other sports
(sports/epl/grade.py), run inside the feeds-sports job on every run, after the board is written (sports/cfb/publish.py main):

  LOCK    When a game's kickoff has passed, its numbers - the posted spread and total, what they imply, and our rating's margin, total and
          win chance - are copied out of the LAST BOARD BUILT BEFORE KICKOFF and never touched again (cfb/locks/<kickoff date>.json). With
          no board from before kickoff in reach the game is marked MISSED and is never graded: a number written down after kickoff is not
          a projection. A game locked with no line posted is graded on our rating alone and counted apart.
  GRADE   As soon as ESPN's mirrored scoreboard calls the game final, on the final score - overtime included, as a sportsbook settles it:
            how far each margin was from the real one (the line's and ours), and each total;
            who was picked to win (the favorite; our rating's side) and the squared error of each win chance;
            our rating's side AGAINST the spread and its side of the total, each won / lost / push - kept two ways: every game, and only
            the games where the rating sat "apart" from the line (3+ points on the spread, 4+ on the total: the page's own words).
          A game ESPN calls postponed or canceled is set aside, not graded.
  RECORD  cfb/record.json keeps every graded game as a row and the totals, which are always re-added from the rows.

The branch these files live on is rebuilt from nothing on every run of the job, so the job copies them forward first
(.github/feeds_sports.py carry(): cfb/locks/*.json and cfb/record.json). Plain files in, plain files out: no pandas here.
"""
import datetime as dt
import glob
import os

from ..epl.grade import load, save, when

FORMAT = 1
APART = 3.0                 # build_cfb.NEAR: our rating this many points from the spread is "apart" from it
APART_TOTAL = 4.0           # build_cfb.NEAR_TOTAL
VOID = ("postponed", "canceled", "cancelled", "abandoned", "forfeit")
NUMS = ("home", "away", "margin", "total", "p_home")


def lock(locks, boards, now, known=()):
    """locks: {day: {"day", "games": {game id: {...}}}} (changed in place). boards: [(where it came from, board)], the newest first.
    Each game whose kickoff has passed and that has no entry yet gets one: from the latest board built before its kickoff, or missed.
    Returns [(day, game id, "locked" | "missed")] for what this call added."""
    done, seen = [], {}
    for src, b in boards:
        if not isinstance(b, dict):
            continue
        for g in b.get("games") or []:
            if g.get("id") and when(g.get("ko")):
                seen.setdefault(str(g["id"]), g)
    have = {gid for e in locks.values() for gid in e["games"]} | set(known)
    for gid, g in sorted(seen.items(), key=lambda kv: (str(kv[1].get("ko")), kv[0])):
        ko = when(g.get("ko"))
        if ko > now or gid in have:
            continue
        best = None
        for src, b in boards:
            built = when((b or {}).get("built")) if isinstance(b, dict) else None
            if not built or built >= ko:
                continue
            gg = next((x for x in b.get("games") or [] if str(x.get("id")) == gid), None)
            if gg and isinstance(gg.get("model"), dict) and (best is None or built > best[0]):
                best = (built, src, b, gg)
        day = ko.strftime("%Y-%m-%d")
        entry = locks.setdefault(day, {"day": day, "games": {}})
        head = {"id": gid, "key": g.get("key"), "name": g.get("name"), "ko": g.get("ko"), "home": g.get("home"), "away": g.get("away"), "neutral": bool(g.get("neutral")),
                "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
        if best:
            built, src, b, gg = best
            entry["games"][gid] = dict(head, board_built=b.get("built"), source=src, minutes_before_ko=round((ko - built).total_seconds() / 60),
                                       line=gg.get("line"), mkt=gg.get("mkt"), model=gg.get("model"))
            done.append((day, gid, "locked"))
        else:
            entry["games"][gid] = dict(head, missed=True, why="no board built before kickoff was in reach")
            done.append((day, gid, "missed"))
    return done


def final_score(ev):
    """ESPN's word on a game: None while it is not over, "void" when it will not be played as scheduled, else {"home", "away"}"""
    if not ev:
        return None
    det = str(ev.get("detail") or "").strip().lower()
    if det.startswith(VOID):
        return "void"
    if ev.get("state") != "post" or not ev.get("done"):
        return None
    t = {x.get("ha"): x for x in ev.get("teams") or []}
    try:
        return {"home": int(t["home"]["score"]), "away": int(t["away"]["score"])}
    except Exception:
        return None


def _wlp(x):
    return "push" if x == 0 else ("won" if x > 0 else "lost")


def grade_game(lk, fs):
    """one graded row: the locked numbers against the final score. Margins are home minus away, as the board keeps them."""
    model, mkt = lk.get("model") or {}, lk.get("mkt")
    am, at = fs["home"] - fs["away"], fs["home"] + fs["away"]
    home_won = 1.0 if am > 0 else 0.0
    row = {"id": lk.get("id"), "key": lk.get("key"), "name": lk.get("name"), "ko": lk.get("ko"), "home": lk.get("home"), "away": lk.get("away"), "final": [fs["away"], fs["home"]],
           "board_built": lk.get("board_built"), "minutes_before_ko": lk.get("minutes_before_ko"),
           "model": {"margin": model.get("margin"), "total": model.get("total"), "margin_miss": round(abs(model["margin"] - am), 1), "total_miss": round(abs(model["total"] - at), 1),
                     "right": (None if model["margin"] == 0 else int((model["margin"] > 0) == (am > 0))), "sq": round((float(model.get("p_home", 0.5)) - home_won) ** 2, 4)}}
    if isinstance(mkt, dict) and all(isinstance(mkt.get(k), (int, float)) for k in ("margin", "total")):
        gm, gt = round(model["margin"] - mkt["margin"], 1), round(model["total"] - mkt["total"], 1)
        row["line"] = {"by": (lk.get("line") or {}).get("by"), "margin": mkt["margin"], "total": mkt["total"], "margin_miss": round(abs(mkt["margin"] - am), 1), "total_miss": round(abs(mkt["total"] - at), 1),
                       "right": (None if mkt["margin"] == 0 else int((mkt["margin"] > 0) == (am > 0))), "sq": round((float(mkt.get("p_home", 0.5)) - home_won) ** 2, 4)}
        # our rating's side against the spread: toward the home side when our margin is the bigger one. It covers when the real margin beat the line's that way.
        row["ats"] = None if gm == 0 else {"side": lk.get("home") if gm > 0 else lk.get("away"), "gap": gm, "apart": abs(gm) >= APART, "res": _wlp((am - mkt["margin"]) * (1 if gm > 0 else -1))}
        row["ou"] = None if gt == 0 else {"side": "over" if gt > 0 else "under", "gap": gt, "apart": abs(gt) >= APART_TOTAL, "res": _wlp((at - mkt["total"]) * (1 if gt > 0 else -1))}
    return row


def totals(rows):
    """always re-added from the rows"""
    T = {"games": len(rows), "with_line": 0, "model": {"margin_miss": 0.0, "total_miss": 0.0, "right": [0, 0], "sq": 0.0},
         "both": {"n": 0, "model_margin_miss": 0.0, "line_margin_miss": 0.0, "model_total_miss": 0.0, "line_total_miss": 0.0, "model_closer": 0, "line_closer": 0, "model_sq": 0.0, "line_sq": 0.0,
                  "model_right": [0, 0], "line_right": [0, 0]},
         "ats": {"won": 0, "lost": 0, "push": 0}, "ats_apart": {"won": 0, "lost": 0, "push": 0}, "ou": {"won": 0, "lost": 0, "push": 0}, "ou_apart": {"won": 0, "lost": 0, "push": 0}}
    for r in rows:
        m = r["model"]
        T["model"]["margin_miss"] += m["margin_miss"]; T["model"]["total_miss"] += m["total_miss"]; T["model"]["sq"] += m["sq"]
        if m.get("right") is not None:
            T["model"]["right"][0] += m["right"]; T["model"]["right"][1] += 1
        ln = r.get("line")
        if not ln:
            continue
        T["with_line"] += 1; B = T["both"]; B["n"] += 1
        B["model_margin_miss"] += m["margin_miss"]; B["line_margin_miss"] += ln["margin_miss"]; B["model_total_miss"] += m["total_miss"]; B["line_total_miss"] += ln["total_miss"]
        B["model_sq"] += m["sq"]; B["line_sq"] += ln["sq"]
        if m["margin_miss"] < ln["margin_miss"]: B["model_closer"] += 1
        elif ln["margin_miss"] < m["margin_miss"]: B["line_closer"] += 1
        for who in ("model", "line"):
            x = (m if who == "model" else ln).get("right")
            if x is not None:
                B[who + "_right"][0] += x; B[who + "_right"][1] += 1
        for k in ("ats", "ou"):
            x = r.get(k)
            if x:
                T[k][x["res"]] += 1
                if x.get("apart"):
                    T[k + "_apart"][x["res"]] += 1
    for d in (T["model"], T["both"]):
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 4)
    return T


def run(folder, boards, scoreboard=None, now=None, say=print):
    """folder: the cfb/ folder of the branch being built (locks/, record.json). boards: [(source, board)] in reach, the newest first.
    scoreboard: ESPN's mirrored scoreboard ({"events": [...]}). Never raises on bad data: a file it cannot read is left exactly as it is."""
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lock_dir = os.path.join(folder, "locks")
    locks = {}
    for f in sorted(glob.glob(os.path.join(lock_dir, "*.json"))):
        d = load(f)
        if isinstance(d, dict) and d.get("day") and isinstance(d.get("games"), dict):
            locks[d["day"]] = d
    rec_path = os.path.join(folder, "record.json")
    rec = load(rec_path)
    readable = not (rec is None and os.path.exists(rec_path))
    if not isinstance(rec, dict):
        rec = {"format": FORMAT, "sport": "cfb", "since": None, "rows": []}
    for k in ("graded", "missed", "void"):
        if not isinstance(rec.get(k), dict):
            rec[k] = {}
    if not isinstance(rec.get("rows"), list):
        rec["rows"] = []
    new = lock(locks, boards, now, set(rec["graded"]) | set(rec["missed"]) | set(rec["void"]))
    changed_days = {d for d, _, _ in new}
    if not readable:
        for day in changed_days:
            save(os.path.join(lock_dir, f"{day}.json"), locks[day])
        say(f"cfb grade: record.json is there but cannot be read - left as it is, nothing graded this run (locked {sum(1 for x in new if x[2] == 'locked')})")
        return {"new": new, "graded": [], "void": [], "record": None}
    events = {str(e.get("id")): e for e in (scoreboard or {}).get("events") or []}
    graded_now, void_now, waiting = [], [], 0
    for day, entry in sorted(locks.items()):
        for gid, lk in sorted(entry["games"].items()):
            if lk.get("missed"):
                rec["missed"].setdefault(gid, day)
                continue
            if gid in rec["graded"] or gid in rec["void"]:
                continue
            fs = final_score(events.get(gid))
            if fs == "void":
                rec["void"][gid] = day; void_now.append(gid)
                continue
            if not fs:
                waiting += 1
                continue
            try:
                row = grade_game(lk, fs)
            except Exception as e:                  # a lock without the numbers it needs: say so, leave it waiting
                say(f"cfb grade: {gid} could not be graded ({type(e).__name__}: {e})"); waiting += 1
                continue
            row["graded_at"] = stamp
            rec["rows"].append(row); rec["graded"][gid] = day; graded_now.append(row)
            rec["since"] = rec.get("since") or day
    rec["rows"].sort(key=lambda r: (str(r.get("ko")), str(r.get("id"))))
    rec.update(format=FORMAT, sport="cfb", updated=stamp, waiting=waiting, total=totals(rec["rows"]), apart=[APART, APART_TOTAL])
    for day in changed_days:
        save(os.path.join(lock_dir, f"{day}.json"), locks[day])
    save(rec_path, rec)
    T = rec["total"]
    say(f"cfb grade: locked {sum(1 for x in new if x[2] == 'locked')}, missed {sum(1 for x in new if x[2] == 'missed')} this run; graded {len(graded_now)} "
        f"({', '.join(str(r.get('key')) + ' ' + '-'.join(map(str, r['final'])) for r in graded_now) or 'none'}); set aside {len(void_now)}; waiting {waiting}. "
        f"Record: {T['games']} games ({T['with_line']} with a line); rating's side vs the spread {T['ats']['won']}-{T['ats']['lost']}-{T['ats']['push']}"
        + (f"; margin missed by {T['both']['line_margin_miss'] / T['both']['n']:.1f} (line) and {T['both']['model_margin_miss'] / T['both']['n']:.1f} (rating)" if T["both"]["n"] else ""))
    return {"new": new, "graded": graded_now, "void": void_now, "record": rec}
