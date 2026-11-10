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
        # 11/5: the raw summary of every live game (play-by-play, drives, box score) - a mirror for testing the live page / Gamecast and a fallback when ESPN is slow
        try: json.dump(sm, open(f"out/summary-{ev['id']}.json", "w"), separators=(",", ":"))
        except Exception as e: print("summary mirror", e)
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
# GitHub's cron is throttled (runs land at odd minutes), so gate on age, not on the clock: refresh when the last mirror is older than 50 minutes
_dc_age = 1e9
try:
    _prev = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/depthcharts.json"]))
    _dc_age = (now - dt.datetime.fromisoformat(_prev["mirrored"])).total_seconds() / 60
except Exception: pass
if _dc_age > 50:
    DC = {"mirrored": now.isoformat(), "teams": {}}
    try:
        tl = get(f"{S}/teams?limit=40") or {}
        for t in (tl.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []) or []):
            tm = t.get("team") or {}; ab = tm.get("abbreviation"); tid = tm.get("id")
            if not ab or not tid: continue
            # ESPN core API: depth chart slots hold athlete $ref links; the team roster (one call) resolves ids to names + positions
            dc = get(f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{now.year}/teams/{tid}/depthcharts")
            ro = get(f"{S}/teams/{tid}/roster")
            if not dc: continue
            names = {}
            for grp in (ro or {}).get("athletes", []) or []:
                for a in grp.get("items", []) or []:
                    names[str(a.get("id"))] = {"name": a.get("displayName") or a.get("fullName"), "pos": ((a.get("position") or {}).get("abbreviation") or ""), "inj": [(i.get("status") or "") for i in (a.get("injuries") or [])]}
            chart = {}
            for item in dc.get("items", []) or []:
                for pkey, pv in (item.get("positions") or {}).items():
                    pab = ((pv.get("position") or {}).get("abbreviation") or pkey).upper()
                    grp = "WR" if "WR" in pab else "RB" if pab in ("RB", "HB") else "QB" if pab == "QB" else "TE" if pab == "TE" else "FB" if pab == "FB" else None
                    if not grp: continue
                    for a in pv.get("athletes", []) or []:
                        ref = ((a.get("athlete") or {}).get("$ref") or ""); aid = re.search(r"/athletes/(\d+)", ref)
                        if not aid: continue
                        info = names.get(aid.group(1), {"name": None, "pos": "", "inj": []})
                        chart.setdefault(grp, []).append({"rank": a.get("rank") or a.get("slot") or 99, "slot": pab, "id": aid.group(1), "name": info["name"], "pos": info["pos"], "inj": info["inj"]})
            for g in chart: chart[g].sort(key=lambda x: (x["rank"], x["slot"]))
            DC["teams"][ab] = {"id": tid, "chart": chart, "roster_n": len(names)}
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
# more wires (owner 11/4: "local news, beat reporters"): national NFL RSS feeds that carry beat-sourced practice / role notes. Each is best-effort;
# a feed that fails or changes shape is skipped. Items are tagged by source and parsed by gen news_desk.py like the RotoWire ones.
for _src, _url in (("cbs", "https://www.cbssports.com/rss/headlines/nfl/"), ("yahoo", "https://sports.yahoo.com/nfl/rss.xml"), ("espn-rss", "https://www.espn.com/espn/rss/nfl/news"),
                   ("pft", "https://www.nbcsports.com/nfl/profootballtalk/rss"), ("nfl", "https://www.nfl.com/rss/rsslanding?searchString=home")):
    try:
        import xml.etree.ElementTree as ET
        rss = subprocess.check_output(["curl", "-fsSL", "--max-time", "20", "-A", "Mozilla/5.0", _url], stderr=subprocess.DEVNULL)
        n = 0
        for it in ET.fromstring(rss).iter("item"):
            ln = (it.findtext("link") or "").strip()
            if not ln or ln in seen: continue
            NEWS.append({"src": _src, "ts": it.findtext("pubDate") or now.isoformat(), "title": (it.findtext("title") or "").strip(), "text": re.sub(r"<[^>]+>", "", it.findtext("description") or "")[:900], "link": ln, "players": [], "teams": []}); seen.add(ln); n += 1
        print("news", _src, "ok", n)
    except Exception as e: print("news", _src, "failed", str(e)[:80])
def _ts(x):
    try: return dt.datetime.fromisoformat(str(x.get("ts")).replace("Z", "+00:00"))
    except Exception:
        try: return dt.datetime.strptime(str(x.get("ts"))[:25].strip(), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        except Exception: return now
NEWS = [x for x in NEWS if (now - _ts(x)).days < 7]
# audit 11/10: Yahoo's feed sends text with HTML entities still in it ("Sunday&#39;s", &quot;, &hellip;). Every reader escapes on output,
# so pages showed the entity itself. Stored titles and text are plain text from here on (old items included; twice for double-encoded ones).
import html as _html
def _plain(t):
    t = t or ""
    for _ in range(2):
        if "&" not in t: break
        t = _html.unescape(t)
    return t
for _x in NEWS:
    for _k in ("title", "text"):
        if isinstance(_x.get(_k), str): _x[_k] = _plain(_x[_k])
json.dump({"items": NEWS, "mirrored": now.isoformat()}, open("out/news.json", "w")); print("news items:", len(NEWS))

# ---- projections.json (owner 11/4: "when could the numbers be wrong" - consensus disagreement detector): Sleeper's public weekly projections and
# ESPN's fantasy projections for the current week, raw, refreshed when older than 50 minutes. gen consensus.py compares them with the model.
_pj_age = 1e9
try:
    _pp = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "20", "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/projections.json"]))
    _pj_age = (now - dt.datetime.fromisoformat(_pp["mirrored"])).total_seconds() / 60
