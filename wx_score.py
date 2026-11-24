"""The weather scorecard (owner 11/23: "Do better at catching weather"): our last forecast before each kickoff against what the nearest
weather station reported during the game. The feeds job keeps wx_score.json on the `feeds` branch (.github/wx_multi.py score()).
   git -C <clone> fetch -q origin feeds && python3 wx_score.py <clone> [week]
Prints one line per graded open-air game and the season tally: wet games we had at 30%+ (caught), wet games we had under 30% (missed),
dry games we had at 60%+ (false alarms)."""
import json, subprocess, sys
def main(clone, week=None):
    try: d = json.loads(subprocess.check_output(["git", "-C", clone, "show", "origin/feeds:wx_score.json"]))
    except Exception as e: print("weather scorecard: no file yet (", str(e)[:60], ")"); return 0
    G = d.get("games") or {}; rows = []
    for k, e in sorted(G.items()):
        w, a, b = k.split("|"); fc, act = e.get("fc"), e.get("actual")
        if not fc or not act or (week and str(w) != str(week)): continue
        rows.append((int(w), f"{a}-{b}", fc.get("pop") or 0, fc.get("field") or "", bool(act.get("wet")), act))
    caught = sum(1 for r in rows if r[4] and (r[2] >= 30 or r[3])); missed = sum(1 for r in rows if r[4] and r[2] < 30 and not r[3])
    false = sum(1 for r in rows if not r[4] and r[2] >= 60)
    for w, g, pop, field, wet, act in rows:
        print(f"  W{w} {g}: forecast {pop:.0f}%{' + ' + field if field else ''} -> {'WET' if wet else 'dry'} ({act.get('wet_reports', '?')}/{act.get('reports', '?')} station reports wet"
              + (f", {act['rain_mm']} mm" if act.get("rain_mm") is not None else "") + f", station {act.get('station', '?')})" + ("  <-- MISSED" if wet and pop < 30 and not field else ""))
    print(f"weather scorecard{' week ' + str(week) if week else ''}: {len(rows)} open-air games graded | wet {sum(1 for r in rows if r[4])}: caught {caught}, missed {missed} | dry games called 60%+: {false}"
          + f" | waiting {sum(1 for e in G.values() if e.get('fc') and not e.get('actual'))}")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
