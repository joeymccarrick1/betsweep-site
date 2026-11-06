#!/usr/bin/env python3
"""build_teams.py - one page per NFL team at /teams/<abbr>/ plus a directory at /teams/ (owner 11/5: "a teams page where you can see team
stats and box scores from each game this season ... similar to players page ... I'd love for those pages to be harmonious too").

The team pages use the player pages' stylesheet (/player/player.css, the .pp layout) so the two read as one family: same header card with
the team badge, same section cards, same tables. Player names link to /player/<slug>/, opponents to /teams/<abbr>/, and build_players.py
links each player page's team badge, crumb and game-log opponents back here.

Sources (all public, nothing changes a projection):
  in/games.csv                         nflverse schedule: scores, FanDuel-era consensus spread / total, roof, weather
  in/stats_team_week_2026.csv          nflverse team box score per game (downloaded here if missing)
  in/stats_player_week_2026.csv        nflverse player box score per game (plydata / build_players download it)
  out/builder_data.json                this week's game: kickoff, model score
Writes out/teams/<abbr>.html (32 bodies), out/teams/index.html, out/teams/teams.js, out/teams/box/<game_id>.json (player lines per game,
fetched when a game is opened, shared by both teams' pages). build_site.py places them at /teams/.
"""
import os, csv, json, html, collections, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
E = html.escape; SEASON = 2026
NV = "https://github.com/nflverse/nflverse-data/releases/download"
import types as _ty
BR = _ty.SimpleNamespace(); _ns = {"HERE": HERE}; exec(open(os.path.join(HERE, "brand.py")).read(), _ns); BR.NAMES, BR.TEAMCOL = _ns["NAMES"], _ns["TEAMCOL"]
from plydata import slugify
try: from stakes import DIV
except Exception: DIV = {}
FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}
def T(x): x = str(x or "").strip(); return FIX.get(x, x)
def f(x):
    try: return float(x)
    except Exception: return 0.0
def rows(name, url):
    p = os.path.join(IN, name)
    if not os.path.exists(p):
        try: urllib.request.urlretrieve(url, p)
        except Exception as e: print(f"warn: could not download {name}: {e}"); return []
    with open(p, newline="") as fh: return list(csv.DictReader(fh))
CITY = {"ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore", "BUF": "Buffalo", "CAR": "Carolina", "CHI": "Chicago", "CIN": "Cincinnati", "CLE": "Cleveland", "DAL": "Dallas",
        "DEN": "Denver", "DET": "Detroit", "GB": "Green Bay", "HOU": "Houston", "IND": "Indianapolis", "JAX": "Jacksonville", "KC": "Kansas City", "LA": "Los Angeles", "LAC": "Los Angeles",
        "LV": "Las Vegas", "MIA": "Miami", "MIN": "Minnesota", "NE": "New England", "NO": "New Orleans", "NYG": "New York", "NYJ": "New York", "PHI": "Philadelphia", "PIT": "Pittsburgh",
        "SEA": "Seattle", "SF": "San Francisco", "TB": "Tampa Bay", "TEN": "Tennessee", "WAS": "Washington"}
def full(t): return f"{CITY.get(t, t)} {BR.NAMES.get(t, '')}".strip()
def colors(t): return BR.TEAMCOL.get(t, ("#2b3442", "#141a24"))

# ---- schedule -----------------------------------------------------------------------------------------------------------------------
G = [g for g in rows("games.csv", None) if g.get("season") == str(SEASON) and g.get("game_type") == "REG"]
for g in G: g["away_team"], g["home_team"] = T(g["away_team"]), T(g["home_team"])
TEAMS = sorted({g["home_team"] for g in G} | {g["away_team"] for g in G})
def played(g): return g.get("home_score") not in ("", "NA", None) and g.get("away_score") not in ("", "NA", None)
# ---- team + player box scores ---------------------------------------------------------------------------------------------------------
TS = [r for r in rows(f"stats_team_week_{SEASON}.csv", f"{NV}/stats_team/stats_team_week_{SEASON}.csv") if r.get("season_type", "REG") == "REG"]
PS = [r for r in rows(f"stats_player_week_{SEASON}.csv", f"{NV}/stats_player/stats_player_week_{SEASON}.csv") if r.get("season_type", "REG") == "REG"]
TBOX = {(T(r["team"]), int(r["week"])): r for r in TS}
PBOX = collections.defaultdict(list)
for r in PS: PBOX[(T(r["team"]), int(r["week"]))].append(r)
def line(r):
    """one team's game in the numbers a box score shows (net passing = gross - sack yards, as the NFL reports it)"""
    if not r: return None
    to = f(r["passing_interceptions"]) + f(r["sack_fumbles_lost"]) + f(r["rushing_fumbles_lost"]) + f(r["receiving_fumbles_lost"])
    net = f(r["passing_yards"]) - f(r["sack_yards_lost"])
    plays = f(r["attempts"]) + f(r["carries"]) + f(r["sacks_suffered"])
    return {"cmp": f(r["completions"]), "att": f(r["attempts"]), "pyd": net, "ptd": f(r["passing_tds"]), "int": f(r["passing_interceptions"]), "sk": f(r["sacks_suffered"]),
            "car": f(r["carries"]), "ryd": f(r["rushing_yards"]), "rtd": f(r["rushing_tds"]), "yds": net + f(r["rushing_yards"]), "plays": plays, "to": to,
            "fd": f(r["passing_first_downs"]) + f(r["rushing_first_downs"]), "pen": f(r["penalties"]), "peny": f(r["penalty_yards"]),
            "dsk": f(r["def_sacks"]), "dint": f(r["def_interceptions"])}
