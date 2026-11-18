#!/usr/bin/env python3
"""how_stats.py - the numbers on /how/ ("How BetSweep picks"), counted from the graded legs on every build.

Why (11/17). The page said "What three graded weeks taught us" (4,929 legs, Weeks 6-8) for two weeks after Weeks 9 and 10 were graded,
and two of its sentences had stopped being true: longer-priced touchdown scorers no longer paid as a group, and the model's weights by
market had changed on 11/10. Owner 11/17: "Yes recount on how betsweep picks". The text in how_body.html now carries {{KEYS}}; fill()
puts the numbers in from the sheet's leg snapshots (in/legsnaps.json: the latest frozen snapshot of each FanDuel leg, HIT or MISS) and
the weights from calib.py, so the page follows the grades by itself. The same definitions as the 11/4 audit (RUNBOOK "Deep dig"); run on
Weeks 6-8 alone it returns that audit's numbers (4,929 legs, -8.1%; rushing -19.1%; the plus-money edge legs 150 at 41.3% / 31.8%, +31.5%).

    python3 how_stats.py [in_dir]     prints every key and value

If the snapshots cannot be read, or hold fewer than 1,000 graded legs, DEFAULT (the 11/17 count) is used so the page never shows a hole.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
NAMES = {"Anytime TD": "touchdowns", "Receptions": "receptions", "Receiving Yards": "receiving yards", "Passing Yards": "passing yards", "Rushing Yards": "rushing yards"}
DEFAULT = {
    "N_WEEKS_WORD": "five", "WEEKS": "Weeks&nbsp;6–&#8288;10", "N_ALL": "8,094", "ROI_ALL": "−9%", "ALL_C": "b",
    "FLOOR_ROI": "−10%", "FLOOR_C": "b", "FLOOR_HIT": "60%", "FLOOR_IMP": "67%", "FLOOR_N": "3,434",
    "RUSH_ROI": "−17%", "RUSH_C": "b", "RUSH_N": "1,199", "RUSH_WHERE": "losing at every price",
    "PLUS_ROI": "+23%", "PLUS_C": "g", "PLUS_HIT": "39%", "PLUS_IMP": "31%", "PLUS_N": "240", "PLUS_WEEKS": "ahead in all five weeks",
    "PLUS_MARKETS": "receiving yards (56% hit against a 36% price, 25 legs), receptions (42% against 33%, 78) and touchdowns (30% against 25%, 69)",
    "TD_SENT": "Touchdown scorers at +151 or longer returned −3% as a group (497 legs) and touchdown favorites −7%: a touchdown price pays only where the model sits well above it.",
    "PASS_SENT": "Passing-yard lines <em>above</em> the projection hit 58% (200 legs); passing legs at −200 or shorter lost 7%.",
    "MODEL70": "legs it had at 70% or better hit 63%",
    "EVEN_HIT": "59%", "EVEN_IMP": "53%", "EVEN_N": "152",
    "WEIGHTS": "about half on touchdowns and receptions, about a quarter on receiving yards, and very little on passing yards and rushing yards, where FanDuel's number alone graded better",
}

def _num(x):
    try: return float(str(x).replace("%", "").replace("+", "").replace(",", ""))
    except (TypeError, ValueError): return None
def _imp(o): return (-o / (-o + 100.0)) if o < 0 else 100.0 / (o + 100.0)
def _dec(o): return 1 + (o / 100.0 if o > 0 else 100.0 / -o)

def legs(in_dir="in", values=None):
    """One dict per graded leg: week, market, odds, hit, raw model chance, shown model chance, line, projection.
    values = the tab's rows when the caller has them loaded already (home.py)."""
    v = values
    if v is None:
        try: v = json.load(open(os.path.join(in_dir, "legsnaps.json")))["values"]
        except Exception: return []
    if not v: return []
    H = {c: i for i, c in enumerate(v[0])}; out = []
    need = ("Week", "Market", "FanDuel odds", "Result", "Latest Snapshot")
    if any(k not in H for k in need): return []
    for r in v[1:]:
        r = list(r) + [""] * (len(v[0]) - len(r))
        if r[H["Latest Snapshot"]] != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
        o, w = _num(r[H["FanDuel odds"]]), _num(r[H["Week"]])
        if not o or not w: continue
        out.append({"w": int(w), "m": r[H["Market"]], "o": o, "hit": r[H["Result"]] == "HIT", "raw": _num(r[H["Raw model %"]]) if "Raw model %" in H else None,
                    "adj": _num(r[H["Model % (hist-adj)"]]) if "Model % (hist-adj)" in H else None, "ln": _num(r[H["Line (X+)"]]) if "Line (X+)" in H else None,
                    "pj": _num(r[H["Projection"]]) if "Projection" in H else None})
    return out

