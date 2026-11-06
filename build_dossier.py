#!/usr/bin/env python3
"""build_dossier.py - the Game Dossier: one page per game this week at /dossier/<gid>/ (owner 11/5: "how does this team in particular play against
similar defenses? Then key matchups, injuries on both sides of the ball, game script, weather, who's been heating up or in the news ... will a good
team play down to another team or a bad team play well against a good team"). Nothing here changes a projection - it is the read before a bet or a
promo, and PROMO_DESK.md requires it.

Per game, for each offense against the other defense:
  1. Similar defenses   every defense gets a profile (per game allowed: net pass yds, rush yds, points, yards/play; sacks and takeaways made),
                        z-scored across the league; the offense's three past opponents nearest to tonight's defense, the offense's output in those
                        games vs its season average, and each skill player's line in them vs his own average.
  2. Where it leaks     what this defense has allowed to each role - the opponent's WR1 / WR2 / TE1 (by season target rank on their team) and RB1
                        (by carries) - in yards and against those players' own averages in their other games; mapped onto tonight's WR1/WR2/TE1/RB1.
  3. Spots              research/situational_backtest.py on 2006-2025 closing spreads: only spots that beat -110 in both decades show as a lean; the
                        common folklore spots that apply tonight are shown with their real cover rate ("no edge").
  plus the model's game script (builder), kickoff weather, defensive injuries (context desk), news-desk items, and who is running hot or cold
  (last 3 games vs season).
Reads: out/builder_data.json, in/stats_team_week_2026.csv, in/stats_player_week_2026.csv, in/games.csv, in/weather.json, in/ctx_definj.json,
in/ctx_news.json, research/situational_spots.json. Writes out/dossier/<gid>.html, out/dossier/index.html, out/dossier.json (served at /b/dossier.json).
"""
import os, csv, json, math, html, collections, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
E = html.escape; SEASON = 2026; NV = "https://github.com/nflverse/nflverse-data/releases/download"
FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}
def T(x): x = str(x or "").strip(); return FIX.get(x, x)
def f(x):
    try: return float(x)
    except Exception: return 0.0
def rows(name, url=None):
    p = os.path.join(IN, name)
    if not os.path.exists(p) and url:
        try: urllib.request.urlretrieve(url, p)
        except Exception as e: print("warn:", name, e); return []
    if not os.path.exists(p): return []
    with open(p, newline="") as fh: return list(csv.DictReader(fh))
def jload(p, d=None):
    try: return json.load(open(p))
    except Exception: return d
from plydata import slugify
_ns = {"HERE": HERE}; exec(open(os.path.join(HERE, "brand.py")).read(), _ns); NAMES, TEAMCOL = _ns["NAMES"], _ns["TEAMCOL"]

B = jload(os.path.join(OUT, "builder_data.json"), {"week": 0, "games": [], "legs": []}); W = int(B.get("week") or 0)
TS = [r for r in rows(f"stats_team_week_{SEASON}.csv", f"{NV}/stats_team/stats_team_week_{SEASON}.csv") if r.get("season_type", "REG") == "REG"]
PS = [r for r in rows(f"stats_player_week_{SEASON}.csv", f"{NV}/stats_player/stats_player_week_{SEASON}.csv") if r.get("season_type", "REG") == "REG" and int(r["week"]) < (W or 99)]
TS = [r for r in TS if int(r["week"]) < (W or 99)]
GS = [g for g in rows("games.csv") if g.get("season") == str(SEASON) and g.get("game_type") == "REG"]
for g in GS: g["home_team"], g["away_team"] = T(g["home_team"]), T(g["away_team"])
SCORE = {}
for g in GS:
    if g.get("home_score") not in ("", "NA", None):
        SCORE[(g["home_team"], int(g["week"]))] = (f(g["home_score"]), f(g["away_score"])); SCORE[(g["away_team"], int(g["week"]))] = (f(g["away_score"]), f(g["home_score"]))

# ---- team game lines (offense) and defense profiles -----------------------------------------------------------------------------------
def tline(r):
    return {"pyd": f(r["passing_yards"]) - f(r["sack_yards_lost"]), "ryd": f(r["rushing_yards"]), "plays": f(r["attempts"]) + f(r["carries"]) + f(r["sacks_suffered"]),
            "sk": f(r["sacks_suffered"]), "to": f(r["passing_interceptions"]) + f(r["sack_fumbles_lost"]) + f(r["rushing_fumbles_lost"]) + f(r["receiving_fumbles_lost"])}
