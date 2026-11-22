#!/usr/bin/env python3
"""build_stocks.py - /stocks/ "Stock Market" (owner 11/22 12:04 AM: "I want you to make a 'Stock Market' page. I want to it to kind of
take from our player pages but I'm basically wanting to add a lot of graphs. I want top rising, trending players of each position. To
fill up the page. It'd be player, team, and then a graph of their recent games total fantasy points. When you click on the fantasy points
graph it opens up to where you'd choose his stats. When you click on any stat it opens up to a graph. I want a search bar the top though
so you can filter players.")

What it writes
  out/stocks.html   the page. A search box, then the top risers at QB / RB / WR / TE as tiles: player, team, a small graph of his fantasy
                    points game by game (his last games in colour), his average over those last games and the change from his earlier
                    ones. Tapping a tile opens his stats under its row; tapping a stat opens that stat's graph under the stat's row.
                    The search covers every player who has a player page, rising or not.
  the data          rides in the page as window.__SK (build_site.py moves it to /stocks/data-<hash>.js like the builder's board).

The rules, all in one place
  window    a player's last 3 games when he has played 6 or more, his last 2 when he has played 4 or 5, none below 4
  riser     averages FLOOR[pos]+ fantasy points over the window; is up MIN_UP+ a game on his earlier games; beat his earlier average in at
            least two games of the window (one blow-up is not a rise); played one of his team's last two games; is not Out / Doubtful
            this week (plydata status: the model's availability tab first, then the weekly report); has a player page
  order     biggest rise first (the change to two decimals; a tie goes by name). The first TOP at each position are written into the page;
            the rest ride in the data and a "Show all N rising ..." button under the list adds them with the same tile template
  faller    the mirror (11/22, "any other good information ... that would go hand in hand"): his EARLIER average was FLOOR[pos]+, he is
            down MIN_UP+ a game, two or more games of the window were under that earlier average, and the same played / not-ruled-out
            tests. A Rising / Falling switch at the top shows one set of lists at a time; both are written into the page
  what moved   two sentences of arithmetic in a player's box (what_moved): his chances before and now (pass attempts for a quarterback,
            carries plus targets for a back, targets for a receiver or tight end) and how much of the fantasy change is touchdowns
            (6 a rushing or receiving TD, 4 a passing TD) when that is 1+ point of a 2+ point move in the same direction
  this week    his game (this_week): opponent, kickoff, and the model's projection for him - out/startsit.json, the Start / Sit page's own
            number, so the two pages cannot disagree - with that defense's rank in yards allowed to his position. A bye, a game already
            played, or a player listed out says so instead
  movers    (11/22 11:42 AM, "Anything else you can do to the stock market page to make it a little more interesting? Added stats?")
            a row of cards above the lists, each the leader in one count among players who could make a list (movers()): biggest riser,
            biggest faller, Breakout (the biggest riser whose earlier average was under FLOOR), Season high (the best latest game that was
            also his best of four or more), Top-12 streak, Most top-12 weeks, Highest floor (the best worst game of a 6+ game starter),
            On the climb (most games running with more points than the game before, the latest at FLOOR or better). A card with nobody is
            left out. A tap opens that player wherever his tile is (openKey in the page script: his list, the other list, or a search)
  finishes  COLS "fr": where a game ranked at his position that week among EVERY player (players with no page too), for weeks before the
            site's week. A top-12 week is fr <= 12. The page ships the number; it cannot be redone from the page alone, so the test checks
            it stays in step with the shipped scores
  numbers   the top of a player's box (quote() in the page script): Rank now (his window average among players at his position who played
            one of their team's last two games; "was" is his earlier average among the same players), Season (points a game, and his rank
            among players with 4+ games), Top-12 weeks, then his season's range with his average and his last game marked on it. Ranks
            count the players on the page (the first player without a page is 72nd at his position)
  rates     STATS built by _rt(): yards per attempt, completion rate, yards per carry, yards per target, catch rate. One point for each
            game with dmin or more chances; an average over games is total over total (the page script weights each game by its chances)
  points    nflverse fantasy_points_ppr (full PPR) - the number in the player page's game log
  context   injweeks.py (the detection the usage page and the projections use) says which games were shaped by an injury. A player's
            panel says so in words when it bears on his arrow: a game of his window in which he was hurt and played less, a game of his
            window in which he played more snaps than usual with a teammate hurt or out who is not ruled out this week (his tile also
            wears a NOTE tag; the note ends with what is known about the teammate: questionable, has played since, or not ruled out), and
            an earlier game in which he was hurt. Each note says what happened to his snaps and why - no forecast. A riser stays a riser;
            the reader gets the reason.

One tile, two renderers: the lists are written here (so the page shows before any script runs) and the search results are written in the
browser. Both fill the same TILE template from the same per-player fields, so a searched player's tile is the tile he has in a list.
The site zooms every page 1.1x on a phone (build_site.py BIGGER_CSS), so a 390px screen is about 333px of layout here: the tile and
stat-tile minimum widths are set for two columns at that width - check tests/stocks_page.py before changing them.
Nothing here changes a projection. Run after build_players.py (it links to the player pages through out/players/slugs.json).
Prints "wrote out/stocks.html: N risers (QB a, RB b, WR c, TE d), M players in the search, week W".
"""
import os, json, html, re
import plydata as PD

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
E = html.escape
S = PD.load(HERE); W = S.week
_ns = {"HERE": HERE, "E": E}; exec(open(os.path.join(HERE, "brand.py")).read(), _ns); NAMES, TEAMCOL, _lum = _ns["NAMES"], _ns["TEAMCOL"], _ns["lum"]
try: SLUG = json.load(open(os.path.join(OUT, "players", "slugs.json")))
except Exception: SLUG = {}
PAGES = set(SLUG.values())
try:
    import injweeks as IW
    INJ = IW.load(os.path.join(HERE, "in"), W)
except Exception as _e:
    print("note: injury context not loaded:", _e); INJ = None

TOP = 8                                                  # risers listed per position
FLOOR = {"QB": 12.0, "RB": 8.0, "WR": 8.0, "TE": 6.0}    # fantasy points a game over the window a riser must reach
MIN_UP = 1.0                                             # ... and the least he must be up on his earlier games
POSN = (("QB", "Quarterbacks", "quarterback"), ("RB", "Running backs", "running back"), ("WR", "Wide receivers", "wide receiver"), ("TE", "Tight ends", "tight end"))
PNAME = {a: c for a, b, c in POSN}

# one row per game, in this column order (the page reads a game as an array)
COLS = ["w", "opp", "ppr", "snap", "tgt", "rec", "recy", "car", "rush", "td", "pass", "att", "cmp", "ptd", "int", "ts", "cs", "fr"]
# "fr" (11/22): where that game finished among every player at his position that week (1 = the most fantasy points; level scores share a
# place), None for a week still being played. See finish().
# the stats a player's panel offers: id, column, label, the words after a number ("112 rushing yards"), decimals of one game's value,
# pct (the column is a share, 0-100), inv (up is bad), flat (a change smaller than this is not called up or down), min (the season total
# below which the stat is not offered - a receiver with one 3-yard carry gets no rushing graph)
def _st(i, col, lab, unit, dec=0, pct=False, inv=False, flat=0.5, mn=0.0001):
    return {"id": i, "col": col, "l": lab, "u": unit, "dec": dec, "pct": pct, "inv": inv, "flat": flat, "min": mn}
# a rate (owner 11/22 11:42 AM: "Added stats?"): num / den, one point for each game in which he had dmin or more chances (a 1-carry game
# is not a yards-per-carry reading). An average over several games is the total over the total - 58 yards on 12 carries and 40 on 20 is
# 3.1 a carry, not the 3.4 the two games average to. "dn" names the chances in words. Offered when three or more games qualify.
def _rt(i, num, den, lab, unit, dn, dmin, dec=1, pct=False, flat=0.3):
    return {"id": i, "num": num, "den": den, "dn": dn, "dmin": dmin, "l": lab, "u": unit, "dec": (0 if pct else dec), "pct": pct, "inv": False, "flat": flat, "min": 0}
STATS = [_st("ppr", "ppr", "Fantasy points", "fantasy points", dec=1, mn=-999),
         _st("pass", "pass", "Passing yards", "passing yards", flat=3), _st("ptd", "ptd", "Passing TDs", "passing TDs", flat=0.15),
         _st("cmp", "cmp", "Completions", "completions"), _st("att", "att", "Pass attempts", "pass attempts"),
         _st("int", "int", "Interceptions", "interceptions", inv=True, flat=0.15),
         _st("car", "car", "Carries", "carries"), _st("rush", "rush", "Rushing yards", "rushing yards", flat=3),
         _st("qtd", "td", "Rushing TDs", "rushing TDs", flat=0.15),
         _st("tgt", "tgt", "Targets", "targets"), _st("rec", "rec", "Catches", "catches"), _st("recy", "recy", "Receiving yards", "receiving yards", flat=3),
         _st("td", "td", "Touchdowns", "touchdowns", flat=0.15),
         _st("wrush", "rush", "Rushing yards", "rushing yards", flat=3, mn=20),
         _st("snap", "snap", "Snap share", "of the snaps", pct=True, flat=2), _st("ts", "ts", "Target share", "of the targets", pct=True, flat=2),
         _st("cs", "cs", "Carry share", "of the carries", pct=True, flat=2),
         _rt("ypa", "pass", "att", "Yards per attempt", "yards per attempt", "pass attempts", 10),
         _rt("cpct", "cmp", "att", "Completion rate", "of his passes completed", "pass attempts", 10, pct=True, flat=2),
         _rt("ypc", "rush", "car", "Yards per carry", "yards per carry", "carries", 5),
         _rt("ypt", "recy", "tgt", "Yards per target", "yards per target", "targets", 3, flat=0.5),
         _rt("crate", "rec", "tgt", "Catch rate", "of his targets caught", "targets", 3, pct=True, flat=3)]
ORDER = {"QB": ["ppr", "pass", "ptd", "cmp", "att", "ypa", "cpct", "int", "rush", "car", "qtd"],
         "RB": ["ppr", "car", "rush", "ypc", "td", "tgt", "rec", "recy", "snap", "cs", "ts"],
         "WR": ["ppr", "tgt", "rec", "recy", "ypt", "crate", "td", "snap", "ts", "wrush"],
         "TE": ["ppr", "tgt", "rec", "recy", "ypt", "crate", "td", "snap", "ts", "wrush"]}

