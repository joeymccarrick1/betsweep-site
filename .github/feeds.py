"""ESPN feeds mirrored for the slip-alerts Edge Function (owner 11/1).

ESPN answers some cloud servers (Supabase's among them) with a block page, so the function could see no injury report and no
scoreboard. GitHub's runners can reach ESPN, so every ~10 minutes this writes, to the orphan branch `feeds` (raw.githubusercontent.com):
  injuries.json   the league injury report, trimmed to what the function reads ({injuries: [{injuries: [{athlete, status, details, date}]}]})
  scoreboard.json this week's scoreboard (events with status, competitors, venue) - what homesOf / the live grader read
  inactives.json  game-day outs from each game's summary for games kicking off within 3 hours (or started in the last 20 min):
                  {"<event id>": {"ko": ISO, "teams": [..], "out": [{"name", "team", "status", "date"}]}} - the inactive list posts ~90 min before kickoff
"""
import json, os, re, subprocess, datetime as dt

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

# ---- livelog.json (owner 11/4: "grade the live page's from-here numbers"): every run during a game, the box score of every player in it with
# the clock and score, so the live model's in-game calls can be studied against what happened next. Rolling 10 days; one entry per game per run.
LOG = []
try: LOG = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/livelog.json"])).get("snaps", [])
except Exception as e: print("livelog: no previous log", e)
cut = (now - dt.timedelta(days=10)).isoformat()
LOG = [x for x in LOG if x.get("ts", "") >= cut]
def box_of(sm):
    out = {}
    for tm in sm.get("boxscore", {}).get("players", []) or []:
        ab = (tm.get("team") or {}).get("abbreviation")
        for cat in tm.get("statistics", []) or []:
            keys = cat.get("keys") or []; nm = cat.get("name")
            for a in cat.get("athletes", []) or []:
                n = (a.get("athlete") or {}).get("displayName");
                if not n: continue
                S = dict(zip(keys, a.get("stats", []))); row = out.setdefault(n, {"tm": ab, "pass": 0, "rush": 0, "rec": 0, "recy": 0, "td": 0})
                def num(v):
                    try: return float(str(v).split("/")[0])
                    except Exception: return 0.0
                if nm == "passing": row["pass"] = num(S.get("passingYards", 0))
                if nm == "rushing": row["rush"] = num(S.get("rushingYards", 0)); row["td"] += num(S.get("rushingTouchdowns", 0))
                if nm == "receiving": row["rec"] = num(S.get("receptions", 0)); row["recy"] = num(S.get("receivingYards", 0)); row["td"] += num(S.get("receivingTouchdowns", 0))
    return out
if sb:
    for ev in sb.get("events") or []:
        st = ((ev.get("status") or {}).get("type") or {})
        if st.get("state") != "in": continue
        sm = get(f"{S}/summary?event={ev['id']}")
        if not sm: continue
        comp = (ev.get("competitions") or [{}])[0]; cs = {c["homeAway"]: c for c in comp.get("competitors", [])}
        sit = comp.get("situation") or {}
        LOG.append({"ts": now.isoformat(), "eid": ev["id"], "home": cs.get("home", {}).get("team", {}).get("abbreviation"), "away": cs.get("away", {}).get("team", {}).get("abbreviation"),
                    "hs": cs.get("home", {}).get("score"), "as": cs.get("away", {}).get("score"), "period": (ev.get("status") or {}).get("period"), "clock": (ev.get("status") or {}).get("displayClock"),
                    "poss": sit.get("possession"), "rz": bool(sit.get("isRedZone")), "dd": sit.get("downDistanceText"), "box": box_of(sm)})
        print("livelog", ev["id"], (ev.get("status") or {}).get("period"), (ev.get("status") or {}).get("displayClock"))
# pin the live page's tracked legs (pregame chance) the first time a week has a game in progress; never overwritten, so a later rebuild cannot leak
# in-game information into the pregame numbers live_grade.py replays against
if any(x["ts"] >= now.isoformat()[:10] for x in LOG[-50:]):
    try:
        ll = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/main/b/live-legs.json"]))
        wk = ll.get("week"); fn = f"out/livelegs_w{wk}.json"
        try: prev = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", f"https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/livelegs_w{wk}.json"]))
        except Exception: prev = None
        json.dump(prev or dict(ll, pinned=now.isoformat()), open(fn, "w")); print("livelegs pinned:", fn, "kept previous" if prev else "new")
    except Exception as e: print("livelegs: skipped", e)
