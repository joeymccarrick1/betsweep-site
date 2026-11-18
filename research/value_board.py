#!/usr/bin/env python3
"""value_board.py - our trade values against the market's: which called the next weeks better? (owner 11/17: "blend into ours until
we can beat it" - this is the check that says when.)

Nothing new has to be saved for it. Every Tuesday build of the Trade calculator is already in the site's history (trade/index.html and
its data file), and the page puts both numbers on every player: `ours` (the model's own value) and `mv` (the market's - FantasyCalc,
from real trades), on the same 0-9,999 scale. For each week's FIRST build this script opens that week's page as it was published,
reads both numbers in the redraft format (1QB, PPR, 12 teams - the page's default), and compares each with what the players then did:
PPR points per game from that week on (nflverse weekly stats, in/stats_player_week_<season>.csv).

  rank    Spearman rank correlation with what followed, inside each position, over the players either side had as startable
          (QB 24, RB 48, WR 60, TE 24 by the higher of the two numbers) who then played. Higher = called it better.
  gaps    players the two numbers disagreed on by 1,500+ : whose side did the next weeks take? (his place among those players
          by points per game afterwards - closer to his place by our number or by the market's)
  drift   the same disagreements: by the latest build, had the market's own number moved toward ours or away? (redraft and dynasty)

    python3 research/value_board.py                 prints the table
    python3 research/value_board.py --write         also writes research/value_board.json

Needs the site history (a clone with origin/main: --hist, default /tmp/fg/hist; blobs are fetched as needed), a built site to serve the
page's scripts (--site, default ./site), and Playwright. Run it on Tuesdays once the week's stats are in."""
import argparse, asyncio, csv, functools, http.server, json, math, os, re, subprocess, sys, threading
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "research" else os.path.dirname(os.path.abspath(__file__))
TOP = {"QB": 24, "RB": 48, "WR": 60, "TE": 24}; GAP = 1500; PORT = 8866

def _nn(s): return re.sub(r"[^a-z]", "", str(s).lower().replace(" jr", "").replace(" sr", "").replace(" iii", "").replace(" ii", ""))
def git(hist, *a): return subprocess.run(["git", "-C", hist] + list(a), capture_output=True, text=True, check=True).stdout

def first_builds(hist):
    """{week: commit} - the first 'Week N boards' commit of each week that touched the trade page."""
    out = {}
    for ln in git(hist, "log", "origin/main", "--reverse", "--format=%h %s", "--", "trade/index.html").splitlines():
        m = re.match(r"(\w+) Week (\d+) boards", ln)
        if m and int(m.group(2)) not in out: out[int(m.group(2))] = m.group(1)
    return out

