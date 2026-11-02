"""Owner notes -> the rebuild (owner 11/1, RUNBOOK Step 2a).

The owner taps a note on a player page (risk_feed kind=note in Supabase). A GitHub Action on the site repo copies the notes to
data/risk-notes.json every 30 minutes, because the rebuild sandbox cannot reach Supabase.

  python3 risk_notes.py <site clone>/data/risk-notes.json <week>

- writes in/risk_notes.json (flags.py reads it: HURT / LIMITED -> a 'bad' flag that keeps the player out of listed parlays,
  STARTING / ROLE_UP -> a 'good' flag)
- prints out/risk_notes_avail.json: the 'AUTO - Weekly Availability' rows to append for this week
    OUT     -> E = OUT (the owner's call stands even before the official report)
    HURT    -> E = QUESTIONABLE, only when the tab has no row for him yet (an official status always wins)
    LIMITED -> same as HURT
    STARTING / ROLE_UP -> no availability row (flag only; nothing here changes a projection beyond what OUT / QUESTIONABLE already do)
Never invents a status: every row carries the owner's note text and the note's timestamp as its source.
"""
import json, os, sys, re

def nn(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()

def main(path, week, IN="in", OUT="out"):
    week = int(week)
    try: notes = json.load(open(path))
    except Exception as e:
        print("risk notes: none (", e, ")"); notes = []
    notes = [n for n in notes if n.get("player") and n.get("status") and int(n.get("week") or week) == week]
    os.makedirs(IN, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    json.dump(notes, open(os.path.join(IN, "risk_notes.json"), "w"), indent=1)
    # model names / teams / positions from the projection tabs
    who = {}
    for f, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
        try:
            d = json.load(open(os.path.join(IN, f))); v = d.get("values", d) if isinstance(d, dict) else d
            for r in v[1:]:
                if r and r[0]: who.setdefault(nn(r[0]), (r[0], r[1] if len(r) > 1 else "", pos))
        except Exception: pass
    have = set()
    try:
        d = json.load(open(os.path.join(IN, "avail.json"))); v = d.get("values", d) if isinstance(d, dict) else d
        for r in v[1:]:
            if len(r) > 4 and str(r[0]) == str(week) and r[1]: have.add(nn(r[1]))
    except Exception: pass
    rows, skipped = [], []
    for n in notes:
        k = nn(n["player"]); st = n["status"]; m = who.get(k)
        if st not in ("OUT", "HURT", "LIMITED"): continue
        if not m: skipped.append(n["player"] + " (not on a projection tab)"); continue
        if st != "OUT" and k in have: skipped.append(n["player"] + " (already on the availability tab)"); continue
        why = "BetSweep note: " + {"OUT": "out", "HURT": "playing hurt", "LIMITED": "limited role"}[st] + (" - " + n["detail"] if n.get("detail") else "")
        rows.append([str(week), m[0], m[1], m[2], "OUT" if st == "OUT" else "QUESTIONABLE", "", "", "", "", why, "BetSweep owner note", (n.get("updated_at") or "")[:16].replace("T", " "), ""])
    json.dump(rows, open(os.path.join(OUT, "risk_notes_avail.json"), "w"), indent=1)
    print(f"risk notes: {len(notes)} this week -> in/risk_notes.json; {len(rows)} availability row(s) -> out/risk_notes_avail.json" + (f"; skipped: {', '.join(skipped)}" if skipped else ""))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
