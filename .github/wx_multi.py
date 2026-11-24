"""Game weather from more than one forecast (owner 11/23, after CIN at WAS: our one forecast said 3-15% all day and it rained from
kickoff - "do all of that so we don't have to deal with this again").

feeds.py calls game() for every open-air game and keeps its old single-forecast row if anything here fails.
  sources   Open-Meteo's default blend, Open-Meteo's GFS and ECMWF runs (one request), and the National Weather Service's hourly forecast
  window    the kickoff hour and the three hours after it, worst value of each (the old row read the kickoff hour only)
  last look inside 3 hours of kickoff (and during the game): what is falling at the stadium now and in the next two hours
  scorecard wx_score.json: the last forecast before kickoff against what the nearest weather station reported during the game
Nothing here needs a key. Every request is optional: a source that does not answer is left out and named in "missing".
"""
import json, re, subprocess, datetime as dt

UA = "BetSweep weather check (betsweep.co, support@betsweep.co)"
OM = "https://api.open-meteo.com/v1/forecast"
MODELS = ("best_match", "gfs_seamless", "ecmwf_ifs025")
NAMES = {"best_match": "Open-Meteo", "gfs_seamless": "GFS", "ecmwf_ifs025": "ECMWF", "nws": "National Weather Service"}
WET = re.compile(r"rain|shower|drizzle|thunder|storm|snow|sleet|wintry|flurr|freezing", re.I)
SNOW = re.compile(r"snow|sleet|wintry|flurr", re.I)
WET_CODES = set(range(51, 68)) | set(range(71, 78)) | set(range(80, 87)) | set(range(95, 100))

def fetch(url, ua=False, timeout=20):
    cmd = ["curl", "-fsS", "--max-time", str(timeout)] + (["-H", "User-Agent: " + UA, "-H", "Accept: application/geo+json"] if ua else []) + [url]
    return json.loads(subprocess.check_output(cmd, stderr=subprocess.DEVNULL))

def _t(s):
    """an ISO time, with or without an offset, as UTC"""
    d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return d.replace(tzinfo=dt.timezone.utc) if d.tzinfo is None else d.astimezone(dt.timezone.utc)

def _mx(xs):
    xs = [x for x in xs if x is not None]
    return max(xs) if xs else None

def _mph(s):
    n = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(s or ""))]
    return max(n) if n else None

def window(ko):
    h0 = ko.replace(minute=0, second=0, microsecond=0)
    return h0, h0 + dt.timedelta(hours=3)

def open_meteo(lat, lon, ko, get=None):
    """{model: {pop, rain, snow, wind, gust, temp}} over the game window. One request for the three models; if that is refused, the default alone."""
    get = get or fetch; h0, h1 = window(ko)
    q = (f"{OM}?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation_probability,precipitation,snowfall"
         "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=UTC&past_days=1&forecast_days=8")
    try: w = get(q + "&models=" + ",".join(MODELS)); models = MODELS
    except Exception: w = get(q); models = ("best_match",)
    H = w["hourly"]; idx = [i for i, t in enumerate(H["time"]) if h0 <= _t(t) <= h1]
    if not idx: return {}
    out = {}
    for m in models:
        def col(v):
            c = H.get(f"{v}_{m}")
            if c is None and (m == "best_match" or len(models) == 1): c = H.get(v)
            return [c[i] for i in idx] if c else []
        pop, rain, snow, wind, gust, temp = col("precipitation_probability"), col("precipitation"), col("snowfall"), col("wind_speed_10m"), col("wind_gusts_10m"), col("temperature_2m")
        if not any(x is not None for x in pop + rain + wind): continue
        out[m] = {"pop": _mx(pop), "rain": round(sum(x or 0 for x in rain), 3) if any(x is not None for x in rain) else None,
                  "snow": round(sum(x or 0 for x in snow), 2) if any(x is not None for x in snow) else None,
                  "wind": _mx(wind), "gust": _mx(gust), "temp": next((x for x in temp if x is not None), None)}
    return out