# ---- per-team season ------------------------------------------------------------------------------------------------------------------
S = {}
for t in TEAMS:
    s = {"g": 0, "w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0, "ats": [0, 0, 0], "ou": [0, 0, 0], "home": [0, 0, 0], "away": [0, 0, 0], "div": [0, 0, 0], "games": [], "streak": ""}
    for g in sorted([g for g in G if t in (g["home_team"], g["away_team"])], key=lambda g: int(g["week"])):
        home = g["home_team"] == t; opp = g["away_team"] if home else g["home_team"]; wk = int(g["week"])
        row = {"g": g, "wk": wk, "opp": opp, "home": home, "done": played(g)}
        if played(g):
            us, them = (f(g["home_score"]), f(g["away_score"])) if home else (f(g["away_score"]), f(g["home_score"]))
            res = "W" if us > them else ("L" if us < them else "T"); row.update(us=us, them=them, res=res)
            s["g"] += 1; s["pf"] += us; s["pa"] += them; s[{"W": "w", "L": "l", "T": "t"}[res]] += 1
            i = "WLT".index(res); s["home" if home else "away"][i] += 1
            if DIV.get(t) and DIV.get(t) == DIV.get(opp): s["div"][i] += 1
            if g.get("spread_line") not in ("", "NA"):
                spr = f(g["spread_line"]); mine = -spr if home else spr; m = (us - them) + mine
                row["spr"] = mine; row["ats"] = "W" if m > 0 else ("L" if m < 0 else "P"); s["ats"]["WLP".index(row["ats"])] += 1
            if g.get("total_line") not in ("", "NA"):
                tl = f(g["total_line"]); tot = us + them; row["tl"] = tl; row["ou"] = "O" if tot > tl else ("U" if tot < tl else "P"); s["ou"]["OUP".index(row["ou"])] += 1
            row["box"] = line(TBOX.get((t, wk))); row["obox"] = line(TBOX.get((opp, wk)))
        else:
            if g.get("spread_line") not in ("", "NA"): row["spr"] = (-f(g["spread_line"])) if home else f(g["spread_line"])
            if g.get("total_line") not in ("", "NA"): row["tl"] = f(g["total_line"])
        s["games"].append(row)
    done = [r for r in s["games"] if r["done"]]
    if done:
        last = done[-1]["res"]; n = 0
        for r in reversed(done):
            if r["res"] != last: break
            n += 1
        s["streak"] = f"{last}{n}"
    # per-game offense / defense from the team box scores
    n = len([r for r in done if r.get("box")]) or 1
    off = collections.Counter(); dfn = collections.Counter()
    for r in done:
        if r.get("box"): off.update(r["box"])
        if r.get("obox"): dfn.update(r["obox"])
    s["off"] = {k: v / n for k, v in off.items()}; s["def"] = {k: v / n for k, v in dfn.items()}
    s["off"]["pts"] = s["pf"] / (s["g"] or 1); s["def"]["pts"] = s["pa"] / (s["g"] or 1)
    s["off"]["ypp"] = off["yds"] / off["plays"] if off["plays"] else 0; s["def"]["ypp"] = dfn["yds"] / dfn["plays"] if dfn["plays"] else 0
    s["off"]["ypa"] = off["pyd"] / (off["att"] + off["sk"]) if off["att"] else 0; s["def"]["ypa"] = dfn["pyd"] / (dfn["att"] + dfn["sk"]) if dfn["att"] else 0
    s["off"]["ypc"] = off["ryd"] / off["car"] if off["car"] else 0; s["def"]["ypc"] = dfn["ryd"] / dfn["car"] if dfn["car"] else 0
    S[t] = s
# league ranks (1 = best): offense more is better except turnovers / sacks taken; defense less allowed is better except takeaways / sacks
STATS = [("pts", "Points", 1), ("yds", "Yards", 1), ("ypp", "Yards / play", 2), ("pyd", "Pass yards", 1), ("ypa", "Net yards / dropback", 2), ("ryd", "Rush yards", 1), ("ypc", "Yards / carry", 2), ("to", "Turnovers", 1), ("sk", "Sacks", 1)]
RANK = {}
for side in ("off", "def"):
    for k, _, _ in STATS:
        good_high = (side == "off") != (k in ("to", "sk"))
        order = sorted(TEAMS, key=lambda t: S[t][side].get(k, 0), reverse=good_high)
        for i, t in enumerate(order): RANK[(t, side, k)] = i + 1
def rank_color(r):   # the players' / boards' scale: 1 green ... 32 red
    t = (r - 1) / 31
    if t < 0.5: h = 140 - 95 * (t / 0.5); l = 0.30 + 0.08 * (t / 0.5)
    else: h = 45 - 45 * ((t - 0.5) / 0.5); l = 0.38 - 0.10 * ((t - 0.5) / 0.5)
    return f"hsl({h:.0f} 62% {l*100:.0f}%)"
def chip(r): return f'<i style="background:{rank_color(r)}">{r}</i>'
def rec(a): return f"{a[0]}-{a[1]}" + (f"-{a[2]}" if a[2] else "")
# ---- builder: this week's game for the header -----------------------------------------------------------------------------------------
try: B = json.load(open(os.path.join(OUT, "builder_data.json")))
except Exception: B = {"week": 0, "games": []}
W = int(B.get("week") or 0)
def this_week(t):
    for g in B.get("games", []):
        if t in (g.get("a"), g.get("b")): return g
    return None
# ---- player links -----------------------------------------------------------------------------------------------------------------------
PP = os.path.join(OUT, "players")
def plink(name):
    s = slugify(name)
    return f'<a href="/player/{s}/">{E(name)}</a>' if os.path.exists(os.path.join(PP, s + ".html")) else E(name)
def tlink(t): return f'<a href="/teams/{t.lower()}/">{E(t)}</a>'
def badge(t, big=False):
    c1, c2 = colors(t)
    return f'<span class="tb{" sm" if not big else ""}" style="--p:{c1};--s:{c2}">{E(t)}</span>'

# ---- per-game player box JSON (fetched on open; one file per game shared by both teams' pages) -----------------------------------------
os.makedirs(os.path.join(OUT, "teams", "box"), exist_ok=True)
def pjson(t, wk):
    out = {"pass": [], "rush": [], "rec": [], "def": [], "k": []}
    for r in PBOX.get((t, wk), []):
        nm = r["player_display_name"]; s = slugify(nm); has = os.path.exists(os.path.join(PP, s + ".html"))
        base = {"n": nm, "s": s if has else "", "p": r["position"]}
        if f(r["attempts"]) > 0: out["pass"].append({**base, "c": f(r["completions"]), "a": f(r["attempts"]), "y": f(r["passing_yards"]), "td": f(r["passing_tds"]), "i": f(r["passing_interceptions"]), "sk": f(r["sacks_suffered"])})
        if f(r["carries"]) > 0: out["rush"].append({**base, "c": f(r["carries"]), "y": f(r["rushing_yards"]), "td": f(r["rushing_tds"])})
        if f(r["targets"]) > 0 or f(r["receptions"]) > 0: out["rec"].append({**base, "r": f(r["receptions"]), "t": f(r["targets"]), "y": f(r["receiving_yards"]), "td": f(r["receiving_tds"])})
        tk = f(r["def_tackles_solo"]) + f(r["def_tackle_assists"])
        if tk >= 3 or f(r["def_sacks"]) or f(r["def_interceptions"]) or f(r["def_fumbles_forced"]):
            out["def"].append({**base, "tk": tk, "sk": f(r["def_sacks"]), "i": f(r["def_interceptions"]), "pd": f(r["def_pass_defended"]), "ff": f(r["def_fumbles_forced"])})
        if f(r["fg_att"]) or f(r["pat_att"]): out["k"].append({**base, "fg": f"{f(r['fg_made']):.0f}/{f(r['fg_att']):.0f}", "lg": f(r["fg_long"]), "xp": f"{f(r['pat_made']):.0f}/{f(r['pat_att']):.0f}"})
    out["pass"].sort(key=lambda x: -x["a"]); out["rush"].sort(key=lambda x: -x["y"]); out["rec"].sort(key=lambda x: (-x["y"], -x["r"])); out["def"].sort(key=lambda x: (-x["sk"] - x["i"], -x["tk"])); out["def"] = out["def"][:8]
    return out
nbox = 0
for g in G:
    if not played(g): continue
    wk = int(g["week"]); a, h = g["away_team"], g["home_team"]
    if not PBOX.get((a, wk)) and not PBOX.get((h, wk)): continue
    json.dump({"id": g["game_id"], "wk": wk, "away": a, "home": h, "as": f(g["away_score"]), "hs": f(g["home_score"]), a: pjson(a, wk), h: pjson(h, wk)},
              open(os.path.join(OUT, "teams", "box", g["game_id"] + ".json"), "w"), separators=(",", ":")); nbox += 1

# ---- page parts ---------------------------------------------------------------------------------------------------------------------------
TCSS = """<style>
.pp .tb.sm{grid-row:auto;width:34px;height:34px;font-size:13px;border-radius:7px;box-shadow:inset 0 -4px 0 var(--s,#000)}
.pp a.tb{text-decoration:none}
.pp .trec{font-family:var(--display);font-weight:700;color:var(--ink);font-size:15px}
.tm-glance{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.tm-glance div{padding:10px 14px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.tm-glance small{display:block;color:var(--mute);font-size:11px;letter-spacing:.06em;text-transform:uppercase;font-family:var(--display);font-weight:700}
.tm-glance b{font-family:var(--display);font-weight:700;font-size:22px} .tm-glance span{color:var(--mute);font-size:12.5px;margin-left:4px}
.pp .rk i{font-style:normal;color:#fff;font-weight:700;font-size:11px;padding:1px 6px;border-radius:3px;margin-left:6px}
.pp td.split{color:var(--mute)}
.gm{border-bottom:1px solid var(--line)} .gm:last-child{border-bottom:0}
.gm>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:44px minmax(0,1fr) auto auto 14px;gap:6px 12px;align-items:center;padding:10px 14px;font-variant-numeric:tabular-nums}
.gm>summary::-webkit-details-marker{display:none}
.gm>summary:hover{background:color-mix(in srgb,var(--chalk) 60%,transparent)}
.gm .wk{font-family:var(--display);font-weight:700;color:var(--mute);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.gm .op{display:flex;align-items:center;gap:8px;min-width:0} .gm .op em{font-style:normal;color:var(--mute);font-size:12.5px}
.gm .sc{font-family:var(--display);font-weight:700;font-size:17px;white-space:nowrap} .gm .sc .W{color:var(--good)} .gm .sc .L{color:var(--bad)} .gm .sc .T{color:var(--mute)}
.gm .bt{display:flex;gap:6px;justify-content:flex-end} .gm .bt span{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.05em;padding:2px 7px;border-radius:999px;background:var(--chalk);color:var(--mute);white-space:nowrap}
.gm .bt span.W,.gm .bt span.O{color:var(--good)} .gm .bt span.L,.gm .bt span.U{color:var(--bad)}
.gm .wk{grid-column:1} .gm .op{grid-column:2} .gm .bt{grid-column:3;grid-row:1} .gm .sc{grid-column:4;grid-row:1} .gm .chev{grid-column:5;grid-row:1;color:var(--mute);transition:transform .15s} .gm[open] .chev{transform:rotate(90deg)}
.gm.up>summary{cursor:default} .gm.up .sc{font-size:13px;color:var(--mute);font-family:var(--body);font-weight:500}
.gm .bx{padding:4px 14px 14px;display:grid;gap:12px}
.gm .bx h3{margin:6px 0 4px;font-family:var(--display);font-weight:700;font-size:14px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute)}
.gm .bx table{border:1px solid var(--line);border-radius:10px;overflow:hidden}
.gm .two{display:grid;grid-template-columns:1fr 1fr;gap:12px} .gm .two h4{margin:0 0 6px;display:flex;align-items:center;gap:8px;font-family:var(--display);font-weight:700;font-size:15px}
.gm .ld{color:var(--mute);font-size:13px;padding:6px 0}
@media (max-width:760px){ .gm .two{grid-template-columns:1fr} .gm>summary{grid-template-columns:38px minmax(0,1fr) auto 14px} .gm .sc{grid-column:3} .gm .chev{grid-column:4} .gm .bt{grid-column:2/5;grid-row:2;justify-content:flex-start} }
.tdir .div{margin:0 0 14px} .tdir .div h2 small{margin-left:auto}
.tdir .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.tdir .grid a{display:grid;grid-template-columns:auto 1fr auto;gap:2px 12px;align-items:center;padding:12px 14px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);text-decoration:none;color:var(--ink)}
.tdir .grid a:hover{background:color-mix(in srgb,var(--chalk) 60%,transparent)}
.tdir .grid .tb{grid-column:1;grid-row:1/3} .tdir .grid b{grid-column:2;grid-row:1;font-family:var(--display);font-weight:700;font-size:16px} .tdir .grid>a>small{grid-column:2;grid-row:2;color:var(--mute);font-size:12px}
.tdir .grid .r{grid-column:3;grid-row:1/3;text-align:right;font-family:var(--display);font-weight:700;font-size:18px} .tdir .grid .r small{display:block;font-family:var(--body);font-weight:400}
.pp th.sort{cursor:pointer} .pp th.sort:hover{color:var(--ink)} .pp th.sort.on{color:var(--ink)}
</style>"""
def head(title, desc):
    link, _ = __import__("account")._base_css()
    return f'<title>{E(title)}</title>\n<meta name="description" content="{E(desc)}">\n{link}\n<link rel="stylesheet" href="/player/player.css">\n{TCSS}\n'

def stat_table(t):
    s = S[t]
    def fm(k, v): return f"{v:.1f}" if k in ("ypp", "ypa", "ypc", "to", "sk", "pts") else f"{v:.0f}"
    body = "".join(f'<tr><td>{lbl}</td><td>{fm(k, s["off"].get(k, 0))}<span class="rk">{chip(RANK[(t, "off", k)])}</span></td>'
                   f'<td>{fm(k, s["def"].get(k, 0))}<span class="rk">{chip(RANK[(t, "def", k)])}</span></td></tr>' for k, lbl, _ in STATS)
    return ('<section><h2>Season stats <small>per game · league rank of 32 (1 = best: most gained on offense, least allowed on defense; for turnovers and sacks the offense ranks fewest, the defense most) · net passing, as the NFL reports it</small></h2>'
            f'<div class="tw"><table><thead><tr><th>Per game</th><th>Offense</th><th>Defense allowed</th></tr></thead><tbody>{body}</tbody></table></div></section>')
def sheet(t):
    s = S[t]; o, d = s["off"], s["def"]
    def c(lbl, v, sub=""): return f'<div><small>{lbl}</small><b>{v}</b>{f"<span>{sub}</span>" if sub else ""}</div>'
    diff = s["pf"] - s["pa"]
    return ('<section><h2>At a glance</h2><div class="tm-glance">' +
            c("Record", f'{s["w"]}-{s["l"]}' + (f'-{s["t"]}' if s["t"] else ""), s["streak"] and f"streak {s['streak']}") +
            c("Points / game", f'{o["pts"]:.1f}', f'allowed {d["pts"]:.1f}') + c("Point diff", f'{diff:+.0f}', f'{diff / (s["g"] or 1):+.1f} / game') +
            c("Against the spread", rec(s["ats"]), "W-L-push") + c("Over / under", f'{s["ou"][0]}-{s["ou"][1]}' + (f'-{s["ou"][2]}' if s["ou"][2] else ""), "overs-unders") +
            c("Home / away", f'{rec(s["home"])}', f'away {rec(s["away"])}') + (c("Division", rec(s["div"]), DIV.get(t, "")) if DIV.get(t) else "") +
            '</div></section>')
def games_block(t):
    s = S[t]; items = []
    for r in s["games"]:
        g = r["g"]; at = "vs" if r["home"] else "@"
        line = []
        if r.get("spr") is not None: line.append(f'{r["spr"]:+g}' if r["spr"] else "PK")
        if r.get("tl") is not None: line.append(f'o/u {r["tl"]:g}')
        if not r["done"]:
            when = f'{g.get("gameday", "")[5:].replace("-", "/")} {g.get("gametime", "")}'.strip()
            items.append(f'<details class="gm up"><summary><span class="wk">Wk {r["wk"]}</span><span class="op">{badge(r["opp"])}<span>{at} {tlink(r["opp"])} <em>{E(full(r["opp"]))}</em></span></span>'
                         f'<span class="sc">{E(when)} CT{(" · " + " · ".join(line)) if line else ""}</span><span></span></summary></details>')
            continue
        tags = ""
        if r.get("ats"): tags += f'<span class="{r["ats"]}" title="{"Covered" if r["ats"] == "W" else ("Did not cover" if r["ats"] == "L" else "Push")} {r["spr"]:+g}">ATS {r["ats"]}</span>'
        if r.get("ou"): tags += f'<span class="{r["ou"]}" title="Total {r["us"] + r["them"]:.0f} vs {r["tl"]:g}">{ {"O": "Over", "U": "Under", "P": "Push"}[r["ou"]]} {r["tl"]:g}</span>'
        b, ob = r.get("box"), r.get("obox")
        if b and ob:
            def tr(lbl, k, fmt="{:.0f}"): return f'<tr><td>{lbl}</td><td>{fmt.format(b[k])}</td><td>{fmt.format(ob[k])}</td></tr>'
            team = ('<table><thead><tr><th>Team</th><th>' + E(t) + '</th><th>' + E(r["opp"]) + '</th></tr></thead><tbody>' +
                    tr("Total yards", "yds") + tr("Plays", "plays") + f'<tr><td>Passing</td><td>{b["cmp"]:.0f}/{b["att"]:.0f}, {b["pyd"]:.0f} yds</td><td>{ob["cmp"]:.0f}/{ob["att"]:.0f}, {ob["pyd"]:.0f} yds</td></tr>'
                    + f'<tr><td>Rushing</td><td>{b["car"]:.0f} for {b["ryd"]:.0f}</td><td>{ob["car"]:.0f} for {ob["ryd"]:.0f}</td></tr>' + tr("First downs", "fd") + tr("Turnovers", "to") + tr("Sacks taken", "sk")
                    + f'<tr><td>Penalties</td><td>{b["pen"]:.0f}-{b["peny"]:.0f}</td><td>{ob["pen"]:.0f}-{ob["peny"]:.0f}</td></tr></tbody></table>')
        else: team = '<p class="ld">The team box score for this game is not in the nflverse file yet.</p>'
        items.append(f'<details class="gm" data-g="{E(g["game_id"])}" data-t="{t}" data-o="{r["opp"]}"><summary><span class="wk">Wk {r["wk"]}</span><span class="op">{badge(r["opp"])}<span>{at} {E(r["opp"])} <em>{E(full(r["opp"]))}</em></span></span>'
                     f'<span class="sc"><span class="{r["res"]}">{r["res"]}</span> {r["us"]:.0f}-{r["them"]:.0f}</span><span class="chev">›</span><span class="bt">{tags}</span></summary>'
                     f'<div class="bx"><h3>Team stats</h3><div class="tw">{team}</div><div class="pbox"><p class="ld">Loading the box score…</p></div>'
                     f'<p class="ld"><a href="/teams/{r["opp"].lower()}/">{E(full(r["opp"]))} team page</a></p></div></details>')
    return ('<section><h2>Results &amp; schedule <small>tap a game for the box score · ATS and over/under against the closing consensus line</small></h2>' + "".join(items) + '</section>')
def leaders(t):
    agg = collections.defaultdict(lambda: collections.Counter()); pos = {}
    for (tm, wk), rs in PBOX.items():
        if tm != t: continue
        for r in rs:
            n = r["player_display_name"]; pos[n] = r["position"]; a = agg[n]
            for k in ("completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions", "carries", "rushing_yards", "rushing_tds", "receptions", "targets", "receiving_yards", "receiving_tds", "def_sacks", "def_interceptions", "def_tackles_solo", "def_tackle_assists"):
                a[k] += f(r[k])
            a["g"] += 1
    def top(k, n=3, min_=1): return [x for x in sorted(agg, key=lambda x: -agg[x][k]) if agg[x][k] >= min_][:n]
    def tbl(title, keys, cols, fmt, n=3):
        ps = top(keys, n)
        if not ps: return ""
        return (f'<div><h3>{title}</h3><div class="tw"><table><thead><tr><th>Player</th>' + "".join(f"<th>{c}</th>" for c in cols) + '</tr></thead><tbody>' +
                "".join(f'<tr><td>{plink(p)} <small style="color:var(--mute)">{E(pos.get(p, ""))}</small></td>' + "".join(f"<td>{x}</td>" for x in fmt(agg[p])) + '</tr>' for p in ps) + '</tbody></table></div></div>')
    blocks = [tbl("Passing", "passing_yards", ["G", "Cmp/Att", "Yds", "TD", "INT"], lambda a: [f'{a["g"]:.0f}', f'{a["completions"]:.0f}/{a["attempts"]:.0f}', f'{a["passing_yards"]:.0f}', f'{a["passing_tds"]:.0f}', f'{a["passing_interceptions"]:.0f}'], 2),
              tbl("Rushing", "rushing_yards", ["G", "Car", "Yds", "Avg", "TD"], lambda a: [f'{a["g"]:.0f}', f'{a["carries"]:.0f}', f'{a["rushing_yards"]:.0f}', f'{a["rushing_yards"] / (a["carries"] or 1):.1f}', f'{a["rushing_tds"]:.0f}']),
              tbl("Receiving", "receiving_yards", ["G", "Rec/Tgt", "Yds", "TD"], lambda a: [f'{a["g"]:.0f}', f'{a["receptions"]:.0f}/{a["targets"]:.0f}', f'{a["receiving_yards"]:.0f}', f'{a["receiving_tds"]:.0f}'], 5),
              tbl("Defense", "def_sacks", ["G", "Tkl", "Sacks", "INT"], lambda a: [f'{a["g"]:.0f}', f'{a["def_tackles_solo"] + a["def_tackle_assists"]:.0f}', f'{a["def_sacks"]:.1f}', f'{a["def_interceptions"]:.0f}'])]
    return '<section><h2>Season leaders <small>2026 regular season · names link to the player pages</small></h2><div class="gm"><div class="bx">' + "".join(blocks) + '</div></div></section>'

# owner 11/5: "how each team does against each stat percentage wise ... did they let the WR1 of the opposite team hit their prop line"
try:
    import defrole as _DEFROLE
    _DRD = _DEFROLE.load(IN, 99)   # every game played so far
except Exception as _e: print("note: defense vs role table skipped:", _e); _DRD = None
def vs_roles(t):
    if not _DRD: return ""
    rows = []
    for role in ("QB1", "RB1", "WR1", "WR2", "TE1"):
        for m in _DEFROLE.MK[role]:
            r = _DRD.rate(t, role, m)
            if not r or not r["n"]: continue
            pct = r["over"] / r["n"]; d = pct - r["lg"]
            cls = "color:var(--good)" if d >= 0.15 else "color:var(--bad)" if d <= -0.15 else ""
            fd = f'{r["fd"][0]}/{r["fd"][1]}' if r["fd"][1] else "-"
            games = "; ".join(f'W{e[0]} {e[1]} {e[2]:g} vs avg {e[3]:g}' for e in sorted(_DRD.ev[(t, role, m)]))
            rows.append(f'<tr title="{E(games)}"><td><b>{role}</b> {E(m.lower())}</td><td>{r["over"]}/{r["n"]}</td><td style="{cls}"><b>{pct*100:.0f}%</b></td><td>{r["lg"]*100:.0f}%</td><td>{fd}</td></tr>')
    if not rows: return ""
    return ('<section><h2>Against each role <small>how often the opponent\'s QB1, RB1, WR1, WR2 and TE1 beat their own season average against this defense '
            '· FD = cleared FanDuel\'s main line (weeks with frozen lines)</small></h2><div class="tw"><table class="vsr"><thead><tr><th>Role</th><th>Beat avg</th><th>%</th><th>Lg</th><th>FD</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table></div><p class="ld" style="font-size:12px;color:var(--mute);padding:0 14px 12px">Green = 15+ pts above the league rate (soft spot), red = 15+ below. '
            'These feed the builder and the best parlays with a small weight: tested on Weeks 6-8, a defense\'s record against a role only slightly sharpened the model\'s own chances.</p></section>')
TJS = r"""(function(){
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function nm(p){ return p.s ? '<a href="/player/' + p.s + '/">' + esc(p.n) + '</a>' : esc(p.n); }
  function n0(v){ return (Math.round(v * 10) / 10).toString(); }
  function tbl(title, cols, rows){ if (!rows.length) return ''; return '<h3>' + title + '</h3><div class="tw"><table><thead><tr><th>Player</th>' + cols.map(function(c){ return '<th>' + c[0] + '</th>'; }).join('') + '</tr></thead><tbody>' +
    rows.map(function(r){ return '<tr><td>' + nm(r) + ' <small style="color:var(--mute)">' + esc(r.p) + '</small></td>' + cols.map(function(c){ return '<td>' + c[1](r) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table></div>'; }
  function side(b, label, t){ return '<div><h4><span class="tb sm" style="' + (window.TCOL && TCOL[t] ? '--p:' + TCOL[t][0] + ';--s:' + TCOL[t][1] : '') + '">' + esc(t) + '</span>' + esc(label) + '</h4>' +
    tbl('Passing', [['C/Att', function(r){ return r.c + '/' + r.a; }], ['Yds', function(r){ return n0(r.y); }], ['TD', function(r){ return r.td; }], ['INT', function(r){ return r.i; }], ['Sk', function(r){ return r.sk; }]], b.pass) +
    tbl('Rushing', [['Car', function(r){ return r.c; }], ['Yds', function(r){ return n0(r.y); }], ['Avg', function(r){ return r.c ? (r.y / r.c).toFixed(1) : '-'; }], ['TD', function(r){ return r.td; }]], b.rush) +
    tbl('Receiving', [['Rec/Tgt', function(r){ return r.r + '/' + r.t; }], ['Yds', function(r){ return n0(r.y); }], ['TD', function(r){ return r.td; }]], b.rec) +
    tbl('Defense', [['Tkl', function(r){ return r.tk; }], ['Sk', function(r){ return r.sk; }], ['INT', function(r){ return r.i; }], ['PD', function(r){ return r.pd; }]], b.def) +
    tbl('Kicking', [['FG', function(r){ return r.fg; }], ['Long', function(r){ return r.lg || '-'; }], ['XP', function(r){ return r.xp; }]], b.k) + '</div>'; }
  document.querySelectorAll('details.gm[data-g]').forEach(function(d){ d.addEventListener('toggle', function(){ if (!d.open || d._ld) return; d._ld = 1; var box = d.querySelector('.pbox');
    fetch('/teams/box/' + d.getAttribute('data-g') + '.json').then(function(r){ if (!r.ok) throw 0; return r.json(); }).then(function(j){ var t = d.getAttribute('data-t'), o = d.getAttribute('data-o');
      box.innerHTML = '<div class="two">' + side(j[t] || {pass:[],rush:[],rec:[],def:[],k:[]}, '', t) + side(j[o] || {pass:[],rush:[],rec:[],def:[],k:[]}, '', o) + '</div>'; })
    .catch(function(){ box.innerHTML = '<p class="ld">The player box score for this game is not posted yet.</p>'; }); }); });
  // directory: sortable league table
  var lt = document.getElementById('leaguet'); if (lt){ var ths = lt.querySelectorAll('th.sort'); ths.forEach(function(th, i){ th.addEventListener('click', function(){ var col = +th.getAttribute('data-c'), asc = th.getAttribute('data-a') === '1';
    var tb = lt.querySelector('tbody'), rows = Array.prototype.slice.call(tb.rows); rows.sort(function(a, b){ var x = +a.cells[col].getAttribute('data-v'), y = +b.cells[col].getAttribute('data-v'); return asc ? x - y : y - x; });
    rows.forEach(function(r){ tb.appendChild(r); }); ths.forEach(function(h){ h.classList.remove('on'); }); th.classList.add('on'); }); }); }
})();
"""
os.makedirs(os.path.join(OUT, "teams"), exist_ok=True)
open(os.path.join(OUT, "teams", "teams.js"), "w").write("window.TCOL=" + json.dumps({t: list(colors(t)) for t in TEAMS}, separators=(",", ":")) + ";\n" + TJS)
for t in TEAMS:
    s = S[t]; c1, c2 = colors(t); g = this_week(t)
    sub = f'<span class="trec">{s["w"]}-{s["l"]}' + (f'-{s["t"]}' if s["t"] else "") + '</span>' + (f'<span>{E(DIV.get(t))}</span>' if DIV.get(t) else "")
    if g:
        opp = g["b"] if g["a"] == t else g["a"]; home = g["b"] == t; tp = g["pb"] if home else g["pa"]; op = g["pa"] if home else g["pb"]
        sub += f'<span>Week {W}: {"vs" if home else "@"} {tlink(opp)} · {E(g.get("kick") or "")}</span>' + (f'<span>model {tp:.0f}-{op:.0f}</span>' if isinstance(tp, (int, float)) and isinstance(op, (int, float)) else "")
    acts = (f'<a class="pri" href="/boards/#{E(g["gid"])}">Matchup board</a>' + (f'<a href="/dossier/{E(g["gid"])}/">Game dossier</a>' if os.path.exists(os.path.join(OUT, "dossier", g["gid"] + ".html")) else "") + f'<a href="/build/?g={E(g["gid"])}">Parlay Builder</a>' if g else "") + '<a href="/teams/">All teams</a><a href="/player/">Players</a>'
    desc = f'{full(t)} 2026: {s["w"]}-{s["l"]} record, points and yards per game with league ranks, against-the-spread and over/under record, and the box score of every game this season.'
    body = (head(f'{full(t)} stats, results & box scores · BetSweep', desc) +
            f'<div class="pp tpage" data-team="{t}"><p class="crumb"><a href="/teams/">Teams</a> › {E(DIV.get(t, ""))} › {E(full(t))}</p>'
            f'<header><span class="tb" style="--p:{c1};--s:{c2}">{E(t)}</span><h1>{E(full(t))}</h1><div class="sub">{sub}</div><div class="acts">{acts}</div></header>'
            + sheet(t) + stat_table(t) + vs_roles(t) + games_block(t) + leaders(t) + '</div><script src="/teams/teams.js" defer></script>')
    open(os.path.join(OUT, "teams", t.lower() + ".html"), "w").write(body)
# ---- directory: divisions + a sortable league table ------------------------------------------------------------------------------------
divs = collections.OrderedDict()
for d in ("AFC East", "AFC North", "AFC South", "AFC West", "NFC East", "NFC North", "NFC South", "NFC West"):
    divs[d] = sorted([t for t in TEAMS if DIV.get(t) == d], key=lambda t: (-(S[t]["w"] + 0.5 * S[t]["t"]) / (S[t]["g"] or 1), -(S[t]["pf"] - S[t]["pa"])))
other = [t for t in TEAMS if not DIV.get(t)]
if other: divs["Teams"] = other
dhtml = "".join(f'<section class="div"><h2>{E(d)}</h2><div class="grid">' + "".join(
    f'<a href="/teams/{t.lower()}/">{badge(t, True)}<b>{E(BR.NAMES.get(t, t))}</b><span class="r">{S[t]["w"]}-{S[t]["l"]}{("-" + str(S[t]["t"])) if S[t]["t"] else ""}<small>{S[t]["pf"] - S[t]["pa"]:+.0f}</small></span>'
    f'<small>{S[t]["off"]["pts"]:.1f} scored · {S[t]["def"]["pts"]:.1f} allowed</small></a>' for t in ts) + '</div></section>' for d, ts in divs.items() if ts)
LCOL = [("W-L", lambda t: (S[t]["w"] + 0.5 * S[t]["t"]) / (S[t]["g"] or 1), lambda t: f'{S[t]["w"]}-{S[t]["l"]}' + (f'-{S[t]["t"]}' if S[t]["t"] else ""), 0),
        ("Pts", lambda t: S[t]["off"]["pts"], lambda t: f'{S[t]["off"]["pts"]:.1f}', 0), ("Pts allowed", lambda t: S[t]["def"]["pts"], lambda t: f'{S[t]["def"]["pts"]:.1f}', 1),
        ("Yds", lambda t: S[t]["off"].get("yds", 0), lambda t: f'{S[t]["off"].get("yds", 0):.0f}', 0), ("Yds allowed", lambda t: S[t]["def"].get("yds", 0), lambda t: f'{S[t]["def"].get("yds", 0):.0f}', 1),
        ("Pass", lambda t: S[t]["off"].get("pyd", 0), lambda t: f'{S[t]["off"].get("pyd", 0):.0f}', 0), ("Rush", lambda t: S[t]["off"].get("ryd", 0), lambda t: f'{S[t]["off"].get("ryd", 0):.0f}', 0),
        ("Pass allowed", lambda t: S[t]["def"].get("pyd", 0), lambda t: f'{S[t]["def"].get("pyd", 0):.0f}', 1), ("Rush allowed", lambda t: S[t]["def"].get("ryd", 0), lambda t: f'{S[t]["def"].get("ryd", 0):.0f}', 1),
        ("ATS", lambda t: S[t]["ats"][0] - S[t]["ats"][1], lambda t: rec(S[t]["ats"]), 0), ("Overs", lambda t: S[t]["ou"][0] - S[t]["ou"][1], lambda t: f'{S[t]["ou"][0]}-{S[t]["ou"][1]}', 0)]
lt = ('<section><h2>League table <small>per game · tap a column to sort</small></h2><div class="tw"><table id="leaguet"><thead><tr><th>Team</th>' +
      "".join(f'<th class="sort" data-c="{i + 1}" data-a="{a}">{E(h)}</th>' for i, (h, _, _, a) in enumerate(LCOL)) + '</tr></thead><tbody>' +
      "".join(f'<tr><td>{badge(t)} <a href="/teams/{t.lower()}/">{E(BR.NAMES.get(t, t))}</a></td>' + "".join(f'<td data-v="{v(t):.3f}">{x(t)}</td>' for _, v, x, _ in LCOL) + '</tr>'
              for t in sorted(TEAMS, key=lambda t: -LCOL[0][1](t))) + '</tbody></table></div></section>')
nwk = max([int(g["week"]) for g in G if played(g)] or [0])
idx = (head("NFL teams: stats, results & box scores · BetSweep", "Every NFL team's 2026 season: record, points and yards per game with league ranks, against-the-spread and over/under records, and the box score of every game.") +
       f'<div class="pp tdir"><p class="crumb"><a href="/">Home</a> › Teams</p><header><span class="tb" style="--p:#d7332a;--s:#8f1d17">NFL</span><h1>Teams</h1>'
       f'<div class="sub"><span>2026 regular season</span><span>through Week {nwk}</span><span>box scores for every game</span></div><div class="acts"><a href="/player/">Players</a><a class="pri" href="/boards/">Matchup boards</a></div></header>'
       + dhtml + lt + '</div><script src="/teams/teams.js" defer></script>')
open(os.path.join(OUT, "teams", "index.html"), "w").write(idx)
print(f"wrote out/teams: {len(TEAMS)} team pages + directory, {nbox} game box scores, through week {nwk}")