except Exception: pass
if _pj_age > 50:
    PJ = {"mirrored": now.isoformat(), "week": None, "sleeper": None, "espn": None}
    try:
        wk = ((sb or {}).get("week") or {}).get("number")
        PJ["week"] = wk
        if wk:
            PJ["sleeper"] = get(f"https://api.sleeper.app/projections/nfl/2026/{wk}?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE&order_by=pts_ppr")
            print("projections sleeper:", len(PJ["sleeper"] or []))
            flt = json.dumps({"players": {"limit": 600, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}, "filterSlotIds": {"value": [0, 2, 4, 6, 23]}}})
            espn = subprocess.check_output(["curl", "-fsS", "--max-time", "40", "-H", f"X-Fantasy-Filter: {flt}", "-H", "Accept: application/json",
                                            f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leaguedefaults/3?scoringPeriodId={wk}&view=kona_player_info"])
            PJ["espn"] = json.loads(espn).get("players"); print("projections espn:", len(PJ["espn"] or []))
    except Exception as e: print("projections: failed", e)
    if PJ["sleeper"] or PJ["espn"]: json.dump(PJ, open("out/projections.json", "w"))
if not os.path.exists("out/projections.json"):
    subprocess.run(["curl", "-fsS", "--max-time", "30", "-o", "out/projections.json", "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/projections.json"], check=False)
    if os.path.exists("out/projections.json") and os.path.getsize("out/projections.json") < 100: os.remove("out/projections.json")
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

# ---- changes.json (owner 11/5 "what changed" feed): every run diffs this mirror against the previous one on the feeds branch and keeps a
# timestamped event log (7 days, 400 events): injury status changes, game-day inactives, weather tier / rain / wind changes, new news items.
# The Live page reads it (plus data/price-moves.json for line moves) and shows what changed since the user's last visit.
def _prev(name):
    try: return json.loads(subprocess.check_output(["curl", "-fsSL", "--max-time", "20", f"https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/{name}"]))
    except Exception as e: print("prev", name, e); return None
try:
    EV = (_prev("changes.json") or {}).get("events", [])
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ"); add = []
    def injmap(j):
        m = {}
        for t in (j or {}).get("injuries") or []:
            ab = (t.get("team") or {}).get("abbreviation") or ""
            for x in t.get("injuries") or []:
                nm = (x.get("athlete") or {}).get("displayName")
                if nm: m[nm] = (ab, str(x.get("status") or ""), (x.get("details") or {}).get("type") or (x.get("type") or {}).get("description") or "")
        return m
    if os.path.exists("out/injuries.json"):
        old = injmap(_prev("injuries.json")); new = injmap(json.load(open("out/injuries.json")))
        if old:   # first run after a gap has nothing to compare with - no flood
            for nm, (ab, st, why) in new.items():
                o = old.get(nm)
                if not o or o[1] != st:
                    add.append({"ts": ts, "k": "injury", "pl": nm, "tm": ab, "st": st, "was": o[1] if o else "", "t": f"{nm} ({ab}) {('now ' + st) if o else st}" + (f" - was {o[1]}" if o else "") + (f" ({why})" if why else "")})
    oi = (_prev("inactives.json") or {}).get("games") or {}
    seen = {(g_id, x.get("name")) for g_id, g in oi.items() for x in g.get("out") or []}
    for g_id, g in ina.items():
        for x in g.get("out") or []:
            if (g_id, x.get("name")) not in seen: add.append({"ts": ts, "k": "inactive", "pl": x.get("name"), "tm": x.get("team"), "t": f"{x.get('name')} ({x.get('team')}) INACTIVE"})
    if rows:
        ow = {(r[2], r[3]): r for r in ((_prev("weather.json") or {}).get("rows") or [])}
        for r in rows:
            o = ow.get((r[2], r[3]))
            if not o: continue
            f = lambda v: float(v) if str(v).strip() not in ("", "None") else None
            msgs = []
            if o[14].split(" ")[0] != r[14].split(" ")[0]: msgs.append(f"weather {o[14].split(' ')[0]} -> {r[14].split(' ')[0]}")
            pc0, pc1 = f(o[12]), f(r[12])
            if pc0 is not None and pc1 is not None and abs(pc1 - pc0) >= 20: msgs.append(f"rain chance {pc0:.0f}% -> {pc1:.0f}%")
            w0, w1 = f(o[9]), f(r[9])
            if w0 is not None and w1 is not None and abs(w1 - w0) >= 5: msgs.append(f"wind {w0:.0f} -> {w1:.0f} mph")
            if msgs: add.append({"ts": ts, "k": "weather", "g": f"{r[2]}-{r[3]}", "t": f"{r[2]}-{r[3]} ({re.sub(r' [(].*$', '', r[4])}): " + ", ".join(msgs)})
    ON = {_plain(x.get("title") or "") for x in ((_prev("news.json") or {}).get("items") or [])}   # audit 11/10: compare as plain text (older items may still carry entities)
    if ON:
        for x in NEWS:
            if (x.get("title") or "") not in ON and x.get("players"): add.append({"ts": x.get("ts") or ts, "k": "news", "pl": (x.get("players") or [""])[0], "t": x.get("title") or "", "u": x.get("link") or ""})
    cut = (now - dt.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    EV = [e for e in EV + add if e.get("ts", "") >= cut][-400:]
    json.dump({"events": EV, "updated": ts}, open("out/changes.json", "w"))
    print("changes:", len(add), "new,", len(EV), "kept")
except Exception as e: print("changes skipped:", e)

# ---- q.json (owner 11/6 "Questionable translator"): this week's official injury report (nflverse, updated as practices are reported) ->
# for every Questionable / Doubtful QB / RB / WR / TE: last practice, chance he plays, share of usual snaps if he plays (qtrans numbers,
# research/q_translator.py on 2024-25). risk.js adds it to the injury chip on every page.
try:
    import csv, io
    QP = {"Full": 0.80, "Limited": 0.64, "DNP": 0.54, "none": 0.57}; QS = {"Full": 0.88, "Limited": 0.90, "DNP": 0.90, "none": 0.85}
    txt = subprocess.check_output(["curl", "-fsSL", "--max-time", "30", "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv"]).decode()
    rr = [r for r in csv.DictReader(io.StringIO(txt)) if r.get("game_type") == "REG" and r.get("position") in ("QB", "RB", "WR", "TE")]
    wk = max((int(r["week"]) for r in rr if str(r.get("week", "")).isdigit()), default=0); Q = {}
    for r in rr:
        if str(r.get("week")) != str(wk): continue
        ps = str(r.get("practice_status") or ""); ps = "DNP" if "Did Not" in ps else "Limited" if "Limited" in ps else "Full" if "Full" in ps else "none"
        st = str(r.get("report_status") or "").strip()
        if st not in ("Questionable", "Doubtful"):
            if ps in ("DNP", "Limited"): Q[r["full_name"]] = {"tm": r.get("team"), "st": "", "ps": ps}   # practice news before the Friday status
            continue
        Q[r["full_name"]] = {"tm": r.get("team"), "st": st[0], "ps": ps, "play": 0.02 if st == "Doubtful" else QP[ps], "snap": None if st == "Doubtful" else QS[ps], "inj": r.get("report_primary_injury") or ""}
    json.dump({"week": wk, "players": Q, "mirrored": now.isoformat()}, open("out/q.json", "w"), separators=(",", ":"))
    print("q.json:", wk, len(Q), "players")
except Exception as e: print("q.json skipped:", e)