# ---------------------------------------------------------------------------------------------------------------- the tile
# Filled by fill() here and by fill() in the page script - same template, same fields. Player, team, then the graph (the owner's order).
TILE = ('<li class="sk {dir}" data-k="{k}" data-pos="{pos}"><button type="button" class="skb" aria-expanded="false" aria-label="{aria}">'
        '<b class="sknm">{n}</b>'
        '<span class="sktm {tg}"><i class="sktb" style="--p:{c1};--s:{c2};--i:{ink}">{t}</i><span class="sksu">{pos}<span> · {tn}</span></span><i class="skst {stc}">{st}</i></span>'
        '<svg class="sksp" viewBox="0 0 120 40" aria-hidden="true" focusable="false"><path class="ska" d="{pa}"/><path class="skr" d="{pr}"/><circle cx="{ex}" cy="{ey}" r="3.5"/></svg>'
        '<span class="skpx"><span class="skv"><b>{val}</b><small>{lab}</small></span><em>{dt}</em></span>'
        '</button></li>')
def _esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
def fill(f):   # one pass, like the page script's fill(): a placeholder with no field is left empty
    return re.sub(r"\{(\w+)\}", lambda m: _esc("" if f.get(m.group(1)) is None else f[m.group(1)]), TILE)

def window(n): return 3 if n >= 6 else (2 if n >= 4 else 0)
def mean(v): return sum(v) / len(v)
def _g(x): return f"{round(x, 1):g}"
def spark(vals, k):
    """the tile graph: every game left to right on a zero-based scale, in a 120 x 40 box; the last k games again as their own path"""
    n = len(vals); lo = min(0.0, min(vals)); hi = max(vals)
    if hi - lo < 1e-9: hi = lo + 1.0
    pts = [((60.0 if n == 1 else 4 + 112.0 * i / (n - 1)), 5 + 30.0 * (1 - (v - lo) / (hi - lo))) for i, v in enumerate(vals)]
    path = lambda ps: ("M" + "L".join(f"{_g(x)} {_g(y)}" for x, y in ps)) if len(ps) > 1 else ""
    return path(pts), (path(pts[-k:]) if k else ""), _g(pts[-1][0]), _g(pts[-1][1])
def delta_text(d, flat=0.5):
    if d is None: return ""
    if abs(d) < flat: return ("" if f"{abs(d):.1f}" == "0.0" else ("+" if d >= 0 else "−")) + f"{abs(d):.1f}"   # a change that rounds to 0.0 wears no sign
    return ("▲ " if d > 0 else "▼ ") + f"{abs(d):.1f}"

def games_of(p): return sorted(p["games"] + p.get("prev_games", []), key=lambda g: g["w"])
# ---- weekly finishes (11/22): every player's score that week at each position, players without a page included (a back with no page had
# the 13th-best running back score of Week 9), a traded player's old-team entry left out (his games ride on his current entry). Only weeks
# before the site's week: a week still being played has no finishing order yet.
_FIN = {}
for _fp in S.players.values():
    if _fp.get("old"): continue
    for _fg in games_of(_fp):
        if _fg["w"] < W: _FIN.setdefault((_fp["pos"], _fg["w"]), []).append(round(_fg["ppr"], 1))
def finish(pos, g):
    """1 = the most fantasy points at his position that week; players level on points share the place. None for a week not finished."""
    v = _FIN.get((pos, g["w"]))
    return None if v is None else 1 + sum(1 for x in v if x > round(g["ppr"], 1))
def _wks(ws): ws = [f"Week {w}" for w in ws]; return ws[0] if len(ws) == 1 else (", ".join(ws[:-1]) + " and " + ws[-1])
def _hurt(why):   # "played hurt (Shoulder, Questionable that week) - 57% of snaps ..." -> "shoulder"
    m = re.search(r"\(([A-Za-z][A-Za-z /]*?)(?:,| on the next|\))", why or ""); return m.group(1).strip().lower() if m else ""
def _label(why):   # what a limited week is called in its note: the injury on the report, or that he left the game
    why = str(why or "")
    if why.startswith("left that game"): return "left the game"
    return _hurt(why) or "hurt"
def _wkl(lim, ws):   # "Week 7 and Week 8 (shoulder)" when the weeks share a reason, "Week 5 (ankle), Week 6 (ankle) and Week 7 (illness)" when not
    labs = [_label(lim[w]) for w in ws]
    if len(set(labs)) == 1: return f"{_wks(ws)} ({labs[0]})"
    parts = [f"Week {w} ({l})" for w, l in zip(ws, labs)]
    return ", ".join(parts[:-1]) + " and " + parts[-1]
_BY = {}
def _mate_now(mate, team, after):
    """what is known about the teammate now, in the page's own terms: his status this week as plydata gives it (the status his own
    tile wears), else whether he has played a game since the week in question. None = he is Out / Doubtful, so nobody is back."""
    if not _BY:
        for q in S.players.values():
            if not q.get("old"): _BY[(IW.norm(q["name"]), q["team"])] = q
    q = _BY.get((IW.norm(mate), team)); st = ((q or {}).get("status") or ("",))[0]
    if st in ("Out", "Doubtful"): return None
    if st == "Questionable": return "is questionable this week"
    try: since = any(w > after for w in INJ.snap.get((IW.norm(mate), IW._t(team)), {}))
    except Exception: since = False
    return "has played since" if since else "is not ruled out this week"
def context(p, gs, kw):
    """the injury notes for a player's panel, and whether a game of his window came with a teammate hurt or out who is back.
    Each note states what injweeks measured (snap share against his own norm, with an injury on the report) - no forecast, and nothing
    about his points: a fill-in week with more snaps can still be a 2-point game.  One sentence per teammate (Elic Ayomanor's last three
    games came with Ridley out, then Tate out twice).  injweeks calls a teammate "back" when this week's report has him as anything but
    Out / Doubtful, or he is off the report and played the team's latest game - so the note ends with what is actually known about him
    (_mate_now), never "he is back": Carnell Tate was out in Week 10, the team's latest game, and is questionable for Week 11."""
    if not INJ or not kw: return [], False
    win = {g["w"] for g in gs[-kw:]}; early = {g["w"] for g in gs[:-kw]}; notes = []; flag = False
    try: fil = INJ.fill(p["name"], p["team"], p["pos"]); lim = INJ.limited(p["name"], p["team"])
    except Exception: return [], False
    fw = sorted(w for w in fil if w in win); by = {}
    for w in fw: by.setdefault(fil[w][0], []).append(w)
    for mate, ws in sorted(by.items(), key=lambda kv: kv[1][0]):
        now = _mate_now(mate, p["team"], ws[-1])
        if not now: continue
        kinds = {("out" if str(fil[w][1]).startswith("out") else "hurt") for w in ws}
        was = "out" if kinds == {"out"} else ("hurt" if kinds == {"hurt"} else "hurt or out")
        last = mate.split()[-1]
        if last.lower().rstrip(".") in ("jr", "sr", "ii", "iii", "iv", "v"): last = mate
        notes.append(f"He played more snaps than usual in {_wks(ws)}, with {mate} {was}. {last} {now}."); flag = True
    lw = sorted(w for w in lim if w in win)
    if lw: notes.append(f"He played less than usual in {_wkl(lim, lw)}.")
    ew = sorted(w for w in lim if w in early)
    if ew: notes.append(f"His earlier games include {_wkl(lim, ew)}, when he played less than usual.")
    return notes, flag
def row(g, pos):
    i = lambda x: int(round(x or 0))
    return [g["w"], g["opp"], round(g["ppr"], 1), (None if g.get("snap") is None else int(round(g["snap"] * 100))), i(g["tgt"]), i(g["rec"]), i(g["recy"]), i(g["car"]), i(g["rush"]),
            i(g["td"]), i(g["pass"]), i(g["att"]), i(g["cmp"]), i(g["ptd"]), i(g["int"]), int(round((g.get("ts") or 0) * 100)), int(round((g.get("cs") or 0) * 100)), finish(pos, g)]
def colors(t):
    p, s = TEAMCOL.get(t, ("#2b3442", "#141a24")); return [p, s, "#101820" if _lum(p) > 0.45 else "#ffffff"]

# ---- this week: the game, and the model's projection (out/startsit.json - the Start / Sit page's own numbers, full PPR) ----
def _nk(name):
    try: return IW.norm(name)
    except Exception: return str(name).lower()
try: _SS = {(_nk(x["n"]), x["t"]): x for x in json.load(open(os.path.join(OUT, "startsit.json")))["players"]}
except Exception as _e: print("note: this week's projections not loaded:", _e); _SS = {}
def _ord(n): n = int(n); return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
PLUR = {"QB": "quarterbacks", "RB": "running backs", "WR": "wide receivers", "TE": "tight ends"}
def this_week(p, gs, st):
    """one or two plain sentences on his game this week, or [] when there is nothing certain to say. The projection is the Start / Sit
    page's number for him (build_team's full-PPR model points) - not a second model."""
    g = S.game_of(p["team"])
    if not g: return [f"The {NAMES.get(p['team'], p['team'])} are off this week."]
    opp = g["b"] if g["a"] == p["team"] else g["a"]; on = NAMES.get(opp, opp)
    if g.get("fin"): return [f"His Week {W} game is played ({g['fin']}); it is the last point on his graph." if gs and gs[-1]["w"] == W else f"His team's Week {W} game is played ({g['fin']})."]
    where = "Away at" if g.get("away") == p["team"] else ("Home against" if g.get("home") == p["team"] else "Against")
    out = [f"{where} the {on}, {g.get('kick') or 'time to come'}."]
    if st in ("Out", "Doubtful"): out[0] += f" He is listed {st.lower()}."; return out
    x = _SS.get((_nk(p["name"]), p["team"]))
    if x and x.get("act") and isinstance(x.get("fp"), (int, float)) and x["fp"] > 0:
        out.append(f"The model projects {x['fp']:.1f} fantasy points." + (f" The {on} are {_ord(x['dr'])} in yards allowed to {PLUR[p['pos']]} (1st allows the most)." if x.get("dr") else ""))
    return out
def what_moved(pos, gs, kw, d):
    """what is behind the arrow, as arithmetic on the same games: his chances (touches, targets or attempts) before and now, and how much
    of the change in fantasy points is touchdowns. Uses the whole-number stats the page ships, so the test redoes every sentence."""
    if not kw or d is None: return []
    R, B = gs[-kw:], gs[:-kw]; av = lambda rows, f: sum(f(g) for g in rows) / len(rows)
    i = lambda x: int(round(x or 0))
    if pos == "QB": lab, f = "Pass attempts", (lambda g: i(g["att"]))
    elif pos == "RB": lab, f = "Carries plus targets", (lambda g: i(g["car"]) + i(g["tgt"]))
    else: lab, f = "Targets", (lambda g: i(g["tgt"]))
    r, b = av(R, f), av(B, f); out = []
    out.append(f"{lab}: {r:.1f} a game over his last {kw}, " + (f"level with before ({b:.1f})." if abs(r - b) < 1.0 else f"{'up' if r > b else 'down'} from {b:.1f}."))
    tdp = (lambda g: 4 * i(g["ptd"]) + 6 * i(g["td"])) if pos == "QB" else (lambda g: 6 * i(g["td"]))
    x = av(R, tdp) - av(B, tdp)
    if abs(d) >= 2.0 and abs(x) >= 1.0 and (x > 0) == (d > 0):
        word = "rise" if d > 0 else "drop"
        out.append(f"Touchdowns are all of the {abs(d):.1f}-point {word}; the rest of his scoring is level or going the other way." if abs(x) > abs(d) + 0.05 else f"Touchdowns are {abs(x):.1f} of the {abs(d):.1f}-point {word}.")
    return out