OFF = {}   # (team, week) -> line incl points, opp
for r in TS:
    t, w = T(r["team"]), int(r["week"]); l = tline(r); l["opp"] = T(r["opponent_team"]); l["pts"] = SCORE.get((t, w), (None, None))[0]; OFF[(t, w)] = l
TEAMS = sorted({t for t, _ in OFF})
DEFG = collections.defaultdict(list)   # defense -> list of opponent lines against it
for (t, w), l in OFF.items(): DEFG[l["opp"]].append({**l, "team": t, "w": w})
KEYS = [("pyd", "pass yds allowed"), ("ryd", "rush yds allowed"), ("pts", "points allowed"), ("ypp", "yards / play allowed"), ("sk", "sacks"), ("to", "takeaways")]
PROF = {}
for d, ls in DEFG.items():
    n = len(ls); pts = [x["pts"] for x in ls if x["pts"] is not None]
    PROF[d] = {"pyd": sum(x["pyd"] for x in ls) / n, "ryd": sum(x["ryd"] for x in ls) / n, "pts": (sum(pts) / len(pts)) if pts else 0,
               "ypp": sum(x["pyd"] + x["ryd"] for x in ls) / max(1, sum(x["plays"] for x in ls)), "sk": sum(x["sk"] for x in ls) / n, "to": sum(x["to"] for x in ls) / n, "g": n}
MU = {k: sum(PROF[d][k] for d in PROF) / len(PROF) for k, _ in KEYS} if PROF else {}
SD = {k: (math.sqrt(sum((PROF[d][k] - MU[k]) ** 2 for d in PROF) / len(PROF)) or 1) for k, _ in KEYS} if PROF else {}
WT = {"pyd": 1.0, "ryd": 1.0, "pts": 0.8, "ypp": 0.8, "sk": 0.6, "to": 0.4}
def z(d): return {k: (PROF[d][k] - MU[k]) / SD[k] for k, _ in KEYS}
def dist(a, b): za, zb = z(a), z(b); return math.sqrt(sum(WT[k] * (za[k] - zb[k]) ** 2 for k, _ in KEYS))
def drank(d, k):   # 1 = allows the most (softest) for allowed stats; 1 = most sacks / takeaways for those
    return sorted(PROF, key=lambda x: -PROF[x][k]).index(d) + 1
def desc_def(d):
    p = PROF[d]; r = {k: drank(d, k) for k, _ in KEYS}
    def soft(k): return "soft" if r[k] <= 8 else ("stingy" if r[k] >= 25 else "middle")
    return (f'{p["pyd"]:.0f} pass yds (#{r["pyd"]} most), {p["ryd"]:.0f} rush yds (#{r["ryd"]}), {p["pts"]:.1f} pts, {p["ypp"]:.1f} yds/play allowed; '
            f'{p["sk"]:.1f} sacks, {p["to"]:.1f} takeaways a game'), soft("pyd"), soft("ryd")

# ---- players: season lines, roles ------------------------------------------------------------------------------------------------------
PG = collections.defaultdict(list)    # (name, team) -> games
for r in PS:
    if r["position"] not in ("QB", "RB", "WR", "TE"): continue
    PG[(r["player_display_name"], T(r["team"]))].append({"w": int(r["week"]), "opp": T(r["opponent_team"]), "pos": r["position"], "tgt": f(r["targets"]), "rec": f(r["receptions"]),
        "recy": f(r["receiving_yards"]), "car": f(r["carries"]), "rush": f(r["rushing_yards"]), "pass": f(r["passing_yards"]), "att": f(r["attempts"]),
        "td": f(r["rushing_tds"]) + f(r["receiving_tds"]), "ptd": f(r["passing_tds"])})
def avg(gs, k): return sum(g[k] for g in gs) / len(gs) if gs else 0.0
def roles(team, upto=None):
    """WR1/WR2/TE1 by season targets, RB1 by carries, QB1 by attempts (games before week `upto`)"""
    agg = {}
    for (n, t), gs in PG.items():
        if t != team: continue
        g2 = [g for g in gs if upto is None or g["w"] < upto]
        if g2: agg[n] = (g2[0]["pos"], sum(g["tgt"] for g in g2), sum(g["car"] for g in g2), sum(g["att"] for g in g2))
    out = {}
    for pos, key, labels in (("WR", 1, ("WR1", "WR2")), ("TE", 1, ("TE1",)), ("RB", 2, ("RB1",)), ("QB", 3, ("QB1",))):
        ps = sorted([n for n, v in agg.items() if v[0] == pos], key=lambda n: -agg[n][key])
        for lab, n in zip(labels, ps): out[lab] = n
    return out
