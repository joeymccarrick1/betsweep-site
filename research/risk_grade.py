"""risk_grade.py - does the site's risk check separate winners from losers?  (owner 11/10: "Deep dive into any inefficiencies")

The risk score (sweep.risk_score: bad 3 / watch 1 / good -1 over a leg's flags) decides what the owner's slips may hold, and it had
never been graded.  The graded frozen legs ('V2 - FanDuel Leg Snapshots' -> in/legsnaps.json) carry the sheet's own warnings but not the
site's flags, so this joins each week's graded legs (player + market + line) to the builder data the site published before that
Sunday's kickoff, which holds every leg's flags, price and shown chance as visitors saw them.

  python3 research/risk_grade.py WEEK=PATH [WEEK=PATH ...]        PATH = a build/data-<hash>.js, or an older build/index.html (data inline)

Where the files come from (site repo, main):  gh api -H "Accept: application/vnd.github.raw" \
      "repos/<owner>/betsweep-site/contents/build/<file>?ref=<commit>"
  Week 6  d0d41127 (10/18 12:56Z, build/index.html)      Week 7  60849a4c (10/24 21:22Z, build/index.html)
  Week 8  29920626 (11/1 17:15Z, data-ec62686e7c5c.js)   Week 9  e221a51a (11/8 16:08Z, data-2fe9d81c6313.js)

Prints, per week and pooled: legs by risk tier (hit %, the price's break-even %, the chance the site showed, units per 100 staked),
the same for favorites (-350..-140), the Short view "easy pick" rule, legs the site showed at or above the price, and a report card
for every flag with 60+ legs.  Read-only: nothing here changes a projection, a flag or a page.
"""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.dirname(HERE)
sys.path.insert(0, GP)
import sweep  # noqa: E402


def num(x):
    try: return float(str(x).replace("+", "").replace("%", "").replace(",", ""))
    except Exception: return None


def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / -o


def load_bd(path):
    s = open(path, encoding="utf-8").read()
    m = re.search(r"window\.__BS\s*=\s*", s)
    if not m: raise SystemExit(f"{path}: no window.__BS")
    return json.JSONDecoder().raw_decode(s, m.end())[0]


def load_results():
    v = json.load(open(os.path.join(GP, "in", "legsnaps.json")))["values"]; H = {c: i for i, c in enumerate(v[0])}
    def g(r, c): return r[H[c]] if H[c] < len(r) else ""
    out = collections.defaultdict(dict)
    for r in v[1:]:
        if str(g(r, "Latest Snapshot")).upper() != "TRUE" or g(r, "Result") not in ("HIT", "MISS"): continue
        out[str(g(r, "Week"))][(str(g(r, "Player")).strip().lower(), g(r, "Market"), round(num(g(r, "Line (X+)")) or 0, 1))] = g(r, "Result") == "HIT"
    return out


def stat(x):
    """x = [(leg, hit)] -> n, hit %, break-even % at the price, the site's shown chance, units won per 100 staked."""
    if not x: return None
    n = len(x); hit = sum(1 for _, h in x if h); price = sum(1 / dec(float(l["o"])) for l, _ in x) / n
    ps = [float(l["p"]) for l, _ in x if l.get("p") is not None]
    u = sum((dec(float(l["o"])) - 1) if h else -1 for l, h in x)
    return dict(n=n, hit=round(hit / n * 100, 1), price=round(price * 100, 1), site=round(sum(ps) / len(ps) * 100, 1) if ps else None,
                per100=round(u / n * 100, 1))


def fmt(s):
    return "-" if not s else f"n={s['n']:5} hit {s['hit']:5} price {s['price']:5} site {s['site']!s:5} per100 {s['per100']:6}"


TIERS = (("low (0-1)", lambda x: x <= 1), ("some (2-3)", lambda x: 2 <= x <= 3), ("high (4+)", lambda x: x >= 4))


def tag_of(f):
    t = str(f[1]).split(":")[0].split(" · ")[0]
    t = re.sub(r"^\d+/\d+ this season$", "N/M this season", t)
    t = re.sub(r"^FD (rec|rush|pass) yds \d+/\d+$", r"FD \1 yds N/M", t)
    t = re.sub(r"^O/U [\d.]+$", "O/U (total)", t)
    t = re.sub(r"^Q\b.*$", "Questionable", t)
    t = re.sub(r"^[A-Z][A-Za-z.'\-]+ returns$", "(teammate) returns", t)
    return t