PL = []; TC = {}
for key, p in S.players.items():
    if p.get("old"): continue                      # a traded player's entry for the team he left: his games ride on his current entry
    if SLUG and p["slug"] not in PAGES: continue   # no player page = no real role this season
    gs = games_of(p)
    if not gs: continue
    vals = [round(g["ppr"], 1) for g in gs]; n = len(vals); kw = window(n)   # the rounded numbers the page shows: anyone can redo the sums from his graph
    if kw:
        r = mean(vals[-kw:]); b = mean(vals[:-kw]); d = r - b; beat = sum(1 for v in vals[-kw:] if v > b); under = sum(1 for v in vals[-kw:] if v < b)
    else:
        r = mean(vals); b = d = None; beat = under = 0
    tw = S.team_weeks.get(p["team"], [])
    active = bool(tw) and gs[-1]["w"] >= (tw[-2] if len(tw) > 1 else tw[-1])
    st = (p.get("status") or ("",))[0]; st = st if st in ("Out", "Doubtful", "Questionable") else ""
    pos, team = p["pos"], p["team"]; TC.setdefault(team, colors(team))
    rising = bool(kw and d >= MIN_UP and r >= FLOOR[pos] and beat >= 2 and active and st not in ("Out", "Doubtful"))
    falling = bool(kw and d <= -MIN_UP and b >= FLOOR[pos] and under >= 2 and active and st not in ("Out", "Doubtful"))   # the mirror: he WAS at the floor, is down, and two of the games were under his old average
    dr = "na" if d is None else ("fl" if abs(d) < 0.5 else ("up" if d > 0 else "dn"))
    pa, pr, ex, ey = spark(vals, kw)
    tn = NAMES.get(team, team)
    notes, fillin = context(p, gs, kw)
    tag = {"Out": "OUT", "Doubtful": "D", "Questionable": "Q"}.get(st, "") or ("NOTE" if fillin else "")   # NOTE: a recent game of his came with a teammate hurt or out who is not ruled out this week
    if kw:
        how = "about level with" if dr == "fl" else (f"up {abs(d):.1f} from" if d > 0 else f"down {abs(d):.1f} from")
        aria = f"{p['name']}, {PNAME[pos]}, {tn}. {r:.1f} fantasy points a game over his last {kw} games, {how} his earlier games."
    else:
        aria = f"{p['name']}, {PNAME[pos]}, {tn}. {r:.1f} fantasy points a game in {n} game{'s' if n != 1 else ''}."
    if st: aria += f" {st} this week."
    if fillin: aria += " There is a note on his recent games."
    aria += " Open his stats."
    PL.append({"k": p["slug"], "n": p["name"], "t": team, "tn": tn, "p": pos, "st": st, "pg": 1 if p["slug"] in PAGES else 0, "ac": 1 if active else 0, "kw": kw, "nt": notes, "fi": 1 if fillin else 0,
               "r": round(r, 2), "d": (None if d is None else round(d, 2)), "up": rising, "dn": falling, "mv": what_moved(pos, gs, kw, (None if d is None else round(d, 1))), "wk": this_week(p, gs, st),
               "f": {"dir": dr, "aria": aria, "tg": ("tg" if tag else ""), "st": tag, "stc": ("o" if st in ("Out", "Doubtful") else ""),
                     "val": f"{r:.1f}", "lab": (f"last {kw}" if kw else (f"{n} games" if n != 1 else "1 game")), "dt": delta_text(d), "pa": pa, "pr": pr, "ex": ex, "ey": ey},
               "g": [row(g, pos) for g in gs]})
PL.sort(key=lambda x: (-x["r"], x["n"]))
def fields(x):
    c = TC[x["t"]]; f = {"k": x["k"], "pos": x["p"], "t": x["t"], "tn": x["tn"], "n": x["n"], "c1": c[0], "c2": c[1], "ink": c[2]}; f.update(x["f"]); return f
ALLR = {pos: sorted([x for x in PL if x["p"] == pos and x["up"]], key=lambda x: (-x["d"], x["n"])) for pos, _, _ in POSN}   # everyone the rule passes, biggest rise first
RISE = {pos: ALLR[pos][:TOP] for pos, _, _ in POSN}    # the tiles written into the page
MORE = {pos: ALLR[pos][TOP:] for pos, _, _ in POSN}    # the rest: one tap ("Show all 19 rising running backs") adds them under the list
ALLF = {pos: sorted([x for x in PL if x["p"] == pos and x["dn"]], key=lambda x: (x["d"], x["n"])) for pos, _, _ in POSN}    # biggest drop first
FALL = {pos: ALLF[pos][:TOP] for pos, _, _ in POSN}; FMORE = {pos: ALLF[pos][TOP:] for pos, _, _ in POSN}
for x in PL: x["up"] = 1 if x["up"] else 0; x["dn"] = 1 if x["dn"] else 0

# ---- market movers (owner 11/22 11:42 AM: "Anything else you can do to the stock market page to make it a little more interesting? Added
# stats?"): a row of headline cards above the lists. Each is one count or average from the game logs the page ships, so the test redoes
# every card (tests/stocks_page.py). Only players who could be on a list are in the running: played one of their team's last two games,
# not ruled out or doubtful. A card nobody qualifies for is left out; one player can lead more than one card.
CI = {c: i for i, c in enumerate(COLS)}
BYK = {x["k"]: x for x in PL}
def _pts(x): return [g[CI["ppr"]] for g in x["g"]]
def _fins(x): return [g[CI["fr"]] for g in x["g"] if g[CI["fr"]] is not None]
def _run12(x):
    """his latest finished games in a row among the top 12 at his position"""
    n = 0
    for f in reversed(_fins(x)):
        if f > 12: break
        n += 1
    return n
def _climb(x):
    """how many games running he has scored more than in the game before"""
    v = _pts(x); n = 0
    for i in range(len(v) - 1, 0, -1):
        if v[i] <= v[i - 1]: break
        n += 1
    return n
def movers():
    live = [x for x in PL if x["ac"] and x["st"] not in ("Out", "Doubtful")]; out = []
    def add(i, lab, x, val, sub, say, tone=""): out.append({"id": i, "l": lab, "k": x["k"], "v": val, "s": sub, "say": say, "tone": tone})
    c = sorted([x for x in live if x["up"]], key=lambda x: (-x["d"], x["n"]))
    if c: add("rise", "Biggest riser", c[0], c[0]["f"]["dt"], "a game", f"Up {abs(c[0]['d']):.1f} fantasy points a game on his earlier games", "tu")
    c = sorted([x for x in live if x["dn"]], key=lambda x: (x["d"], x["n"]))
    if c: add("fall", "Biggest faller", c[0], c[0]["f"]["dt"], "a game", f"Down {abs(c[0]['d']):.1f} fantasy points a game on his earlier games", "td")
    # a breakout: on a Rising list, and his earlier games averaged under the floor a riser has to reach (he was not a starter before)
    c = []
    for x in live:
        if not x["up"]: continue
        v = _pts(x); b = mean(v[:-x["kw"]]); r = mean(v[-x["kw"]:])
        if b < FLOOR[x["p"]]: c.append((-x["d"], x["n"], x, r, b))
    if c: _, _, x, r, b = sorted(c, key=lambda t: t[:2])[0]; add("break", "Breakout", x, f"{r:.1f}", f"a game, from {b:.1f}", f"{r:.1f} fantasy points a game over his last {x['kw']}, from {b:.1f} before")
    # a season high: his latest game is his best of four or more, on its own
    c = sorted([x for x in live if len(x["g"]) >= 4 and _pts(x)[-1] == max(_pts(x)) and _pts(x).count(max(_pts(x))) == 1], key=lambda x: (-_pts(x)[-1], x["n"]))
    if c: add("high", "Season high", c[0], f"{_pts(c[0])[-1]:.1f}", f"in Week {c[0]['g'][-1][0]}", f"{_pts(c[0])[-1]:.1f} fantasy points in Week {c[0]['g'][-1][0]}, his best game of the season")
    c = sorted([x for x in live if _run12(x) >= 2], key=lambda x: (-_run12(x), -x["r"], x["n"]))
    if c: add("run", "Top-12 streak", c[0], f"{_run12(c[0])} straight", "top-12 weeks", f"Among the top 12 {PLUR[c[0]['p']]} in each of his last {_run12(c[0])} games")
    c = sorted([x for x in live if sum(1 for f in _fins(x) if f <= 12) >= 1], key=lambda x: (-sum(1 for f in _fins(x) if f <= 12), len(_fins(x)), -mean(_pts(x)), x["n"]))
    if c: t = sum(1 for f in _fins(c[0]) if f <= 12); add("most", "Most top-12 weeks", c[0], f"{t} of {len(_fins(c[0]))}", "top-12 weeks", f"Among the top 12 {PLUR[c[0]['p']]} in {t} of his {len(_fins(c[0]))} games")
    # the highest floor: a regular starter (six or more games, averaging the floor) whose worst game is the best worst game
    c = sorted([x for x in live if len(x["g"]) >= 6 and mean(_pts(x)) >= FLOOR[x["p"]]], key=lambda x: (-min(_pts(x)), -mean(_pts(x)), x["n"]))
    if c: add("floor", "Highest floor", c[0], f"{min(_pts(c[0])):.1f}", "his worst game", f"His worst game of {len(c[0]['g'])} is {min(_pts(c[0])):.1f} fantasy points")
    c = sorted([x for x in live if _climb(x) >= 3 and _pts(x)[-1] >= FLOOR[x["p"]]], key=lambda x: (-_climb(x), -_pts(x)[-1], x["n"]))
    if c: add("climb", "On the climb", c[0], f"{_climb(c[0])} straight", "games, each better", f"{_climb(c[0])} games running, each better than the one before")
    return out
MK = movers()
def mover_html(c):
    x = BYK[c["k"]]; col = TC[x["t"]]; f = x["f"]
    aria = f"{c['l']}: {x['n']}, {PNAME[x['p']]}, {x['tn']}. {c['say']}. Open his stats."
    return (f'<li><button type="button" class="skmc {c["tone"]} {f["dir"]}" data-k="{E(x["k"])}" data-m="{c["id"]}" aria-label="{E(aria)}"><span class="skmt">{E(c["l"])}</span><b class="skmn">{E(x["n"])}</b>'
            f'<span class="skmw"><i class="sktb" style="--p:{col[0]};--s:{col[1]};--i:{col[2]}">{E(x["t"])}</i><span>{x["p"]}</span>'
            f'<svg class="sksp" viewBox="0 0 120 40" aria-hidden="true" focusable="false"><path class="ska" d="{f["pa"]}"/><path class="skr" d="{f["pr"]}"/></svg></span>'
            f'<span class="skmx"><b>{E(c["v"])}</b><small>{E(c["s"])}</small></span></button></li>')