ROLE_STAT = {"WR1": ("recy", "rec yds"), "WR2": ("recy", "rec yds"), "TE1": ("recy", "rec yds"), "RB1": ("rush", "rush yds"), "QB1": ("pass", "pass yds")}
def leak(d):
    """per role: what d allowed, and vs those players' own average in their other games"""
    out = {}
    for lab, (k, unit) in ROLE_STAT.items():
        vals, rel = [], []
        for x in DEFG.get(d, []):
            n = roles(x["team"], upto=None).get(lab)
            if not n: continue
            gs = PG.get((n, x["team"]), []); g = [g for g in gs if g["w"] == x["w"]]
            if not g: continue
            others = [h[k] for h in gs if h["w"] != x["w"]]
            vals.append((g[0][k], n, x["team"], x["w"]))
            if others and sum(others) / len(others) > 0: rel.append(g[0][k] / (sum(others) / len(others)))
        if vals:
            out[lab] = {"unit": unit, "avg": sum(v[0] for v in vals) / len(vals), "vs_own": (sum(rel) / len(rel)) if rel else None, "n": len(vals),
                        "games": sorted(vals, key=lambda v: v[3])}
    return out
LEAK_RANK = {}
for lab in ROLE_STAT:
    vals = {d: leak(d).get(lab, {}).get("vs_own") for d in DEFG}
    order = sorted([d for d in vals if vals[d] is not None], key=lambda d: -vals[d])
    for i, d in enumerate(order): LEAK_RANK[(d, lab)] = i + 1

# ---- situational spots -----------------------------------------------------------------------------------------------------------------
SPOTS = jload(os.path.join(HERE, "research", "situational_spots.json"), {"spots": []})
BT = {}
try:
    for ln in open(os.path.join(HERE, "research", "situational_backtest.txt")):
        p = ln.split()
        if len(p) >= 8 and p[0].replace("_", "").isalpha() and p[1].isdigit(): BT[p[0]] = {"n": int(p[1]), "cover": p[2]}
except Exception: pass
def record(t, before):
    w = l = ti = 0
    for g in GS:
        if int(g["week"]) >= before or g.get("home_score") in ("", "NA", None) or t not in (g["home_team"], g["away_team"]): continue
        us, them = SCORE[(t, int(g["week"]))]
        if us > them: w += 1
        elif us < them: l += 1
        else: ti += 1
    return w, l, ti
def spots_for(t, o, line, home):
    tags = []
    w, l, ti = record(t, W); ow, ol, oti = record(o, W); gp, ogp = w + l + ti, ow + ol + oti
    wp = (w + .5 * ti) / gp if gp else None; owp = (ow + .5 * oti) / ogp if ogp else None
    past = sorted([g for g in GS if t in (g["home_team"], g["away_team"]) and int(g["week"]) < W and (t, int(g["week"])) in SCORE], key=lambda g: int(g["week"]))
    last = (SCORE[(t, int(past[-1]["week"]))][0] - SCORE[(t, int(past[-1]["week"]))][1]) if past else None
    nxt = sorted([g for g in GS if t in (g["home_team"], g["away_team"]) and int(g["week"]) > W], key=lambda g: int(g["week"]))
    applies = {
        "bounce_after_blowout_loss": last is not None and last <= -21,
        "lookahead_fav": line is not None and line <= -3 and bool(nxt) and nxt[0].get("div_game") == "1",
        "big_fav_vs_worse": line is not None and line <= -7 and gp >= 3 and owp is not None and wp is not None and wp > owp,
        "bad_dog_vs_good": W >= 5 and line is not None and line > 0 and wp is not None and owp is not None and wp <= .35 and owp >= .65,
        "letdown_after_blowout": line is not None and line < 0 and last is not None and last >= 21,
        "double_digit_fav": line is not None and line <= -10,
        "home_dog": home and line is not None and line > 0,
    }
    kept = {s["key"]: s for s in SPOTS.get("spots", [])}
    LBL = {"bounce_after_blowout_loss": "coming off a 21+ point loss", "lookahead_fav": "favorite of 3+ with a division game next", "big_fav_vs_worse": "7+ point favorite against a team with a worse record (\"playing down\")",
           "bad_dog_vs_good": "bad team as an underdog to a good team", "letdown_after_blowout": "favorite coming off a 21+ point win", "double_digit_fav": "double-digit favorite", "home_dog": "home underdog"}
    for k, on in applies.items():
        if not on: continue
        if k in kept:
            s = kept[k]; verb = "covered" if s["side"] == "with" else "covered only"
            tags.append(("lean", f'{t}: {LBL[k]} - teams in this spot {verb} {s["cover"]*100:.1f}% of the time over {s["n"]} games (2006-2025, both decades); a {s["tier"]}, not a projection input'))
        elif k in BT:
            tags.append(("none", f'{t}: {LBL[k]} - no edge: {BT[k]["cover"]} cover rate over {BT[k]["n"]} games (2006-2025)'))
    return tags

