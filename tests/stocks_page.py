"""/stocks/ "Stock Market" (owner 11/22): the top risers at each position as tiles (player, team, a graph of his fantasy points), a
tap opens his stats under his row, a tap on a stat opens that stat's graph under the stat's row, and the search finds any player.
Phone 390x844 in light and dark, then a desktop pass.  The riser lists are recomputed here from the game logs the page ships, so the
rule in build_stocks.py and the tiles on the page cannot drift apart.     python3 tests/stocks_page.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8874; SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def window(n): return 3 if n >= 6 else (2 if n >= 4 else 0)
def trend(v):
    k = window(len(v))
    if not k: return 0, sum(v) / len(v), None, None, 0
    r = sum(v[-k:]) / k; b = sum(v[:-k]) / (len(v) - k); return k, r, b, r - b, sum(1 for x in v[-k:] if x > b)
def under(v):
    k = window(len(v))
    if not k: return 0
    b = sum(v[:-k]) / (len(v) - k); return sum(1 for x in v[-k:] if x < b)
def dtxt(d, flat=0.5):
    if d is None: return ""
    if abs(d) < flat: return ("" if f"{abs(d):.1f}" == "0.0" else ("+" if d >= 0 else "−")) + f"{abs(d):.1f}"
    return ("▲ " if d > 0 else "▼ ") + f"{abs(d):.1f}"

async def main():
    page = open(os.path.join(ROOT, "stocks", "index.html"), encoding="utf-8").read()
    m = re.search(r'<script src="/stocks/(data-[0-9a-f]{8,}\.js)"></script>', page)
    blob = open(os.path.join(ROOT, "stocks", m.group(1)), encoding="utf-8").read() if m else re.search(r"<script>(window\.__SK = .*?)</script>", page, re.S).group(1)
    D = json.loads(blob[len("window.__SK = "):].rstrip().rstrip(";")); PL = D["pl"]; BY = {p["k"]: p for p in PL}; C = {c: i for i, c in enumerate(D["cols"])}
    check(bool(m) and len(PL) >= 150, f"the page links its data file ({m.group(1) if m else 'inline'}; {len(PL)} players, {len(blob) // 1024} KB)")
    # ---- the rule, redone from the shipped game logs
    want = {}; rest = {}
    for pos in D["rise"]:
        c = []
        for p in PL:
            if p["p"] != pos: continue
            k, r, b, d, beat = trend([g[C["ppr"]] for g in p["g"]])
            if k and d >= D["min_up"] and r >= D["floor"][pos] and beat >= 2 and p["ac"] and p["st"] not in ("Out", "Doubtful"): c.append((-round(d, 2), p["n"], p["k"]))   # biggest rise first; a tie to two decimals goes by name, as in the build
        want[pos] = [x[2] for x in sorted(c)[:D["top"]]]; rest[pos] = [x[2] for x in sorted(c)[D["top"]:]]
    check(want == D["rise"] and all(len(v) <= D["top"] for v in want.values()), "the riser lists are exactly what the rule gives from the game logs shipped with the page: " + ", ".join(f"{a} {len(v)}" for a, v in D["rise"].items()))
    check(rest == D["more"] and all(p["up"] == (p["k"] in want[p["p"]] or p["k"] in rest[p["p"]]) for p in PL), "the players behind each \"Show all\" button are the rest of the players the rule passes, in order: " + ", ".join(f"{a} +{len(v)}" for a, v in D["more"].items()))
    allb = {(a, l): t for a, l, t in re.findall(r'<button type="button" class="skmore" data-pos="([A-Z]+)" data-list="(rise|fall)">([^<]+)</button>', page)}
    btns = {a: t for (a, l), t in allb.items() if l == "rise"}; fbtns = {a: t for (a, l), t in allb.items() if l == "fall"}
    check(set(btns) == {a for a, v in D["more"].items() if v} and all(btns[a].startswith(f"Show all {len(D['rise'][a]) + len(D['more'][a])} rising ") for a in btns), f"a position with more risers than its list has a button that says how many there are in all: {sorted(btns.values())}")
    mp = next((a for a in ("RB", "WR", "TE", "QB") if D["more"].get(a)), None)
    def written(mode): return {pos: re.findall(r'<li class="sk [a-z]+" data-k="([^"]+)" data-pos="' + pos + '"', "".join(re.findall(r'<ul class="skg" data-list="' + mode + r'">(.*?)</ul>', page, re.S))) for pos in D["rise"]}
    html_keys = written("rise")
    check(html_keys == D["rise"], "the tiles written into the page are those players, in that order")
    # ---- owner 11/22 2:11 AM ("any other good information ... that would go hand in hand"): the falling lists, what moved, this week
    wantf = {}; restf = {}
    for pos in D["fall"]:
        c = []
        for p in PL:
            if p["p"] != pos: continue
            v = [g[C["ppr"]] for g in p["g"]]; k, r, b, d, beat = trend(v)
            if k and d <= -D["min_up"] and b >= D["floor"][pos] and under(v) >= 2 and p["ac"] and p["st"] not in ("Out", "Doubtful"): c.append((round(d, 2), p["n"], p["k"]))
        wantf[pos] = [x[2] for x in sorted(c)[:D["top"]]]; restf[pos] = [x[2] for x in sorted(c)[D["top"]:]]
    check(wantf == D["fall"] and restf == D["fmore"] and written("fall") == D["fall"] and all(bool(p["dn"]) == (p["k"] in wantf[p["p"]] or p["k"] in restf[p["p"]]) for p in PL) and not any(p["up"] and p["dn"] for p in PL),
          "the falling lists are the mirror rule redone from the shipped game logs, written into the page in order, and nobody is on both: " + ", ".join(f"{a} {len(v)}+{len(D['fmore'][a])}" for a, v in D["fall"].items()))
    check(set(fbtns) == {a for a, v in D["fmore"].items() if v} and all(fbtns[a].startswith(f"Show all {len(D['fall'][a]) + len(D['fmore'][a])} falling ") for a in fbtns), f"a position with more fallers than its list has its own button ({sorted(fbtns.values())})")
    def moved(p):
        k = p["kw"]
        if not k: return []
        v = [g[C["ppr"]] for g in p["g"]]; _, r, b, d, _ = trend(v); d = round(d, 1); R, B = p["g"][-k:], p["g"][:-k]; av = lambda rows, f: sum(f(g) for g in rows) / len(rows)
        lab, f = (("Pass attempts", lambda g: g[C["att"]]) if p["p"] == "QB" else ("Carries plus targets", lambda g: g[C["car"]] + g[C["tgt"]]) if p["p"] == "RB" else ("Targets", lambda g: g[C["tgt"]]))
        a, c = av(R, f), av(B, f); out = [f"{lab}: {a:.1f} a game over his last {k}, " + (f"level with before ({c:.1f})." if abs(a - c) < 1.0 else f"{'up' if a > c else 'down'} from {c:.1f}.")]
        tp = (lambda g: 4 * g[C["ptd"]] + 6 * g[C["td"]]) if p["p"] == "QB" else (lambda g: 6 * g[C["td"]]); x = av(R, tp) - av(B, tp)
        if abs(d) >= 2.0 and abs(x) >= 1.0 and (x > 0) == (d > 0):
            w = "rise" if d > 0 else "drop"
            out.append(f"Touchdowns are all of the {abs(d):.1f}-point {w}; the rest of his scoring is level or going the other way." if abs(x) > abs(d) + 0.05 else f"Touchdowns are {abs(x):.1f} of the {abs(d):.1f}-point {w}.")
        return out
    badm = [(p["n"], p["mv"], moved(p)) for p in PL if p["mv"] != moved(p)]
    check(not badm and sum(1 for p in PL if len(p["mv"]) == 2) >= 5, f"every 'What moved' line is the arithmetic it says it is, redone from his shipped games ({sum(1 for p in PL if p['mv'])} players, {sum(1 for p in PL if len(p['mv']) == 2)} with a touchdown line; off: {badm[:2]})")
    try: SS = {(x["n"], x["t"]): x for x in json.load(open(os.path.join(ROOT, "b", "startsit.json")))["players"]}
    except Exception: SS = {}
    proj = [(p, float(re.search(r"The model projects (\d+\.\d) fantasy points", " ".join(p["wk"])).group(1))) for p in PL if "The model projects" in " ".join(p["wk"])]
    offp = [(p["n"], x, SS.get((p["n"], p["t"]), {}).get("fp")) for p, x in proj if (p["n"], p["t"]) in SS and abs(round(SS[(p["n"], p["t"])]["fp"], 1) - x) > 0.051]
    check(len(proj) >= 100 and sum(1 for p, x in proj if (p["n"], p["t"]) in SS) >= 0.9 * len(proj) and not offp and all(p["wk"] and len(p["wk"]) <= 2 for p in PL) and not any(p["st"] in ("Out", "Doubtful") and "projects" in " ".join(p["wk"]) for p in PL),
          f"'This week' gives {len(proj)} players a projection, each the number Start / Sit publishes for him; a player listed out gets none; everyone gets a line (bye, played or game) (off: {offp[:3]})")
    faller = next((BY[k] for v in D["fall"].values() for k in v if len(BY[k]["mv"]) == 2), None) or next((BY[k] for v in D["fall"].values() for k in v), None)
    fpos = next((a for a in ("RB", "WR", "TE", "QB") if D["fmore"].get(a)), None)
    check(all(BY[k]["st"] not in ("Out", "Doubtful") and BY[k]["ac"] and BY[k]["up"] for v in D["rise"].values() for k in v), "nobody on a list is ruled out, doubtful or two games gone")
    bad = []
    for p in PL:
        k, r, b, d, beat = trend([g[C["ppr"]] for g in p["g"]]); f = p["f"]
        if f["val"] != f"{r:.1f}" or f["dt"] != dtxt(d) or f["lab"] != (f"last {k}" if k else (f"{len(p['g'])} games" if len(p["g"]) != 1 else "1 game")) or f["dir"] != ("na" if d is None else ("fl" if abs(d) < 0.5 else ("up" if d > 0 else "dn"))): bad.append(p["n"])
    check(not bad, f"every player's big number, arrow and window label follow from his own game log ({len(PL)} players; off: {bad[:4]})")
    # ---- the injury notes: each one names weeks that sit where it says they sit in his own game log, and the tag on his tile follows from them
    A = re.compile(r"^He played more snaps than usual in (.+?), with (.+?) (out|hurt|hurt or out)\. (.+?) (is questionable this week|has played since|is not ruled out this week)\.$")
    B = re.compile(r"^He played less than usual in (.+)\.$"); Cx = re.compile(r"^His earlier games include (.+), when he played less than usual\.$")
    wk = lambda t: [int(x) for x in re.findall(r"Week (\d+)", t)]
    badn = []; kinds = {"more": 0, "less": 0, "earlier": 0}
    for p in PL:
        ws = [g[0] for g in p["g"]]; k = p["kw"]; win = set(ws[-k:]) if k else set(); early = set(ws[:-k]) if k else set(); fi = 0
        for t in p["nt"]:
            a, b_, c = A.match(t), B.match(t), Cx.match(t)
            if a: fi = 1; kinds["more"] += 1; good = bool(wk(a.group(1))) and set(wk(a.group(1))) <= win and a.group(4) in a.group(2) and a.group(2) != p["n"]
            elif c: kinds["earlier"] += 1; good = bool(wk(c.group(1))) and set(wk(c.group(1))) <= early
            elif b_: kinds["less"] += 1; good = bool(wk(b_.group(1))) and set(wk(b_.group(1))) <= win
            else: good = False
            if not good: badn.append((p["n"], t))
        tag = {"Out": "OUT", "Doubtful": "D", "Questionable": "Q"}.get(p["st"], "") or ("NOTE" if fi else "")
        if p["fi"] != fi or p["f"]["st"] != tag or p["f"]["stc"] != ("o" if p["st"] in ("Out", "Doubtful") else "") or (p["nt"] and not k) or ("note on his recent games" in p["f"]["aria"]) != bool(fi): badn.append((p["n"], "tag", p["f"]["st"], tag))
    check(not badn and kinds["more"] >= 1 and kinds["less"] + kinds["earlier"] >= 1, f"every injury note names games that are where it says they are in his game log, and every tile's tag follows from his status and his notes "
          f"({kinds['more']} more-snaps notes, {kinds['less']} played-less, {kinds['earlier']} earlier-game; off: {badn[:3]})")
    check(not any(re.search(r"\b(will|should|expect|likely|projected?|regress|fade|sell|buy)\b", t, re.I) for p in PL for t in p["nt"]), "no note forecasts anything: each says what happened and what is known now")
    noted = next((p for p in PL if p["f"]["st"] == "NOTE" and len(p["nt"]) >= 2), None) or next((p for p in PL if p["f"]["st"] == "NOTE"), None)
    quest = next((p for p in PL if p["st"] == "Questionable"), None)
    nrise = sum(len(v) for v in D["rise"].values()); first_pos = next(a for a, v in D["rise"].items() if len(v) >= 3); r0 = BY[D["rise"][first_pos][0]]
    rb = BY[(D["rise"].get("RB") or D["rise"][first_pos])[0]]
    out = next((p for p in PL if p["st"] == "Out" and len(p["g"]) >= 4), None)
    cold = next((p for p in PL if not p["up"] and not p["st"] and len(p["g"]) >= 6 and p["f"]["dir"] == "dn"), None)

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    U = f"http://127.0.0.1:{PORT}/stocks/"
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(U, wait_until="domcontentloaded"); await pg.wait_for_selector("#skm[data-ready='1']", timeout=8000); await pg.wait_for_timeout(500)
            T = lambda s: f"[{theme}] " + s
            d = await pg.evaluate("""(function(){ var t = [...document.querySelectorAll('#sksecs [data-for="rise"] .sk')], g = document.querySelector('#sksecs .skg').children;
              var cs = function(e){ return getComputedStyle(e); };
              return {n: t.length, over: document.documentElement.scrollWidth - innerWidth, two: g.length >= 3 && g[0].offsetTop === g[1].offsetTop && g[2].offsetTop > g[0].offsetTop,
                tap: [...document.querySelectorAll('.skj a')].every(function(a){ return a.getBoundingClientRect().height >= 40; }) && document.getElementById('skq').getBoundingClientRect().height >= 44,
                tile: Math.min.apply(null, t.map(function(x){ return x.getBoundingClientRect().height; })), menu: !!document.querySelector('.sitenav a[href="/stocks/"], nav a[href="/stocks/"]'),
                clip: t.filter(function(x){ var s = x.querySelector('.sksp').getBoundingClientRect(), r = x.getBoundingClientRect(); return s.width < 60 || s.right > r.right + 1 || s.height < 24; }).length,
                up: cs(document.querySelector('.sk.up em')).color, mute: cs(document.querySelector('.sk .skv small')).color, ink: cs(document.querySelector('.sk .sknm')).color,
                screens: document.documentElement.scrollHeight / innerHeight, firsttile: t[0].getBoundingClientRect().top}; })()""")
            check(d["n"] == nrise and not errs, T(f"{d['n']} tiles on the page, no script error ({errs[:1]})"))
            check(d["over"] <= 0 and d["two"], T(f"two tiles to a row on a phone and no sideways scroll ({d['over']})"))
            check(d["tap"] and d["tile"] >= 100 and d["clip"] == 0, T(f"the search box, the position chips and every tile are easy to hit, and every tile's graph fits its tile (shortest tile {d['tile']:.0f}px)"))
            check(d["up"] != d["mute"] and d["up"] != d["ink"], T("the up arrow wears the up colour, not the text colour"))
            check(d["firsttile"] < 844 * 0.62 and d["screens"] <= 7.5, T(f"the first tiles start on the first screen ({d['firsttile']:.0f}px down) and the page is {d['screens']:.1f} screens long"))
            check(d["menu"], T("the site menu links to Stock Market"))
            chips = await pg.evaluate("[...document.querySelectorAll('#sksecs [data-for=\"rise\"] .sk')].map(function(x){ var c = x.querySelector('.skst'); return [x.getAttribute('data-k'), c.textContent, getComputedStyle(c).display !== 'none', c.classList.contains('o')]; })")
            check(all(c[1] == BY[c[0]]["f"]["st"] and c[2] == bool(c[1]) and c[3] == (BY[c[0]]["f"]["stc"] == "o") for c in chips), T(f"every tile wears the tag its data gives it and none when it has none ({sum(1 for c in chips if c[1])} of {len(chips)} tagged: {sorted(set(c[1] for c in chips if c[1]))})"))
            t0 = await pg.evaluate("(function(k){ var li = document.querySelector('#sksecs .sk[data-k=\"' + k + '\"]'), b = li.querySelector('.skb'); return {h: li.outerHTML, nm: li.querySelector('.sknm').textContent, tm: li.querySelector('.sktb').textContent, sub: li.querySelector('.sktm span').textContent, val: li.querySelector('.skv b').textContent, lab: li.querySelector('.skv small').textContent, dt: li.querySelector('em').textContent, pts: (li.querySelector('.ska').getAttribute('d').match(/[ML]/g) || []).length, rec: (li.querySelector('.skr').getAttribute('d').match(/[ML]/g) || []).length, d: li.querySelector('.ska').getAttribute('d'), aria: b.getAttribute('aria-label'), ex: b.getAttribute('aria-expanded')}; })", rb["k"])
            vals = [g[C["ppr"]] for g in rb["g"]]; k, r, bs, dd, beat = trend(vals)
            check(t0["nm"] == rb["n"] and t0["tm"] == rb["t"] and rb["tn"] in t0["sub"] and t0["pts"] == len(vals) and t0["rec"] == k and t0["val"] == f"{r:.1f}" and t0["dt"] == dtxt(dd) and t0["lab"] == f"last {k}" and t0["ex"] == "false" and rb["n"] in t0["aria"],
                  T(f"a tile is the player, his team and a graph with a point for every game: {rb['n']}, {t0['tm']}, {t0['pts']} games, {t0['val']} over his {t0['lab']}, {t0['dt']}"))
            # ---- tap the tile: his stats open under his row
            await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(700)
            p1 = await pg.evaluate("""(function(k){ var li = document.querySelector('#sksecs .sk[data-k="' + k + '"]'), p = document.getElementById('skp'); if(!p) return null;
              var row = [...li.parentNode.children].filter(function(x){ return x !== p && x.offsetTop === li.offsetTop; }), r = p.getBoundingClientRect(), st = [...p.querySelectorAll('.skt')];
              return {after: row[row.length - 1].nextElementSibling === p, full: Math.abs(r.width - li.parentNode.getBoundingClientRect().width) < 2, ex: li.querySelector('.skb').getAttribute('aria-expanded'), h3: p.querySelector('h3').textContent,
                ids: st.map(function(x){ return x.getAttribute('data-s'); }), two: st.length >= 3 && st[0].offsetTop === st[1].offsetTop && st[2].offsetTop > st[0].offsetTop, tap: Math.min.apply(null, st.map(function(x){ return x.getBoundingClientRect().height; })),
                sp: st.every(function(x){ return !!x.querySelector('svg.sksp path'); }), fan: p.querySelector('.skt[data-s="ppr"] .ska').getAttribute('d'), fv: p.querySelector('.skt[data-s="ppr"] .sktv b').textContent, fd: p.querySelector('.skt[data-s="ppr"] .sktv em').textContent,
                link: (p.querySelector('.skpl a') || {}).getAttribute ? p.querySelector('.skpl a').getAttribute('href') : '', chart: !!p.querySelector('.skcw'), notes: [...p.querySelectorAll('.skwn')].map(function(x){ return x.textContent; }), mv: [...p.querySelectorAll('.skmv p')].map(function(x){ return x.textContent; }), wk: [...p.querySelectorAll('.skwk p')].map(function(x){ return x.textContent; }),
                fxtop: p.querySelector('.skfx') ? Math.round(p.querySelector('.skfx').getBoundingClientRect().bottom) : -1, sttop: Math.round(p.querySelector('.skt').getBoundingClientRect().top), heads: [...p.querySelectorAll('.skfx b')].map(function(x){ return x.textContent; }), over: document.documentElement.scrollWidth - innerWidth, top: r.top, tiletop: li.getBoundingClientRect().top}; })""", rb["k"])
            offered = [i for i in D["order"][rb["p"]] if any(g[C[next(s for s in D["stats"] if s["id"] == i)["col"]]] is not None for g in rb["g"]) and sum((g[C[next(s for s in D["stats"] if s["id"] == i)["col"]]] or 0) for g in rb["g"]) >= next(s for s in D["stats"] if s["id"] == i)["min"]]
            check(bool(p1) and p1["after"] and p1["full"] and p1["ex"] == "true" and p1["h3"] == rb["n"] and not p1["chart"], T("tapping a tile opens his stats in a full-width panel right under his row; no graph until a stat is picked"))
            check(bool(p1) and p1["notes"] == rb["nt"], T(f"his panel carries exactly the notes his data has ({len(rb['nt'])})"))
            check(bool(p1) and p1["mv"] == rb["mv"] and p1["wk"] == rb["wk"] and len(rb["mv"]) >= 1 and len(rb["wk"]) >= 1 and p1["heads"] == ["What moved", "This week"] and 0 < p1["fxtop"] <= p1["sttop"] + 1,
                  T(f"above his stats the panel says what moved and what his week holds: {rb['mv'][0][:60]} | {rb['wk'][0][:50]}"))
            check(bool(p1) and p1["ids"] == offered and p1["two"] and p1["tap"] >= 56 and p1["sp"] and p1["over"] <= 0, T(f"the panel offers his stats to pick from, two to a row, each with its own small graph: {', '.join(p1['ids']) if p1 else ''}"))
            num = lambda s: [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]
            check(bool(p1) and p1["fv"] == t0["val"] and p1["fd"] == t0["dt"] and len(num(p1["fan"])) == len(num(t0["d"])) and max(abs(a - c) for a, c in zip(num(p1["fan"]), num(t0["d"]))) <= 0.11,
                  T("his Fantasy points stat is the tile's number, arrow and graph again (the page script and the build draw the same picture)"))
            check(bool(p1) and p1["link"] == f"/player/{rb['k']}/" and os.path.exists(os.path.join(ROOT, "player", rb["k"], "index.html")), T("the panel links to his player page, and that page exists"))
            check(bool(p1) and p1["tiletop"] >= 50 and p1["top"] < 844 - 64, T(f"after the tap his tile is still on screen under the menu and the panel is in view (tile {p1['tiletop']:.0f}px, panel {p1['top']:.0f}px)"))
            # ---- tap a stat: its graph opens under that stat's row
            sid = next((i for i in ("rush", "recy", "pass") if i in offered), offered[-1]); sdef = next(s for s in D["stats"] if s["id"] == sid)
            ser = [(g[0], g[1], g[C[sdef["col"]]]) for g in rb["g"] if g[C[sdef["col"]]] is not None]; sk, sr, sb, sd, _ = trend([x[2] for x in ser])
            await pg.click(f'#skp .skt[data-s="{sid}"]'); await pg.wait_for_timeout(900)
            c1 = await pg.evaluate("""(function(sid){ var p = document.getElementById('skp'), b = p.querySelector('.skt[data-s="' + sid + '"]'), box = document.getElementById('skcw'); if(!box) return null;
              var row = [...b.parentNode.children].filter(function(x){ return x !== box && x.offsetTop === b.offsetTop; }), r = box.getBoundingClientRect(), svg = box.querySelector('svg').getBoundingClientRect();
              return {after: row[row.length - 1].nextElementSibling === box, pressed: b.getAttribute('aria-pressed'), others: [...p.querySelectorAll('.skt[aria-pressed="true"]')].length, ttl: box.querySelector('.skct').textContent,
                dots: box.querySelectorAll('circle.dt, circle.dt2').length, hot: box.querySelectorAll('circle.dt2').length, rd: box.querySelector('.skrd').textContent, cc: box.querySelector('.skcc').textContent, xo: [...box.querySelectorAll('.xo')].map(function(x){ return x.textContent; }),
                rows: box.querySelectorAll('.sktbl tbody tr').length, top: r.top, bottom: r.bottom, btop: b.getBoundingClientRect().top, svgw: svg.width, boxw: r.width, over: document.documentElement.scrollWidth - innerWidth,
                avg: box.querySelectorAll('line.av, line.av2').length, ticks: [...box.querySelectorAll('svg text:not(.xo):not(.wk)')].map(function(x){ return x.textContent; })}; })""", sid)
            one = lambda v: (f"{round(v)}%" if sdef["pct"] else (f"{v:.{sdef['dec']}f}" if sdef["dec"] else str(round(v))))
            mid = lambda v: (f"{round(v)}%" if sdef["pct"] else f"{v:.1f}")
            check(bool(c1) and c1["after"] and c1["pressed"] == "true" and c1["others"] == 1 and c1["ttl"] == sdef["l"], T(f"tapping a stat opens its graph right under that stat's row ({sdef['l']})"))
            check(bool(c1) and c1["dots"] == len(ser) and c1["hot"] == sk and c1["xo"] == [x[1] for x in ser] and c1["rows"] == len(ser) and c1["avg"] == (2 if sk else 0),
                  T(f"the graph has a point and a label for each of his {len(ser)} games, his last {sk} in colour, both averages drawn, and the same numbers as a table"))
            check(bool(c1) and c1["rd"].startswith(f"Week {ser[-1][0]} vs {ser[-1][1]}{one(ser[-1][2])}") and (not sk or (f"Last {sk} games: {mid(sr)} " in c1["cc"] and f"Before that: {mid(sb)}." in c1["cc"])),
                  T(f"it opens on his latest game and says both averages in words: {c1['rd'][:26] if c1 else ''} | {c1['cc'][:70] if c1 else ''}"))
            check(bool(c1) and c1["over"] <= 0 and abs(c1["svgw"] - c1["boxw"]) < 2 and c1["top"] >= 50 and c1["bottom"] <= 844 - 62 and c1["btop"] >= 50,
                  T(f"the whole graph is on screen between the menu and the tabs, with its stat still in view, and nothing scrolls sideways (graph {c1['top']:.0f}-{c1['bottom']:.0f}px)" if c1 else "graph"))
            # the reading moves with a finger and with the arrow keys
            xy = await pg.evaluate("(function(){ var s = document.querySelector('#skcw svg').getBoundingClientRect(), c = document.querySelector('#skcw circle.dt, #skcw circle.dt2').getBoundingClientRect(); return [c.left + c.width / 2, s.top + s.height / 2]; })()")
            await pg.touchscreen.tap(xy[0], xy[1]); await pg.wait_for_timeout(200)
            r_first = await pg.inner_text("#skrd")
            await pg.focus("#skplot"); await pg.keyboard.press("End"); await pg.keyboard.press("ArrowLeft"); await pg.wait_for_timeout(120)
            r_prev = await pg.inner_text("#skrd")
            check(r_first.startswith(f"Week {ser[0][0]} vs {ser[0][1]}") and one(ser[0][2]) in r_first and r_prev.startswith(f"Week {ser[-2][0]} vs {ser[-2][1]}") and one(ser[-2][2]) in r_prev,
                  T(f"a tap on the first game reads it ({r_first.splitlines()[0]}) and the arrow keys step game to game ({r_prev.splitlines()[0]})"))
            # another stat moves the graph; the same stat again closes it; Escape and Close work
            other = next(i for i in offered if i != sid)
            await pg.click(f'#skp .skt[data-s="{other}"]'); await pg.wait_for_timeout(700)
            mv = await pg.evaluate("[document.querySelectorAll('.skcw').length, document.querySelector('.skcw .skct').textContent, document.querySelectorAll('.skt[aria-pressed=\"true\"]').length]")
            await pg.click(f'#skp .skt[data-s="{other}"]'); await pg.wait_for_timeout(300)
            gone = await pg.evaluate("[document.querySelectorAll('.skcw').length, document.querySelectorAll('.skt[aria-pressed=\"true\"]').length, !!document.getElementById('skp')]")
            check(mv == [1, next(s for s in D["stats"] if s["id"] == other)["l"], 1] and gone == [0, 0, True], T("picking another stat moves the graph to it; tapping the open stat again shuts the graph and leaves his stats open"))
            await pg.click(f'#skp .skt[data-s="{sid}"]'); await pg.wait_for_timeout(500); await pg.focus("#skplot"); await pg.keyboard.press("Escape"); await pg.wait_for_timeout(150)
            e1 = await pg.evaluate("[document.querySelectorAll('.skcw').length, !!document.getElementById('skp'), document.activeElement.getAttribute('data-s')]")
            await pg.keyboard.press("Escape"); await pg.wait_for_timeout(150)
            e2 = await pg.evaluate("[!!document.getElementById('skp'), document.activeElement.className, document.querySelectorAll('.skb[aria-expanded=\"true\"]').length]")
            check(e1 == [0, True, sid] and e2 == [False, "skb", 0], T("Escape shuts the graph and hands focus back to its stat, then shuts the panel and hands focus back to his tile"))
            await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(500); await pg.click("#skp .skx"); await pg.wait_for_timeout(200)
            cl = await pg.evaluate("[!!document.getElementById('skp'), document.querySelectorAll('.skb[aria-expanded=\"true\"]').length]")
            await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(400); await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(200)
            cl2 = await pg.evaluate("!!document.getElementById('skp')")
            await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(400); await pg.click(f'#sksecs .sk[data-k="{r0["k"]}"] .skb'); await pg.wait_for_timeout(600)
            sw = await pg.evaluate("[document.querySelectorAll('.skp').length, document.querySelector('.skp h3').textContent, document.querySelectorAll('.skb[aria-expanded=\"true\"]').length]")
            check(cl == [False, 0] and cl2 is False and sw == [1, r0["n"], 1], T("Close closes it, a second tap on the tile closes it, and tapping another player swaps the panel to him"))
            # ---- search
            last = rb["n"].split()[-1] if rb["n"].split()[-1].lower().rstrip(".") not in ("jr", "sr", "ii", "iii", "iv") else rb["n"].split()[-2]
            await pg.fill("#skq", last.lower()); await pg.wait_for_timeout(250)
            s1 = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'); return {h: li ? li.outerHTML : '', n: document.querySelectorAll('#skrl .sk').length, lists: document.getElementById('sksecs').hidden, res: document.getElementById('skres').hidden, panel: !!document.getElementById('skp'), cnt: document.querySelector('#skrh small').textContent, over: document.documentElement.scrollWidth - innerWidth}; })", rb["k"])
            check(s1["h"] == t0["h"] and s1["lists"] and not s1["res"] and not s1["panel"] and s1["n"] >= 1 and s1["over"] <= 0, T(f"typing \"{last.lower()}\" swaps the lists for the search results, and his tile there is letter for letter the tile he has in his list ({s1['n']} found: {s1['cnt']})"))
            team = [p for p in PL if p["t"] == rb["t"]]
            await pg.fill("#skq", rb["tn"]); await pg.wait_for_timeout(250)
            s2 = await pg.evaluate("[...document.querySelectorAll('#skrl .sk')].map(function(x){ return x.getAttribute('data-k'); })")
            check(s2 == [p["k"] for p in team][:24] and len(s2) >= 3, T(f"a team name finds that team, best recent scorer first ({rb['tn']}: {len(s2)} players)"))
            if cold:
                await pg.fill("#skq", cold["n"]); await pg.wait_for_timeout(250)
                s3 = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'); return li ? {cls: li.className, dt: li.querySelector('em').textContent, c: getComputedStyle(li.querySelector('em')).color, up: getComputedStyle(document.querySelector('.skkey .k2')).borderTopColor} : null; })", cold["k"])
                check(bool(s3) and "dn" in s3["cls"] and s3["dt"].startswith("▼ ") and s3["c"] != s3["up"] and cold["k"] not in sum(D["rise"].values(), []), T(f"the search finds a player who is falling and shows him falling: {cold['n']} {s3 and s3['dt']}"))
                await pg.click(f'#skrl .sk[data-k="{cold["k"]}"] .skb'); await pg.wait_for_timeout(500)
                check(await pg.evaluate("(document.querySelector('#skrl .skp h3') || {}).textContent") == cold["n"] and len(await pg.query_selector_all("#skp .skt")) >= 3, T("a searched player opens the same way: his stats under his tile"))
            if out:
                await pg.fill("#skq", out["n"]); await pg.wait_for_timeout(250)
                s4 = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'); return li ? [li.querySelector('.skst').textContent, getComputedStyle(li.querySelector('.skst')).display !== 'none', li.querySelector('.skb').getAttribute('aria-label')] : null; })", out["k"])
                check(bool(s4) and s4[0] == "OUT" and s4[1] and "Out this week" in s4[2] and out["k"] not in sum(D["rise"].values(), []), T(f"a player who is out this week ({out['n']}) is in the search with an OUT tag and on no list"))
            if noted:
                await pg.fill("#skq", noted["n"]); await pg.wait_for_timeout(250)
                s7 = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'); if(!li) return null; var c = li.querySelector('.skst'), r = c.getBoundingClientRect(), t = li.getBoundingClientRect(); return [c.textContent, getComputedStyle(c).display !== 'none', li.querySelector('.skb').getAttribute('aria-label'), r.right <= t.right + 1 && r.width > 10, getComputedStyle(c).backgroundColor]; })", noted["k"])
                await pg.click(f'#skrl .sk[data-k="{noted["k"]}"] .skb'); await pg.wait_for_timeout(600)
                n7 = await pg.evaluate("(function(){ var p = document.getElementById('skp'); if(!p) return null; var n = [...p.querySelectorAll('.skwn')], f = p.querySelector('.skt'); return {t: n.map(function(x){ return x.textContent; }), above: n.length && n[n.length - 1].getBoundingClientRect().bottom <= f.getBoundingClientRect().top + 1, over: document.documentElement.scrollWidth - innerWidth, fs: n.length ? parseFloat(getComputedStyle(n[0]).fontSize) : 0}; })()")
                check(bool(s7) and s7[0] == "NOTE" and s7[1] and s7[3] and "There is a note on his recent games" in s7[2], T(f"a player whose recent games came with a teammate missing wears a NOTE tag that fits on his tile, and his tile says so to a screen reader ({noted['n']})"))
                check(bool(n7) and n7["t"] == noted["nt"] and n7["above"] and n7["over"] <= 0 and n7["fs"] >= 12, T(f"his panel opens with the notes in words, above his stats: {noted['nt'][0][:80]}"))
                if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"stocks_{theme}_note.png"))
                if out:
                    await pg.fill("#skq", out["n"]); await pg.wait_for_timeout(250)
                    oc = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'); return li ? getComputedStyle(li.querySelector('.skst')).backgroundColor : ''; })", out["k"])
                    check(bool(oc) and oc != s7[4], T("an OUT tag is a different colour from a NOTE tag, and both carry the word"))
            longest = max(PL, key=lambda p: len(p["n"]))
            await pg.fill("#skq", longest["n"]); await pg.wait_for_timeout(250)
            ln = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'); if(!li) return null; var n = li.querySelector('.sknm'), b = li.querySelector('.skb').getBoundingClientRect(), r = n.getBoundingClientRect(); return [n.textContent, n.scrollWidth <= n.clientWidth + 1 && n.scrollHeight <= n.clientHeight + 1, r.right <= b.right + 1, document.documentElement.scrollWidth - innerWidth]; })", longest["k"])
            check(bool(ln) and ln[0] == longest["n"] and ln[1] and ln[2] and ln[3] <= 0, T(f"the longest name on the site shows in full on its tile ({longest['n']})"))
            if noted:
                await pg.fill("#skq", noted["n"]); await pg.wait_for_timeout(250)
                su = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'), s = li.querySelector('.sksu'); return [s.innerText.trim(), s.scrollWidth <= s.clientWidth + 1, s.textContent]; })", noted["k"])
                check(su[0] == noted["p"] and su[1] and noted["tn"] in su[2], T(f"a tagged tile on a phone keeps its team badge and position and drops the team name instead of cutting it off ({su[0]})"))
            await pg.fill("#skq", "zzzqq"); await pg.wait_for_timeout(200)
            s5 = await pg.evaluate("[document.querySelectorAll('#skrl .sk').length, document.getElementById('skrn').hidden, document.getElementById('skrn').textContent]")
            await pg.fill("#skq", ""); await pg.wait_for_timeout(200)
            s6 = await pg.evaluate("[document.getElementById('sksecs').hidden, document.getElementById('skres').hidden, document.querySelectorAll('#sksecs [data-for=\"rise\"] .sk').length]")
            check(s5[0] == 0 and s5[1] is False and "No player matches" in s5[2] and s6 == [False, True, nrise], T("a name nobody has says so, and clearing the box brings the lists back"))
            await pg.fill("#skq", last.lower()); await pg.wait_for_timeout(200); await pg.click(".skj a[href='#sk-te']"); await pg.wait_for_timeout(500)
            j = await pg.evaluate("[document.getElementById('skq').value, document.getElementById('sksecs').hidden, Math.round(document.getElementById('sk-te').getBoundingClientRect().top)]")
            check(j[0] == "" and j[1] is False and 40 <= j[2] <= 140, T(f"a position chip clears a search and jumps to that position, clear of the sticky menu (heading {j[2]}px down)"))
            if SHOTS:
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(150); await pg.screenshot(path=os.path.join(SHOTS, f"stocks_{theme}.png"))
                await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(600); await pg.click(f'#skp .skt[data-s="{sid}"]'); await pg.wait_for_timeout(900); await pg.screenshot(path=os.path.join(SHOTS, f"stocks_{theme}_graph.png"))
            if mp:
                full = D["rise"][mp] + D["more"][mp]
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.fill("#skq", ""); await pg.wait_for_timeout(150)
                if await pg.query_selector("#skp"): await pg.click("#skp .skx"); await pg.wait_for_timeout(200)
                await pg.click(f'#sk-{mp.lower()} [data-for="rise"] .skmore'); await pg.wait_for_timeout(350)
                a1 = await pg.evaluate("""(function(pos){ var sec = document.getElementById('sk-' + pos.toLowerCase()).querySelector('div[data-for="rise"]'), t = [...sec.querySelectorAll('.sk')], hd = document.getElementById('sk-' + pos.toLowerCase());
                  return {keys: t.map(function(x){ return x.getAttribute('data-k'); }), btn: !!sec.querySelector('.skmore'), head: hd.querySelector('h2 small[data-for="rise"]').textContent, two: t[t.length - 2].offsetTop === t[t.length - 1].offsetTop || t.length % 2 === 1,
                    over: document.documentElement.scrollWidth - innerWidth, focus: (document.activeElement.closest('.sk') || {getAttribute: function(){ return ''; }}).getAttribute('data-k'), other: document.querySelectorAll('#sksecs [data-for="rise"] .skmore').length}; })""", mp)
                check(a1["keys"] == full and not a1["btn"] and a1["head"] == f"all {len(full)} rising" and a1["over"] <= 0 and a1["focus"] == D["more"][mp][0] and a1["other"] == len(btns) - 1,
                      T(f"\"{btns[mp]}\" adds the rest under the list in order, the heading then says all {len(full)}, and the other positions keep their buttons"))
                await pg.fill("#skq", BY[full[-1]]["n"]); await pg.wait_for_timeout(250)
                hs = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'); return li ? li.outerHTML : ''; })", full[-1])
                await pg.fill("#skq", ""); await pg.wait_for_timeout(200)
                hl = await pg.evaluate("(function(k){ var li = document.querySelector('#sksecs .sk[data-k=\"' + k + '\"]'); return li ? li.outerHTML : ''; })", full[-1])
                await pg.click(f'#sksecs .sk[data-k="{full[-1]}"] .skb'); await pg.wait_for_timeout(600)
                a2 = await pg.evaluate("(function(k){ var li = document.querySelector('#sksecs .sk[data-k=\"' + k + '\"]'), p = document.getElementById('skp'); if(!p) return null; var row = [...li.parentNode.children].filter(function(x){ return x !== p && x.offsetTop === li.offsetTop; }); return [row[row.length - 1].nextElementSibling === p, p.querySelector('h3').textContent, p.querySelectorAll('.skt').length]; })", full[-1])
                check(bool(hs) and hs == hl and bool(a2) and a2[0] and a2[1] == BY[full[-1]]["n"] and a2[2] >= 3, T(f"a tile added that way is the tile the search gives him, and it opens the same way ({BY[full[-1]]['n']})"))
                await pg.click("#skp .skx"); await pg.wait_for_timeout(150)
            # ---- owner 11/22 2:11 AM: the Falling view
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.fill("#skq", ""); await pg.wait_for_timeout(150)
            if await pg.query_selector("#skp"): await pg.click("#skp .skx"); await pg.wait_for_timeout(200)
            VIS = """(function(){ var r = document.getElementById('skm'), vis = function(e){ return e.getClientRects().length > 0; }, t = [...document.querySelectorAll('#sksecs .sk')].filter(vis), g = t.length ? t[0].parentNode.children : [];
              return {mode: r.getAttribute('data-mode'), keys: t.map(function(x){ return x.getAttribute('data-k'); }), dn: t.every(function(x){ return x.classList.contains('dn') && /^▼ /.test(x.querySelector('em').textContent); }), up: t.every(function(x){ return x.classList.contains('up'); }),
                pressed: [...document.querySelectorAll('.skmode button')].map(function(b){ return b.getAttribute('aria-pressed'); }), heads: [...document.querySelectorAll('#sksecs h2 small')].filter(vis).map(function(x){ return x.textContent; }),
                over: document.documentElement.scrollWidth - innerWidth, two: g.length >= 3 && g[0].offsetTop === g[1].offsetTop && g[2].offsetTop > g[0].offsetTop, key: getComputedStyle(document.querySelector('.skkey .k2')).borderTopColor, em: t.length ? getComputedStyle(t[0].querySelector('em')).color : '',
                sw: Math.round(document.querySelector('.skmode button').getBoundingClientRect().height), panel: !!document.getElementById('skp')}; })()"""
            v0 = await pg.evaluate(VIS)
            await pg.tap('.skmode button[data-mode="fall"]'); await pg.wait_for_timeout(300); v1 = await pg.evaluate(VIS)
            fallkeys = [k for a in D["fall"] for k in D["fall"][a]]
            check(v0["mode"] == "rise" and v0["pressed"] == ["true", "false"] and v0["sw"] >= 40 and v1["mode"] == "fall" and v1["pressed"] == ["false", "true"] and v1["keys"] == fallkeys and v1["dn"] and v1["two"] and v1["over"] <= 0,
                  T(f"a Rising / Falling switch sits above the lists; Falling swaps every list for that position's biggest drops, all pointing down ({len(v1['keys'])} tiles)"))
            check(all(h.endswith("falling") for h in v1["heads"]) and len(v1["heads"]) == len(D["fall"]) and v1["key"] == v1["em"] and v1["key"] != v0["key"], T(f"the headings and the colour key follow the switch ({v1['heads'][:2]})"))
            if faller:
                await pg.click(f'#sksecs [data-for="fall"] .sk[data-k="{faller["k"]}"] .skb'); await pg.wait_for_timeout(700)
                f1 = await pg.evaluate("""(function(k){ var li = document.querySelector('#sksecs [data-for="fall"] .sk[data-k="' + k + '"]'), p = document.getElementById('skp'); if(!p) return null; var row = [...li.parentNode.children].filter(function(x){ return x !== p && x.offsetTop === li.offsetTop; });
                  return [row[row.length - 1].nextElementSibling === p, p.querySelector('h3').textContent, [...p.querySelectorAll('.skmv p')].map(function(x){ return x.textContent; }), [...p.querySelectorAll('.skwk p')].map(function(x){ return x.textContent; }), p.querySelector('.skt[data-s="ppr"] .sktv em').textContent]; })""", faller["k"])
                check(bool(f1) and f1[0] and f1[1] == faller["n"] and f1[2] == faller["mv"] and f1[3] == faller["wk"] and f1[4].startswith("▼ "), T(f"a faller opens the same way, with his own what-moved and this-week lines ({faller['n']}: {faller['mv'][-1][:60]})"))
                await pg.click("#skp .skx"); await pg.wait_for_timeout(150)
            if fpos:
                fullf = D["fall"][fpos] + D["fmore"][fpos]
                await pg.click(f'#sk-{fpos.lower()} [data-for="fall"] .skmore'); await pg.wait_for_timeout(350)
                fa = await pg.evaluate("""(function(pos){ var sec = document.getElementById('sk-' + pos.toLowerCase()), w = sec.querySelector('div[data-for="fall"]'); return [[...w.querySelectorAll('.sk')].map(function(x){ return x.getAttribute('data-k'); }), !!w.querySelector('.skmore'), sec.querySelector('h2 small[data-for="fall"]').textContent, sec.querySelector('h2 small[data-for="rise"]').textContent]; })""", fpos)
                check(fa[0] == fullf and not fa[1] and fa[2] == f"all {len(fullf)} falling" and "falling" not in fa[3], T(f"\"{fbtns[fpos]}\" adds the rest of the fallers in order and leaves the rising heading alone"))
            await pg.tap('.skmode button[data-mode="rise"]'); await pg.wait_for_timeout(300); v2 = await pg.evaluate(VIS)
            risekeys = [k for a in D["rise"] for k in (D["rise"][a] + (D["more"][a] if a == mp else []))]
            check(v2["mode"] == "rise" and v2["pressed"] == ["true", "false"] and v2["keys"] == risekeys and v2["up"] and v2["key"] == v0["key"] and not v2["panel"], T("Rising brings the rising lists back as they were left"))
            if faller:
                pg3 = await ctx.new_page(); await pg3.goto(U + "#p=" + faller["k"], wait_until="domcontentloaded"); await pg3.wait_for_selector("#skm[data-ready='1']", timeout=8000); await pg3.wait_for_timeout(400)
                dl = await pg3.evaluate("[document.getElementById('skm').getAttribute('data-mode'), (document.querySelector('.skp h3') || {}).textContent, !!document.querySelector('#sksecs [data-for=\"fall\"] .skp')]")
                check(dl == ["fall", faller["n"], True], T(f"a link to a player on a falling list opens the Falling view on him ({dl})")); await pg3.close()
            # a link to one player: /stocks/#p=<slug>
            who = cold or out or r0
            pg2 = await ctx.new_page(); await pg2.goto(U + "#p=" + who["k"], wait_until="domcontentloaded"); await pg2.wait_for_selector("#skm[data-ready='1']", timeout=8000); await pg2.wait_for_timeout(400)
            check(await pg2.evaluate("(document.querySelector('.skp h3') || {}).textContent") == who["n"], T(f"/stocks/#p={who['k']} opens straight to {who['n']}"))
            await ctx.close()
        # ---- desktop: more tiles to a row, the panel still spans the row
        ctx = await b.new_context(viewport={"width": 1280, "height": 900})
        await ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        await pg.goto(U, wait_until="domcontentloaded"); await pg.wait_for_selector("#skm[data-ready='1']", timeout=8000); await pg.wait_for_timeout(400)
        await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(600); await pg.click(f'#skp .skt[data-s="{sid}"]'); await pg.wait_for_timeout(800)
        w = await pg.evaluate("""(function(){ var g = document.querySelector('#sksecs .skg'), t = [...g.children].filter(function(x){ return x.classList.contains('sk'); }), per = t.filter(function(x){ return x.offsetTop === t[0].offsetTop; }).length, p = document.getElementById('skp'), box = document.getElementById('skcw');
          return {per: per, full: Math.abs(p.getBoundingClientRect().width - g.getBoundingClientRect().width) < 2, over: document.documentElement.scrollWidth - innerWidth, cw: box.getBoundingClientRect().width, sw: box.querySelector('svg').getBoundingClientRect().width, dots: box.querySelectorAll('circle.dt, circle.dt2').length}; })()""")
        check(w["per"] >= 4 and w["full"] and w["over"] <= 0 and not errs and abs(w["cw"] - w["sw"]) < 2 and w["cw"] <= 900 and w["dots"] == len(ser), f"[desktop] {w['per']} tiles to a row, the panel spans the row, the graph keeps a readable width ({w['cw']:.0f}px), no script error")
        await pg.set_viewport_size({"width": 700, "height": 900}); await pg.wait_for_timeout(600)
        z = await pg.evaluate("""(function(k){ var li = document.querySelector('#sksecs .sk[data-k="' + k + '"]'), p = document.getElementById('skp'), box = document.getElementById('skcw'), b = p.querySelector('.skt[aria-pressed="true"]');
          var row = [...li.parentNode.children].filter(function(x){ return x !== p && x.offsetTop === li.offsetTop; }), srow = [...b.parentNode.children].filter(function(x){ return x !== box && x.offsetTop === b.offsetTop; });
          return [row[row.length - 1].nextElementSibling === p, srow[srow.length - 1].nextElementSibling === box, Math.abs(box.querySelector('svg').getBoundingClientRect().width - box.getBoundingClientRect().width) < 2, document.documentElement.scrollWidth - innerWidth <= 0]; })""", rb["k"])
        check(z == [True, True, True, True], "[desktop] narrowing the window re-seats the panel under his row and the graph under its stat, redrawn to fit")
        await pg.set_viewport_size({"width": 1280, "height": 900}); await pg.wait_for_timeout(500)
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "stocks_desktop.png"))
        if noted:
            await pg.fill("#skq", noted["n"]); await pg.wait_for_timeout(250)
            dsu = await pg.evaluate("(function(k){ var li = document.querySelector('#skrl .sk[data-k=\"' + k + '\"]'), s = li.querySelector('.sksu'); return [s.innerText.trim(), s.scrollWidth <= s.clientWidth + 1]; })", noted["k"])
            check(noted["tn"] in dsu[0] and dsu[1], f"[desktop] a tagged tile has room for the team name and shows it ({dsu[0]})")
        if mp:
            await pg.fill("#skq", ""); await pg.wait_for_timeout(200)
            lastk = D["rise"][mp][-1]
            await pg.click(f'#sksecs .sk[data-k="{lastk}"] .skb'); await pg.wait_for_timeout(500)
            await pg.click(f'#sk-{mp.lower()} [data-for="rise"] .skmore'); await pg.wait_for_timeout(400)
            g = await pg.evaluate("""(function(k){ var li = document.querySelector('#sksecs .sk[data-k="' + k + '"]'), p = document.getElementById('skp'); if(!p) return null;
              var row = [...li.parentNode.children].filter(function(x){ return x !== p && x.offsetTop === li.offsetTop; }), first = [...li.parentNode.children].filter(function(x){ return x.offsetTop === li.parentNode.children[0].offsetTop; }).length;
              return [row[row.length - 1].nextElementSibling === p, row.length, first, li.querySelector('.skb').getAttribute('aria-expanded'), li.parentNode.querySelectorAll('.sk').length, document.querySelectorAll('.skp').length]; })""", lastk)
            check(bool(g) and g[0] and g[1] == g[2] and g[3] == "true" and g[4] == len(D["rise"][mp]) + len(D["more"][mp]) and g[5] == 1,
                  f"[desktop] growing a list with a player open keeps his panel under his row, which is now a full row ({g[1] if g else 0} tiles)")
        await ctx.close(); await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