# how far the games go: "through Week 10" or "through Week 10, plus the Week 11 game already played (HOU, IND)"
_wk = {}
for t, ws in S.team_weeks.items():
    for w in ws: _wk.setdefault(w, set()).add(t)
_last = max(_wk) if _wk else 0
if _last and len(_wk[_last]) < 20 and (_last - 1) in _wk:
    _tm = sorted(_wk[_last]); THRU = f"Games through Week {_last - 1}, plus the Week {_last} game{'s' if len(_tm) > 2 else ''} already played ({', '.join(_tm)})"
else:
    THRU = f"Games through Week {_last}"

CSS = """
.skm{max-width:1100px;margin:14px auto 40px;padding:0 6px;--skc:#0f141c}
/* the tag's ink: the site's amber is light on the dark theme (dark ink, 10:1) and dark on the light theme (white ink, 4.7:1; dark ink there is 3.9:1) */
@media (prefers-color-scheme: light){ :root:not([data-theme="dark"]) .skm{--skc:#fff} }
:root[data-theme="light"] .skm{--skc:#fff}
@media (max-width:760px){ .skm .sktm.tg .sksu span{display:none} }
.skm [hidden]{display:none !important}
.skm .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.skm .skhd{margin:0 2px 10px} .skm h1{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:40px;letter-spacing:-.02em;line-height:1}
.skm .sksub{display:block;margin-top:6px;color:var(--mute);font-size:14px;line-height:1.45;max-width:700px}
.skm .skfind{margin:0 0 8px} .skm .skfind input{display:block;width:100%;max-width:520px;box-sizing:border-box;font:inherit;font-size:16px;min-height:44px;padding:8px 12px;border:1.5px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}
.skm .skfind input:focus{outline:none;border-color:var(--red);box-shadow:0 0 0 3px color-mix(in srgb,var(--red) 22%,transparent)}
/* Rising / Falling: one switch for the whole page; the list that is not picked is not shown */
.skm .skmode{display:inline-flex;margin:0 0 10px;border:1.5px solid var(--line);border-radius:999px;padding:3px;gap:3px;background:var(--card)}
.skm .skmode button{font:inherit;font-family:var(--display);font-weight:700;font-size:14.5px;letter-spacing:.04em;min-height:38px;min-width:96px;padding:0 18px;border:0;border-radius:999px;background:none;color:var(--mute);cursor:pointer}
.skm .skmode button[aria-pressed="true"]{background:var(--ink);color:var(--bg)} .skm .skmode button:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.skm[data-mode="rise"] [data-for="fall"],.skm[data-mode="fall"] [data-for="rise"]{display:none}
.skm[data-mode="fall"] .skkey i.k2{border-top-color:var(--bad)}
.skm .skbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;margin:0 0 2px}
.skm .skj{display:flex;gap:6px} .skm .skj a{display:inline-flex;align-items:center;justify-content:center;min-width:46px;min-height:40px;box-sizing:border-box;padding:0 10px;border:1.5px solid var(--line);border-radius:999px;font-family:var(--display);font-weight:700;font-size:14px;letter-spacing:.05em;color:var(--ink);text-decoration:none}
.skm .skj a:hover{border-color:var(--mute)}
.skm .skkey{display:flex;flex-wrap:wrap;gap:2px 14px;margin:0 2px;color:var(--mute);font-size:12.5px;line-height:1.4} .skm .skkey span{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.skm .skkey i{display:inline-block;width:18px;height:0;border-top:1.5px solid var(--mute);opacity:.8} .skm .skkey i.k2{border-top:3px solid var(--good);opacity:1;border-radius:2px}
.skm .sksec{margin:0 0 6px;scroll-margin-top:60px}
.skm h2{margin:16px 2px 9px;font-family:var(--display);font-weight:700;font-size:22px;line-height:1.15;color:var(--ink);display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.skm h2 small{font-family:var(--body);font-weight:500;font-size:13.5px;color:var(--mute)}
.skm .skg{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(146px,1fr));gap:8px}
.skm .sk{min-width:0;display:flex}
.skm .skb{flex:1;min-width:0;box-sizing:border-box;display:flex;flex-direction:column;align-items:stretch;text-align:left;font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 10px 9px;cursor:pointer;-webkit-tap-highlight-color:transparent}
.skm .skb:hover{border-color:var(--mute)} .skm .skb:focus-visible,.skm .skt:focus-visible,.skm .skx:focus-visible,.skm .skj a:focus-visible,.skm .skpl a:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.skm .skb[aria-expanded="true"]{border-color:var(--ink);box-shadow:inset 0 -3px 0 var(--ink)}
/* a long name takes a second line instead of losing its end ("Jacory Croskey-Merr…" on a 390px phone); two lines is the cap */
.skm .sknm{font-weight:600;font-size:14.5px;line-height:1.25;overflow:hidden;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.skm .sktm{display:flex;align-items:center;gap:6px;min-width:0;margin-top:3px;color:var(--mute);font-size:12px;line-height:1.2} .skm .sksu{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.skm .sktb{flex:none;font-style:normal;display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:17px;padding:0 4px;box-sizing:border-box;border-radius:4px;background:var(--p,#333);box-shadow:inset 0 -3px 0 var(--s,#000);color:var(--i,#fff);font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.03em;line-height:1}
.skm .skst{flex:none;font-style:normal;font-weight:800;font-size:10px;letter-spacing:.05em;padding:1px 5px;border-radius:3px;background:var(--warn);color:var(--skc)} .skm .skst.o{background:var(--red);color:#fff} .skm .skst:empty{display:none}
.skm .sksp{display:block;width:100%;height:auto;margin:8px 0 6px;overflow:visible}
.skm .sksp path{fill:none;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}
.skm .ska{stroke:var(--mute);stroke-width:1.5;opacity:.7} .skm .skr{stroke:var(--mute);stroke-width:3}
.skm .sksp circle{fill:var(--mute);stroke:var(--card);stroke-width:2;vector-effect:non-scaling-stroke}
.skm .up .skr{stroke:var(--good)} .skm .up .sksp circle{fill:var(--good)} .skm .dn .skr{stroke:var(--bad)} .skm .dn .sksp circle{fill:var(--bad)}
.skm .skpx{display:flex;align-items:baseline;justify-content:space-between;gap:6px;min-width:0;margin-top:auto}
.skm .skv{display:inline-flex;align-items:baseline;gap:5px;min-width:0} .skm .skv b{font-family:var(--display);font-weight:700;font-size:23px;line-height:1}
.skm .skv small{color:var(--mute);font-size:11.5px;white-space:nowrap}
.skm em{font-style:normal;font-weight:700;font-size:13px;color:var(--mute);white-space:nowrap} .skm .up em{color:var(--good)} .skm .dn em{color:var(--bad)}
.skm .sknone{color:var(--mute);font-size:14.5px;line-height:1.5;margin:6px 2px 14px}
.skm .skmr{margin:10px 0 0} .skm .skmore{display:inline-flex;align-items:center;min-height:42px;box-sizing:border-box;padding:0 16px;border:1.5px solid var(--line);border-radius:999px;background:transparent;color:var(--ink);font:inherit;font-weight:600;font-size:14px;cursor:pointer}
.skm .skmore:hover{border-color:var(--mute)} .skm .skmore:focus-visible{outline:2px solid var(--red);outline-offset:2px}
/* the open player: one panel under his row, full width */
.skm .skp{grid-column:1/-1;min-width:0;box-sizing:border-box;background:var(--card);border:1.5px solid var(--ink);border-radius:14px;padding:12px 10px 8px;scroll-margin-top:60px}
.skm .skph{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin:0 2px}
.skm .skph h3{margin:0;font-family:var(--display);font-weight:700;font-size:22px;line-height:1.1;color:var(--ink)} .skm .skph p{margin:2px 0 0;color:var(--mute);font-size:13px;line-height:1.35}
.skm .skx{flex:none;font:inherit;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.05em;text-transform:uppercase;min-height:40px;padding:0 12px;border-radius:8px;border:1.5px solid var(--line);background:transparent;color:var(--ink);cursor:pointer}
.skm .skx:hover{border-color:var(--mute)}
.skm .skpq{margin:8px 2px;font-size:13.5px;color:var(--mute);line-height:1.4}
.skm .skwn{margin:8px 2px 0;padding-left:10px;border-left:3px solid var(--warn);font-size:13.5px;line-height:1.4;color:var(--ink)}
/* what moved, and his game this week: two short fact blocks above the stats */
.skm .skfx{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;margin:10px 0 0} .skm .skfx div{border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:var(--bg);min-width:0}
.skm .skfx b{display:block;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.04em;color:var(--mute);margin-bottom:2px} .skm .skfx p{margin:0;font-size:13.5px;line-height:1.45;color:var(--ink)} .skm .skfx p + p{margin-top:3px}
.skm .skts{display:grid;grid-template-columns:repeat(auto-fill,minmax(136px,1fr));gap:8px}
.skm .skt{min-width:0;box-sizing:border-box;display:grid;grid-template-columns:minmax(0,1fr) 54px;gap:2px 6px;align-items:end;text-align:left;font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:8px 9px;min-height:62px;cursor:pointer;-webkit-tap-highlight-color:transparent}
.skm .skt:hover{border-color:var(--mute)} .skm .skt[aria-pressed="true"]{border-color:var(--ink);box-shadow:inset 0 -3px 0 var(--ink)}
.skm .sktl{grid-column:1/-1;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.03em;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.skm .skt[aria-pressed="true"] .sktl{color:var(--ink)}
.skm .sktv{display:flex;flex-direction:column;min-width:0} .skm .sktv b{font-family:var(--display);font-weight:700;font-size:21px;line-height:1.05} .skm .sktv em{font-size:12px}
.skm .skt .sksp{margin:0 0 3px} .skm .skt .sksp circle{stroke:none}
/* the graph of the picked stat: under that stat's row */
.skm .skcw{grid-column:1/-1;min-width:0;scroll-margin-top:60px}
.skm .skc{margin:0;padding:6px 0 8px}
.skm .skc figcaption{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin:0 2px 4px}
.skm .skct{font-family:var(--display);font-weight:700;font-size:20px;line-height:1.1;color:var(--ink)}
.skm .skrd{text-align:right;font-size:12.5px;line-height:1.3;color:var(--mute)} .skm .skrd b{display:block;font-family:var(--display);font-weight:700;font-size:26px;line-height:1;color:var(--ink)}
.skm .skplot{position:relative;border-radius:8px;touch-action:pan-y;-webkit-user-select:none;user-select:none;cursor:crosshair} .skm .skplot:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.skm .skplot svg{display:block;width:100%;height:auto;overflow:visible}
.skm .skplot text{font-family:var(--body);font-size:10.5px;fill:var(--mute);font-variant-numeric:tabular-nums}
.skm .skplot .gr{stroke:var(--line);stroke-width:1} .skm .skplot .wk{font-size:9.5px;opacity:.85}
.skm .skplot .ar{fill:var(--mute);opacity:.10} .skm .skplot .ar2{fill:var(--mute);opacity:.16}
.skm .skplot .ln{fill:none;stroke:var(--mute);stroke-width:2;stroke-linecap:round;stroke-linejoin:round} .skm .skplot .ln2{fill:none;stroke:var(--mute);stroke-width:3;stroke-linecap:round;stroke-linejoin:round}
.skm .skplot .av{stroke:var(--mute);stroke-width:1.5;stroke-dasharray:5 4;opacity:.9} .skm .skplot .av2{stroke:var(--mute);stroke-width:1.5;stroke-dasharray:5 4}
.skm .skplot .dt{fill:var(--mute);stroke:var(--card);stroke-width:2} .skm .skplot .dt2{fill:var(--mute);stroke:var(--card);stroke-width:2}
.skm .skc.up .ar2{fill:var(--good)} .skm .skc.up .ln2,.skm .skc.up .av2{stroke:var(--good)} .skm .skc.up .dt2{fill:var(--good)}
.skm .skc.dn .ar2{fill:var(--bad)} .skm .skc.dn .ln2,.skm .skc.dn .av2{stroke:var(--bad)} .skm .skc.dn .dt2{fill:var(--bad)}
.skm .skplot .cx{stroke:var(--ink);stroke-width:1;opacity:.55} .skm .skplot .sel{fill:none;stroke:var(--ink);stroke-width:2}
.skm .skplot .on{fill:var(--ink);font-weight:600}
.skm .skcc{margin:6px 2px 0;font-size:13.5px;line-height:1.45;color:var(--mute)} .skm .skcc b{color:var(--ink);font-weight:600} .skm .skcc span{display:inline-block;margin-right:14px}
.skm .skcc i{display:inline-block;width:16px;height:0;border-top:2px dashed var(--mute);vertical-align:middle;margin-right:6px} .skm .skc.up .skcc i.k2{border-top-color:var(--good)} .skm .skc.dn .skcc i.k2{border-top-color:var(--bad)}
.skm .sktbl{margin:4px 2px 0;font-size:13px} .skm .sktbl summary{cursor:pointer;color:var(--mute);min-height:40px;display:flex;align-items:center;list-style:none} .skm .sktbl summary::-webkit-details-marker{display:none}
.skm .sktbl summary::before{content:"";width:7px;height:7px;border-right:2px solid var(--mute);border-bottom:2px solid var(--mute);transform:rotate(-45deg);margin:0 10px 0 2px} .skm .sktbl[open] summary::before{transform:rotate(45deg)}
.skm .sktbl table{border-collapse:collapse;width:100%;max-width:360px;font-variant-numeric:tabular-nums} .skm .sktbl th,.skm .sktbl td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}
.skm .sktbl th:first-child,.skm .sktbl td:first-child,.skm .sktbl th:nth-child(2),.skm .sktbl td:nth-child(2){text-align:left} .skm .sktbl th{font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.05em;color:var(--mute)}
.skm .skpl{margin:8px 2px 0;font-size:14px} .skm .skpl a{color:var(--ink);display:inline-block;padding:9px 0}
.skm .skfoot{margin:22px 2px 0;color:var(--mute);font-size:12px;line-height:1.5;max-width:860px}
/* market movers (11/22): a row of headline cards above the lists - a swipe row on a phone, four to a row on a wide screen */
.skm .skmk{margin:0 0 10px} .skm .skml{list-style:none;margin:0 -6px;padding:2px 6px 6px;display:flex;gap:8px;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x proximity;scroll-padding:0 6px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.skm .skml::-webkit-scrollbar{display:none} .skm .skml li{flex:0 0 158px;min-width:0;display:flex;scroll-snap-align:start}
.skm .skmc{flex:1;min-width:0;box-sizing:border-box;display:flex;flex-direction:column;align-items:stretch;gap:2px;text-align:left;font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:12px;padding:9px 10px 8px;cursor:pointer;-webkit-tap-highlight-color:transparent}
.skm .skmc:hover{border-color:var(--mute)} .skm .skmc:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.skm .skmt{font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.04em;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.skm .skmn{font-weight:600;font-size:14px;line-height:1.2;overflow:hidden;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.skm .skmw{display:flex;align-items:center;gap:6px;min-width:0;color:var(--mute);font-size:12px;line-height:1.2} .skm .skmw .sksp{flex:none;width:60px;height:20px;margin:0 0 0 auto}
.skm .skmx{display:flex;flex-direction:column;gap:2px;min-width:0;margin-top:auto;padding-top:5px} .skm .skmx b{font-family:var(--display);font-weight:700;font-size:21px;line-height:1;white-space:nowrap}
.skm .skmx small{color:var(--mute);font-size:11.5px;line-height:1.2;white-space:nowrap} .skm .skmc.tu .skmx b{color:var(--good)} .skm .skmc.td .skmx b{color:var(--bad)}
/* the numbers at the top of a player's box: where he ranks, his top-12 weeks, and his season's range with his last game on it */
.skm .skqt{display:flex;gap:6px;margin:10px 0 0}
.skm .skqc{flex:1 1 0;min-width:0;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:10px;background:var(--bg);padding:7px 8px 6px}
.skm .skqc span{font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.03em;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.skm .skqc b{font-family:var(--display);font-weight:700;font-size:21px;line-height:1.15;color:var(--ink);white-space:nowrap} .skm .skqc small{font-size:11.5px;line-height:1.25;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.skm .skrg{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:4px 12px;margin:12px 2px 0}
.skm .skre{display:flex;flex-direction:column;line-height:1.15} .skm .skre.hi{text-align:right} .skm .skre b{font-family:var(--display);font-weight:700;font-size:17px;color:var(--ink)} .skm .skre small{font-size:11px;color:var(--mute);white-space:nowrap}
.skm .skrt{position:relative;height:6px;border-radius:3px;background:var(--line)} .skm .skrt i{position:absolute;top:50%;transform:translate(-50%,-50%)}
.skm .skrv{width:2px;height:16px;border-radius:1px;background:var(--mute)} .skm .skrx{width:12px;height:12px;box-sizing:border-box;border-radius:50%;background:var(--ink);box-shadow:0 0 0 2px var(--card)}
.skm .skrc{margin:6px 2px 0;font-size:13px;line-height:1.45;color:var(--mute)} .skm .skrc b{color:var(--ink);font-weight:600} .skm .skrc span{display:inline-block;margin-right:12px}
.skm .skrc i{display:inline-block;vertical-align:middle;margin-right:6px} .skm .skrc i.kx{width:10px;height:10px;border-radius:50%;background:var(--ink)} .skm .skrc i.kv{width:2px;height:13px;border-radius:1px;background:var(--mute);margin-left:4px;margin-right:10px}
@media (min-width:761px){ .skm{padding:0 12px} .skm .skg{grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
  .skm .skml{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;overflow:visible;margin:0;padding:0} .skm .skml li{flex:none} .skm .skqt{max-width:560px} .skm .skrg{max-width:556px} .skm .skp{padding:16px 16px 10px} .skm .skts{grid-template-columns:repeat(auto-fill,minmax(160px,1fr))}
  .skm .skb{padding:12px 12px 11px} .skm .sknm{font-size:15.5px} .skm .skcw{max-width:760px} }
@media (max-width:380px){ .skm h1{font-size:34px} }
@media (prefers-reduced-motion:no-preference){ .skm .skb,.skm .skt{transition:border-color .12s} }
"""

