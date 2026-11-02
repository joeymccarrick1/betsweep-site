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

# ---- weather.json (owner 11/1): the sheet's 'AUTO - Game Weather' rows had last week's venues against this week's matchups (ATL-TB was read
# as a roofed game in Atlanta), so the boards had no usable forecast. This builds the same 16 columns from ESPN's home team / venue and
# Open-Meteo's kickoff hour; the rebuild prefers it (RUNBOOK Step 2) and the Edge Function keeps doing its own live check.
STADIUM = {"ARI": (33.5276, -112.2626, "retractable"), "ATL": (33.7554, -84.4008, "retractable"), "BAL": (39.2780, -76.6227, "outdoors"), "BUF": (42.7738, -78.7870, "outdoors"),
  "CAR": (35.2258, -80.8528, "outdoors"), "CHI": (41.8623, -87.6167, "outdoors"), "CIN": (39.0955, -84.5161, "outdoors"), "CLE": (41.5061, -81.6995, "outdoors"),
  "DAL": (32.7473, -97.0945, "retractable"), "DEN": (39.7439, -105.0201, "outdoors"), "DET": (42.3400, -83.0456, "dome"), "GB": (44.5013, -88.0622, "outdoors"),
  "HOU": (29.6847, -95.4107, "retractable"), "IND": (39.7601, -86.1639, "retractable"), "JAX": (30.3239, -81.6373, "outdoors"), "KC": (39.0489, -94.4839, "outdoors"),
  "LV": (36.0909, -115.1833, "dome"), "LAC": (33.9535, -118.3392, "dome"), "LA": (33.9535, -118.3392, "dome"), "MIA": (25.9580, -80.2389, "outdoors"),
  "MIN": (44.9738, -93.2577, "dome"), "NE": (42.0909, -71.2643, "outdoors"), "NO": (29.9511, -90.0812, "dome"), "NYG": (40.8135, -74.0745, "outdoors"),
  "NYJ": (40.8135, -74.0745, "outdoors"), "PHI": (39.9008, -75.1675, "outdoors"), "PIT": (40.4468, -80.0158, "outdoors"), "SF": (37.4033, -121.9694, "outdoors"),
  "SEA": (47.5952, -122.3316, "outdoors"), "TB": (27.9759, -82.5033, "outdoors"), "TEN": (36.1665, -86.7713, "outdoors"), "WAS": (38.9078, -76.8645, "outdoors")}
EAB = {"WSH": "WAS", "LAR": "LA"}
CT = dt.timezone(dt.timedelta(hours=-6))   # Central (CST from Nov 1); dates only
WX_HDR = ["Week", "Game Date", "Matchup Team 1", "Matchup Team 2", "Venue", "Roof Status", "Forecast Source", "Forecast Updated", "Temperature F", "Wind MPH", "Gust MPH",
          "Precipitation Type", "Precipitation Chance %", "Field Condition", "Weather Risk", "Adjustment Status"]
rows = []
if sb:
    wk = (sb.get("week") or {}).get("number")
    for ev in sb.get("events") or []:
        c = ev["competitions"][0]; teams = {x["homeAway"]: EAB.get(x["team"]["abbreviation"], x["team"]["abbreviation"]) for x in c["competitors"]}
        home, away = teams.get("home"), teams.get("away"); ko = dt.datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        v = c.get("venue") or {}; vname = v.get("fullName") or ""; neutral = bool(c.get("neutralSite"))
        t1, t2 = sorted([home, away]); upd = now.astimezone(CT).strftime("%Y-%m-%d %H:%M CT")
        base = [str(wk), ko.astimezone(CT).strftime("%Y-%m-%d"), t1, t2, f"{vname} ({home} home)" + (" - neutral site" if neutral else "")]
        st = STADIUM.get(home)
        if neutral or not st:
            rows.append(base + ["", "", upd, "", "", "", "", "", "", "UNKNOWN (neutral site - no forecast)", ""]); continue
        roof = "dome" if (v.get("indoor") and st[2] == "outdoors") else st[2]
        if roof == "dome":
            rows.append(base + ["dome", "Open-Meteo (kickoff hour)", upd, "", "", "", "none (dome)", "", "", "NONE (dome)", ""]); continue
        hr = ko.strftime("%Y-%m-%dT%H:00")
        try:
            w = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20",
                f"https://api.open-meteo.com/v1/forecast?latitude={st[0]}&longitude={st[1]}&hourly=temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation_probability,precipitation,snowfall&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=UTC&past_days=1&forecast_days=8"]))
            H = w["hourly"]; i = H["time"].index(hr)
        except Exception as e:
            print("weather fail", t1, t2, e); rows.append(base + [roof, "", upd, "", "", "", "", "", "", "UNKNOWN (forecast unavailable)", ""]); continue
        tmp, wind, gust, pch, pr, sn = (H[k][i] for k in ("temperature_2m", "wind_speed_10m", "wind_gusts_10m", "precipitation_probability", "precipitation", "snowfall"))
        ptype = "snow" if (sn or 0) > 0 else "rain" if (pr or 0) >= 0.01 else "none"
        risk = "HIGH" if ((wind or 0) >= 15 or (gust or 0) >= 28 or ptype == "snow" or (ptype == "rain" and (pch or 0) >= 60) or (tmp is not None and tmp <= 25)) else \
               "MODERATE" if ((wind or 0) >= 12 or (pch or 0) >= 40) else "LOW"
        if roof == "retractable": risk += " (roof can close)"
        rows.append(base + [roof, "Open-Meteo (kickoff hour)", upd, f"{tmp:.0f}", f"{wind:.0f}", f"{gust:.0f}", ptype, f"{(pch or 0):.0f}", "", risk, ""])
    rows.sort(key=lambda r: (r[2], r[3]))
    json.dump({"header": WX_HDR, "rows": rows, "week": wk, "mirrored": now.isoformat()}, open("out/weather.json", "w"))
    print("weather rows:", len(rows), [(r[2], r[3], r[5], r[14]) for r in rows])