# ---- weather / injuries / news -----------------------------------------------------------------------------------------------------------
WX = {}
wx = jload(os.path.join(IN, "weather.json"), {"values": []}).get("values", [])
if wx:
    H = {c: i for i, c in enumerate(wx[0])}
    for r in wx[1:]:
        if len(r) > H.get("Weather Risk", 99) and str(r[0]) == str(W): WX[frozenset((T(r[H["Matchup Team 1"]]), T(r[H["Matchup Team 2"]])))] = r
def wx_line(a, b):
    r = WX.get(frozenset((a, b)))
    if not r: return None
    H = {c: i for i, c in enumerate(wx[0])}; g = lambda c: r[H[c]] if len(r) > H[c] else ""
    if "dome" in str(g("Roof Status")).lower(): return ("info", f'Dome ({g("Venue")}).')
    risk = str(g("Weather Risk")); k = "bad" if risk.upper().startswith("HIGH") else ("watch" if risk.upper().startswith("MOD") else "info")
    return (k, f'{g("Temperature F")}F, wind {g("Wind MPH")} (gusts {g("Gust MPH") or "-"}), {g("Precipitation Type") or "no precipitation"} {g("Precipitation Chance %") and str(g("Precipitation Chance %")) + "%"} - risk {risk}.')
DEFINJ = jload(os.path.join(IN, "ctx_definj.json"), {}) or {}
NEWS = jload(os.path.join(IN, "ctx_news.json"), {}) or {}

# ---- hot / cold -----------------------------------------------------------------------------------------------------------------------------
def heat(team):
    out = []
    for (n, t), gs in PG.items():
        if t != team or len(gs) < 4: continue
        pos = gs[0]["pos"]; k = "pass" if pos == "QB" else ("rush" if pos == "RB" and avg(gs, "rush") > avg(gs, "recy") else "recy")
        s, l3 = avg(gs, k), avg(gs[-3:], k)
        if s < (120 if pos == "QB" else 25): continue
        ch = (l3 - s) / s
        if abs(ch) >= .25: out.append((ch, n, pos, k, s, l3))
    out.sort(key=lambda x: -abs(x[0]))
    U = {"pass": "pass yds", "rush": "rush yds", "recy": "rec yds"}
    return [("good" if ch > 0 else "bad", f'{n} ({pos}): {l3:.0f} {U[k]} a game over the last 3 vs {s:.0f} on the season ({ch*100:+.0f}%)') for ch, n, pos, k, s, l3 in out[:5]]

# ---- page ------------------------------------------------------------------------------------------------------------------------------------
def plink(n):
    s = slugify(n); return f'<a href="/player/{s}/">{E(n)}</a>' if os.path.exists(os.path.join(OUT, "players", s + ".html")) else E(n)
