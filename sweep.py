#!/usr/bin/env python3
"""sweep.py - The Daily Sweep (owner 11/10: "I'd love for us to start 1-3").

One house slip per game day: three favorites at -300 to -200 (two or four when the board says so; four was the shape until 11/10), low-risk legs only, on the site before the first
kickoff and graded like every other promoted bet. Why it exists: the receipts showed 0-37 on the slips we posted in Weeks 6-9 (34 of
them +477 or longer) while the short favorite slips that won in Week 9 were built in chat and never went on the record.

A Daily Sweep is an ordinary row on 'PROMO - Promoted Bets' whose Title starts with "Daily Sweep" ("Daily Sweep: Buffalo Wings", or
just "Daily Sweep"). Legs, FanDuel odds, link, Status and Result work exactly as before - grade_promos.py, the receipt's "What we
posted" block, the /b/ short links and the posters need nothing new. This module is the one place that knows the convention:

  is_sweep(title)        True when the row is a Daily Sweep
  name(title)            the title without the marker ("Buffalo Wings"); "" when the row is only called Daily Sweep
  res_kind(result)       "W" / "L" / None from the tab's Result cell (Hit, Cashed, Won ... / Missed, Lost ...)
  units(odds, kind)      profit at 1 unit and the posted FanDuel odds (+3.05 for a +305 that cashed, -1 for a miss)
  fmt_u(u)               "+2.1u"
  record(values)         season record from the whole tab: {"n", "w", "l", "u", "pending", "weeks": {week: [w, l, u]}, "noprice"}
  one_per_day(promos)    at most one Sweep per game day in build_promo's list (lowest slot keeps the name; the rest are ordinary
                         promoted bets and a warning is returned for the run log)
  risk_score(leg, bd)    the builder's risk score for a leg of builder_data.json (bad 3, watch 1, good -1, floored at 0) - the same sum
                         PROMO_DESK rule 1 uses; 2-3 = "Some risk", 4+ = "High risk"

Rules the record depends on (PROMO_DESK.md "Daily Sweep", RUNBOOK Step 3c):
  - exactly one per game day, and the row goes on the tab BEFORE the first leg kicks off. Never add, rename or re-price one afterwards.
  - nothing is invented: a row without a Result is pending and counts for nothing.

python3 sweep.py --selftest runs the cases below.
"""
import re, datetime as dt
try:
    from zoneinfo import ZoneInfo
    CT = ZoneInfo("America/Chicago")
except Exception:   # pragma: no cover
    CT = dt.timezone(dt.timedelta(hours=-6))

PREFIX = re.compile(r"^\s*(?:the\s+)?daily\s+sweep\b\s*(?:[:\-–—·|]+\s*)?", re.I)
WIN = {"HIT", "CASHED", "CASH", "WON", "WIN", "W"}
LOSS = {"MISSED", "MISS", "LOST", "LOSS", "L"}

def is_sweep(title):
    return bool(PREFIX.match(str(title or "")))

def name(title):
    return PREFIX.sub("", str(title or ""), count=1).strip()

def res_kind(result):
    r = str(result or "").strip().upper()
    return "W" if r in WIN else "L" if r in LOSS else None

def _num(x):
    try: return float(str(x).replace("+", "").replace(",", "").strip())
    except Exception: return None

def units(odds, kind):
    """profit at 1 unit. A win without a posted price cannot be valued: returns None (the caller reports it, never guesses)."""
    if kind == "L": return -1.0
    o = _num(odds)
    if kind != "W" or not o: return None
    return o / 100.0 if o > 0 else 100.0 / -o

def record(values):
    """values = in/promos.json["values"] (header + every week's rows)."""
    out = {"n": 0, "w": 0, "l": 0, "u": 0.0, "pending": 0, "weeks": {}, "noprice": 0, "total": 0}
    if not values: return out
    H = {str(c).strip().split(" (")[0]: i for i, c in enumerate(values[0])}
    need = ("Week", "Title", "FanDuel odds", "Result")
    if any(k not in H for k in need): return out
    for r in values[1:]:
        r = list(r) + [""] * (len(values[0]) - len(r))
        if not is_sweep(r[H["Title"]]): continue
        wk = _num(r[H["Week"]])
        if wk is None: continue
        out["total"] += 1
        k = res_kind(r[H["Result"]])
        if not k: out["pending"] += 1; continue
        u = units(r[H["FanDuel odds"]], k)
        if u is None: out["noprice"] += 1; u = 0.0
        d = out["weeks"].setdefault(int(wk), [0, 0, 0.0])
        out["n"] += 1; out["w" if k == "W" else "l"] += 1; out["u"] += u
        d[0 if k == "W" else 1] += 1; d[2] += u
    return out

