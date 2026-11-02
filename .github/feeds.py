"""ESPN feeds mirrored for the slip-alerts Edge Function (owner 11/1).

ESPN answers some cloud servers (Supabase's among them) with a block page, so the function could see no injury report and no
scoreboard. GitHub's runners can reach ESPN, so every ~10 minutes this writes, to the orphan branch `feeds` (raw.githubusercontent.com):
  injuries.json   the league injury report, trimmed to what the function reads ({injuries: [{injuries: [{athlete, status, details, date}]}]})
  scoreboard.json this week's scoreboard (events with status, competitors, venue) - what homesOf / the live grader read
  inactives.json  game-day outs from each game's summary for games kicking off within 3 hours (or started in the last 20 min):
                  {"<event id>": {"ko": ISO, "teams": [..], "out": [{"name", "team", "status", "date"}]}} - the inactive list posts ~90 min before kickoff
"""
import json, os, subprocess, datetime as dt

S = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
def get(u):
    for x in (u, u.replace("site.api.espn.com", "site.web.api.espn.com")):
        try: return json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", x]))
        except Exception as e: print("fail", x, e)
    return None

now = dt.datetime.now(dt.timezone.utc)
os.makedirs("out", exist_ok=True)
inj = get(f"{S}/injuries")
if inj:
    keep = {"injuries": [{"team": {"abbreviation": (t.get("team") or {}).get("abbreviation"), "displayName": t.get("displayName") or (t.get("team") or {}).get("displayName")},
                          "injuries": [{"athlete": {"displayName": (x.get("athlete") or {}).get("displayName")}, "status": x.get("status"),
                                        "type": {"description": (x.get("type") or {}).get("description")}, "details": {"type": (x.get("details") or {}).get("type")},
                                        "shortComment": x.get("shortComment"), "date": x.get("date")} for x in (t.get("injuries") or [])]}
                         for t in (inj.get("injuries") or [])]}
    json.dump(keep, open("out/injuries.json", "w"))
    print("injuries:", sum(len(t["injuries"]) for t in keep["injuries"]))
dr = (now - dt.timedelta(days=2)).strftime("%Y%m%d") + "-" + (now + dt.timedelta(days=6)).strftime("%Y%m%d")
sb = get(f"{S}/scoreboard")   # the current NFL week (a dates= range answered 400 from the runner)
ina = {}
if sb:
    json.dump({"events": sb.get("events") or [], "mirrored": now.isoformat()}, open("out/scoreboard.json", "w"))
    for ev in sb.get("events") or []:
        ko = dt.datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        mins = (ko - now).total_seconds() / 60
        if not (-20 <= mins <= 180): continue
        sm = get(f"{S}/summary?event={ev['id']}")
        if not sm: continue
        outs = []
        for t in sm.get("injuries") or []:
            ab = (t.get("team") or {}).get("abbreviation")
            for x in t.get("injuries") or []:
                if str(x.get("status", "")).lower() in ("out", "inactive"):
                    outs.append({"name": (x.get("athlete") or {}).get("displayName"), "team": ab, "status": x.get("status"), "date": x.get("date")})
        teams = [c["team"]["abbreviation"] for c in ev["competitions"][0]["competitors"]]
        ina[ev["id"]] = {"ko": ev["date"], "teams": teams, "out": outs}
        print("inactives", teams, len(outs))
json.dump({"games": ina, "mirrored": now.isoformat()}, open("out/inactives.json", "w"))