def main(argv):
    res = load_results(); J = []            # (week, leg, hit, risk, flags)
    for a in argv:
        wk, path = a.split("=", 1); bd = load_bd(path); R = res.get(wk, {}); n = 0
        for l in bd["legs"]:
            if l.get("o") is None or l.get("ln") is None: continue
            h = R.get((str(l.get("pl", "")).strip().lower(), l.get("m"), round(float(l["ln"]), 1)))
            if h is None: continue
            fl = [f for f in list(l.get("fh") or []) + list((bd.get("pf") or {}).get(l.get("pl")) or [])
                  if isinstance(f, (list, tuple)) and len(f) >= 2 and f[0] in ("bad", "watch", "good")]
            J.append((wk, l, h, sweep.risk_score(l, bd), fl)); n += 1
        print(f"week {wk}: built {bd.get('built')!r}, {len(bd['legs'])} builder legs, {len(R)} graded snapshot legs, {n} joined")
    weeks = sorted({w for w, *_ in J}, key=int)

    def block(title, keep):
        print(f"\n{title}")
        for lab, f in TIERS:
            print(f"  {lab:11} {fmt(stat([(l, h) for w, l, h, r, _ in J if keep(l) and f(r)]))}")
            for wk in weeks:
                print(f"      wk {wk:2}   {fmt(stat([(l, h) for w, l, h, r, _ in J if w == wk and keep(l) and f(r)]))}")

    fav = lambda l: -350 <= float(l["o"]) <= -140
    block("ALL LEGS by risk tier", lambda l: True)
    block("FAVORITES (-350..-140) by risk tier", fav)
    gap = lambda l: float(l["p"]) - 1 / dec(float(l["o"])) if l.get("p") is not None else None
    print("\nSHORT VIEW easy-pick rule (favorite, risk 0-1, shown chance within 2 pts of the price or better):")
    print("  pooled     ", fmt(stat([(l, h) for w, l, h, r, _ in J if fav(l) and r <= 1 and gap(l) is not None and gap(l) >= -0.02])))
    for wk in weeks: print(f"      wk {wk:2}   ", fmt(stat([(l, h) for w, l, h, r, _ in J if w == wk and fav(l) and r <= 1 and gap(l) is not None and gap(l) >= -0.02])))
    print("\nLEGS THE SITE SHOWED AT OR ABOVE THE PRICE (shown chance >= break-even), any price:")
    for lab, lo, hi in (("below by 3+", -9, -0.03), ("below 0-3", -0.03, 0), ("above 0-2", 0, 0.02), ("above 2+", 0.02, 9)):
        print(f"  {lab:12}", fmt(stat([(l, h) for w, l, h, r, _ in J if gap(l) is not None and lo <= gap(l) < hi])))
    print("  by market, shown at or above the price:")
    for mk in ("Passing Yards", "Receiving Yards", "Receptions", "Rushing Yards", "Longest Reception", "Anytime TD"):
        x = [(w, l, h) for w, l, h, r, _ in J if l.get("m") == mk and gap(l) is not None and gap(l) >= 0]
        wkpos = sum(1 for wk in weeks if (stat([(l, h) for w, l, h in x if w == wk]) or {"per100": -1})["per100"] > 0)
        print(f"    {mk:18}", fmt(stat([(l, h) for _, l, h in x])), f" weeks in profit {wkpos}/{len(weeks)}")
    print("\nFAVORITES, low risk, by market:")
    for mk in ("Passing Yards", "Receiving Yards", "Receptions", "Rushing Yards", "Longest Reception", "Anytime TD"):
        print(f"    {mk:18}", fmt(stat([(l, h) for w, l, h, r, _ in J if fav(l) and r <= 1 and l.get("m") == mk])))

    T = collections.defaultdict(list)
    for w, l, h, r, fl in J:
        for k in {(f[0], tag_of(f)) for f in fl}: T[k].append((w, l, h))
    print("\nFLAG REPORT CARD (60+ legs).  gap = hit % minus the price's break-even %; weeks = weeks the flag pointed the way its colour says")
    rows = []
    for (k, t), x in T.items():
        if len(x) < 60: continue
        s = stat([(l, h) for _, l, h in x]); right = n_w = 0
        for wk in weeks:
            sw = stat([(l, h) for w, l, h in x if w == wk])
            if not sw or sw["n"] < 15: continue
            n_w += 1; g = sw["hit"] - sw["price"]
            base = stat([(l, h) for w, l, h, *_ in J if w == wk]); gb = base["hit"] - base["price"]
            right += (g < gb) if k in ("bad", "watch") else (g > gb)
        rows.append((k, s["hit"] - s["price"], t, s, right, n_w))
    for k, gp_, t, s, right, n_w in sorted(rows, key=lambda r: (r[0], r[1])):
        print(f"  {k:5} {t[:30]:30} n={s['n']:5} hit {s['hit']:5} price {s['price']:5} gap {gp_:+6.1f} per100 {s['per100']:6}  weeks {right}/{n_w}")
    base = stat([(l, h) for w, l, h, *_ in J]); print(f"  (every joined leg: {fmt(base)}  gap {base['hit'] - base['price']:+.1f})")
    lowo(J, weeks, fav)