def badge(t): c1, c2 = TEAMCOL.get(t, ("#2b3442", "#141a24")); return f'<a class="tb sm" href="/teams/{t.lower()}/" style="--p:{c1};--s:{c2}">{E(t)}</a>'
def similar_block(off, d):
    if d not in PROF: return "<p class=\"none\">Not enough games for a defense profile yet.</p>", {}
    ds, s1, s2 = desc_def(d)
    past = [(w, l) for (t, w), l in OFF.items() if t == off and l["opp"] != d]
    near = sorted(past, key=lambda x: dist(d, x[1]["opp"]))[:3]
    if not near: return "", {}
    seas = [l for (t, w), l in OFF.items() if t == off]
    def tav(ls, k): v = [x[k] for x in ls if x.get(k) is not None]; return sum(v) / len(v) if v else 0
    rows_ = "".join(f'<tr><td>Wk {w} {badge(l["opp"])}</td><td>{l["pts"]:.0f}</td><td>{l["pyd"]:.0f}</td><td>{l["ryd"]:.0f}</td><td>{l["to"]:.0f}</td><td class="m">{dist(d, l["opp"]):.1f}</td></tr>' for w, l in sorted(near))
    rows_ += f'<tr class="sum"><td>Those {len(near)} games</td><td>{tav([l for _, l in near], "pts"):.1f}</td><td>{tav([l for _, l in near], "pyd"):.0f}</td><td>{tav([l for _, l in near], "ryd"):.0f}</td><td>{tav([l for _, l in near], "to"):.1f}</td><td></td></tr>'
    rows_ += f'<tr class="sum"><td>Season average</td><td>{tav(seas, "pts"):.1f}</td><td>{tav(seas, "pyd"):.0f}</td><td>{tav(seas, "ryd"):.0f}</td><td>{tav(seas, "to"):.1f}</td><td></td></tr>'
    weeks = {w for w, _ in near}
    pl = []
    for (n, t), gs in PG.items():
        if t != off or len(gs) < 2: continue
        pos = gs[0]["pos"]; k = "pass" if pos == "QB" else ("rush" if pos == "RB" else "recy")
        s = avg(gs, k); sg = [g for g in gs if g["w"] in weeks]
        if not sg or s < (100 if pos == "QB" else 15): continue
        v = avg(sg, k); tds = sum(g["td"] + g["ptd"] for g in sg)
        pl.append((s, f'<tr><td>{plink(n)} <small>{pos}</small></td><td>{len(sg)}</td><td>{v:.0f}</td><td>{s:.0f}</td><td class="{"up" if v > s * 1.1 else ("dn" if v < s * .9 else "")}">{(v - s) / s * 100:+.0f}%</td><td>{tds:.0f}</td></tr>'))
    pl.sort(key=lambda x: -x[0])
    U = '<small>main stat: pass yds QB, rush yds RB, rec yds WR/TE</small>'
    data = {"near": [{"w": w, "opp": l["opp"], "pts": l["pts"], "pyd": l["pyd"], "ryd": l["ryd"]} for w, l in sorted(near)], "pts_near": tav([l for _, l in near], "pts"), "pts_season": tav(seas, "pts")}
    return (f'<p class="lede">{E(d)} defense: {E(ds)}. Closest past opponents of {E(off)} by that profile:</p>'
            f'<div class="tw"><table><thead><tr><th>{E(off)} vs</th><th>Pts</th><th>Pass</th><th>Rush</th><th>TO</th><th>Distance</th></tr></thead><tbody>{rows_}</tbody></table></div>'
            + (f'<h3>{E(off)} players in those games {U}</h3><div class="tw"><table><thead><tr><th>Player</th><th>G</th><th>In those</th><th>Season</th><th>Diff</th><th>TD</th></tr></thead><tbody>{"".join(h for _, h in pl[:10])}</tbody></table></div>' if pl else "")), data
def leak_block(off, d):
    L = leak(d); mine = roles(off)
    if not L: return "", {}
    body = ""
    for lab, x in L.items():
        r = LEAK_RANK.get((d, lab)); vo = x["vs_own"]; who = mine.get(lab)
        cls = "up" if vo and vo >= 1.1 else ("dn" if vo and vo <= .9 else "")
        body += (f'<tr><td><b>{lab}</b></td><td>{x["avg"]:.0f} <small>{x["unit"]}</small></td><td class="{cls}">{(vo - 1) * 100:+.0f}%</td><td>{f"#{r} of 32" if r else ""}</td>'
                 f'<td>{plink(who) if who else "-"}</td></tr>') if vo is not None else ""
    data = {lab: {"avg": round(x["avg"], 1), "vs_own": round(x["vs_own"], 3) if x["vs_own"] else None, "rank": LEAK_RANK.get((d, lab)), "player": mine.get(lab)} for lab, x in L.items()}
    return ('<div class="tw"><table><thead><tr><th>Role</th><th>Allowed / game</th><th>vs their own avg</th><th>Leakiest</th><th>Tonight</th></tr></thead><tbody>' + body + '</tbody></table></div>'
            f'<p class="note">Roles by season targets (WR, TE) and carries (RB) on each opponent. "vs their own avg" compares what those players did against {E(d)} with their other games; #1 = the defense that lets that role exceed its average the most.</p>'), data