JS = r"""
(function(){
  var root = document.getElementById('skm'), D = window.__SK;
  if(!root || !D) return;
  var CI = {}, BY = {}, SD = {};
  D.cols.forEach(function(c, i){ CI[c] = i; });
  D.pl.forEach(function(p){ BY[p.k] = p; });
  D.stats.forEach(function(s){ SD[s.id] = s; });
  var q = document.getElementById('skq'), secs = document.getElementById('sksecs'), res = document.getElementById('skres'), mk = document.getElementById('skmk'),
      rl = document.getElementById('skrl'), rh = document.getElementById('skrh'), rn = document.getElementById('skrn');
  var cur = null, CAP = 24;
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function fields(p){
    var c = D.tc[p.t] || ['#2b3442', '#141a24', '#ffffff'], f = {k: p.k, pos: p.p, t: p.t, tn: p.tn, n: p.n, c1: c[0], c2: c[1], ink: c[2]}, x;
    for(x in p.f) f[x] = p.f[x];
    return f;
  }
  function fill(f){ return D.tpl.replace(/\{(\w+)\}/g, function(m, k){ return esc(f[k] == null ? '' : f[k]); }); }
  function avg(a){ var s = 0; for(var i = 0; i < a.length; i++) s += a[i]; return a.length ? s / a.length : 0; }
  function win(n){ return n >= 6 ? 3 : (n >= 4 ? 2 : 0); }
  function series(p, st){
    /* one point a game. A rate (st.den: yards per carry, catch rate) is that game's own rate, kept only when he had st.dmin or more
       chances in it; the chances ride along as the point's weight, so an average over several games is total over total */
    var c = CI[st.col], cn = CI[st.num], cd = CI[st.den], out = [], g, v, d;
    for(var i = 0; i < p.g.length; i++){
      g = p.g[i];
      if(st.den){ d = g[cd] || 0; if(d < st.dmin) continue; out.push({w: g[0], o: g[1], v: (g[cn] || 0) / d * (st.pct ? 100 : 1), wt: d}); continue; }
      v = g[c]; if(v == null) continue; out.push({w: g[0], o: g[1], v: v, wt: 1});
    }
    return out;
  }
  function wavg(s){ var a = 0, b = 0; for(var i = 0; i < s.length; i++){ a += s[i].v * s[i].wt; b += s[i].wt; } return b ? a / b : 0; }
  function trend(vals, s){
    /* s (the series itself) is passed for a rate: its averages are weighted by each game's chances */
    var n = vals.length, k = win(n), m = s ? function(a, b){ return wavg(s.slice(a, b)); } : function(a, b){ return avg(vals.slice(a, b)); };
    if(!k) return {k: 0, r: m(0, n), b: null, d: null};
    var r = m(n - k, n), b = m(0, n - k);
    return {k: k, r: r, b: b, d: r - b};
  }
  function tone(t, st){ return t.d == null ? 'na' : (Math.abs(t.d) < st.flat ? 'fl' : ((t.d > 0) !== !!st.inv ? 'up' : 'dn')); }
  function one(v, st){ return st.pct ? Math.round(v) + '%' : (st.dec ? v.toFixed(st.dec) : String(Math.round(v))); }
  function mid(v, st){ return st.pct ? Math.round(v) + '%' : v.toFixed(1); }
  function dtxt(d, st){
    if(d == null) return '';
    var a = Math.abs(d), s = st.pct ? Math.round(a) + '%' : a.toFixed(1);
    if(a < st.flat) return (/^0(\.0)?%?$/.test(s) ? '' : (d >= 0 ? '+' : '−')) + s;
    return (d > 0 ? '▲ ' : '▼ ') + s;
  }
  function r1(x){ return Math.round(x * 10) / 10; }
  function spark(vals, k){
    /* the same picture as the tile's graph (build_stocks.py spark), with a plain end dot sized for a small box */
    var n = vals.length, lo = Math.min(0, Math.min.apply(null, vals)), hi = Math.max.apply(null, vals);
    if(hi - lo < 1e-9) hi = lo + 1;
    var pts = vals.map(function(v, i){ return [r1(n === 1 ? 60 : 4 + 112 * i / (n - 1)), r1(5 + 30 * (1 - (v - lo) / (hi - lo)))]; });
    function path(ps){ return ps.length > 1 ? 'M' + ps.map(function(p){ return p[0] + ' ' + p[1]; }).join('L') : ''; }
    return '<svg class="sksp" viewBox="0 0 120 40" aria-hidden="true" focusable="false"><path class="ska" d="' + path(pts) + '"/><path class="skr" d="' + (k ? path(pts.slice(n - k)) : '') +
      '"/><circle cx="' + pts[n - 1][0] + '" cy="' + pts[n - 1][1] + '" r="5"/></svg>';
  }

  /* ---- a player's panel: his stats to pick from; the picked stat's graph opens under its row ---- */
  function statBtn(p, st){
    var s = series(p, st); if(!s.length) return '';
    var vals = s.map(function(x){ return x.v; }), tot = 0; vals.forEach(function(v){ tot += v; });
    if(st.den ? s.length < 3 : tot < st.min) return '';
    var t = trend(vals, st.den ? s : null), d = dtxt(t.d, st), say = st.l + ': ' + mid(t.r, st) + (t.k ? ' over his last ' + t.k + ' games' : (st.den ? ' this season' : ' a game'));
    return '<button type="button" class="skt ' + tone(t, st) + '" data-s="' + st.id + '" aria-pressed="false" aria-label="' + esc(say) + '. Graph it."><span class="sktl">' + esc(st.l) + '</span>' +
      '<span class="sktv"><b>' + mid(t.r, st) + '</b><em>' + (d || '&nbsp;') + '</em></span>' + spark(vals, t.k) + '</button>';
  }
  /* ---- the numbers at the top of a player's box (owner 11/22 11:42 AM: "Added stats?"): where he ranks at his position, his top-12
     weeks, and his season's range with his last game on it. Everything is counted from the games the page ships (tests/stocks_page.py
     redoes each number); the ranks count the players on this page. ---- */
  var RK = null;
  function ranks(){
    if(RK) return RK;
    RK = {};
    D.pl.forEach(function(p){
      var v = p.g.map(function(g){ return g[CI.ppr]; }), t = trend(v), o = RK[p.p] || (RK[p.p] = {now: [], was: [], sea: []});
      if(t.k && p.ac){ o.now.push(t.r); o.was.push(t.b); }
      if(v.length >= 4) o.sea.push(avg(v));
    });
    return RK;
  }
  function place(list, v){ var n = 1; for(var i = 0; i < list.length; i++) if(list[i] > v + 1e-9) n++; return n; }
  function quote(p){
    var v = p.g.map(function(g){ return g[CI.ppr]; }), n = v.length; if(!n) return '';
    var R = ranks()[p.p] || {now: [], was: [], sea: []}, t = trend(v), a = avg(v), cells = '', i, h = '';
    function cell(l, b, s){ return '<div class="skqc"><span>' + l + '</span><b>' + b + '</b><small>' + (s || '&nbsp;') + '</small></div>'; }
    if(t.k && p.ac) cells += cell('Rank now', esc(p.p) + place(R.now, t.r), 'was ' + esc(p.p) + place(R.was, t.b));
    cells += cell('Season', a.toFixed(1), 'a game' + (n >= 4 ? ' · ' + esc(p.p) + place(R.sea, a) : ''));
    var fr = [], t12 = 0, t24 = 0, run = 0;
    p.g.forEach(function(g){ var f = g[CI.fr]; if(f == null) return; fr.push(f); if(f <= 12) t12++; if(f <= 24) t24++; });
    for(i = fr.length - 1; i >= 0 && fr[i] <= 12; i--) run++;
    if(fr.length) cells += cell('Top-12 weeks', t12 + ' of ' + fr.length, run >= 2 ? 'last ' + run + ' in a row' : ((p.p === 'RB' || p.p === 'WR') ? 'top 24: ' + t24 : ''));
    h = '<div class="skqt">' + cells + '</div>';
    if(n < 2) return h;
    var hi = Math.max.apply(null, v), lo = Math.min.apply(null, v), ih = v.lastIndexOf(hi), il = v.lastIndexOf(lo), last = v[n - 1], up = 0, dn = 0;
    function at(x){ return hi - lo < 1e-9 ? 50 : Math.round((x - lo) / (hi - lo) * 1000) / 10; }
    function only(x){ var c = 0; for(var j = 0; j < n; j++) if(v[j] === x) c++; return c === 1; }
    for(i = n - 1; i > 0 && v[i] > v[i - 1]; i--) up++;
    for(i = n - 1; i > 0 && v[i] < v[i - 1]; i--) dn++;
    var tag = n >= 4 && last === hi && only(hi) ? ', his season high' : (n >= 4 && last === lo && only(lo) ? ', his season low' : '');
    var runs = up >= 2 ? 'Improved in ' + up + ' straight games.' : (dn >= 2 ? 'Dropped in ' + dn + ' straight games.' : '');
    h += '<div class="skrg" role="img" aria-label="' + esc('His season range: ' + lo.toFixed(1) + ' in Week ' + p.g[il][0] + ' to ' + hi.toFixed(1) + ' in Week ' + p.g[ih][0] + '.') + '">' +
      '<span class="skre"><b>' + lo.toFixed(1) + '</b><small>low · Wk ' + p.g[il][0] + '</small></span>' +
      '<span class="skrt"><i class="skrv" style="left:' + at(a) + '%"></i><i class="skrx" style="left:' + at(last) + '%"></i></span>' +
      '<span class="skre hi"><b>' + hi.toFixed(1) + '</b><small>high · Wk ' + p.g[ih][0] + '</small></span></div>' +
      '<p class="skrc"><span><i class="kx"></i>Last game: <b>' + last.toFixed(1) + '</b> in Week ' + p.g[n - 1][0] + tag + '.</span> <span><i class="kv"></i>Average: <b>' + a.toFixed(1) + '</b>.</span>' + (runs ? ' <span>' + runs + '</span>' : '') + '</p>';
    return h;
  }
  function panelHTML(p){
    var ids = D.order[p.p] || ['ppr'], b = '';
    ids.forEach(function(id){ if(SD[id]) b += statBtn(p, SD[id]); });
    var stl = p.st ? ' · ' + esc(p.st) + ' this week' : '', nt = '';
    (p.nt || []).forEach(function(x){ nt += '<p class="skwn">' + esc(x) + '</p>'; });
    var fx = '', blk = function(cls, title, lines){ return lines && lines.length ? '<div class="' + cls + '"><b>' + title + '</b>' + lines.map(function(x){ return '<p>' + esc(x) + '</p>'; }).join('') + '</div>' : ''; };
    fx = blk('skmv', 'What moved', p.mv) + blk('skwk', 'This week', p.wk); if(fx) nt += '<div class="skfx">' + fx + '</div>';
    var hint = p.kw ? 'Pick a stat to graph it. Each number is his average over his last ' + p.kw + ' games; the arrow is the change from before.' : 'Pick a stat to graph it. Each number is his average a game.';
    return '<div class="skph"><div><h3 id="skpt">' + esc(p.n) + '</h3><p>' + esc(D.pos[p.p] || p.p) + ' · ' + esc(p.tn) + stl + '</p></div>' +
      '<button type="button" class="skx">Close</button></div>' + quote(p) + nt +
      '<p class="skpq" id="skpq">' + hint + '</p>' +
      '<div class="skts" role="group" aria-labelledby="skpq">' + b + '</div>' +
      (p.pg ? '<p class="skpl"><a href="/player/' + encodeURIComponent(p.k) + '/">' + esc(p.n) + '’s player page: props, matchup and game log</a></p>' : '');
  }
  function fit(el, keep){
    /* bring el into view under the sticky menu and above the phone tabs, without pushing `keep` off the top */
    var vh = window.innerHeight, r = el.getBoundingClientRect(), k = (keep || el).getBoundingClientRect();
    var d = Math.min(r.bottom - (vh - 84), k.top - 64);
    if(d > 4) window.scrollBy({top: d, behavior: calm ? 'auto' : 'smooth'});
  }
  function seat(item, box){
    /* box goes after the last item of `item`'s row (a full-width row of its own in the grid) */
    var last = item, top = item.offsetTop, nx;
    while((nx = last.nextElementSibling) && nx !== box && nx.offsetTop === top) last = nx;
    item.parentNode.insertBefore(box, last.nextSibling);
  }
  function closePanel(back){
    if(!cur) return;
    cur.btn.setAttribute('aria-expanded', 'false'); cur.btn.removeAttribute('aria-controls');
    if(cur.panel.parentNode) cur.panel.parentNode.removeChild(cur.panel);
    var b = cur.btn; cur = null;
    if(back && document.body.contains(b)) b.focus();
  }
  function openPanel(li, quiet){
    var p = BY[li.getAttribute('data-k')], btn = li.querySelector('.skb');
    if(!p || !btn) return;
    var same = cur && cur.li === li;
    closePanel(false);
    if(same) return;
    var panel = document.createElement('li');
    panel.className = 'skp'; panel.id = 'skp'; panel.setAttribute('role', 'region'); panel.setAttribute('aria-labelledby', 'skpt');
    panel.innerHTML = panelHTML(p);
    seat(li, panel);
    btn.setAttribute('aria-expanded', 'true'); btn.setAttribute('aria-controls', 'skp');
    cur = {li: li, btn: btn, panel: panel, p: p, st: null, sb: null, box: null, i: -1, w: 0};
    if(!quiet) fit(panel, li);
  }

  function ticks(lo, hi, whole){
    var span = (hi - lo) || 1, raw = span / 4, mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), nrm = raw / mag;
    var step = (nrm <= 1 ? 1 : (nrm <= 2 ? 2 : (nrm <= 5 ? 5 : 10))) * mag;
    if(whole && step < 1) step = 1;
    var t0 = Math.floor(lo / step + 1e-9) * step, t1 = Math.ceil(hi / step - 1e-9) * step, list = [];
    if(t1 <= t0) t1 = t0 + step;
    for(var v = t0; v <= t1 + step / 2; v += step) list.push(Math.round(v * 1000) / 1000);
    return {min: t0, max: t1, step: step, list: list};
  }
  function draw(){
    /* the graph of cur.st for cur.p, sized to its box */
    var p = cur.p, st = cur.st, box = cur.box, s = series(p, st), n = s.length;
    var vals = s.map(function(x){ return x.v; }), t = trend(vals, st.den ? s : null), k = t.k;
    var Wd = Math.max(250, Math.floor(box.clientWidth)), H = 232, ml = 34, mr = 10, mt = 14, mb = 38, pw = Wd - ml - mr, ph = H - mt - mb;
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var tk = ticks(lo < -0.08 * Math.max(hi, 1) ? lo : 0, hi, !st.dec);
    function X(i){ return n === 1 ? ml + pw / 2 : ml + 14 + (pw - 28) * i / (n - 1); }
    function Y(v){ return mt + ph * (1 - (v - tk.min) / (tk.max - tk.min)); }
    function f1(x){ return (Math.round(x * 10) / 10); }
    function line(a, b){ var d = ''; for(var i = a; i <= b; i++) d += (i === a ? 'M' : 'L') + f1(X(i)) + ' ' + f1(Y(vals[i])); return d; }
    function area(a, b){ var y0 = f1(Y(Math.max(tk.min, 0))); return line(a, b) + 'L' + f1(X(b)) + ' ' + y0 + 'L' + f1(X(a)) + ' ' + y0 + 'Z'; }
    var g = '', i, tl;
    for(i = 0; i < tk.list.length; i++){
      tl = st.pct ? tk.list[i] + '%' : (tk.step < 1 ? tk.list[i].toFixed(1) : String(tk.list[i]));
      g += '<line class="gr" x1="' + ml + '" x2="' + (Wd - mr) + '" y1="' + f1(Y(tk.list[i])) + '" y2="' + f1(Y(tk.list[i])) + '"/><text x="' + (ml - 7) + '" y="' + (f1(Y(tk.list[i])) + 3.5) + '" text-anchor="end">' + tl + '</text>';
    }
    if(n > 1){
      g += '<path class="ar" d="' + area(0, n - 1) + '"/>';
      if(k) g += '<path class="ar2" d="' + area(n - k, n - 1) + '"/>';
      g += '<path class="ln" d="' + line(0, k ? n - k : n - 1) + '"/>';
      if(k) g += '<path class="ln2" d="' + line(n - k, n - 1) + '"/>';
    }
    if(k){
      g += '<line class="av" x1="' + f1(X(0) - 8) + '" x2="' + f1(X(n - k - 1) + 8) + '" y1="' + f1(Y(t.b)) + '" y2="' + f1(Y(t.b)) + '"/>';
      g += '<line class="av2" x1="' + f1(X(n - k) - 8) + '" x2="' + f1(X(n - 1) + 8) + '" y1="' + f1(Y(t.r)) + '" y2="' + f1(Y(t.r)) + '"/>';
    }
    g += '<line class="cx" id="skcx" x1="0" x2="0" y1="' + mt + '" y2="' + (mt + ph) + '"/>';
    var every = n > 12 ? Math.ceil(n / 12) : 1;
    for(i = 0; i < n; i++){
      g += '<circle class="' + (k && i >= n - k ? 'dt2' : 'dt') + '" cx="' + f1(X(i)) + '" cy="' + f1(Y(vals[i])) + '" r="4"/>';
      if(i % every === 0 || i === n - 1) g += '<text class="xo" data-i="' + i + '" x="' + f1(X(i)) + '" y="' + (H - 21) + '" text-anchor="middle">' + esc(s[i].o) + '</text><text class="wk" x="' + f1(X(i)) + '" y="' + (H - 8) + '" text-anchor="middle">W' + s[i].w + '</text>';
    }
    g += '<circle class="sel" id="sksel" cx="0" cy="0" r="7"/>';
    var per = (st.pct || st.den) ? '' : ' a game', note;
    if(k) note = '<span><i class="k2"></i>Last ' + k + ' games: <b>' + mid(t.r, st) + '</b> ' + esc(st.u) + per + '.</span> <span><i></i>Before that: <b>' + mid(t.b, st) + '</b>.</span>';
    else note = '<b>' + mid(t.r, st) + '</b> ' + esc(st.u) + per + ' in ' + n + ' game' + (n === 1 ? '' : 's') + '. A trend needs four.';
    if(st.den && n < p.g.length) note += ' <span>Left out: ' + (p.g.length - n) + ' game' + (p.g.length - n === 1 ? '' : 's') + ' with fewer than ' + st.dmin + ' ' + esc(st.dn) + '.</span>';
    var rows = '';
    for(i = n - 1; i >= 0; i--) rows += '<tr><td>' + s[i].w + '</td><td>' + esc(s[i].o) + '</td><td>' + one(s[i].v, st) + '</td></tr>';
    box.innerHTML = '<figure class="skc ' + tone(t, st) + '"><figcaption><span class="skct" id="skct">' + esc(st.l) + '</span><span class="skrd" id="skrd" aria-live="polite"></span></figcaption>' +
      '<div class="skplot" id="skplot" tabindex="0" role="group" aria-label="' + esc(p.n + ', ' + st.l.toLowerCase() + ' by game. Left and right arrow keys read each game.') + '">' +
      '<svg viewBox="0 0 ' + Wd + ' ' + H + '" width="' + Wd + '" height="' + H + '" aria-hidden="true" focusable="false">' + g + '</svg></div>' +
      '<p class="skcc">' + note + '</p>' +
      '<details class="sktbl"><summary>Show the numbers</summary><table><thead><tr><th>Week</th><th>Opp</th><th>' + esc(st.l) + '</th></tr></thead><tbody>' + rows + '</tbody></table></details></figure>';
    cur.w = Wd; cur.geo = {X: X, Y: Y, n: n, s: s, vals: vals};
    var plot = document.getElementById('skplot');
    function near(e){
      var r = plot.getBoundingClientRect(), x = (e.clientX - r.left) * (Wd / r.width), best = 0, bd = 1e9;
      for(var j = 0; j < n; j++){ var dd = Math.abs(X(j) - x); if(dd < bd){ bd = dd; best = j; } }
      pick(best);
    }
    plot.addEventListener('pointerdown', near);
    plot.addEventListener('pointermove', function(e){ if(e.pointerType === 'mouse' || e.buttons || e.pressure > 0) near(e); });
    plot.addEventListener('keydown', function(e){
      var j = cur.i;
      if(e.key === 'ArrowLeft') j = Math.max(0, j - 1); else if(e.key === 'ArrowRight') j = Math.min(n - 1, j + 1); else if(e.key === 'Home') j = 0; else if(e.key === 'End') j = n - 1; else return;
      e.preventDefault(); pick(j);
    });
    pick(cur.i >= 0 && cur.i < n ? cur.i : n - 1);
  }
  function pick(i){
    var G = cur.geo, st = cur.st; if(!G) return;
    cur.i = i;
    var cx = document.getElementById('skcx'), sel = document.getElementById('sksel'), rd = document.getElementById('skrd'), x = Math.round(G.X(i) * 10) / 10, y = Math.round(G.Y(G.vals[i]) * 10) / 10;
    cx.setAttribute('x1', x); cx.setAttribute('x2', x); sel.setAttribute('cx', x); sel.setAttribute('cy', y);
    rd.textContent = '';
    var a = document.createElement('span'), b = document.createElement('b'), u = document.createElement('span');
    a.textContent = 'Week ' + G.s[i].w + ' vs ' + G.s[i].o; b.textContent = one(G.vals[i], st); u.className = 'sr'; u.textContent = ' ' + st.u;
    rd.appendChild(a); rd.appendChild(b); rd.appendChild(u);
    var xs = cur.box.querySelectorAll('.xo');
    for(var j = 0; j < xs.length; j++) xs[j].setAttribute('class', 'xo' + (+xs[j].getAttribute('data-i') === i ? ' on' : ''));
  }
  function shut(){
    /* close the open graph, leave the panel */
    if(!cur || !cur.box) return;
    if(cur.box.parentNode) cur.box.parentNode.removeChild(cur.box);
    if(cur.sb) cur.sb.setAttribute('aria-pressed', 'false');
    cur.box = null; cur.sb = null; cur.st = null; cur.geo = null; cur.i = -1;
  }
  function choose(btn){
    var st = SD[btn.getAttribute('data-s')]; if(!cur || !st) return;
    var same = cur.sb === btn;
    shut();
    if(same) return;
    var box = document.createElement('div');
    box.className = 'skcw'; box.id = 'skcw';
    seat(btn, box);
    btn.setAttribute('aria-pressed', 'true');
    cur.st = st; cur.sb = btn; cur.box = box; cur.i = -1;
    draw();
    fit(box, btn);
  }

  /* ---- search: every player with a page, best recent scorer first ---- */
  function norm(s){ return String(s).toLowerCase().replace(/['’.]/g, '').replace(/[^a-z0-9]+/g, ' ').replace(/^ +| +$/g, ''); }
  var IDX = D.pl.map(function(p){ return {p: p, s: ' ' + norm(p.n + ' ' + p.t + ' ' + p.tn + ' ' + p.p + ' ' + (D.pos[p.p] || ''))}; });
  function search(){
    var v = norm(q.value);
    closePanel(false);
    if(mk) mk.hidden = v.length >= 2;
    if(v.length < 2){ res.hidden = true; secs.hidden = false; rl.innerHTML = ''; return []; }
    var tk = v.split(' '), hits = [], i, j, ok;
    for(i = 0; i < IDX.length; i++){
      ok = true;
      for(j = 0; j < tk.length; j++){ if(IDX[i].s.indexOf(' ' + tk[j]) < 0){ ok = false; break; } }
      if(ok) hits.push(IDX[i].p);
    }
    var h = '';
    for(i = 0; i < hits.length && i < CAP; i++) h += fill(fields(hits[i]));
    rl.innerHTML = h; secs.hidden = true; res.hidden = false;
    rh.querySelector('small').textContent = hits.length ? (hits.length === 1 ? '1 player' : (hits.length > CAP ? 'top ' + CAP + ' of ' + hits.length + ' · keep typing to narrow it' : hits.length + ' players')) : '';
    rn.hidden = hits.length > 0;
    if(!hits.length) rn.textContent = 'No player matches “' + q.value.replace(/^\s+|\s+$/g, '') + '”. Try a last name or a team, like Cook or Bills.';
    return hits;
  }
  function more(btn){
    /* the rest of that position's risers, same tile template, under the ones the page came with */
    var pos = btn.getAttribute('data-pos'), mode = btn.getAttribute('data-list') || 'rise', sec = btn.closest('.sksec'), wrap = btn.closest('[data-for]'), ul = wrap && wrap.querySelector('.skg'),
        ks = ((mode === 'fall' ? D.fmore : D.more) || {})[pos] || [], h = '', i;
    if(!ul) return;
    for(i = 0; i < ks.length; i++) if(BY[ks[i]]) h += fill(fields(BY[ks[i]]));
    var open = cur && cur.li.parentNode === ul;
    if(open && cur.panel.parentNode) cur.panel.parentNode.removeChild(cur.panel);
    ul.insertAdjacentHTML('beforeend', h);
    if(open) seat(cur.li, cur.panel);
    var sm = sec.querySelector('h2 small[data-for="' + mode + '"]'), n = ul.querySelectorAll('.sk').length;
    if(sm) sm.textContent = 'all ' + n + (mode === 'fall' ? ' falling' : ' rising');
    var first = ks.length ? ul.querySelector('.sk[data-k="' + ks[0] + '"] .skb') : null;
    btn.parentNode.parentNode.removeChild(btn.parentNode);
    if(first){ try{ first.focus({preventScroll: true}); }catch(e){ first.focus(); } }
  }
  function openKey(k, jump){
    /* open a player wherever his tile is: the list on show, the other list (the switch moves to it), or a search for his name */
    if(!BY[k]) return;
    if(q.value){ q.value = ''; search(); }
    var mode = root.getAttribute('data-mode') === 'fall' ? 'fall' : 'rise', other = mode === 'fall' ? 'rise' : 'fall';
    var li = root.querySelector('#sksecs [data-for="' + mode + '"] .sk[data-k="' + k + '"]');
    if(!li && (li = root.querySelector('#sksecs [data-for="' + other + '"] .sk[data-k="' + k + '"]'))) setMode(other);
    if(!li){ q.value = BY[k].n; search(); li = rl.querySelector('.sk[data-k="' + k + '"]'); }
    if(!li) return;
    if(!(cur && cur.li === li)) openPanel(li, true);
    if(jump){ li.scrollIntoView({block: 'start'}); return; }
    window.scrollBy({top: li.getBoundingClientRect().top - 70, behavior: calm ? 'auto' : 'smooth'});
  }
  function setMode(m){ if(m !== 'fall') m = 'rise'; if(root.getAttribute('data-mode') === m) return; closePanel(false); root.setAttribute('data-mode', m);
    [].forEach.call(root.querySelectorAll('.skmode button'), function(b){ b.setAttribute('aria-pressed', b.getAttribute('data-mode') === m ? 'true' : 'false'); }); }
  q.addEventListener('input', search);
  q.addEventListener('keydown', function(e){ if(e.key === 'Escape' && q.value){ q.value = ''; search(); } });

  root.addEventListener('click', function(e){
    var t = e.target, el;
    if((el = t.closest('.skb'))){ openPanel(el.parentNode); return; }
    if((el = t.closest('.skmc'))){ openKey(el.getAttribute('data-k')); return; }
    if((el = t.closest('.skx'))){ closePanel(true); return; }
    if((el = t.closest('.skt'))){ choose(el); return; }
    if((el = t.closest('.skmore'))){ more(el); return; }
    if((el = t.closest('.skmode button'))){ if(q.value){ q.value = ''; search(); } setMode(el.getAttribute('data-mode')); return; }
    if((el = t.closest('.skj a')) && q.value){ q.value = ''; search(); }
  });
  root.addEventListener('keydown', function(e){
    if(e.key !== 'Escape' || !cur) return;
    if(cur.box && cur.box.contains(e.target)){ e.preventDefault(); var b = cur.sb; shut(); if(b) b.focus(); return; }
    if(cur.panel.contains(e.target) || cur.li.contains(e.target)){ e.preventDefault(); closePanel(true); }
  });
  var rz = 0;
  window.addEventListener('resize', function(){
    clearTimeout(rz);
    rz = setTimeout(function(){
      if(!cur) return;
      if(cur.panel.parentNode) cur.panel.parentNode.removeChild(cur.panel);
      seat(cur.li, cur.panel);
      if(cur.box){
        if(cur.box.parentNode) cur.box.parentNode.removeChild(cur.box);
        seat(cur.sb, cur.box);
        if(Math.abs(cur.box.clientWidth - cur.w) > 2) draw();
      }
    }, 150);
  });
  /* /stocks/#p=<player slug> opens that player (links from other pages) */
  var m = /^#p=([a-z0-9-]+)$/.exec(location.hash || '');
  if(m && BY[m[1]]) openKey(m[1], true);
  root.setAttribute('data-ready', '1');
})();
"""

