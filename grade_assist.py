#!/usr/bin/env python3
"""grade_assist.py - Tuesday grading of the chat-built slips in 'ASSIST - Slip Log' (owner 11/10: they were graded by hand).

Reads  in/assist.json   ({"values": 'ASSIST - Slip Log'!A1:J500} - Date | Week | Game(s) | Slip | Legs | Price | Type | Built by | Result | Notes)
       in/gamelog.json + in/games.csv through slipgrade.py (the same rules as the PROMO grader: nothing is invented).
Writes out/assist_grades.json:
  {"week": W, "updates": [{"range": "'ASSIST - Slip Log'!I<row>:J<row>", "values": [["WON" | "LOST", "<notes>"]]}], "pending": [...], "summary": "..."}
The run writes each update back with update_values. Only rows of week W whose Result is EMPTY are touched; a slip with a leg that cannot be
read or has no stat row stays empty (unless another leg has plainly missed - then it is LOST whatever the unread leg did) and is named in
"pending" for a hand grade. An existing note is kept; the leg-by-leg line is added after it.

Usage: python3 grade_assist.py [week]            default: the latest week in the tab that has an ungraded row and a game log
       python3 grade_assist.py [week] --check    grade the rows that already HAVE a result and say where the grader disagrees (changes nothing)
       --file=PATH / --out=PATH                  another copy of the tab / another place for the result (tests)
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE); import slipgrade as SG
COLS = ["Date", "Week", "Game(s)", "Slip", "Legs", "Price", "Type", "Built by", "Result", "Notes"]

def load(path=None):
    try: v = json.load(open(path or os.path.join(IN, "assist.json")))["values"]
    except Exception as e: raise SystemExit(f"no in/assist.json ({e}) - read 'ASSIST - Slip Log'!A1:J500 into it first")
    if not v or [str(c).strip() for c in v[0][:len(COLS)]] != COLS: raise SystemExit(f"'ASSIST - Slip Log' header is not {COLS} - not grading a tab I cannot read")
    return [(i, dict(zip(COLS, list(r) + [""] * (len(COLS) - len(r))))) for i, r in enumerate(v[1:], start=2) if any(str(c).strip() for c in r)]
def wk(r):
    try: return int(float(str(r["Week"]).strip()))
    except Exception: return None
def units(price, won):
    try: p = float(str(price).replace("+", "").replace(",", "").strip())
    except Exception: return None
    if not p: return None
    return (p / 100 if p > 0 else 100 / -p) if won else -1.0

def main(argv):
    check = "--check" in argv; args = [a for a in argv if not a.startswith("--")]
    opt = dict(a[2:].split("=", 1) for a in argv if a.startswith("--") and "=" in a)
    dest = opt.get("out") or os.path.join(OUT, "assist_grades.json")
    rows = load(opt.get("file"))
    todo = [(i, r) for i, r in rows if wk(r) is not None and (bool(str(r["Result"]).strip()) == check) and str(r["Legs"]).strip()]
    week = int(args[0]) if args else None
    if week is None:
        for w in sorted({wk(r) for _, r in todo}, reverse=True):
            if SG.Grader(IN, w).ready: week = w; break
    if week is None:
        print("assist log: nothing to grade (no ungraded row in a week that has a game log)" if not check else "assist log: no graded rows to check")
        json.dump({"week": None, "updates": [], "pending": [], "summary": "nothing to grade"}, open(dest, "w"), indent=1); return 0
    G = SG.Grader(IN, week)
    if not G.ready:
        print(f"assist log: no game-log rows for week {week} yet - slips stay open")
        json.dump({"week": week, "updates": [], "pending": [], "summary": f"week {week} not in the game log yet"}, open(dest, "w"), indent=1); return 0
    updates, pending, lines, n = [], [], [], {"WON": 0, "LOST": 0}; u = 0.0; agree = disagree = 0
    for i, r in todo:
        if wk(r) != week: continue
        g = G.slip(r["Legs"], r["Game(s)"]); res = g["result"]
        if check:
            had = str(r["Result"]).upper(); want = "WON" if "WON" in had and "LOST" not in had else "LOST" if "LOST" in had else None
            ok = res == want or res == "PENDING"
            agree += res == want; disagree += not ok
            lines.append(f"row {i} {r['Slip'][:38]}: sheet says {r['Result'][:28]!r}, grader {res} ({g['hit']}/{g['n']})" + ("" if ok else "  <-- DISAGREES") + (f" | not graded: {'; '.join(g['pending'])[:120]}" if g["pending"] else ""))
            continue
        if res == "PENDING":
            pending.append(f"row {i} {r['Slip']}: {'; '.join(g['pending'])}"); lines.append(f"row {i} {r['Slip'][:38]}: open ({g['hit']}/{g['n']} so far) - {'; '.join(g['pending'])[:140]}"); continue
        note = (str(r["Notes"]).strip() + " | " if str(r["Notes"]).strip() else "") + "Auto-graded: " + g["notes"]
        updates.append({"range": f"'ASSIST - Slip Log'!I{i}:J{i}", "values": [[res, note[:900]]]})
        n[res] += 1; x = units(r["Price"], res == "WON"); u += x or 0
        lines.append(f"row {i} {r['Slip'][:38]}: {res} ({g['hit']}/{g['n']})" + (f" {x:+.2f}u at {r['Price']}" if x is not None else ""))
    for l in lines: print(l)
    if check:
        print(f"assist log check, week {week}: grader agrees on {agree}, disagrees on {disagree}, could not grade the rest"); return 1 if disagree else 0
    summary = f"assist log week {week}: {n['WON']} won, {n['LOST']} lost ({u:+.2f}u at the logged prices), {len(pending)} left open for a hand grade"
    json.dump({"week": week, "updates": updates, "pending": pending, "summary": summary}, open(dest, "w"), indent=1)
    print(summary); return 0

if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