# keep every pinned week that is still on the branch (the branch is rebuilt from out/ each run)
try:
    for it in json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", "https://api.github.com/repos/joeymccarrick1/betsweep-site/contents?ref=feeds"])):
        ln = it.get("name", "")
        if ln.startswith("livelegs_w") and not os.path.exists("out/" + ln):
            subprocess.run(["curl", "-fsS", "--max-time", "20", "-o", "out/" + ln, f"https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/{ln}"], check=False)
except Exception as e: print("livelegs carry:", e)
json.dump({"snaps": LOG, "mirrored": now.isoformat()}, open("out/livelog.json", "w"))

# ---- depthcharts.json (owner 11/4: "I wish you'd take news into account" - Emanuel Wilson lost his job when Charbonnet and Price came back and
# the model still had him RB1). ESPN's team depth charts, once an hour, raw per team, so the rebuild can compare ESPN's RB/WR/TE order with the
# model's auto depth role and force roles / flag legs (gen depth_check.py). Only at :0x past the hour to keep the run light.
if now.minute < 10:
    DC = {"mirrored": now.isoformat(), "teams": {}}
    try:
        tl = get(f"{S}/teams?limit=40") or {}
        for t in (tl.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []) or []):
            tm = t.get("team") or {}; ab = tm.get("abbreviation"); tid = tm.get("id")
            if not ab or not tid: continue
            dc = get(f"https://site.web.api.espn.com/apis/v2/sports/football/nfl/teams/{tid}/depthcharts")
            if dc: DC["teams"][ab] = dc
        print("depthcharts:", len(DC["teams"]), "teams")
    except Exception as e: print("depthcharts: failed", e)
    if DC["teams"]: json.dump(DC, open("out/depthcharts.json", "w"))
# ---- news.json (owner 11/4: "check news and use player news, team news in our projections"): player-news items from ESPN's NFL news API and
# RotoWire's public NFL RSS, every run, rolling 7 days, de-duplicated by link. The rebuild's news desk (gen news_desk.py) reads it; nothing here judges.
NEWS = []
try: NEWS = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/news.json"])).get("items", [])
except Exception: pass
seen = {x.get("link") for x in NEWS}
try:
    nj = get(f"{S}/news?limit=100") or {}
    for a in nj.get("articles", []) or []:
        ln = (a.get("links") or {}).get("web", {}).get("href") or a.get("id")
        if not ln or ln in seen: continue
        ath = [c.get("description") for c in (a.get("categories") or []) if c.get("type") == "athlete" and c.get("description")]
        tms = [c.get("description") for c in (a.get("categories") or []) if c.get("type") == "team" and c.get("description")]
        NEWS.append({"src": "espn", "ts": a.get("published") or now.isoformat(), "title": a.get("headline"), "text": (a.get("description") or "")[:600], "link": ln, "players": ath, "teams": tms}); seen.add(ln)
    print("news espn ok")
except Exception as e: print("news espn failed", e)
try:
    import xml.etree.ElementTree as ET
    rss = subprocess.check_output(["curl", "-fsSL", "--max-time", "20", "-A", "Mozilla/5.0", "https://www.rotowire.com/rss/news.php?sport=NFL"])
    for it in ET.fromstring(rss).iter("item"):
        ln = (it.findtext("link") or "").strip()
        if not ln or ln in seen: continue
        NEWS.append({"src": "rotowire", "ts": it.findtext("pubDate") or now.isoformat(), "title": (it.findtext("title") or "").strip(), "text": re.sub(r"<[^>]+>", "", it.findtext("description") or "")[:900], "link": ln, "players": [], "teams": []}); seen.add(ln)
    print("news rotowire ok")
