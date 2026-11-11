"""two_way.py - on the same line, which side has been paying: the over or the under?  (owner 11/10 deep dive)

  python3 research/two_way.py WEEK

Inputs: in/undersnaps.json ('V2 - FanDuel Under Snapshots': line, under price and over price, frozen before kickoff) and the week's
actuals from in/legsnaps.json (graded 'V2 - FanDuel Leg Snapshots').  One line per player + market (the last freeze before kickoff).
Prints, overall / by market / by the model's under %, each side's hit rate, the price's break-even rate and units won per 100 staked.
Read-only.  Week 9 was the first week with under snapshots.
"""
import json, os, sys

GP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def num(x):
    try: return float(str(x).replace("+", "").replace("%", "").replace(",", ""))
    except Exception: return None


def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / -o


def stale_pull(pulled, frozen, days=3):
    """True when the FanDuel pull behind a frozen row is more than `days` older than the freeze - another week's line."""
    import datetime
    def d(x):
        try: return datetime.datetime.strptime(str(x).strip()[:10], "%Y-%m-%d")
        except Exception: return None
    a, b = d(pulled), d(frozen)
    return bool(a and b and (b - a).days > days)


def rows_for(week):
    v = json.load(open(os.path.join(GP, "in", "legsnaps.json")))["values"]; H = {c: i for i, c in enumerate(v[0])}
    def g(r, c): return r[H[c]] if H[c] < len(r) else ""
    act = {}
    for r in v[1:]:
        if str(g(r, "Week")) == week and g(r, "Result") in ("HIT", "MISS") and num(g(r, "Actual")) is not None:
            act[(str(g(r, "Player")).strip().lower(), g(r, "Market"))] = num(g(r, "Actual"))
    u = json.load(open(os.path.join(GP, "in", "undersnaps.json")))["values"]; U = {c: i for i, c in enumerate(u[0])}
    def gu(r, c): return r[U[c]] if U[c] < len(r) else ""
    last = {}
    for r in u[1:]:
        if str(gu(r, "Week")) != week or gu(r, "Frozen at (CT)") > gu(r, "Kickoff (CT)"): continue
        if stale_pull(gu(r, "Pulled (CT)"), gu(r, "Frozen at (CT)")): continue      # 11/10: 15 Week 10 rows carry Week 9's lines (pulled 11/5)
        k = (str(gu(r, "Player")).strip().lower(), gu(r, "Market"))
        if k not in last or gu(r, "Frozen at (CT)") > gu(last[k], "Frozen at (CT)"): last[k] = r
    out = []
    for k, r in last.items():
        a, ln, uo, oo = act.get(k), num(gu(r, "Line")), num(gu(r, "Under odds")), num(gu(r, "Over odds"))
        if None in (a, ln, uo, oo) or a == ln: continue
        out.append((k[1], a < ln, uo, oo, num(gu(r, "Raw model under %"))))
    return out, len(last)


def show(lab, x):
    if not x: print(f"{lab:20} -"); return
    n = len(x); uh = sum(1 for _, h, *_ in x if h)
    ur = sum((dec(uo) - 1) if h else -1 for _, h, uo, _, _ in x) / n * 100
    orr = sum((dec(oo) - 1) if not h else -1 for _, h, _, oo, _ in x) / n * 100
    up = sum(1 / dec(uo) for _, _, uo, _, _ in x) / n * 100; op = sum(1 / dec(oo) for _, _, _, oo, _ in x) / n * 100
    print(f"{lab:20} n={n:4}  under hit {uh / n * 100:5.1f} (break-even {up:4.1f}) per100 {ur:+6.1f}   |   "
          f"over hit {100 - uh / n * 100:5.1f} (break-even {op:4.1f}) per100 {orr:+6.1f}")


if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    rows, n_lines = rows_for(sys.argv[1])
    print(f"week {sys.argv[1]}: {len(rows)} main lines graded of {n_lines} frozen (one per player + market)")
    show("ALL", rows)
    for mk in ("Receptions", "Receiving Yards", "Rushing Yards", "Passing Yards"): show(mk, [x for x in rows if x[0] == mk])
    show("model under >= 55%", [x for x in rows if x[4] is not None and x[4] >= 0.55])
    show("model under 45-55%", [x for x in rows if x[4] is not None and 0.45 <= x[4] < 0.55])
    show("model under < 45%", [x for x in rows if x[4] is not None and x[4] < 0.45])
