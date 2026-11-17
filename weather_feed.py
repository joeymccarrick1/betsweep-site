"""Game weather from the site repo's `feeds` branch (owner 11/1, RUNBOOK Step 2).

The sheet's 'AUTO - Game Weather' rows were carrying last week's venues against this week's matchups (Week 8: ATL-TB read as a
roofed game in Atlanta, so Mayfield's passing legs got no weather flag). .github/feeds.py on the site repo rebuilds the same 16
columns every ~10 minutes from ESPN's home team / venue and Open-Meteo's kickoff hour.

  python3 weather_feed.py <site clone> <WEEK>

Reads origin/feeds:weather.json (run `git -C <clone> fetch -q origin feeds` first). If it is for this week and under 6 hours old it
replaces in/weather.json (same layout prep.py writes: header row + rows) and writes out/weather_values.json for the sheet tab
('AUTO - Game Weather'!A4:P40, cleared first). Otherwise it leaves in/weather.json alone and says why.
"""
import csv, json, os, subprocess, sys, datetime as dt

def week_done(IN, week, now=None):
    """True when every game of this week (newest season in in/games.csv) has kicked off. None when that cannot be told."""
    try:
        from zoneinfo import ZoneInfo
        rows = list(csv.DictReader(open(os.path.join(IN, "games.csv"), newline="")))
        season = max(int(r["season"]) for r in rows if r.get("game_type") == "REG")
        wk = [r for r in rows if int(r["season"]) == season and r.get("game_type") == "REG" and str(r["week"]) == str(week)]
        if not wk: return None
        now = now or dt.datetime.now(dt.timezone.utc)
        for r in wk:
            if r.get("home_score") not in ("", None, "NA"): continue                      # a final score: it has been played
            ko = dt.datetime.strptime(r["gameday"] + " " + (r.get("gametime") or "13:00"), "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/New_York"))
            if ko > now: return False
        return True
    except Exception:
        return None

def decide(feed_week, week, done):
    """(exit code, why) for a feed that is on another week. 11/16: the moment the week's last game ends the feed moves on to next week.
    Weather only flags games still to be played, so when every game of the build's week has kicked off there is nothing to get wrong:
    the sheet's weather stays and the build is NOT failed (it was - which stopped every publish from Monday night's final to Tuesday's roll).
    Any other mismatch still fails the build, as before."""
    try: nxt = int(feed_week) == int(week) + 1
    except Exception: nxt = False
    if nxt and done is True: return 0, f"weather feed: it is on week {feed_week} and every week {week} game has kicked off - kept the sheet's weather (nothing left to flag)"
    return 1, f"weather feed: week {feed_week} != {week} - kept the sheet's weather"

def main(clone, week, IN="in", OUT="out"):
    try:
        d = json.loads(subprocess.check_output(["git", "-C", clone, "show", "origin/feeds:weather.json"]))
    except Exception as e:
        print("weather feed: unavailable (", str(e)[:80], ") - kept the sheet's weather"); return 1
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(d["mirrored"])).total_seconds() / 3600
    if str(d.get("week")) != str(week):
        code, why = decide(d.get("week"), week, week_done(IN, week)); print(why); return code
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
