#!/usr/bin/env python3
"""pairs.py - an either-or touchdown leg judged as a pair (owner 11/8-11/9: "Give me your favorites from the either-ors", "there's a good
chance that ONE of them hits a TD", and the house rule that such a leg is judged as a pair, not as two singles).

    either(A, B, games)   A, B = two "Anytime TD" legs from out/builder_data.json; games = {gid: game dict with "a", "b", "probs"}
        -> {"p": chance that at least one scores, "ind": the same if the two were unrelated, "hedge": p - ind,
            "worst": the pair's chance in its worst game ending, "same_game", "same_team", "book": what FanDuel's two single prices imply}
    risk(A, B, bd)        -> the pair's risk score: the SAFER player's (one of them scoring is the bet, so a thin hit rate or a tough
                             matchup on one name is what the second name is there for; the pair reads risky only when both do)

Same game: the two share one game ending, so the chance is mixed over the four endings with each leg's own chance under that ending
(the builder's l.sc, which mixes back to the chance the site shows): a back who needs a lead next to a receiver who needs a chase is
worth more together than apart, two receivers on one team a little less (-2% of the smaller chance per ending for the shared ball,
the same haircut build_promo.py has always used). Different games: the endings are unrelated and the singles simply multiply.
Nothing here changes a leg's own chance.
"""
import sweep as SW

def _w(g):
    pr = [float(x or 0) for x in (g or {}).get("probs") or []]
    if len(pr) != 4 or sum(pr) <= 0: return None
    return [x / sum(pr) for x in pr]
def _sc(l, w):
    """the leg's chance under each ending, scaled so the mix is exactly the chance shown; None when it carries none"""
    sc = l.get("sc"); p = l.get("p")
    if p is None: return None
    if not (isinstance(sc, (list, tuple)) and len(sc) == 4 and w): return None
    m = sum(a * float(b) for a, b in zip(w, sc))
    if m <= 0: return None
    return [min(0.97, max(0.0, float(x) * p / m)) for x in sc]
def either(A, B, games):
    pa, pb = A.get("p"), B.get("p")
    if pa is None or pb is None: return None
    ind = 1 - (1 - pa) * (1 - pb)
    out = {"ind": ind, "same_game": A.get("g") == B.get("g") and bool(A.get("g")), "same_team": A.get("tm") == B.get("tm") and bool(A.get("tm")),
           "book": (1 - (1 - A["bk"]) * (1 - B["bk"])) if A.get("bk") is not None and B.get("bk") is not None else None}
    wa = _w((games or {}).get(A.get("g"))); wb = _w((games or {}).get(B.get("g")))
    sa = _sc(A, wa); sb = _sc(B, wb)
    if out["same_game"] and sa and sb:
        per = []
        for k in range(4):
            pe = 1 - (1 - sa[k]) * (1 - sb[k])
            if out["same_team"]: pe -= 0.02 * min(sa[k], sb[k])
            per.append(pe)
        out["p"] = sum(x * y for x, y in zip(wa, per)); out["worst"] = min(per); out["per"] = per
    else:
        haircut = 0.02 * min(pa, pb) if out["same_team"] else 0.0
        out["p"] = ind - haircut
        out["worst"] = (1 - (1 - min(sa)) * (1 - min(sb))) if sa and sb else None
        out["per"] = None
    out["hedge"] = out["p"] - ind
    return out
def risk(A, B, bd):
    return min(SW.risk_score(A, bd), SW.risk_score(B, bd))
def fair_american(p):
    if not p or p <= 0 or p >= 1: return None
    return -round(100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)
def implied(american):
    try: o = float(american)
    except Exception: return None
    if o == 0: return None
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)

