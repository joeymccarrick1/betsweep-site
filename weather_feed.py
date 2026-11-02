"""Game weather from the site repo's `feeds` branch (owner 11/1, RUNBOOK Step 2).

The sheet's 'AUTO - Game Weather' rows were carrying last week's venues against this week's matchups (Week 8: ATL-TB read as a
roofed game in Atlanta, so Mayfield's passing legs got no weather flag). .github/feeds.py on the site repo rebuilds the same 16
columns every ~10 minutes from ESPN's home team / venue and Open-Meteo's kickoff hour.

  python3 weather_feed.py <site clone> <WEEK>

Reads origin/feeds:weather.json (run `git -C <clone> fetch -q origin feeds` first). If it is for this week and under 6 hours old it
replaces in/weather.json (same layout prep.py writes: header row + rows) and writes out/weather_values.json for the sheet tab
('AUTO - Game Weather'!A4:P40, cleared first). Otherwise it leaves in/weather.json alone and says why.
"""
import json, os, subprocess, sys, datetime as dt

def main(clone, week, IN="in", OUT="out"):
    try:
        d = json.loads(subprocess.check_output(["git", "-C", clone, "show", "origin/feeds:weather.json"]))
    except Exception as e:
        print("weather feed: unavailable (", str(e)[:80], ") - kept the sheet's weather"); return 1
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(d["mirrored"])).total_seconds() / 3600
    if str(d.get("week")) != str(week): print(f"weather feed: week {d.get('week')} != {week} - kept the sheet's weather"); return 1
    if age > 6: print(f"weather feed: {age:.1f} h old - kept the sheet's weather"); return 1
    rows = [r for r in d["rows"] if str(r[0]) == str(week)]
    os.makedirs(OUT, exist_ok=True)
    json.dump({"values": [d["header"]] + rows}, open(os.path.join(IN, "weather.json"), "w"))
    json.dump({"range": "'AUTO - Game Weather'!A4:P40", "values": rows}, open(os.path.join(OUT, "weather_values.json"), "w"))
    hi = [f"{r[2]}-{r[3]} {r[14]}" for r in rows if str(r[14]).startswith(("HIGH", "MODERATE"))]
    print(f"weather feed: {len(rows)} games, {age*60:.0f} min old" + (f"; watch: {', '.join(hi)}" if hi else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