CSS = """<style>
.pp .lede{margin:10px 14px 6px;font-size:13.5px;line-height:1.5;color:var(--mute)} .pp .note{margin:6px 14px 12px;font-size:12px;color:var(--mute);line-height:1.45}
.pp h3{margin:12px 14px 6px;font-family:var(--display);font-weight:700;font-size:14px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute)} .pp h3 small{text-transform:none;letter-spacing:0;font-family:var(--body);font-weight:400;margin-left:6px}
.pp td small{color:var(--mute)} .pp td.up{color:var(--good);font-weight:700} .pp td.dn{color:var(--bad);font-weight:700} .pp td.m{color:var(--mute)} .pp tr.sum td{font-weight:600;background:color-mix(in srgb,var(--chalk) 55%,transparent)}
.pp .tb.sm{grid-row:auto;width:30px;height:30px;font-size:11.5px;border-radius:6px;box-shadow:inset 0 -3px 0 var(--s,#000);text-decoration:none;vertical-align:middle;margin-left:6px}
.dsx{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px} .dsx>div{display:grid;gap:14px;align-content:start;min-width:0} @media (max-width:900px){.dsx{grid-template-columns:minmax(0,1fr)}}
.dsx section{margin:0}
.dsgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.dsgrid a{display:block;text-decoration:none;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px} .dsgrid a:hover{border-color:var(--red)}
.dsgrid b{font-family:var(--display);font-weight:700;font-size:20px} .dsgrid small{display:block;color:var(--mute);font-size:12.5px;margin-top:4px}
</style>"""
def head(title, desc):
    link, _ = __import__("account")._base_css()
    return f'<title>{E(title)}</title>\n<meta name="description" content="{E(desc)}">\n{link}\n<link rel="stylesheet" href="/player/player.css">\n{CSS}\n'
