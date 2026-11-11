#!/usr/bin/env python3
"""parity.py - does the code say what the sheet says?  (research/model_port, owner 11/10 deep dive)

  python3 research/model_port/parity.py [in dir]

For every column port.py claims (port.PORTED) it recomputes the value from the row's other columns in the mirror (in/*.json) and
compares it with the sheet's own cell: rows compared, rows within 0.05, the largest gap and the three worst rows. A column is
"ported" only at 100%. Also prints the census the port works from: every mirrored tab with its row and column counts.
Exit 1 when a claimed column misses parity, so a later change to the sheet that the code has not followed is caught the same day.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, HERE)
import port  # noqa: E402

def vals(in_dir, n):
    d = json.load(open(os.path.join(in_dir, n))); return d.get("values", d) if isinstance(d, dict) else d

if __name__ == "__main__":
    in_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(GP, "in"); bad = 0
    sc = port.scoring(vals(in_dir, "settings.json"))
    for tab, (col, fn, claimed) in port.PORTED.items():
        v = vals(in_dir, tab); H = v[0]; n = ok = 0; worst = []
        for r in v[1:]:
            row = {H[i]: (r[i] if i < len(r) else "") for i in range(len(H))}
            if not str(row.get("Player") or "").strip() or str(row.get(col, "")).strip() == "": continue
            want = port._f(row[col], None)
            if want is None: continue
            got = fn(row, sc); n += 1; d = abs(got - want); ok += d <= 0.05; worst.append((d, row["Player"], round(got, 2), want))
        worst.sort(reverse=True); bad += (ok != n and claimed)
        print(f"{tab:14} {col:18} {ok}/{n} rows within 0.05" + (("   CLAIMED AND BROKEN" if claimed else "   in progress") + " - worst: " + "; ".join(f"{p} code {g} sheet {w}" for _, p, g, w in worst[:3]) if ok != n else "   PARITY" + ("" if claimed else " (not yet claimed)")))
    try:
        m = json.load(open(os.path.join(in_dir, "MIRROR.json")))
        print(f"\ncensus of the mirror ({m.get('pulled')}): {len(m.get('rows', {}))} tabs")
        for f, rows in sorted(m.get("rows", {}).items()):
            try: cols = len(vals(in_dir, f)[0])
            except Exception: cols = "?"
            print(f"  {f:22} {rows:6} rows  {cols:>3} cols")
    except Exception as e: print("census skipped:", e)
    sys.exit(1 if bad else 0)