def nws(lat, lon, ko, get=None):
    """the National Weather Service's hourly forecast over the game window (it reaches about a week out)"""
    get = get or fetch; h0, h1 = window(ko)
    p = get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", ua=True)["properties"]
    per = get(p["forecastHourly"], ua=True)["properties"]["periods"]
    hit = [x for x in per if h0 <= _t(x["startTime"]) <= h1]
    if not hit: return None
    words = [str(x.get("shortForecast") or "") for x in hit]
    return {"pop": _mx([(x.get("probabilityOfPrecipitation") or {}).get("value") for x in hit]), "wind": _mx([_mph(x.get("windSpeed")) for x in hit]),
            "gust": _mx([_mph(x.get("windGust")) for x in hit]), "temp": hit[0].get("temperature"),
            "words": next((s for s in words if WET.search(s)), words[0] if words else ""), "wet": any(WET.search(s) for s in words), "snowy": any(SNOW.search(s) for s in words),
            "stations": p.get("observationStations")}

def last_look(lat, lon, now, get=None):
    """what is falling at the stadium now, and what the next two hours hold (quarter-hour steps)"""
    get = get or fetch
    w = get(f"{OM}?latitude={lat}&longitude={lon}&current=precipitation,weather_code&minutely_15=precipitation&precipitation_unit=inch&timezone=UTC&past_days=0&forecast_days=2")
    cur = w.get("current") or {}; m = w.get("minutely_15") or {}
    nxt = [p for t, p in zip(m.get("time") or [], m.get("precipitation") or []) if now <= _t(t) <= now + dt.timedelta(hours=2)]
    code = cur.get("weather_code")
    return {"at": now.isoformat(timespec="minutes"), "falling": bool((cur.get("precipitation") or 0) > 0 or (code in WET_CODES)), "code": code,
            "now_in": cur.get("precipitation"), "next2h_in": round(sum(x or 0 for x in nxt), 3) if nxt else None}

def combine(srcs, look=None):
    """the wettest reading across the sources. srcs: {name: {pop, rain, snow, wind, gust, temp, wet?}}"""
    pops = {k: v.get("pop") for k, v in srcs.items() if v.get("pop") is not None}
    pop = max(pops.values()) if pops else None
    rain = _mx([v.get("rain") for v in srcs.values()]); snow = _mx([v.get("snow") for v in srcs.values()])
    wind = _mx([v.get("wind") for v in srcs.values()]); gust = _mx([v.get("gust") for v in srcs.values()])
    temp = next((srcs[k]["temp"] for k in ("best_match", "nws", "gfs_seamless", "ecmwf_ifs025") if k in srcs and srcs[k].get("temp") is not None), None)
    snowy = (snow or 0) > 0 or any(v.get("snowy") for v in srcs.values())
    rainy = (rain or 0) >= 0.01 or any(v.get("wet") for v in srcs.values())
    falling = bool(look and look.get("falling")); soon = bool(look and (look.get("next2h_in") or 0) >= 0.01)
    ptype = "snow" if snowy else "rain" if (rainy or falling or soon) else "none"
    field = "rain now" if falling else "rain within 2 hours" if soon else ""
    p = pop or 0
    wet_amount = (rain or 0) >= 0.10   # a tenth of an inch over the game in any run is a wet game, whatever chance is quoted
    risk = "HIGH" if ((wind or 0) >= 15 or (gust or 0) >= 28 or snowy or p >= 60 or falling or wet_amount or (temp is not None and temp <= 25)) else \
           "MODERATE" if ((wind or 0) >= 12 or p >= 30 or soon or (rain or 0) >= 0.03) else "LOW"
    lo = min(pops.values()) if pops else None
    return {"pop": pop, "pop_low": lo, "pops": pops, "rain": rain, "snow": snow, "wind": wind, "gust": gust, "temp": temp, "ptype": ptype, "field": field, "risk": risk,
            "disagree": bool(pops and len(pops) > 1 and pop - lo >= 25), "wettest": max(pops, key=pops.get) if pops else None}