def _s(rows):
    """(legs, hit rate, average implied chance, return per leg at one unit each) - (0, 0, 0, 0) for an empty cut"""
    n = len(rows)
    if not n: return 0, 0.0, 0.0, 0.0
    h = sum(1 for x in rows if x["hit"])
    return n, h / n, sum(_imp(x["o"]) for x in rows) / n, sum((_dec(x["o"]) - 1) if x["hit"] else -1 for x in rows) / n

def _pct(x): return f"{round(100 * x):d}%"
def _roi(x):
    v = round(100 * x); return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v)}%"
def _word(n): return WORDS[n] if 0 <= n < len(WORDS) else str(n)
def _join(xs): return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]

def weeks_txt(weeks, html=True):
    """'Weeks 6–10' - in HTML with a no-break space and a word joiner so a phone never ends a line on 'Weeks 6–'; plain text for a title."""
    if len(weeks) > 1 and weeks == list(range(weeks[0], weeks[-1] + 1)):
        return f"Weeks&nbsp;{weeks[0]}–&#8288;{weeks[-1]}" if html else f"Weeks {weeks[0]}-{weeks[-1]}"
    return ("Week " if len(weeks) == 1 else "Weeks ") + ", ".join(str(w) for w in weeks)

PLUS_MK = ("Receiving Yards", "Receptions", "Passing Yards", "Anytime TD")   # keep in step with build_builder._PLUS_MK (the plus tier's markets)
PLUS_DEFAULT = "{W}: 40% hit against a 30% price, +30% at a unit each (175 legs)"
def plus_phrase(in_dir="in", values=None, html=True):
    """The record behind the plus-money tier, for Model's Best and the builder's tier chip: the tier's own markets, +150 or longer, raw
    model 5+ points over the price. 'Weeks 6–10: 40% hit against a 30% price, +30% at a unit each (175 legs)'."""
    try:
        L = legs(in_dir, values); weeks = sorted({x["w"] for x in L})
        pm = [x for x in L if x["m"] in PLUS_MK and x["o"] >= 150 and x["raw"] is not None and x["raw"] - _imp(x["o"]) >= 0.05]; n, h, im, r = _s(pm)
        if n < 60: raise ValueError(f"only {n} graded plus-tier legs")
        return f"{weeks_txt(weeks, html)}: {_pct(h)} hit against a {_pct(im)} price, {_roi(r) if html else _roi(r).replace('−', '-')} at a unit each ({n:,} legs)"
    except Exception as e:
        print("note how_stats.plus_phrase: the 11/17 count stays -", e)
        return PLUS_DEFAULT.replace("{W}", "Weeks&nbsp;6–&#8288;10" if html else "Weeks 6-10")

EVEN_MK = ("Passing Yards", "Receiving Yards", "Receptions")   # keep in step with build_builder.py's even / safe tier markets
def _tiers(L):
    """(even overs, touchdown tier, safe tier) cut the way build_builder.py assigns the tiers, as far as a graded snapshot can tell:
    overs only (the snapshots hold no under prices) and without the 11/17 touchdown role rule (snap projections are not frozen)."""
    R = [x for x in L if x["raw"] is not None]
    ev = [x for x in R if x["m"] in EVEN_MK and -135 <= x["o"] <= 115 and x["raw"] - _imp(x["o"]) >= 0.08]
    td = [x for x in R if x["m"] == "Anytime TD" and x["o"] <= 200 and x["raw"] >= _imp(x["o"])]
    sf = [x for x in R if x["m"] in EVEN_MK and x["adj"] is not None and x["adj"] >= 0.65 and x["raw"] >= _imp(x["o"]) and not (-135 <= x["o"] <= 115 and x["raw"] - _imp(x["o"]) >= 0.08)]
    return ev, td, sf
TIER_DEFAULT = {"even": "overs like this, Weeks 6-10: 59% hit against a 53% price (152 legs)",
                "td": "Weeks 6-10, before the role rule: 38% hit against a 39% price (47 legs, a small sample)",
                "safe": "Weeks 6-10: 64% hit against a 68% price (333 legs)"}
