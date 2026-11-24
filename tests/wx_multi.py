"""Game weather from several forecasts (owner 11/23, CIN at WAS). Runs <clone>/.github/wx_multi.py against made-up answers from the
weather services (no network): the wettest forecast wins, the whole game window is read, a source that fails is left out, the last look
near kickoff sees rain that is falling, and the scorecard keeps the last pre-kickoff forecast and adds what happened.
   CLONE=/path/to/site python3 tests/wx_multi.py"""
import os, sys, json, datetime as dt, importlib.util
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLONE = os.environ.get("CLONE") or "/home/claude/betsweep-site"
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
p = os.path.join(CLONE, ".github", "wx_multi.py")
if not os.path.exists(p): print("no .github/wx_multi.py in the clone - skipped"); print("0 passed, 0 failed"); sys.exit(0)
spec = importlib.util.spec_from_file_location("wx_multi", p); W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
U = dt.timezone.utc
KO = dt.datetime(2026, 11, 24, 1, 15, tzinfo=U)   # Monday 7:15 PM CT
HOURS = [(KO.replace(minute=0) + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(-3, 8)]

def om(best, gfs, ecm, multi=True, rain=(0, 0, 0)):
    """an Open-Meteo answer: each of best/gfs/ecm is the chance for every hour (a number, or a list across HOURS)"""
    def col(v): return list(v) if isinstance(v, (list, tuple)) else [v] * len(HOURS)
    H = {"time": HOURS}
    for name, pop, r in (("best_match", best, rain[0]), ("ecmwf_ifs025", gfs, rain[1]), ("icon_seamless", ecm, rain[2])):
        suf = "_" + name if multi else ""
        if not multi and name != "best_match": continue
        H["precipitation_probability" + suf] = col(pop); H["precipitation" + suf] = col(r); H["snowfall" + suf] = col(0)
        H["temperature_2m" + suf] = col(48); H["wind_speed_10m" + suf] = col(11); H["wind_gusts_10m" + suf] = col(22)
    return {"hourly": H}
def nws_periods(pop, words="Mostly Cloudy", wind="8 mph"):
    return {"properties": {"periods": [{"startTime": (KO.replace(minute=0) + dt.timedelta(hours=h)).astimezone(dt.timezone(dt.timedelta(hours=-5))).isoformat(),
            "probabilityOfPrecipitation": {"value": pop if not isinstance(pop, list) else pop[h + 3]}, "windSpeed": wind, "windGust": None, "temperature": 47,
            "shortForecast": words} for h in range(-3, 8)]}}
def getter(om_ans, nws_ans=None, look=None, fail=(), calls=None, obs=None):
    def get(url, ua=False, timeout=20):
        if calls is not None: calls.append(url)
        if "api.open-meteo.com" in url:
            if "current=" in url:
                if "look" in fail: raise RuntimeError("down")
                return look or {"current": {"precipitation": 0, "weather_code": 3}, "minutely_15": {"time": [], "precipitation": []}}
            if "models=" in url and "multi" in fail: raise RuntimeError("400")
            if "om" in fail: raise RuntimeError("down")
            return om_ans if "models=" in url or not isinstance(om_ans, tuple) else om_ans
        if "/points/" in url:
            if "nws" in fail: raise RuntimeError("503")
            return {"properties": {"forecastHourly": "https://api.weather.gov/gridpoints/LWX/1,1/forecast/hourly", "observationStations": "https://api.weather.gov/gridpoints/LWX/1,1/stations"}}
        if "forecast/hourly" in url: return nws_ans
        if url.endswith("/stations"): return {"features": [{"properties": {"stationIdentifier": "KADW"}}]}
        if "/observations" in url: return obs
        raise RuntimeError("unexpected " + url)
    return get
NOW = KO - dt.timedelta(hours=9)

# the CIN at WAS shape: our old source says 8%, another run and the weather service say much more
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(8, 55, 20), nws_periods(70, "Rain Likely")))
check(c["pop"] == 70 and c["pop_low"] == 8 and c["n"] == 4 and c["wettest"] == "nws", f"the wettest of four forecasts is the one shown (8 / 55 / 20 / 70 -> {c['pop']}, from {c['wettest']})")
check(c["disagree"] and c["ptype"] == "rain" and c["risk"] == "HIGH", f"they disagree by 25+ points and it is said; 60%+ in any forecast is HIGH ({c['risk']}, {c['ptype']})")
check(W.source_text(c) == "4 forecasts, wettest shown, whole game window", "the row says how many forecasts it stands on")
# the whole game window: dry at kickoff, wet in the third hour
late = [5, 5, 5, 5, 10, 65, 65, 5, 5, 5, 5]
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(late, 5, 5), nws_periods(5)))
check(c["pop"] == 65, f"rain that arrives two hours after kickoff counts (kickoff hour 5%, later 65% -> {c['pop']})")
c = W.game(38.9, -76.86, KO, NOW, None, getter(om([5] * 7 + [90] * 4, 5, 5), nws_periods(5)))
check(c["pop"] == 5 and c["risk"] == "LOW", f"rain after the game is over does not ({c['pop']})")
# rain by amount, whatever chance is quoted
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(15, 45, 15, rain=(0, 0.04, 0)), nws_periods(15)))
check(c["rain"] == 0.16 and c["risk"] == "HIGH" and c["ptype"] == "rain", f"a run that drops rain through the game, with a 40%+ chance behind it, is HIGH before any forecast reaches 60% (amount {c['rain']} in, {c['pop']}%, {c['risk']})")
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(15, 15, 15, rain=(0, 0.04, 0)), nws_periods(15)))
check(c["risk"] == "MODERATE", f"the same rain amount at a 15% chance is MODERATE, not HIGH ({c['risk']})")
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(5, 5, 5), nws_periods(5, wind="20 to 25 mph")))
check(c["wind"] == 11 and c["risk"] == "LOW", f"wind stays with the default forecast - a windier second source does not raise the Wind flags ({c['wind']} mph)")
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(10, 12, 8), nws_periods(10)))
check(c["risk"] == "LOW" and c["ptype"] == "none" and not c["disagree"] and c["field"] == "", "four dry forecasts that agree: low, no rain typed, nothing else said")
# sources that fail
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(20, 0, 0, multi=False), nws_periods(45), fail=("multi",)))
check(c["n"] == 2 and c["pop"] == 45 and any("ECMWF" in m for m in c["missing"]), f"when the three-model request is refused the default forecast and the weather service still stand ({c['n']} sources, missing {c['missing']})")
c = W.game(38.9, -76.86, KO, NOW, None, getter(om(20, 30, 10), None, fail=("nws",)))
check(c["n"] >= 3 and c["pop"] == 30 and any("National Weather Service" in m for m in c["missing"]), "the weather service down: three forecasts, and the gap is named")
c = W.game(38.9, -76.86, KO, NOW, None, getter(None, nws_periods(35, "Chance Showers", "10 to 14 mph"), fail=("om",)))
check(c["n"] == 1 and c["pop"] == 35 and c["ptype"] == "rain" and c["temp"] == 47 and c["wind"] == 14 and c["risk"] == "MODERATE", f"Open-Meteo down: the weather service alone still gives a row (wind from '10 to 14 mph' = {c['wind']})")
try: W.game(38.9, -76.86, KO, NOW, None, getter(None, None, fail=("om", "nws"))); bad = False
except RuntimeError: bad = True
check(bad, "nothing answering raises, so the feed keeps its old single-forecast row")
# the weather service is asked again only when its reading is old
calls = []; c1 = W.game(38.9, -76.86, KO, NOW, None, getter(om(10, 10, 10), nws_periods(10), calls=calls)); n1 = sum("weather.gov" in u for u in calls)
calls = []; c2 = W.game(38.9, -76.86, KO, NOW + dt.timedelta(minutes=30), c1, getter(om(10, 10, 10), nws_periods(99), calls=calls)); n2 = sum("weather.gov" in u for u in calls)
calls = []; c3 = W.game(38.9, -76.86, KO, NOW + dt.timedelta(minutes=55), c1, getter(om(10, 10, 10), nws_periods(40), calls=calls)); n3 = sum("weather.gov" in u for u in calls)
check((n1, n2, n3) == (2, 0, 2) and c2["pop"] == 10 and c3["pop"] == 40, f"the weather service is asked again after 50 minutes, not before (requests {n1}, {n2}, {n3})")
# the last look
calls = []; c = W.game(38.9, -76.86, KO, NOW, None, getter(om(10, 10, 10), nws_periods(10), calls=calls))
check(c["look"] is None and not any("current=" in u for u in calls), "nine hours out there is no last look")
soon = KO - dt.timedelta(minutes=30)
c = W.game(38.9, -76.86, KO, soon, None, getter(om(8, 8, 8), nws_periods(8), look={"current": {"precipitation": 0.02, "weather_code": 61}, "minutely_15": {"time": [], "precipitation": []}}))
check(c["field"] == "rain now" and c["risk"] == "HIGH" and c["ptype"] == "rain" and c["pop"] == 8, f"30 minutes out with rain falling at the stadium: 'rain now', HIGH, and the quoted chance is left as it was ({c['pop']}%)")
m15 = {"time": [(soon + dt.timedelta(minutes=15 * i)).strftime("%Y-%m-%dT%H:%M") for i in range(1, 9)], "precipitation": [0, 0, 0, 0.01, 0.02, 0.02, 0, 0]}
c = W.game(38.9, -76.86, KO, soon, None, getter(om(8, 8, 8), nws_periods(8), look={"current": {"precipitation": 0, "weather_code": 3}, "minutely_15": m15}))
check(c["field"] == "rain within 2 hours" and c["risk"] == "MODERATE" and c["ptype"] == "rain", f"dry now but rain in the next two hours: said, and at least MODERATE ({c['field']!r}, {c['risk']})")
c = W.game(38.9, -76.86, KO, soon, None, getter(om(8, 8, 8), nws_periods(8), fail=("look",)))
check(c["field"] == "" and any("last look" in m for m in c["missing"]), "a last look that fails is named, not guessed")
# the scorecard
S = {}
e = W.score(S, "11|CIN|WAS", W.game(38.9, -76.86, KO, NOW, None, getter(om(8, 12, 9), nws_periods(15))), 38.9, -76.86, KO, NOW)
e = W.score(S, "11|CIN|WAS", W.game(38.9, -76.86, KO, soon, None, getter(om(13, 12, 9), nws_periods(15))), 38.9, -76.86, KO, soon)
check(e["fc"]["pop"] == 15 and e["fc"]["at"].startswith("2026-11-24T00:45") and e.get("stations", "").endswith("/stations") and "actual" not in e, "before kickoff the latest forecast is kept, with the station list for later")
W.score(S, "11|CIN|WAS", {}, 38.9, -76.86, KO, KO + dt.timedelta(hours=2), getter(om(0, 0, 0)))
check("actual" not in S["11|CIN|WAS"] and S["11|CIN|WAS"]["fc"]["pop"] == 15, "during the game the forecast is frozen and nothing is graded")
obs = {"features": [{"properties": {"textDescription": d, "precipitationLastHour": {"value": v}}} for d, v in (("Light Rain", 1.2), ("Rain", 3.0), ("Rain", None), ("Cloudy", 0))]}
W.score(S, "11|CIN|WAS", {}, 38.9, -76.86, KO, KO + dt.timedelta(hours=4, minutes=5), getter(om(8, 0, 0, rain=(0.05, 0, 0)), obs=obs))
a = S["11|CIN|WAS"].get("actual") or {}
check(a.get("wet") is True and a.get("station") == "KADW" and a.get("wet_reports") == 3 and a.get("rain_mm") == 4.2 and a.get("model_rain_in") == 0.2, f"four hours after kickoff the station's reports are added: wet, 3 of 4 reports, 4.2 mm ({a})")
W.score(S, "11|CIN|WAS", {}, 38.9, -76.86, KO, KO + dt.timedelta(hours=5), getter(None, fail=("om", "nws")))
check(S["11|CIN|WAS"]["actual"] == a, "and it is written once")
# the feed keeps its old row when the module fails, and the scorecard file is never restarted after a failed read
fsrc = open(os.path.join(CLONE, ".github", "feeds.py"), encoding="utf-8").read()
check('print("wx_multi fail"' in fsrc and "hr = ko.strftime" in fsrc.split('print("wx_multi fail"')[1][:200], "feeds.py falls through to its single-forecast row when the module fails")
check("if WX_SCORE and WX_SCORE_OK: json.dump" in fsrc and '_code == "404"' in fsrc, "feeds.py only writes the scorecard when the old one was read (or does not exist yet)")
# the alert function goes by the worse of its own forecast and the feed's (push/slip-alerts.ts; the owner deploys it)
import re, subprocess, tempfile
ts = open(os.path.join(HERE, "push", "slip-alerts.ts"), encoding="utf-8").read()
mt = re.search(r"export type Wx = .*?\n", ts); mb = re.search(r"export function wxBad\(.*?\n}\n", ts, re.S); mm = re.search(r"export function wxMerge\(.*?\n}\n", ts, re.S)
check(bool(mt and mb and mm) and 'wxAt(st[0], st[1], g.ko, h.home, h.away)' in ts and 'wxAt(stad[0], stad[1], g.ko, h.home, h.away)' in ts, "slip-alerts.ts merges the feed's reading into both of its weather checks (subscriber alerts and the promo watch)")
if mt and mb and mm:
    KOMS = int(KO.timestamp() * 1000)
    prog = mt.group(0) + mb.group(0) + mm.group(0) + """
const KO = %d, iso = new Date(KO).toISOString();
const own = {wind: 9, gust: 18, pop: 8, rain: 0};
console.log(JSON.stringify({
  own: wxBad(own),
  wet: wxBad(wxMerge(own, {pop: 70, rain: 0.2, wind: 10, gust: 20, field: "", ko: iso}, KO)!),
  poss: wxBad(wxMerge(own, {pop: 35, rain: 0, ko: iso}, KO)!),
  now: wxBad(wxMerge(own, {pop: 8, rain: 0, field: "rain now", ko: iso}, KO)!),
  soon: wxBad(wxMerge(own, {pop: 8, rain: 0, field: "rain within 2 hours", ko: iso}, KO)!),
  other: wxBad(wxMerge(own, {pop: 90, rain: 1, field: "rain now", ko: new Date(KO + 5 * 3600e3).toISOString()}, KO)!),
  nofeed: wxBad(wxMerge(own, null, KO)!), feedonly: wxBad(wxMerge(null, {pop: 65, rain: 0.1, wind: 16, gust: 30, ko: iso}, KO)!),
  kept: wxMerge({wind: 20, gust: 33, pop: 50, rain: 0.3}, {pop: 10, rain: 0, wind: 5, gust: 9, ko: iso}, KO)}));
""" % KOMS
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "wx.ts"); open(f, "w", encoding="utf-8").write(prog)
        r = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", f], capture_output=True, text=True, timeout=60)
    try: o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: o = None
    check(o is not None, f"wxBad and wxMerge run under node ({(r.stderr or '').strip()[:200]})")
    if o:
        check(o["own"] == [] and o["nofeed"] == [], "our own 8% alone raises nothing - that was Monday night")
        check(o["wet"] == ["heavy rain 70%"] and o["poss"] == ["rain possible (35% chance in the wettest forecast)"], f"the feed's wetter forecast raises it: {o['wet']}, and 30%+ says rain possible: {o['poss']}")
        check(o["now"] == ["rain is falling at the stadium now"] and o["soon"] == ["rain moving in within two hours"], f"the last look is said in plain words ({o['now']}, {o['soon']})")
        check(o["other"] == [], "a reading for a different kickoff is not used for this game")
        check(o["feedonly"] == ["wind 16 mph, gusts 30", "rain 65%"] and o["kept"] == {"wind": 20, "gust": 33, "pop": 50, "rain": 0.3}, "with our own forecast down the feed still alerts; a calmer feed never lowers our own reading")
check("const mk = live ? \"wxnow\" : \"wx\"" in ts and "bs-${mk}-${W}-${gid}" in ts, "rain seen near kickoff is its own one-time alert, so an earlier forecast push does not swallow it")
own = "/home/claude/work/owner_send/slip-alerts.ts"
if os.path.exists(own): check(open(own, encoding="utf-8").read() == ts, "the owner's copy of the function equals the one in the repo")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