os.makedirs(os.path.join(OUT, "dossier"), exist_ok=True)
J = {"week": W, "games": {}}
cards = []
for g in B.get("games", []):
    a, b, gid = g["a"], g["b"], g["gid"]
    try: probs = json.loads(g["probs"]) if isinstance(g.get("probs"), str) else g.get("probs")
    except Exception: probs = None
    sch = next((x for x in GS if int(x["week"]) == W and {x["home_team"], x["away_team"]} == {a, b}), None)
    home = sch["home_team"] if sch else b
    away = a if home == b else b
    spr = f(sch["spread_line"]) if sch and sch.get("spread_line") not in ("", "NA", None) else None
    line = {home: -spr, (a if home == b else b): spr} if spr is not None else {a: None, b: None}
    flags = []
    w1 = wx_line(a, b)
    if w1: flags.append((w1[0], "Weather: " + w1[1]))
    for x in (DEFINJ.get("games", {}) or {}).get(gid, []): flags.append((x.get("k", "info"), f'{x.get("tag", "")}: {x.get("txt", "")}'))
    news = [p for p in (NEWS.get("players") or []) if p.get("team") in (a, b) and p.get("sev", 0) >= 3][:6]
    for p in news: flags.append((p.get("k", "info"), f'{p["player"]} ({p["team"]}): {p.get("tag", "")} - {p.get("txt", "")[:180]}'))
    spot = spots_for(a, b, line.get(a), home == a) + spots_for(b, a, line.get(b), home == b)
    sims, leaks = {}, {}
    sides = ""
    for off, d in ((a, b), (b, a)):
        sh, sd = similar_block(off, d); lh, ld = leak_block(off, d); sims[off] = sd; leaks[off] = ld
        sides += (f'<div><section><h2>{badge(off)} {E(NAMES.get(off, off))} offense vs similar defenses</h2><p class="none">Context, not a pick: tested 2024-26, a player&#39;s numbers against the most similar past defenses did not predict his next game (players 20%+ above their average in those games hit FanDuel overs 46.5% vs 56.7% priced).</p>{sh}</section>'
                  f'<section><h2>Where the {E(NAMES.get(d, d))} defense leaks <small>by role, this season</small></h2>{lh}</section>'
                  f'<section><h2>{E(off)} running hot / cold <small>last 3 games vs season</small></h2><ul class="fl">' + ("".join(f'<li class="{k}">{E(t)}</li>' for k, t in heat(off)) or '<li>Nobody 25%+ off his season pace.</li>') + '</ul></section></div>')
    script = ""
    if probs and len(probs) == 4:
        script = (f'<p class="lede">Model: {E(a)} {g.get("pa", 0):.1f} - {E(b)} {g.get("pb", 0):.1f}. {E(a)} by 10+ {probs[0]:.0f}% · close, low scoring {probs[1]:.0f}% · shootout {probs[2]:.0f}% · {E(b)} by 10+ {probs[3]:.0f}%. Most likely: {E(g.get("most", ""))}.'
                  + (f' Market: {E(home)} {-spr:+g}' if spr is not None else "") + (f', total {sch["total_line"]}' if sch and sch.get("total_line") not in ("", "NA") else "") + '.</p>')
    fl = "".join(f'<li class="{k}">{E(t)}</li>' for k, t in flags) or '<li>No weather, defensive-injury or news flags in this build.</li>'
    sp = "".join(f'<li class="{"good" if k == "lean" else ""}">{E(t)}</li>' for k, t in spot) or '<li>No tested spot applies to this game.</li>'
    desc = f'{away} at {home}, Week {W}: how each offense has done against defenses like this one, where each defense leaks by position, game script, weather, injuries, news and the situational spots that actually hold up.'
    body = (head(f'{away} @ {home} game preview · Week {W} · BetSweep', desc) +
            f'<div class="pp"><p class="crumb"><a href="/dossier/">Game previews</a> › {E(away)} @ {E(home)}</p>'
            f'<header><span class="tb" style="--p:#d7332a;--s:#8f1d17">{W}</span><h1>{E(away)} @ {E(home)}</h1><div class="sub"><span>{E(g.get("kick", ""))}</span><span>Week {W} game preview</span></div>'
            f'<div class="acts"><a class="pri" href="/boards/#{E(gid)}">Matchup board</a><a href="/build/?g={E(gid)}">Parlay Builder</a><a href="/teams/{a.lower()}/">{E(a)}</a><a href="/teams/{b.lower()}/">{E(b)}</a></div></header>'
            f'<section><h2>Game script</h2>{script or "<p class=lede>No script for this game in the build.</p>"}</section>'
            f'<section><h2>Injuries, weather, news</h2><ul class="fl">{fl}</ul></section>'
            f'<section><h2>Situational spots <small>tested on 2006-2025 closing spreads; only spots that beat -110 in both decades count</small></h2><ul class="fl">{sp}</ul></section>'
            f'<div class="dsx">{sides}</div></div>')
    open(os.path.join(OUT, "dossier", gid + ".html"), "w").write(body)
    J["games"][gid] = {"a": a, "b": b, "kick": g.get("kick"), "script": probs, "flags": [t for _, t in flags], "spots": [{"k": k, "t": t} for k, t in spot], "similar": sims, "leak": leaks}
    cards.append((g.get("sort", ""), f'<a href="/dossier/{E(gid)}/"><b>{E(away)} @ {E(home)}</b><small>{E(g.get("kick", ""))} · {E(g.get("most", "") or "")}</small>'
                  + "".join(f'<small>{E(t[:110])}</small>' for k, t in spot if k == "lean") + '</a>'))
idx = (head(f"Game previews · Week {W} · BetSweep", "Every game this week: similar-defense splits, where each defense leaks, game script, weather, injuries, news and tested situational spots.") +
       f'<div class="pp"><p class="crumb"><a href="/">Home</a> › Game previews</p><header><span class="tb" style="--p:#d7332a;--s:#8f1d17">{W}</span><h1>Game previews</h1>'
       '<div class="sub"><span>the read before the bet</span><span>similar defenses · leaks by role · script · weather · injuries · news · spots</span></div></header>'
       '<div class="dsgrid">' + "".join(h for _, h in sorted(cards)) + '</div></div>')
open(os.path.join(OUT, "dossier", "index.html"), "w").write(idx)
json.dump(J, open(os.path.join(OUT, "dossier.json"), "w"), separators=(",", ":"))
print(f"wrote out/dossier: {len(cards)} game previews for week {W}, {sum(1 for v in J['games'].values() for s in v['spots'] if s['k'] == 'lean')} situational leans, defense profiles for {len(PROF)} teams")