def section(pos, title, word):
    """one position: its rising list and its falling list (owner 11/22 2:11 AM: "any other good information ... that would go hand in hand"),
    one shown at a time by the Rising / Falling switch (#skm[data-mode]); both are in the page so the switch is instant and works offline"""
    def one(mode, top, more, full, verb):
        body = (f'<ul class="skg" data-list="{mode}">' + "".join(fill(fields(x)) for x in top) + '</ul>') if top else f'<p class="sknone">No {word} is clearly {verb} right now.</p>'
        if more: body += f'<p class="skmr"><button type="button" class="skmore" data-pos="{pos}" data-list="{mode}">Show all {len(full)} {verb} {E(title.lower())}</button></p>'
        return f'<div data-for="{mode}">{body}</div>'
    def small(mode, top, verb): return f'<small data-for="{mode}">{"top " + str(len(top)) + " " + verb if top else "nobody " + verb}</small>'
    return (f'<section class="sksec" id="sk-{pos.lower()}" data-pos="{pos}"><h2>{E(title)} {small("rise", RISE[pos], "rising")}{small("fall", FALL[pos], "falling")}</h2>'
            + one("rise", RISE[pos], MORE[pos], ALLR[pos], "rising") + one("fall", FALL[pos], FMORE[pos], ALLF[pos], "falling") + '</section>')