def lowo(J, weeks, fav, min_n=60, shrink=200.0):
    """Would a risk score built from the report card have worked on a week it had not seen?
    For each week: learn every flag's weight from the OTHER weeks (how far its legs ran from the price, next to the average leg, shrunk
    toward zero for small samples), add the weights up for each leg of the held-out week, and compare the third of legs the learned score
    likes least with the third it likes most.  The same split by today's risk score sits next to it."""
    if len(weeks) < 3: return
    def gapof(x): return (sum(1 for _, h in x if h) / len(x) - sum(1 / dec(float(l["o"])) for l, _ in x) / len(x)) * 100 if x else None
    print("\nHELD-OUT TEST (each week scored with flag weights learned from the other weeks).  gap = hit % minus break-even %")
    pooled = collections.defaultdict(list)
    for wk in weeks:
        tr = [x for x in J if x[0] != wk]; te = [x for x in J if x[0] == wk]
        b = gapof([(l, h) for _, l, h, _, _ in tr]) / 100
        T = collections.defaultdict(list)
        for _, l, h, _, fl in tr:
            for k in {(f[0], tag_of(f)) for f in fl}: T[k].append((1.0 if h else 0.0) - 1 / dec(float(l["o"])))
        W = {k: (sum(v) / len(v) - b) * len(v) / (len(v) + shrink) for k, v in T.items() if len(v) >= min_n}
        for scope, keep in (("all legs", lambda l: True), ("favorites", fav)):
            rows = [(sum(W.get(k, 0.0) for k in {(f[0], tag_of(f)) for f in fl}), r, l, h) for _, l, h, r, fl in te if keep(l)]
            if len(rows) < 30: continue
            by_new = sorted(rows, key=lambda x: x[0]); n3 = len(by_new) // 3
            worst, best = by_new[:n3], by_new[-n3:]
            lo = [x for x in rows if x[1] <= 1]; hi = [x for x in rows if x[1] >= 4]
            g = lambda xs: gapof([(l, h) for _, _, l, h in xs])
            print(f"  wk {wk:2} {scope:9}  learned score: worst third {g(worst):+6.1f}  best third {g(best):+6.1f}   |   today's score: high risk {g(hi):+6.1f} (n={len(hi)})  low risk {g(lo):+6.1f} (n={len(lo)})")
            pooled[(scope, "worst")] += worst; pooled[(scope, "best")] += best; pooled[(scope, "hi")] += hi; pooled[(scope, "lo")] += lo
    for scope in ("all legs", "favorites"):
        g = lambda key: gapof([(l, h) for _, _, l, h in pooled[(scope, key)]])
        if not pooled[(scope, "worst")]: continue
        hitp = lambda key: sum(1 for _, _, _, h in pooled[(scope, key)] if h) / len(pooled[(scope, key)]) * 100
        print(f"  POOLED {scope:9}  learned score: worst third {g('worst'):+6.1f} (hit {hitp('worst'):.1f}, n={len(pooled[(scope, 'worst')])})  "
              f"best third {g('best'):+6.1f} (hit {hitp('best'):.1f})   |   today's score: high risk {g('hi'):+6.1f} (hit {hitp('hi'):.1f})  low risk {g('lo'):+6.1f} (hit {hitp('lo'):.1f})")


if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    main(sys.argv[1:])