def tier_phrases(in_dir="in", values=None):
    """Plain-text records for the builder's even / touchdown / safe tier chips (they quoted Weeks 6-7 until 11/17)."""
    try:
        L = legs(in_dir, values); weeks = sorted({x["w"] for x in L}); W = weeks_txt(weeks, html=False); ev, td, sf = _tiers(L); out = {}
        for k, rows, lead, tail in (("even", ev, "overs like this, ", ""), ("td", td, "", ""), ("safe", sf, "", "")):
            n, h, im, r = _s(rows)
            if n < 30: out[k] = TIER_DEFAULT[k]; continue
            out[k] = f"{lead}{W}{', before the role rule' if k == 'td' else ''}: {_pct(h)} hit against a {_pct(im)} price ({n:,} legs{', a small sample' if n < 100 else ''})"
        return out
    except Exception as e:
        print("note how_stats.tier_phrases: the 11/17 count stays -", e); return dict(TIER_DEFAULT)

def weights_text():
    """The model's share of the shown chance by market, in words, from calib.py (W_MARKET + the two recalibrated markets)."""
    try:
        sys.path.insert(0, HERE); import calib
        w = dict(calib.W_MARKET); w.update({m: 0.1 for m in getattr(calib, "RECAL", {})})
    except Exception: return DEFAULT["WEIGHTS"]
    def phrase(x): return "about two thirds" if x >= 0.6 else "about half" if x >= 0.45 else "about a third" if x >= 0.3 else "about a quarter" if x >= 0.2 else "very little"
    groups = {}
    for m, x in sorted(w.items(), key=lambda kv: (-kv[1], kv[0] != "Anytime TD", kv[0])):
        if m in NAMES: groups.setdefault(phrase(x), []).append(NAMES[m])
    if not groups: return DEFAULT["WEIGHTS"]
    parts = [f"{p} on {_join(ms)}" for p, ms in groups.items()]
    txt = _join(parts) if len(parts) < 3 else ", ".join(parts[:-1]) + ", and " + parts[-1]
    return txt + (", where FanDuel's number alone graded better" if "very little" in groups else "") + _floor_text(calib)

def _floor_text(calib):
    """One more sentence when calib.py takes points off floor lines (FLOOR_CUT / FLOOR_BAND), so the page says what the numbers do."""
    try:
        cut = (getattr(calib, "FLOOR_CUT", {}) or {}).get("Receiving Yards"); band = getattr(calib, "FLOOR_BAND", None)
        if not cut or not band: return ""
        return (f". Receiving-yards lines that sit at {band[1] * 100:.0f} to {band[2] * 100:.0f} percent of a player's projection also come down about "
                f"{_word(max(1, round(cut * 100)))} point{'s' if round(cut * 100) != 1 else ''}, because the shown number ran above the hit rate there in every graded week it was tested on") + _price_text(calib)
    except Exception: return ""

def _price_text(calib):
    """And one for calib.py's reading of a short price (PRICE_KNOT / PRICE_SLOPE)."""
    try:
        k = getattr(calib, "PRICE_KNOT", None); sl = getattr(calib, "PRICE_SLOPE", None)
        if not k or sl is None or sl >= 1: return ""
        odds = -round(100 * k / (1 - k)); how = "half" if abs(sl - 0.5) < 1e-9 else f"{sl * 100:.0f}%"
        return (f". A FanDuel price shorter than {odds} ({k * 100:.0f} percent) counts at {how} strength above that mark, because legs priced shorter than that "
                f"have hit about two times in three however short the price got")
    except Exception: return ""