DATA = {"week": W, "cols": COLS, "stats": STATS, "order": ORDER, "pos": {a: c.capitalize() for a, b, c in POSN}, "tc": TC, "tpl": TILE, "top": TOP, "floor": FLOOR, "min_up": MIN_UP,
        "rise": {pos: [x["k"] for x in RISE[pos]] for pos, _, _ in POSN}, "more": {pos: [x["k"] for x in MORE[pos]] for pos, _, _ in POSN},
        "fall": {pos: [x["k"] for x in FALL[pos]] for pos, _, _ in POSN}, "fmore": {pos: [x["k"] for x in FMORE[pos]] for pos, _, _ in POSN}, "mk": MK, "pl": PL}
blob = json.dumps(DATA, separators=(",", ":")).replace("</", "<\\/")   # ASCII only: the data file is read right whatever the server says its charset is
nrise = sum(len(v) for v in RISE.values())
link, base = __import__("account")._base_css()
floors = f'{FLOOR["QB"]:g} fantasy points as a quarterback, {FLOOR["RB"]:g} as a back or receiver, or {FLOOR["TE"]:g} as a tight end'
page = (f'<title>NFL fantasy stock market: rising players at every position · Week {W} · BetSweep</title>\n'
        f'<meta name="description" content="Whose fantasy stock is rising going into Week {W}: the top risers at quarterback, running back, wide receiver and tight end, with a game-by-game graph of fantasy points and every stat.">\n'
        f'{link}\n<style>{base}{CSS}</style>\n'
        f'<div class="skm" id="skm" data-week="{W}" data-mode="rise">'
        '<div class="skhd"><h1>Stock Market</h1>'
        f'<span class="sksub">Who is rising and falling going into Week {W}. Tap a player for his graphs and stats.</span></div>'
        '<div class="skfind"><label class="sr" for="skq">Search players</label><input id="skq" type="search" placeholder="Search a player or team" autocomplete="off" autocapitalize="words" spellcheck="false" enterkeyhint="search"></div>'
        + (('<section class="skmk" id="skmk" aria-labelledby="skmkh"><h2 class="sr" id="skmkh">Market movers</h2><ul class="skml">' + "".join(mover_html(c) for c in MK) + '</ul></section>') if MK else '') +
        '<div class="skmode" role="group" aria-label="Show the risers or the fallers"><button type="button" data-mode="rise" aria-pressed="true">Rising</button><button type="button" data-mode="fall" aria-pressed="false">Falling</button></div>'
        '<div class="skbar"><nav class="skj" aria-label="Jump to a position">' + "".join(f'<a href="#sk-{a.lower()}">{a}</a>' for a, b, c in POSN) + '</nav>'
        '<p class="skkey"><span><i class="k2"></i>last 3 games</span><span><i></i>earlier games</span></p></div>'
        '<div id="sksecs">' + "".join(section(a, b, c) for a, b, c in POSN) + '</div>'
        '<div id="skres" hidden><h2 id="skrh">Search results <small></small></h2><ul class="skg" id="skrl"></ul><p class="sknone" id="skrn" role="status" hidden></p></div>'
        '<noscript><p class="sknone">Turn on JavaScript to open a player\'s stats and to search.</p></noscript>'
        f'<p class="skfoot">The big number on a tile is the player\'s fantasy points a game over his last 3 games (his last 2 if he has played only 4 or 5); the arrow is the change from his earlier games. '
        f'To make a Rising list a player has to average at least {floors} over those games, be up at least {MIN_UP:g} a game, and have beaten his earlier average in at least two of them, so one big game is not a rise. '
        f'A Falling list is the mirror: he averaged that much before, is down at least {MIN_UP:g} a game, and was under his old average in at least two of those games. '
        'Players ruled out or doubtful this week, and players who missed their team\'s last two games, are left off the lists; the search still finds them. '
        'Each card at the top names the leader in one count, among players who could make a list. Breakout is the biggest riser whose earlier average was under the mark a riser has to reach. Season high is the highest score that was a player\'s best of the season and came in his latest game. '
        'On the climb is the most games in a row with more points than the game before. Highest floor is the best worst game among regular starters (six or more games). '
        'A top-12 week is a week he finished among the 12 highest scorers at his position, counting every player; a week still being played is not counted. '
        'In a player\'s box, Rank now is where his last-3 average stands at his position among players who played one of their team\'s last two games; the season rank is by points a game among players with four or more games. Both count the players on this page. '
        'A rate such as yards per carry is total over total for the games shown; games with too few chances to mean anything are left out. '
        'What moved is arithmetic on his latest games and his earlier ones (a rushing or receiving touchdown is 6 points, a passing touchdown 4). This week\'s projection is BetSweep\'s model in full PPR, the number Start / Sit shows; a defense ranked 1st in yards allowed gives up the most. '
        f'{E(THRU)}. Fantasy points are full PPR. Stats and snap counts: nflverse.</p></div>\n'
        f'<script>window.__SK = {blob};</script>\n<script>{JS}</script>\n')
open(os.path.join(OUT, "stocks.html"), "w", encoding="utf-8").write(page)
print(f"wrote out/stocks.html: {nrise} risers ({', '.join(a + ' ' + str(len(RISE[a])) for a, b, c in POSN)}), {sum(len(v) for v in FALL.values())} fallers ({', '.join(a + ' ' + str(len(FALL[a])) for a, b, c in POSN)}), {len(PL)} players in the search, week {W}; movers {", ".join(c["id"] for c in MK)}; data {len(blob) // 1024} KB")