def game(lat, lon, ko, now, prev=None, get=None):
    """Everything for one open-air game. prev is this game's entry from the last run (the weather service is asked again only when its
    reading is 50 minutes old, 20 inside six hours of kickoff). Raises only if no source answered."""
    srcs, missing = {}, []
    try: srcs.update(open_meteo(lat, lon, ko, get))
    except Exception as e: missing.append("Open-Meteo: " + str(e)[:60])
    for m in MODELS:
        if m not in srcs and not any(x.startswith("Open-Meteo") for x in missing): missing.append(NAMES[m] + ": no values for these hours")
    mins = (ko - now).total_seconds() / 60
    old = (prev or {}).get("srcs", {}).get("nws"); age = None
    try: age = (now - _t((prev or {}).get("nws_at"))).total_seconds() / 60
    except Exception: pass
    nws_at = (prev or {}).get("nws_at")
    if old is not None and age is not None and 0 <= age < (20 if mins <= 360 else 50) and (prev or {}).get("ko") == ko.isoformat(): srcs["nws"] = old
    else:
        try:
            r = nws(lat, lon, ko, get)
            if r: srcs["nws"] = r; nws_at = now.isoformat(timespec="minutes")
            else: missing.append("National Weather Service: not in range yet")
        except Exception as e: missing.append("National Weather Service: " + str(e)[:60])
    if not srcs: raise RuntimeError("no forecast source answered: " + "; ".join(missing))
    look = None
    if -240 <= mins <= 180:
        try: look = last_look(lat, lon, now, get)
        except Exception as e: missing.append("last look: " + str(e)[:60])
    c = combine(srcs, look)
    c.update({"srcs": srcs, "look": look, "missing": missing, "nws_at": nws_at, "ko": ko.isoformat(), "n": len(c["pops"])})
    return c

def source_text(c):
    n = c.get("n") or 0
    return (f"{n} forecasts, wettest shown" if n > 1 else "1 forecast") + ", whole game window"

def observed(stations_url, ko, get=None):
    """what the nearest weather station reported from kickoff to three and a half hours later"""
    get = get or fetch
    st = get(stations_url, ua=True)["features"][0]["properties"]["stationIdentifier"]
    a, b = ko.strftime("%Y-%m-%dT%H:%M:%SZ"), (ko + dt.timedelta(hours=3, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    obs = get(f"https://api.weather.gov/stations/{st}/observations?start={a}&end={b}", ua=True)["features"]
    words = [str((o.get("properties") or {}).get("textDescription") or "") for o in obs]
    mm = [((o.get("properties") or {}).get("precipitationLastHour") or {}).get("value") for o in obs]
    return {"station": st, "reports": len(obs), "wet_reports": sum(1 for s in words if WET.search(s)), "said": sorted({s for s in words if s})[:6],
            "rain_mm": round(sum(x or 0 for x in mm), 1) if any(x is not None for x in mm) else None}

def score(S, key, c, lat, lon, ko, now, get=None):
    """S is wx_score.json's games dict. Before kickoff: keep the latest forecast. Four hours after: add what happened, once."""
    e = S.setdefault(key, {"ko": ko.isoformat()})
    if now < ko:
        e["fc"] = {"at": now.isoformat(timespec="minutes"), "pop": c.get("pop"), "pops": c.get("pops"), "rain": c.get("rain"), "ptype": c.get("ptype"), "risk": c.get("risk"),
                   "field": c.get("field"), "wind": c.get("wind"), "gust": c.get("gust")}
        st = ((c.get("srcs") or {}).get("nws") or {}).get("stations")
        if st: e["stations"] = st
    elif now >= ko + dt.timedelta(hours=4) and "actual" not in e and e.get("tries", 0) < 6:
        e["tries"] = e.get("tries", 0) + 1; act = {}
        try:
            if e.get("stations"): act.update(observed(e["stations"], ko, get))
        except Exception as x: act["station_error"] = str(x)[:80]
        try:
            om = open_meteo(lat, lon, ko, get).get("best_match") or {}
            act["model_rain_in"] = om.get("rain")
        except Exception as x: act["model_error"] = str(x)[:80]
        if "wet_reports" in act or act.get("model_rain_in") is not None:
            act["wet"] = bool(act.get("wet_reports") or (act.get("rain_mm") or 0) > 0 or (act.get("model_rain_in") or 0) >= 0.02)
            e["actual"] = act
    return e