def stats(in_dir="in"):
    L = legs(in_dir)
    if len(L) < 1000: return dict(DEFAULT)
    weeks = sorted({x["w"] for x in L}); d = {}
    d["N_WEEKS_WORD"] = _word(len(weeks))
    d["WEEKS"] = weeks_txt(weeks)
    n, h, im, r = _s(L); d["N_ALL"] = f"{n:,}"; d["ROI_ALL"] = _roi(r); d["ALL_C"] = "g" if r > 0 else "b"
    n, h, im, r = _s([x for x in L if -400 <= x["o"] <= -130]); d.update(FLOOR_ROI=_roi(r), FLOOR_C="g" if r > 0 else "b", FLOOR_HIT=_pct(h), FLOOR_IMP=_pct(im), FLOOR_N=f"{n:,}")
    ru = [x for x in L if x["m"] == "Rushing Yards"]; n, h, im, r = _s(ru)
    bands = [_s([x for x in ru if lo <= x["o"] <= hi]) for lo, hi in ((-99999, -200), (-199, -111), (-110, 150), (151, 99999))]
    d.update(RUSH_ROI=_roi(r), RUSH_C="g" if r > 0 else "b", RUSH_N=f"{n:,}", RUSH_WHERE="losing at every price" if all(b[0] and b[3] < 0 for b in bands) else "all prices together")
    pm = [x for x in L if x["o"] >= 150 and x["raw"] is not None and x["raw"] - _imp(x["o"]) >= 0.05]; n, h, im, r = _s(pm)
    up = sum(1 for w in weeks if _s([x for x in pm if x["w"] == w])[3] > 0)
    d.update(PLUS_ROI=_roi(r), PLUS_C="g" if r > 0 else "b", PLUS_HIT=_pct(h), PLUS_IMP=_pct(im), PLUS_N=f"{n:,}",
             PLUS_WEEKS=(f"ahead in all {_word(len(weeks))} weeks" if up == len(weeks) else f"ahead in {_word(up)} of the {_word(len(weeks))} weeks"))
    by = []
    for m in ("Receptions", "Receiving Yards", "Anytime TD", "Passing Yards"):
        mn, mh, mi, mr = _s([x for x in pm if x["m"] == m])
        if mn >= 20 and mh > mi: by.append((mr, m, mh, mi, mn))
    by.sort(reverse=True)   # the leg counts stay in the sentence: the best-looking market is usually the smallest sample
    d["PLUS_MARKETS"] = _join([f"{NAMES[m]} ({_pct(mh)} hit against a {_pct(mi)} price, {mn} legs)" if i == 0 else f"{NAMES[m]} ({_pct(mh)} against {_pct(mi)}, {mn})" for i, (mr, m, mh, mi, mn) in enumerate(by)]) if by else "no single market yet"
    td = [x for x in L if x["m"] == "Anytime TD"]; ln, lh, li, lr = _s([x for x in td if x["o"] >= 151]); fn, fh, fi, fr = _s([x for x in td if x["o"] < 0])
    if lr > 0 and fr <= 0: d["TD_SENT"] = f"Longer-priced touchdown scorers paid ({_roi(lr)} at +151 or longer, {ln:,} legs); touchdown favorites did not ({_roi(fr)})."
    elif lr > 0: d["TD_SENT"] = f"Touchdown scorers at +151 or longer returned {_roi(lr)} ({ln:,} legs) and touchdown favorites {_roi(fr)}."
    else: d["TD_SENT"] = f"Touchdown scorers at +151 or longer returned {_roi(lr)} as a group ({ln:,} legs) and touchdown favorites {_roi(fr)}: a touchdown price pays only where the model sits well above it."
    pa = [x for x in L if x["m"] == "Passing Yards"]; an, ah, ai, ar = _s([x for x in pa if x["ln"] is not None and x["pj"] is not None and x["ln"] > x["pj"]]); sn, sh, si, sr = _s([x for x in pa if x["o"] <= -200])
    d["PASS_SENT"] = (f"Passing-yard lines <em>above</em> the projection hit {_pct(ah)} ({an:,} legs); " if an >= 40 else "") + (f"passing legs at −200 or shorter {'lost ' + str(abs(round(100 * sr))) + '%' if sr < 0 else 'returned ' + _roi(sr)}." if sn >= 40 else "")
    d["PASS_SENT"] = d["PASS_SENT"][:1].upper() + d["PASS_SENT"][1:] if d["PASS_SENT"] else DEFAULT["PASS_SENT"]
    hi = [x for x in L if x["adj"] is not None and x["adj"] >= 0.70]; n70, h70, _, _ = _s(hi)
    d["MODEL70"] = f"legs it had at 70% or better hit {_pct(h70)}" if n70 >= 100 else DEFAULT["MODEL70"]
    en, eh, ei, er = _s(_tiers(L)[0]); d.update(EVEN_HIT=_pct(eh), EVEN_IMP=_pct(ei), EVEN_N=f"{en:,}") if en >= 30 else d.update({k: DEFAULT[k] for k in ("EVEN_HIT", "EVEN_IMP", "EVEN_N")})
    d["WEIGHTS"] = weights_text()
    return d

def fill(src, in_dir="in"):
    """how_body.html with every {{KEY}} replaced. A key this module does not know is filled from DEFAULT, never left in the page."""
    try: d = stats(in_dir)
    except Exception as e: print("WARN how_stats: counted nothing, the 11/17 numbers stay:", e); d = dict(DEFAULT)
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: str(d.get(m.group(1), DEFAULT.get(m.group(1), ""))), src)

if __name__ == "__main__":
    for k, v in stats(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "in")).items(): print(f"{k:14s} {v}")
