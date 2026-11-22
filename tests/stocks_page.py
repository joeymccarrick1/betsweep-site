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

    # ---- owner 11/22 11:42 AM ("Anything else you can do to the stock market page to make it a little more interesting? Added stats?"):
    # weekly finishes, the numbers at the top of a player's box, rates, and the market-movers cards - each redone here from the shipped games
    FR = C["fr"]; WEEK = D["week"]; SDEF = {s_["id"]: s_ for s_ in D["stats"]}; NUM = re.compile(r"\d+(?:\.\d+)?")
    def same(a, b, tol=0.051):   # the same words with the same numbers; a number may differ by a rounding of its last digit (the page rounds in the browser, this test in Python)
        na, nb = NUM.findall(a or ""), NUM.findall(b or "")
        return NUM.sub("#", a or "") == NUM.sub("#", b or "") and len(na) == len(nb) and all(abs(float(x) - float(y)) <= tol for x, y in zip(na, nb))
    pts = lambda p: [g[C["ppr"]] for g in p["g"]]
    fins = lambda p: [g[FR] for g in p["g"] if g[FR] is not None]
    badf = []; byw = {}; gap = 0
    for p in PL:
        for g in p["g"]:
            if (g[FR] is None) != (g[0] >= WEEK): badf.append((p["n"], g[0], g[FR]))
            if g[FR] is not None: byw.setdefault((p["p"], g[0]), []).append((g[C["ppr"]], g[FR], p["n"]))
    for key, v in byw.items():
        v.sort(reverse=True)
        for j, a in enumerate(v):
            among = 1 + sum(1 for b_ in v if b_[0] > a[0])
            if a[1] <= 24: gap = max(gap, a[1] - among)
            if a[1] < among or (a[1] <= 24 and a[1] - among > 4): badf.append((key, a))   # players with no page are counted too: they can only push a finish back, and near the top only a place or two
            if j and ((v[j - 1][0] == a[0]) != (v[j - 1][1] == a[1]) or v[j - 1][1] > a[1]): badf.append((key, "order", v[j - 1], a))   # more points, better finish; level points, the same finish
    check(not badf and len(byw) >= 4 * (WEEK - 2) and all(min(x[1] for x in v) <= 2 for v in byw.values()),
          f"every game of a finished week carries where it ranked at his position that week, in step with the scores; the week being played carries none ({len(byw)} position-weeks; the furthest a player with no page pushes a top-24 finish back: {gap}; off: {badf[:2]})")
    def series(p, sd):
        if sd.get("den"): return [(g[0], g[1], (g[C[sd["num"]]] or 0) / g[C[sd["den"]]] * (100 if sd["pct"] else 1), g[C[sd["den"]]]) for g in p["g"] if (g[C[sd["den"]]] or 0) >= sd["dmin"]]
        return [(g[0], g[1], g[C[sd["col"]]], 1) for g in p["g"] if g[C[sd["col"]]] is not None]
    def wtrend(ser):   # averages weighted by each game's chances: for a rate that is total over total, for anything else the plain average
        k = window(len(ser)); wa = lambda rows: sum(x[2] * x[3] for x in rows) / sum(x[3] for x in rows)
        if not k: return 0, wa(ser), None, None
        return k, wa(ser[-k:]), wa(ser[:-k]), wa(ser[-k:]) - wa(ser[:-k])
    def offered_ids(p):
        out = []
        for i_ in D["order"][p["p"]]:
            sd = SDEF[i_]; ser_ = series(p, sd)
            if (len(ser_) >= 3) if sd.get("den") else (bool(ser_) and sum(x[2] or 0 for x in ser_) >= sd["min"]): out.append(i_)
        return out
    rates = [s_ for s_ in D["stats"] if s_.get("den")]
    check(len(rates) >= 5 and all(any(s_["id"] in D["order"][a] for a in D["order"]) and s_["dmin"] >= 3 and s_["dn"] for s_ in rates) and all("ppr" == D["order"][a][0] for a in D["order"]),
          f"the stats on offer now include rates, each with the fewest chances a game needs to count: {', '.join(s_['l'] + ' (' + str(s_['dmin']) + '+ ' + s_['dn'] + ')' for s_ in rates)}")
    RK = {}
    for p in PL:
        v = pts(p); k, r, b_, d_, _ = trend(v); o = RK.setdefault(p["p"], {"now": [], "was": [], "sea": []})
        if k and p["ac"]: o["now"].append(r); o["was"].append(b_)
        if len(v) >= 4: o["sea"].append(sum(v) / len(v))
    place = lambda lst, x: 1 + sum(1 for y in lst if y > x + 1e-9)
    def run12(p):
        n = 0
        for f in reversed(fins(p)):
            if f > 12: break
            n += 1
        return n
    def streak(v, up=True):
        n = 0
        for j in range(len(v) - 1, 0, -1):
            if not (v[j] > v[j - 1] if up else v[j] < v[j - 1]): break
            n += 1
        return n
    def quote(p):
        """what the top of his box must say: the cells [label, value, small], then the range line, or None with fewer than two games"""
        v = pts(p); n = len(v); k, r, b_, d_, _ = trend(v); a = sum(v) / n; R = RK[p["p"]]; cells = []
        if k and p["ac"]: cells.append(["Rank now", f"{p['p']}{place(R['now'], r)}", f"was {p['p']}{place(R['was'], b_)}"])
        cells.append(["Season", f"{a:.1f}", "a game" + (f" · {p['p']}{place(R['sea'], a)}" if n >= 4 else "")])
        f = fins(p)
        if f:
            t12 = sum(1 for x in f if x <= 12); t24 = sum(1 for x in f if x <= 24)
            cells.append(["Top-12 weeks", f"{t12} of {len(f)}", f"last {run12(p)} in a row" if run12(p) >= 2 else (f"top 24: {t24}" if p["p"] in ("RB", "WR") else "")])
        if n < 2: return cells, None
        hi, lo, last = max(v), min(v), v[-1]; ih = n - 1 - v[::-1].index(hi); il = n - 1 - v[::-1].index(lo); up, dn = streak(v), streak(v, False)
        tag = ", his season high" if n >= 4 and last == hi and v.count(hi) == 1 else (", his season low" if n >= 4 and last == lo and v.count(lo) == 1 else "")
        runs = f"Improved in {up} straight games." if up >= 2 else (f"Dropped in {dn} straight games." if dn >= 2 else "")
        at = lambda x: 50.0 if hi - lo < 1e-9 else (x - lo) / (hi - lo) * 100
        return cells, {"lo": [f"{lo:.1f}", f"low · Wk {p['g'][il][0]}"], "hi": [f"{hi:.1f}", f"high · Wk {p['g'][ih][0]}"], "cap": f"Last game: {last:.1f} in Week {p['g'][-1][0]}{tag}. Average: {a:.1f}." + (" " + runs if runs else ""), "avg": at(a), "last": at(last)}
    def movers():
        """the cards, redone: [id, player key, value, words after it]"""
        mean = lambda v: sum(v) / len(v); live = [p for p in PL if p["ac"] and p["st"] not in ("Out", "Doubtful")]; out = []; fl = D["floor"]
        c = sorted([p for p in live if p["up"]], key=lambda p: (-p["d"], p["n"]))
        if c: out.append(["rise", c[0]["k"], c[0]["f"]["dt"], "a game"])
        c = sorted([p for p in live if p["dn"]], key=lambda p: (p["d"], p["n"]))
        if c: out.append(["fall", c[0]["k"], c[0]["f"]["dt"], "a game"])
        c = sorted([(-p["d"], p["n"], p) for p in live if p["up"] and mean(pts(p)[:-p["kw"]]) < fl[p["p"]]], key=lambda t: t[:2])
        if c: p = c[0][2]; out.append(["break", p["k"], f"{mean(pts(p)[-p['kw']:]):.1f}", f"a game, from {mean(pts(p)[:-p['kw']]):.1f}"])
        c = sorted([p for p in live if len(p["g"]) >= 4 and pts(p)[-1] == max(pts(p)) and pts(p).count(max(pts(p))) == 1], key=lambda p: (-pts(p)[-1], p["n"]))
        if c: out.append(["high", c[0]["k"], f"{pts(c[0])[-1]:.1f}", f"in Week {c[0]['g'][-1][0]}"])
        c = sorted([p for p in live if run12(p) >= 2], key=lambda p: (-run12(p), -p["r"], p["n"]))
        if c: out.append(["run", c[0]["k"], f"{run12(c[0])} straight", "top-12 weeks"])
        t12 = lambda p: sum(1 for f in fins(p) if f <= 12)
        c = sorted([p for p in live if t12(p) >= 1], key=lambda p: (-t12(p), len(fins(p)), -mean(pts(p)), p["n"]))
        if c: out.append(["most", c[0]["k"], f"{t12(c[0])} of {len(fins(c[0]))}", "top-12 weeks"])
        c = sorted([p for p in live if len(p["g"]) >= 6 and mean(pts(p)) >= fl[p["p"]]], key=lambda p: (-min(pts(p)), -mean(pts(p)), p["n"]))
        if c: out.append(["floor", c[0]["k"], f"{min(pts(c[0])):.1f}", "his worst game"])
        c = sorted([p for p in live if streak(pts(p)) >= 3 and pts(p)[-1] >= fl[p["p"]]], key=lambda p: (-streak(pts(p)), -pts(p)[-1], p["n"]))
        if c: out.append(["climb", c[0]["k"], f"{streak(pts(c[0]))} straight", "games, each better"])
        return out
    MK = D.get("mk") or []; wantm = movers()
    check([[c["id"], c["k"], c["v"], c["s"]] for c in MK] == wantm and len(MK) >= 6 and len({c["id"] for c in MK}) == len(MK),
          f"the market-movers cards are the leaders the shipped games give, each redone here: {'; '.join(c['l'] + ' ' + BY[c['k']]['n'] + ' ' + c['v'] + ' ' + c['s'] for c in MK)}" + (f" (off: {[x for x in zip([[c['id'], c['k'], c['v'], c['s']] for c in MK], wantm) if x[0] != x[1]][:2]})" if [[c["id"], c["k"], c["v"], c["s"]] for c in MK] != wantm else ""))
    check(all(BY[c["k"]]["ac"] and BY[c["k"]]["st"] not in ("Out", "Doubtful") for c in MK) and not any(re.search(r"\b(will|should|expect|likely|buy|sell)\b", c["l"] + " " + c["say"], re.I) for c in MK),
          "every card's player could be on a list (played lately, not ruled out), and no card forecasts anything")
    cardhtml = re.findall(r'<button type="button" class="skmc[^"]*" data-k="([^"]+)" data-m="([a-z]+)"', page)
    check(cardhtml == [(c["k"], c["id"]) for c in MK] and page.index('class="skmk"') < page.index('class="skmode"') and page.index('id="skq"') < page.index('class="skmk"'),
          "the cards are written into the page (they show before any script runs), under the search box and above the Rising / Falling switch")
    short = next((p for p in PL if 2 <= len(p["g"]) <= 3), None); single = next((p for p in PL if len(p["g"]) == 1), None)
    benched = next((p for p in PL if not p["ac"] and len(p["g"]) >= 6), None)

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
            check(d["firsttile"] < 844 * 0.72 and d["screens"] <= 7.7, T(f"the first list starts on the first screen ({d['firsttile']:.0f}px down) and the page is {d['screens']:.1f} screens long"))
            mk = await pg.evaluate("""(function(){ var ul = document.querySelector('.skml'), cs = [...document.querySelectorAll('.skmc')], r = function(e){ var b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
              return {n: cs.length, box: r(ul), cards: cs.map(r), inner: ul.scrollWidth - ul.clientWidth, over: document.documentElement.scrollWidth - innerWidth, vw: innerWidth,
                rows: cs.map(function(c){ return {m: c.getAttribute('data-m'), k: c.getAttribute('data-k'), l: c.querySelector('.skmt').textContent, n: c.querySelector('.skmn').textContent, t: c.querySelector('.sktb').textContent, p: c.querySelector('.skmw span').textContent,
                  v: c.querySelector('.skmx b').textContent, s: c.querySelector('.skmx small').textContent, a: c.getAttribute('aria-label'), sp: c.querySelector('svg.sksp .ska').getAttribute('d').length > 10, cut: c.querySelector('.skmn').scrollWidth > c.querySelector('.skmn').clientWidth + 1 || c.querySelector('.skmx').scrollWidth > c.querySelector('.skmx').clientWidth + 1,
                  vc: getComputedStyle(c.querySelector('.skmx b')).color}; }), ink: getComputedStyle(document.querySelector('.skmn')).color}; })()""")
            check(mk["n"] == len(MK) and all(r_["m"] == c["id"] and r_["k"] == c["k"] and r_["l"] == c["l"] and r_["n"] == BY[c["k"]]["n"] and r_["t"] == BY[c["k"]]["t"] and r_["p"] == BY[c["k"]]["p"] and r_["v"] == c["v"] and r_["s"] == c["s"] and r_["sp"] and c["say"] in r_["a"] and BY[c["k"]]["n"] in r_["a"] for r_, c in zip(mk["rows"], MK)),
                  T(f"each card shows its count, the player, his team and position, a small graph and the number ({mk['n']} cards: {', '.join(r_['l'] for r_ in mk['rows'][:4])} ...)"))
            check(mk["over"] <= 0 and mk["inner"] > 40 and mk["cards"][0][0] >= 0 and mk["cards"][1][2] <= mk["vw"] and mk["cards"][2][0] < mk["vw"] - 8 < mk["vw"] < mk["cards"][2][2] and mk["box"][3] < 844 * 0.55 and all(c[3] - c[1] >= 88 for c in mk["cards"]) and max(c[3] - c[1] for c in mk["cards"]) - min(c[3] - c[1] for c in mk["cards"]) < 2,
                  T(f"on a phone the cards are one swipe row on the first screen: two in full, the third peeking in to show there are more, all one height, and the page itself does not scroll sideways (row ends {mk['box'][3]:.0f}px down)"))
            check(not any(r_["cut"] for r_ in mk["rows"]) and all((r_["vc"] != mk["ink"]) == (c["id"] in ("rise", "fall")) for r_, c in zip(mk["rows"], MK)), T("no card cuts off its name or its number; only the rise and the drop wear the up and down colours"))
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
            offered = offered_ids(rb)
            check(bool(p1) and p1["after"] and p1["full"] and p1["ex"] == "true" and p1["h3"] == rb["n"] and not p1["chart"], T("tapping a tile opens his stats in a full-width panel right under his row; no graph until a stat is picked"))
            check(bool(p1) and p1["notes"] == rb["nt"], T(f"his panel carries exactly the notes his data has ({len(rb['nt'])})"))
            check(bool(p1) and p1["mv"] == rb["mv"] and p1["wk"] == rb["wk"] and len(rb["mv"]) >= 1 and len(rb["wk"]) >= 1 and p1["heads"] == ["What moved", "This week"] and 0 < p1["fxtop"] <= p1["sttop"] + 1,
                  T(f"above his stats the panel says what moved and what his week holds: {rb['mv'][0][:60]} | {rb['wk'][0][:50]}"))
            check(bool(p1) and p1["ids"] == offered and p1["two"] and p1["tap"] >= 56 and p1["sp"] and p1["over"] <= 0, T(f"the panel offers his stats to pick from, two to a row, each with its own small graph: {', '.join(p1['ids']) if p1 else ''}"))
            num = lambda s: [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]
            check(bool(p1) and p1["fv"] == t0["val"] and p1["fd"] == t0["dt"] and len(num(p1["fan"])) == len(num(t0["d"])) and max(abs(a - c) for a, c in zip(num(p1["fan"]), num(t0["d"]))) <= 0.11,
                  T("his Fantasy points stat is the tile's number, arrow and graph again (the page script and the build draw the same picture)"))
            check(bool(p1) and p1["link"] == f"/player/{rb['k']}/" and os.path.exists(os.path.join(ROOT, "player", rb["k"], "index.html")), T("the panel links to his player page, and that page exists"))
            QT = r"""(function(){ var p = document.getElementById('skp'); if(!p) return null; var q = p.querySelector('.skqt'), g = p.querySelector('.skrg'), c = p.querySelector('.skrc'), tx = function(e){ return e ? e.textContent : ''; }, pct = function(e){ return e ? parseFloat(e.style.left) : -1; };
              var cells = q ? [...q.querySelectorAll('.skqc')] : [], first = p.querySelector('.skwn, .skfx, .skpq');
              return {cells: cells.map(function(x){ return [tx(x.querySelector('span')), tx(x.querySelector('b')), tx(x.querySelector('small')).replace(/\u00a0/g, '')]; }), bar: !!g, lo: g ? [tx(g.querySelector('.skre b')), tx(g.querySelector('.skre small'))] : null,
                hi: g ? [tx(g.querySelector('.skre.hi b')), tx(g.querySelector('.skre.hi small'))] : null, avg: g ? pct(g.querySelector('.skrv')) : -1, last: g ? pct(g.querySelector('.skrx')) : -1, cap: tx(c).replace(/\s+/g, ' ').trim(), aria: g ? g.getAttribute('aria-label') : '',
                above: !!q && !!first && q.getBoundingClientRect().bottom <= first.getBoundingClientRect().top + 1, one: cells.length ? cells.every(function(x){ return Math.abs(x.offsetTop - cells[0].offsetTop) < 2; }) : false, cut: cells.some(function(x){ var b = x.querySelector('b'); return b.scrollWidth > x.clientWidth; }),
                over: document.documentElement.scrollWidth - innerWidth, w: q ? q.getBoundingClientRect().width : 0, pw: p.getBoundingClientRect().width}; })()"""
            def quote_ok(q_, p_):
                cells, rng = quote(p_)
                if not q_ or len(q_["cells"]) != len(cells) or not all(a_[0] == b_[0] and same(a_[1], b_[1]) and same(a_[2], b_[2]) for a_, b_ in zip(q_["cells"], cells)): return False
                if rng is None: return not q_["bar"] and not q_["cap"]
                return q_["bar"] and same(q_["lo"][0], rng["lo"][0]) and q_["lo"][1] == rng["lo"][1] and same(q_["hi"][0], rng["hi"][0]) and q_["hi"][1] == rng["hi"][1] and same(q_["cap"], rng["cap"]) and abs(q_["avg"] - rng["avg"]) <= 0.11 and abs(q_["last"] - rng["last"]) <= 0.11
            q1 = await pg.evaluate(QT); qc, qr = quote(rb)
            check(quote_ok(q1, rb) and len(qc) == 3 and q1["above"] and q1["one"] and not q1["cut"] and q1["over"] <= 0,
                  T(f"his box opens with his numbers, redone here from his games: {' | '.join(' '.join(x for x in c_ if x) for c_ in qc)}") + (f" (page: {q1['cells'] if q1 else None})" if not quote_ok(q1, rb) else ""))
            check(bool(q1) and bool(qr) and q1["bar"] and 0 <= q1["avg"] <= 100 and 0 <= q1["last"] <= 100 and "season range" in q1["aria"].lower(), T(f"under them his season's range, low to high, with his average and his last game marked on it: {qr['lo'][0]} to {qr['hi'][0]} · {qr['cap']}"))
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
            # ---- a rate (yards per carry, yards per target, yards per attempt): total over total, games with too few chances left out
            rid = next((x for x in ("ypc", "ypt", "ypa") if x in offered), None)
            if rid:
                rd = SDEF[rid]; rs = series(rb, rd); rk, rr, rbf, rdd = wtrend(rs); left = len(rb["g"]) - len(rs)
                rm = lambda v: (f"{round(v)}%" if rd["pct"] else f"{v:.1f}")
                await pg.click(f'#sksecs .sk[data-k="{rb["k"]}"] .skb'); await pg.wait_for_timeout(500); await pg.click(f'#skp .skt[data-s="{rid}"]'); await pg.wait_for_timeout(800)
                rt = await pg.evaluate(r"""(function(sid){ var b = document.querySelector('#skp .skt[data-s="' + sid + '"]'), box = document.getElementById('skcw'); if(!b || !box) return null;
                  return {v: b.querySelector('.sktv b').textContent, d: b.querySelector('.sktv em').textContent.replace(/\u00a0/g, ''), dots: box.querySelectorAll('circle.dt, circle.dt2').length, hot: box.querySelectorAll('circle.dt2').length, cc: box.querySelector('.skcc').textContent.replace(/\s+/g, ' ').trim(),
                    rows: [...box.querySelectorAll('.sktbl tbody tr')].map(function(r){ return r.children[2].textContent; }), ttl: box.querySelector('.skct').textContent, over: document.documentElement.scrollWidth - innerWidth}; })""", rid)
                tot = lambda rows, c_: sum(g[C[c_]] for g in rows); kept = [g for g in rb["g"] if (g[C[rd["den"]]] or 0) >= rd["dmin"]]
                plain = sum(x[2] for x in rs[-rk:]) / rk if rk else None
                check(bool(rt) and rt["ttl"] == rd["l"] and same(rt["v"], rm(rr)) and rt["dots"] == len(rs) == len(kept) and rt["hot"] == rk and (not rk or abs(rr - tot(kept[-rk:], rd["num"]) / tot(kept[-rk:], rd["den"]) * (100 if rd["pct"] else 1)) < 1e-9),
                      T(f"{rd['l']} is total over total: {rm(rr)} over his last {rk} ({tot(kept[-rk:], rd['num']) if rk else 0} on {tot(kept[-rk:], rd['den']) if rk else 0} {rd['dn']}" + (f"; the plain average of those games would say {plain:.2f}" if rk else "") + f"), {len(rs)} games on the graph"))
                check(bool(rt) and (not rk or (same(rt["cc"].split("Left out")[0].strip(), f"Last {rk} games: {rm(rr)} {rd['u']}. Before that: {rm(rbf)}.") and same(rt["d"], dtxt(rdd, rd["flat"])))) and (("Left out: " + str(left) + " game") in rt["cc"]) == (left > 0) and (left == 0 or f"fewer than {rd['dmin']} {rd['dn']}" in rt["cc"]) and rt["over"] <= 0,
                      T(f"its graph says both averages in words and what it left out ({left} game{'s' if left != 1 else ''} with too few {rd['dn']}): {rt['cc'][:110] if rt else ''}"))
                await pg.click("#skp .skx"); await pg.wait_for_timeout(200)
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
            await pg2.close()
            # ---- the numbers for players of other kinds: off the lists, out, a short season, one game
            kinds = [(x_, w_) for x_, w_ in ((cold, "a player who is falling"), (benched, "a player who has missed his team's last two games"), (short, "a player with two or three games"), (single, "a player with one game")) if x_]
            okq = []
            for x_, w_ in kinds:
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.fill("#skq", x_["n"]); await pg.wait_for_timeout(250); await pg.click(f'#skrl .sk[data-k="{x_["k"]}"] .skb'); await pg.wait_for_timeout(500)
                qx = await pg.evaluate(QT); cx, rx_ = quote(x_); okq.append((w_, x_["n"], quote_ok(qx, x_) and (qx["over"] <= 0), [c_[0] for c_ in cx], bool(rx_)))
            check(all(o[2] for o in okq) and len(okq) >= 3, T("the same numbers hold for every kind of player: " + "; ".join(f"{o[0]} ({o[1]}): {', '.join(o[3])}{', range' if o[4] else ', no range yet'}" for o in okq) + (f" (off: {[o[1] for o in okq if not o[2]]})" if not all(o[2] for o in okq) else "")))
            if benched: check("Rank now" not in [c_[0] for c_ in quote(benched)[0]], T(f"a player who has not played lately gets no Rank now ({benched['n']})"))
            hid = await pg.evaluate("[document.getElementById('skmk').hidden, document.getElementById('skmk').getClientRects().length]")
            await pg.fill("#skq", ""); await pg.wait_for_timeout(200)
            back = await pg.evaluate("[document.getElementById('skmk').hidden, document.querySelectorAll('.skmc').length]")
            check(hid == [True, 0] and back == [False, len(MK)], T("the cards step aside while a search is on and come back when it is cleared"))
            # ---- tap each card: it opens that player wherever his tile is
            took = []
            for c in MK:
                await pg.evaluate("(function(){ window.scrollTo(0, 0); var q = document.getElementById('skq'); if(q.value){ q.value = ''; q.dispatchEvent(new Event('input')); } var x = document.querySelector('#skp .skx'); if(x) x.click(); var b = document.querySelector('.skmode button[data-mode=\"rise\"]'); if(b.getAttribute('aria-pressed') !== 'true') b.click(); })()"); await pg.wait_for_timeout(200)
                where = await pg.evaluate("(function(k){ return document.querySelector('#sksecs [data-for=\"rise\"] .sk[data-k=\"' + k + '\"]') ? 'rise' : (document.querySelector('#sksecs [data-for=\"fall\"] .sk[data-k=\"' + k + '\"]') ? 'fall' : 'search'); })", c["k"])
                await pg.click(f'.skmc[data-m="{c["id"]}"]'); await pg.wait_for_timeout(900)
                got = await pg.evaluate("""(function(k){ var p = document.getElementById('skp'), li = p && p.parentNode.querySelector('.sk[data-k="' + k + '"]'); if(!p || !li) return null;
                  return {h3: p.querySelector('h3').textContent, mode: document.getElementById('skm').getAttribute('data-mode'), q: document.getElementById('skq').value, res: !document.getElementById('skres').hidden, inlist: !!p.closest('#sksecs'), fall: !!p.closest('[data-for="fall"]'),
                    top: li.getBoundingClientRect().top, ex: li.querySelector('.skb').getAttribute('aria-expanded'), cells: p.querySelectorAll('.skqc').length}; })""", c["k"])
                nm = BY[c["k"]]["n"]
                good = bool(got) and got["h3"] == nm and got["ex"] == "true" and 40 <= got["top"] <= 320 and got["cells"] >= 2 and ((where == "rise" and got["mode"] == "rise" and got["inlist"] and not got["fall"] and got["q"] == "") or (where == "fall" and got["mode"] == "fall" and got["fall"] and got["q"] == "") or (where == "search" and got["res"] and got["q"] == nm and not got["inlist"]))
                took.append((c["l"], nm, where, good, got and round(got["top"])))
            check(all(t_[3] for t_ in took) and len(took) == len(MK), T("tapping a card opens that player's box with his tile in view: " + "; ".join(f"{t_[0]} → {t_[1]} ({'his list' if t_[2] == 'rise' else 'the Falling list' if t_[2] == 'fall' else 'found by search'})" for t_ in took) + (f" (off: {[t_ for t_ in took if not t_[3]]})" if not all(t_[3] for t_ in took) else "")))
            check(len({t_[2] for t_ in took}) >= 2, T(f"the cards reach players in more than one place ({sorted({t_[2] for t_ in took})})"))
            if SHOTS:
                await pg.evaluate("(function(){ window.scrollTo(0, 0); var q = document.getElementById('skq'); if(q.value){ q.value = ''; q.dispatchEvent(new Event('input')); } var x = document.querySelector('#skp .skx'); if(x) x.click(); var b = document.querySelector('.skmode button[data-mode=\"rise\"]'); if(b.getAttribute('aria-pressed') !== 'true') b.click(); })()"); await pg.wait_for_timeout(250)
                await pg.screenshot(path=os.path.join(SHOTS, f"stocks_{theme}_movers.png")); await pg.click(f'.skmc[data-m="{MK[0]["id"]}"]'); await pg.wait_for_timeout(900); await pg.screenshot(path=os.path.join(SHOTS, f"stocks_{theme}_numbers.png"))
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
        dm = await pg.evaluate("""(function(){ var ul = document.querySelector('.skml'), cs = [...document.querySelectorAll('.skmc')], t0 = cs[0].getBoundingClientRect().top, q = document.querySelector('#skp .skqt');
          return {per: cs.filter(function(c){ return Math.abs(c.getBoundingClientRect().top - t0) < 2; }).length, inner: ul.scrollWidth - ul.clientWidth, n: cs.length, cut: cs.some(function(c){ var x = c.querySelector('.skmx'); return x.scrollWidth > x.clientWidth + 1; }), qw: q ? q.getBoundingClientRect().width : 0}; })()""")
        check(dm["per"] == min(4, dm["n"]) and dm["inner"] <= 1 and not dm["cut"] and 0 < dm["qw"] <= 600, f"[desktop] the cards sit four to a row with nothing to swipe, and a player's numbers keep a readable width ({dm['qw']:.0f}px)")
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