def selftest():
    bad = 0
    def ok(c, what):
        nonlocal bad
        print(("ok   " if c else "FAIL ") + what); bad += 0 if c else 1
    G = {"AAA-BBB": {"a": "AAA", "b": "BBB", "probs": [40, 20, 20, 20]}, "CCC-DDD": {"a": "CCC", "b": "DDD", "probs": [25, 25, 25, 25]}}
    rb = {"pl": "Back", "tm": "AAA", "g": "AAA-BBB", "p": 0.50, "bk": 0.55, "sc": [0.70, 0.45, 0.45, 0.20]}     # needs the lead
    wr = {"pl": "Wideout", "tm": "AAA", "g": "AAA-BBB", "p": 0.40, "bk": 0.45, "sc": [0.25, 0.35, 0.55, 0.60]}  # needs the chase
    w2 = {"pl": "Wideout Two", "tm": "AAA", "g": "AAA-BBB", "p": 0.40, "bk": 0.45, "sc": [0.25, 0.35, 0.55, 0.60]}
    opp = {"pl": "Other Side", "tm": "BBB", "g": "AAA-BBB", "p": 0.40, "bk": 0.45, "sc": [0.20, 0.35, 0.55, 0.65]}
    far = {"pl": "Far Away", "tm": "CCC", "g": "CCC-DDD", "p": 0.40, "bk": 0.45, "sc": [0.5, 0.3, 0.5, 0.3]}
    flat = {"pl": "No Script", "tm": "DDD", "g": "CCC-DDD", "p": 0.30, "bk": 0.33}
    x = either(rb, wr, G); y = either(wr, w2, G); z = either(rb, far, G); q = either(rb, opp, G)
    ok(abs(sum(a * b for a, b in zip(_w(G["AAA-BBB"]), _sc(rb, _w(G["AAA-BBB"])))) - 0.50) < 1e-9, "a leg's ending chances are scaled to mix back to the chance shown")
    ok(x["hedge"] > 0.005 and x["p"] > x["ind"] - 0.02 * 0.4, f"a back who needs a lead + a receiver who needs a chase: worth more together ({x['p']:.3f} vs {x['ind']:.3f})")
    ok(y["hedge"] < -0.01 and y["p"] < y["ind"], f"two receivers who need the same game: worth less together ({y['p']:.3f} vs {y['ind']:.3f})")
    ok(abs(z["p"] - z["ind"]) < 1e-12 and z["hedge"] == 0 and not z["same_game"], "different games: the singles simply multiply")
    ok(q["same_game"] and not q["same_team"] and q["per"] is not None, "opposite sides of one game share the ending, no shared-ball haircut")
    ok(all(0 < v["p"] < 1 and v["worst"] <= v["p"] + 1e-9 for v in (x, y, q)), "the worst ending is never better than the mix")
    f = either(far, flat, G); ok(f is not None and abs(f["p"] - 0.58) < 1e-9 and f["per"] is None, "a leg with no ending chances falls back to the plain product")
    ok(abs(x["book"] - (1 - 0.45 * 0.55)) < 1e-12, "what FanDuel's two single prices imply")
    ok(either({"pl": "X", "p": None}, rb, G) is None, "a leg without a chance: no number")
    bd = {"pf": {"Back": [["bad", "Role Down", ""]], "Wideout": []}}
    ok(risk(dict(rb, fh=[["bad", "2/8 this season", ""]]), dict(wr, fh=[]), bd) == 0, "the pair is as safe as its safer player (6 and 0 -> 0)")
    ok(risk(dict(rb, fh=[]), dict(wr, fh=[["bad", "Backup QB", ""]]), {"pf": {"Back": [["bad", "Role Down", ""]]}}) == 3, "both flagged: the pair is flagged (3 and 3 -> 3)")
    ok(fair_american(0.8) == -400 and fair_american(0.25) == 300 and fair_american(1) is None, "fair price from a chance")
    ok(abs(implied(-475) - 0.826087) < 1e-5 and abs(implied(150) - 0.4) < 1e-9 and implied("x") is None, "chance a price needs")
    print("pairs selftest:", "ok" if not bad else f"{bad} FAILED"); return bad

if __name__ == "__main__":
    import sys
    sys.exit(1 if selftest() else 0)