except Exception as e: print("news rotowire failed", e)
def _ts(x):
    try: return dt.datetime.fromisoformat(str(x.get("ts")).replace("Z", "+00:00"))
    except Exception:
        try: return dt.datetime.strptime(str(x.get("ts"))[:25].strip(), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        except Exception: return now
NEWS = [x for x in NEWS if (now - _ts(x)).days < 7]
json.dump({"items": NEWS, "mirrored": now.isoformat()}, open("out/news.json", "w")); print("news items:", len(NEWS))

# carry the last depth chart forward on the other runs (the branch is rebuilt from out/ each time)
if not os.path.exists("out/depthcharts.json"):
    subprocess.run(["curl", "-fsS", "--max-time", "30", "-o", "out/depthcharts.json", "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/depthcharts.json"], check=False)
    if os.path.exists("out/depthcharts.json") and os.path.getsize("out/depthcharts.json") < 100: os.remove("out/depthcharts.json")
print("livelog entries:", len(LOG))

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
# 11/3 audit: ESPN's scoreboard stays on the finished week until Tuesday night, so the Tuesday rebuild saw "still on week 8" and fell back to
# the sheet. The target week and the matchups now come from nflverse games.csv (first 2026 REG week with an unplayed game, played games
# within it excluded); ESPN's scoreboard is only the fallback when nflverse cannot be fetched.
def _nflverse_games():
    import csv, io
    try:
        txt = subprocess.check_output(["curl", "-fsSL", "--max-time", "30", "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"]).decode()
    except Exception as e:
        print("nflverse fail", e); return None, []
    gs = [g for g in csv.DictReader(io.StringIO(txt)) if g.get("season") == "2026" and g.get("game_type") == "REG"]
    today = now.astimezone(CT).date().isoformat()
    unplayed = [g for g in gs if g.get("home_score") in ("", None, "NA") and g.get("gameday", "") >= today]
    if not unplayed: return None, []
    wk_ = min(int(g["week"]) for g in unplayed)
    return wk_, [g for g in unplayed if int(g["week"]) == wk_]
ET = dt.timezone(dt.timedelta(hours=-5))   # Eastern (EST from Nov 1) - nflverse gametime is ET
wk, games = _nflverse_games()
evs = []
if games:
    for g in games:
        home, away = EAB.get(g["home_team"], g["home_team"]), EAB.get(g["away_team"], g["away_team"])
        ko = dt.datetime.fromisoformat(g["gameday"] + "T" + (g.get("gametime") or "13:00")).replace(tzinfo=ET).astimezone(dt.timezone.utc)
        evs.append((home, away, ko, g.get("stadium") or "", g.get("location") == "Neutral", g.get("roof") or ""))
elif sb:
    wk = (sb.get("week") or {}).get("number")
    for ev in sb.get("events") or []:
        c = ev["competitions"][0]; teams = {x["homeAway"]: EAB.get(x["team"]["abbreviation"], x["team"]["abbreviation"]) for x in c["competitors"]}
        v = c.get("venue") or {}
        evs.append((teams.get("home"), teams.get("away"), dt.datetime.fromisoformat(ev["date"].replace("Z", "+00:00")), v.get("fullName") or "", bool(c.get("neutralSite")), "dome" if v.get("indoor") else ""))
for home, away, ko, vname, neutral, nroof in evs:
        t1, t2 = sorted([home, away]); upd = now.astimezone(CT).strftime("%Y-%m-%d %H:%M CT")
        base = [str(wk), ko.astimezone(CT).strftime("%Y-%m-%d"), t1, t2, f"{vname} ({home} home)" + (" - neutral site" if neutral else "")]
        st = STADIUM.get(home)
        if neutral or not st:
            rows.append(base + ["", "", upd, "", "", "", "", "", "", "UNKNOWN (neutral site - no forecast)", ""]); continue
        roof = "dome" if (nroof in ("dome", "closed") and st[2] == "outdoors") else st[2]
        if roof == "dome" or nroof == "closed":
            rows.append(base + ["dome" if roof == "dome" else "retractable (closed)", "Open-Meteo (kickoff hour)", upd, "", "", "", "none (dome)", "", "", "NONE (dome)", ""]); continue
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
if rows:
    json.dump({"header": WX_HDR, "rows": rows, "week": wk, "mirrored": now.isoformat(), "source": "nflverse schedule" if games else "ESPN scoreboard"}, open("out/weather.json", "w"))
print("weather rows:", len(rows), "week", wk, [(r[2], r[3], r[5], r[14]) for r in rows])