def fmt_u(u):
    """+2.1u - one decimal, halves rounded away from zero (3.05 - 1 is 2.0499... in binary and would print as +2.0)"""
    return f"{u + (1e-9 if u >= 0 else -1e-9):+.1f}u"

def record_text(R, short=False):
    """one plain line for the hero, the receipt and the season page"""
    if not R or not R.get("n"):
        return "Record starts with the first one" if not (R or {}).get("pending") else "First one is in play - the record starts when it is graded"
    s = f'{R["w"]}–{R["l"]} · {fmt_u(R["u"])} at 1 unit each'
    if short: return s
    if R.get("pending"): s += f' · {R["pending"]} pending'
    if R.get("noprice"): s += f' · units leave out {R["noprice"]} win{"s" if R["noprice"] != 1 else ""} posted without a price'
    return s

def day_of(ms):
    """CT calendar date of a kickoff in epoch ms - the 'game day' a Sweep belongs to. Games that kick off after midnight CT do not exist
    in the NFL schedule, so the calendar date is the game day."""
    if not ms: return None
    return dt.datetime.fromtimestamp(float(ms) / 1000, CT).strftime("%Y-%m-%d")

def day_label(ms):
    return dt.datetime.fromtimestamp(float(ms) / 1000, CT).strftime("%a %-m/%-d") if ms else ""

def one_per_day(promos):
    """promos = build_promo.py's list (dicts with title, slot, first_ko, status). Sets p["sweep"], p["name"], p["day"]; returns warnings."""
    warn = []; seen = {}
    for p in sorted(promos, key=lambda x: x.get("slot") or 0):
        p["sweep"] = is_sweep(p.get("title")); p["name"] = name(p.get("title")) if p["sweep"] else ""
        p["day"] = day_of(p.get("first_ko"))
        if not p["sweep"]: continue
        if not p["day"]:
            warn.append(f'Daily Sweep slot {p.get("slot")} "{p.get("title")}": no leg matched a game, so it has no game day - shown as an ordinary promoted bet'); p["sweep"] = False; continue
        if p["day"] in seen:
            warn.append(f'two Daily Sweeps on {p["day"]}: slot {seen[p["day"]]} keeps the name, slot {p.get("slot")} "{p.get("title")}" is shown as an ordinary promoted bet - rename it on the tab (one Sweep per game day)')
            p["sweep"] = False; continue
        seen[p["day"]] = p.get("slot")
    return warn

def risk_score(leg, bd):
    """leg = a builder_data.json leg (fh = [[kind, tag], ...] or [kind, ...]); bd["pf"][player] = the player-level flags."""
    W = {"bad": 3, "watch": 1, "good": -1}
    def kinds(fs):
        for f in fs or []:
            k = f[0] if isinstance(f, (list, tuple)) and f else (f.get("k") if isinstance(f, dict) else f)
            if k in W: yield k
    s = sum(W[k] for k in kinds(leg.get("fh"))) + sum(W[k] for k in kinds(((bd or {}).get("pf") or {}).get(leg.get("pl"))))
    return max(0, s)

def risk_tag(score):
    return "High risk" if score >= 4 else "Some risk" if score >= 2 else ""