def spearman(xs, ys):
    n = len(xs)
    if n < 8: return None
    def rk(v):
        o = sorted(range(n), key=lambda i: v[i]); r = [0.0] * n; i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]: j += 1
            for k in range(i, j + 1): r[o[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    a, b = rk(xs), rk(ys); ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else None

def realized(in_dir, season):
    """{(norm name, pos): {week: ppr points}} for regular-season weeks."""
    out = {}
    with open(os.path.join(in_dir, f"stats_player_week_{season}.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r.get("season_type") != "REG" or r.get("position") not in TOP: continue
            try: out.setdefault((_nn(r["player_display_name"]), r["position"]), {})[int(r["week"])] = float(r.get("fantasy_points_ppr") or 0)
            except ValueError: pass
    return out

async def read_pages(hist, site, builds):
    """{week: {"redraft": [...], "dynasty": [...]}} - each player's ours / mv as that week's page showed them."""
    from playwright.async_api import async_playwright
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=site)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for wk, c in sorted(builds.items()):
            page = git(hist, "show", f"{c}:trade/index.html"); m = re.search(r"trade/(data-[a-f0-9]+\.js)", page)
            if not m: print(f"week {wk} ({c}): no data file on that page - skipped"); continue
            data = git(hist, "show", f"{c}:trade/{m.group(1)}")
            ctx = await b.new_context(); pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
            async def old(route, *, page=page, data=data):
                u = route.request.url
                if re.search(r"/trade/data-[a-f0-9]+\.js", u): await route.fulfill(status=200, content_type="application/javascript", body=data)
                elif u.rstrip("/").endswith("/trade"): await route.fulfill(status=200, content_type="text/html", body=page)
                else: await route.continue_()
            await ctx.route("**/trade/**", old); await ctx.route("**/api.sleeper.app/**", lambda r: r.abort()); await ctx.route("**/*supabase*/**", lambda r: r.abort())
            await pg.goto(f"http://127.0.0.1:{PORT}/trade/", wait_until="domcontentloaded"); await pg.wait_for_timeout(900)
            grab = "window.__BS.players.filter(p => p.ours != null).map(p => ({n: p.n, pos: p.pos, ours: p.ours, mv: p.mv == null ? null : p.mv, v: p.v, adj: p.adj}))"
            red = await pg.evaluate(grab); w = await pg.evaluate("window.__BS.mkt_w")
            dyn = []
            if await pg.query_selector("#dyn"):
                await pg.evaluate("(() => { const e = document.querySelector('#dyn'); e.checked = true; e.dispatchEvent(new Event('change', {bubbles: true})); })()"); await pg.wait_for_timeout(400); dyn = await pg.evaluate(grab)
            out[wk] = {"commit": c, "redraft": red, "dynasty": dyn, "mkt_w": w}
            print(f"week {wk} ({c}): {len(red)} players with our number, {sum(1 for x in red if x['mv'] is not None)} with the market's; market share shown then {w}; script errors {len(errs)}")
            await ctx.close()
        await b.close()
    srv.shutdown(); return out

def board(pages, real, last_played):
    rows = []; latest = max(pages)
    for wk in sorted(pages):
        if wk > last_played: continue
        P = [x for x in pages[wk]["redraft"] if x["mv"] is not None and x["pos"] in TOP]
        weeks = list(range(wk, last_played + 1)); rec = {"week": wk, "through": last_played, "games": len(weeks), "pos": {}, "gaps": {"n": 0, "ours": 0, "market": 0}, "drift": {}}
        allx = {"o": [], "m": [], "b30": [], "b70": [], "y": []}
        for pos, top in TOP.items():
            pool = sorted([x for x in P if x["pos"] == pos], key=lambda x: -max(x["ours"], x["mv"]))[:top]; got = []
            for x in pool:
                g = [v for w_, v in (real.get((_nn(x["n"]), pos)) or {}).items() if w_ in weeks]
                if g: got.append((x, sum(g) / len(g)))
            if len(got) < 8: continue
            o = [x["ours"] for x, _ in got]; mk = [x["mv"] for x, _ in got]; y = [v for _, v in got]
            b30 = [0.7 * a + 0.3 * b_ for a, b_ in zip(o, mk)]; b70 = [0.3 * a + 0.7 * b_ for a, b_ in zip(o, mk)]
            rec["pos"][pos] = {"n": len(got), "ours": spearman(o, y), "market": spearman(mk, y), "ours70": spearman(b30, y), "market70": spearman(b70, y)}
            # disagreements: his place among these players by each number against his place by points per game afterwards. Places, not
            # values: the first version turned his finish into a value off the higher of the two numbers, which leans toward whichever
            # side is higher on a player - and on most disagreements that is ours (38-18 "for ours" on that count; see the table for
            # the count that stands).
            def places(v): o_ = sorted(range(len(v)), key=lambda i: -v[i]); r_ = [0] * len(v); [r_.__setitem__(i, k) for k, i in enumerate(o_)]; return r_
            po, pm, py = places(o), places(mk), places(y)
            for i, (x, _) in enumerate(got):
                if abs(x["ours"] - x["mv"]) >= GAP:
                    rec["gaps"]["n"] += 1; do, dm = abs(po[i] - py[i]), abs(pm[i] - py[i])
                    if do < dm: rec["gaps"]["ours"] += 1
                    elif dm < do: rec["gaps"]["market"] += 1
                    rec["gaps"].setdefault("who", []).append([x["n"], pos, x["ours"], x["mv"], po[i] + 1, pm[i] + 1, py[i] + 1])
            # pooled: each number as a z-score inside its position, so one correlation covers the four positions
            def z(v):
                m_ = sum(v) / len(v); s_ = math.sqrt(sum((q - m_) ** 2 for q in v) / len(v)) or 1; return [(q - m_) / s_ for q in v]
            for k, v in (("o", o), ("m", mk), ("b30", b30), ("b70", b70), ("y", y)): allx[k] += z(v)
        if allx["y"]: rec["all"] = {"n": len(allx["y"]), "ours": spearman(allx["o"], allx["y"]), "market": spearman(allx["m"], allx["y"]), "ours70": spearman(allx["b30"], allx["y"]), "market70": spearman(allx["b70"], allx["y"])}
        # drift: did the market's own number move toward ours by the latest build?
        if latest > wk:
            for fmt in ("redraft", "dynasty"):
                now = {(x["n"], x["pos"]): x["mv"] for x in pages[latest][fmt] if x["mv"] is not None}; t = a = 0
                for x in pages[wk][fmt]:
                    if x["mv"] is None or x["pos"] not in TOP or abs(x["ours"] - x["mv"]) < GAP: continue
                    nv = now.get((x["n"], x["pos"]))
                    if nv is None or abs(nv - x["mv"]) < 150: continue
                    t += 1; a += ((nv - x["mv"]) > 0) == ((x["ours"] - x["mv"]) > 0)
                rec["drift"][fmt] = {"n": t, "toward_ours": a}
        rows.append(rec)
    return rows

def show(rows):
    f = lambda v: "  -  " if v is None else f"{v:+.3f}"
    for r in rows:
        print(f"\nBuilt before Week {r['week']}, graded on Weeks {r['week']}-{r['through']} ({r['games']} game{'s' if r['games'] != 1 else ''} each at most)")
        print(f"  {'':5s} {'n':>4s}  {'ours':>6s} {'market':>6s} {'70% ours':>8s} {'70% mkt':>8s}")
        for pos, d in r["pos"].items(): print(f"  {pos:5s} {d['n']:4d}  {f(d['ours'])} {f(d['market'])}   {f(d['ours70'])}   {f(d['market70'])}")
        if r.get("all"): d = r["all"]; print(f"  {'all':5s} {d['n']:4d}  {f(d['ours'])} {f(d['market'])}   {f(d['ours70'])}   {f(d['market70'])}")
        g = r["gaps"]; print(f"  disagreements of {GAP:,}+: {g['n']} players - the weeks after sided with ours {g['ours']}, with the market {g['market']}")
        for fmt, d in r["drift"].items(): print(f"  market drift ({fmt}): of {d['n']} disagreements whose market number moved, {d['toward_ours']} moved toward ours")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--hist", default="/tmp/fg/hist"); ap.add_argument("--site", default=os.path.join(HERE, "site")); ap.add_argument("--in", dest="in_dir", default=os.path.join(HERE, "in"))
    ap.add_argument("--season", default="2026"); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    subprocess.run(["git", "-C", a.hist, "fetch", "-q", "origin", "main"], check=False)
    builds = first_builds(a.hist); real = realized(a.in_dir, a.season); last_played = max(w for d in real.values() for w in d)
    print(f"first builds: {builds}; stats through Week {last_played}")
    pages = asyncio.run(read_pages(a.hist, a.site, builds)); rows = board(pages, real, last_played); show(rows)
    tot = {"n": 0, "ours": 0, "market": 0}
    for r in rows:
        for k in tot: tot[k] += r["gaps"][k]
    wins = [(r["week"], (r.get("all") or {}).get("ours"), (r.get("all") or {}).get("market")) for r in rows if r.get("all")]
    ahead = sum(1 for _, o, m in wins if o is not None and m is not None and o > m)
    print(f"\nScoreboard: ours ranked the next weeks better than the market in {ahead} of {len(wins)} builds; disagreements settled {tot['ours']} for ours, {tot['market']} for the market ({tot['n']} players).")
    if a.write:
        out = os.path.join(HERE, "research", "value_board.json")
        json.dump({"through": last_played, "builds": {str(k): v for k, v in builds.items()}, "rows": rows, "ahead": ahead, "of": len(wins), "gaps": tot}, open(out, "w"), indent=1); print("wrote", out)

if __name__ == "__main__": main()