def selftest():
    bad = 0
    def eq(got, want, what):
        nonlocal bad
        if got != want: bad += 1; print(f"FAIL {what}: got {got!r}, want {want!r}")
    for t, w, n in (("Daily Sweep: Buffalo Wings", True, "Buffalo Wings"), ("daily sweep", True, ""), ("The Daily Sweep – TNF", True, "TNF"),
                    ("Daily Sweep | Bear Down", True, "Bear Down"), ("Daily Sweeper", False, ""), ("Trick or Treat Sweep", False, ""),
                    ("The Clean Sweep", False, ""), ("Sunday Sweep: 11 Games", False, ""), ("  DAILY  SWEEP - Chalk", True, "Chalk")):
        eq(is_sweep(t), w, f"is_sweep({t})")
        if w: eq(name(t), n, f"name({t})")
    eq(res_kind("Hit"), "W", "Hit"); eq(res_kind("missed"), "L", "missed"); eq(res_kind(""), None, "blank"); eq(res_kind("PENDING"), None, "pending")
    eq(round(units("305", "W"), 2), 3.05, "+305 win"); eq(round(units("-120", "W"), 3), 0.833, "-120 win"); eq(units("305", "L"), -1.0, "loss"); eq(units("", "W"), None, "win, no price")
    vals = [["Week", "Slot", "Title", "Legs (one per line: who | market | FanDuel odds)", "FanDuel odds", "FanDuel link", "Status", "Caption", "Result", "Posted"],
            ["9", "8", "Buffalo Wings", "", "363", "", "HIDDEN", "", "Missed", ""],
            ["10", "1", "Daily Sweep: TNF", "", "305", "", "LIVE", "", "Hit", ""],
            ["10", "2", "Daily Sweep: Sunday", "", "+340", "", "LIVE", "", "Missed", ""],
            ["10", "3", "Piss Missile Monday", "", "4613", "", "LIVE", "", "Missed", ""],
            ["10", "4", "Daily Sweep: MNF", "", "290", "", "LIVE", "", "", ""],
            ["11", "1", "Daily Sweep", "", "", "", "LIVE", "", "Hit"]]
    R = record(vals)
    eq((R["n"], R["w"], R["l"], round(R["u"], 2), R["pending"], R["noprice"], R["total"]), (3, 2, 1, 2.05, 1, 1, 4), "record")
    eq(R["weeks"].get(10), [1, 1, 2.05], "week 10"); eq(R["weeks"].get(11), [1, 0, 0.0], "week 11")
    eq(record_text(R), "2–1 · +2.1u at 1 unit each · 1 pending · units leave out 1 win posted without a price", "record_text")
    eq(fmt_u(2.05), "+2.1u", "fmt_u half up"); eq(fmt_u(-1.0), "-1.0u", "fmt_u loss"); eq(fmt_u(0.0), "+0.0u", "fmt_u zero")
    eq(record_text(record(vals[:2])), "Record starts with the first one", "empty record")
    thu = dt.datetime(2026, 11, 12, 19, 15, tzinfo=CT).timestamp() * 1000; sun = dt.datetime(2026, 11, 15, 12, 0, tzinfo=CT).timestamp() * 1000
    ps = [{"title": "Daily Sweep: A", "slot": 2, "first_ko": thu}, {"title": "Daily Sweep: B", "slot": 1, "first_ko": thu}, {"title": "Daily Sweep", "slot": 3, "first_ko": sun},
          {"title": "Lotto", "slot": 4, "first_ko": sun}, {"title": "Daily Sweep: C", "slot": 5, "first_ko": None}]
    w = one_per_day(ps)
    eq([(p["slot"], p["sweep"], p["day"]) for p in sorted(ps, key=lambda x: x["slot"])], [(1, True, "2026-11-12"), (2, False, "2026-11-12"), (3, True, "2026-11-15"), (4, False, "2026-11-15"), (5, False, None)], "one_per_day")
    eq(len(w), 2, "one_per_day warnings")
    eq(day_label(thu), "Thu 11/12", "day_label")
    bd = {"pf": {"A": [["watch", "x"]], "B": [["bad", "x"], ["good", "y"]]}}
    eq(risk_score({"pl": "A", "fh": [["watch", "t"]]}, bd), 2, "risk A"); eq(risk_score({"pl": "B", "fh": []}, bd), 2, "risk B"); eq(risk_score({"pl": "C", "fh": [["good", "g"]]}, bd), 0, "risk floor")
    eq(risk_tag(4), "High risk", "tag 4"); eq(risk_tag(2), "Some risk", "tag 2"); eq(risk_tag(1), "", "tag 1")
    print(f"sweep selftest: {'ok' if not bad else str(bad) + ' failed'}"); return bad

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": sys.exit(1 if selftest() else 0)
    print(__doc__)
