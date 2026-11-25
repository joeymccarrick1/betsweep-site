"""calib.py - the one place the site turns the model's raw leg probability into the number it shows and prices with.

Why: on the frozen pre-kickoff FanDuel legs the raw model has run overconfident where it disagrees with the price.
  Week 6 (1,646 graded legs): Brier raw model 0.2482 · FanDuel price 0.2380 · 50/50 blend 0.2396 (best 0.2379 at 25/75).
  Edge >= +10 legs hit 48% against a 67% raw model; edge +5..10 hit 50% vs 60%; legs the model faded (edge <= -5) hit 53% vs 44%.
  Week 5 (Underdog pick'em snapshots) told the same story: the half-way blend beat the raw number.
So every player-prop leg's shown "Model %" is  W_MODEL * raw + (1 - W_MODEL) * book-implied, and edge = shown - book.
Ranking is unchanged (the blend is monotone in raw edge); what changes is the size of the edge numbers, the parlay fair odds
and the joint probabilities, which now sit where the graded weeks say they belong. Hard edge gates in the generators were halved
to keep the same candidate pools (raw +5 == blended +2.5).

Promote-only-if-better: move W_MODEL only after a graded week's Brier (season receipt, calibration card) says a different weight
wins for the second straight week. Game-line legs (moneyline/spread/total) are priced in gamelines.py and are NOT blended here.
"""
W_MODEL = 0.5

def shrink(p, book, w=W_MODEL):
    """Shown probability for a player-prop leg. Returns p unchanged when there is no book price to blend with."""
    if p is None: return None
    if book is None: return p
    return max(0.01, min(0.99, w * p + (1 - w) * book))


# ---- owner 11/6 "real outcome ranges": per-market recalibration where a bell curve misses the shape ----
# research/recal.py (graded frozen legs, Weeks 6-8, leave-one-week-out): shown = sigmoid(c + a*logit(raw) + b*logit(book)).
# Rushing yards: c = -0.4 in every held-out week (a typical game lands below the average, so X+ overs near the projection miss more than
# the curve says) - log loss 0.6954 -> 0.6713, better in all three weeks. Longest reception: c = -0.25, better in all three weeks.
# Passing yards also improved overall but not in Week 8 - held back until Week 9 is graded (re-run research/recal.py on Tuesday).
# Receiving yards / receptions / TDs: today's 50/50 blend stays (recalibration did not beat it).
import math as _m
RECAL = {"Rushing Yards": (0.1, 0.85, -0.4), "Longest Reception": (0.1, 0.9, -0.25)}
def _lg(p): p = min(max(p, 1e-4), 1 - 1e-4); return _m.log(p / (1 - p))
# owner 11/6 ("make the change now"): per-market model weight from research/blend_weight.py (graded frozen legs Weeks 6-8, leave-one-week-out
# log loss): FanDuel alone beat the 50/50 blend pooled. Passing yards: weight 0 won every held-out week (0.1 kept so the model still moves it a
# little); receptions ~0.3; receiving yards 0.2-0.3; anytime TD 0.6-0.7 (the model adds real value there). Markets not listed keep W_MODEL.
# Rushing yards and longest reception keep their RECAL rows below (model weight ~0.1 already). Re-run blend_weight.py every Tuesday.
# owner 11/10 ("whatever is going to make us hit more often"): blend_weight.py re-run with Week 9 in (4 graded weeks). Receptions 0.3 -> 0.5
# (pooled best 0.5; 0.5 matched or beat the picked weight in all four held-out weeks). Anytime TD 0.65 -> 0.5 (pooled best 0.2-0.3, but 0.5
# beat the picked weight in every held-out week and the pooled gap is 0.001 - so half-way, not 0.2). Both gaps are small: this sizes the
# edge numbers more honestly, it does not by itself make legs hit. Passing and receiving yards unchanged.
# owner 11/18 ("strengthening our probabilities when choosing legs"): Week 10 graded (five weeks, 678 touchdown legs). FanDuel alone beat
# the 0.5 touchdown blend in Week 9 AND Week 10 (log loss by 0.012 and 0.0145; the best single-week weight was 0 both times, after 1.0, 0.7
# and 0.5 in Weeks 6-8) - the second straight week the rule asks for. Pooled best is 0.1 and the leave-one-week-out picks are 0-0.3, so
# Anytime TD 0.5 -> 0.3: a step, not the whole way (0.3 still beat 0.5 in Weeks 9-10 and gave back under 0.007 in Weeks 6-8). Where the
# model had a scorer 8+ points over the price he scored 26.5% of the time against a 26.5% price (34 legs): the lead has not been an edge.
# Receptions 0.5, receiving yards 0.25, passing 0.1 and both RECAL rows beat FanDuel alone in Week 10 again and stay.
W_MARKET = {"Passing Yards": 0.1, "Receptions": 0.5, "Receiving Yards": 0.25, "Anytime TD": 0.3}

# ---- owner 11/18 ("strengthening our probabilities when choosing legs"): research/floor_depth.py, graded frozen legs Weeks 6-10 ----
# Receiving-yards floors: where the line sits at 55-85% of the player's projection the shown % has run about 4.5 points above the hit
# rate (1,040 legs; high in every one of the five weeks at 55-70%, and at 70-85%). Deeper lines (under 55%) and lines at or over the
# projection were fine. Leave-one-week-out, taking HALF the bias measured on the other four weeks off the shown number: log loss better in
# all 5 held-out weeks (0.6841 -> 0.6814 on 1,328 legs). The full-size cut was better in 4 of 5, so half it is. The band tapers over
# 50-55% and 85-90% so a one-yard move in a line cannot jump the number.
# NOT adopted (re-run floor_depth.py on Tuesdays): the same cut on Receptions at 70-85% (4 of 5 weeks); a heavier model weight on deep
# receiving lines (2-3 of 5 weeks once the weight is fitted off-week; Week 7 carries it); deep line + model 10+ over the price (32 of 50
# player-weeks against a 52.9% price, z 1.6, cell picked after looking) - tracked, not a lead. Rushing floors need no cut (RECAL does it).
FLOOR_CUT = {"Receiving Yards": 0.0225}
FLOOR_BAND = (0.50, 0.55, 0.85, 0.90)

def floor_cut(market, line, proj):
    """What comes off an over's shown % (as a fraction) for how deep its line sits under the projection; 0 outside the band."""
    c = FLOOR_CUT.get(market)
    if not c or line is None or proj is None: return 0.0
    try: r = float(line) / float(proj)
    except Exception: return 0.0
    a, b, hi, d = FLOOR_BAND
    if not (a < r < d): return 0.0
    return c * ((r - a) / (b - a) if r < b else (1.0 if r <= hi else (d - r) / (d - hi)))

# ---- owner 11/18 morning ("Keep working"): FanDuel's shortest prices (research/floor_depth.py section 5, Weeks 6-10) ----
# In the three blend markets the hit rate climbs with the price up to about 70% and then stops: priced 68-72% hit 66.3% (416 legs),
# 72-76% hit 67.7% (381), 76-80% hit 63.4% (186). Across every market a leg at -317 or shorter lost 14.6% a leg, negative in all five
# weeks. Fitted on the other four weeks, the best slope for the price above 70% was 0 in every fold (the extra price carried no
# information); that full squeeze was better in 4 of 5 held-out weeks, and HALF of it in all 5 (+0.0002 / +0.0062 / +0.0034 / +0.0015 /
# +0.0028; log loss 0.6534 -> 0.6507 on 779 legs). At knots of 68% and 72% the half squeeze tied its worst week (-0.0000, -0.0002) and
# won the other four. So above PRICE_KNOT the price counts at half strength: -300 (75%) reads as 72.5%, -400 (80%) as 75%.
# Over side of the three blend markets only (the RECAL markets have their own fitted map; no graded unders or other markets up there).
# The edge is still shown against the REAL price, so a leg the model merely agrees with at -300 now shows a few points under it.
# NOT adopted: giving the model no credit above a short price (3 of 5 weeks on its own), squeezing the shown number itself above 68%
# (half size: 4 of 5), a flat cut for legs shown 70%+ (4 of 5; 5 of 5 only at 72%). Legs shown 70%+ still hit about 65% - the builder's
# honest chance (honest.py, capped at 68%) is the number that says so, and build_builder keeps -200 or shorter out of the short-priced tier.
PRICE_KNOT = 0.70; PRICE_SLOPE = 0.5
PRICE_MARKETS = ("Receiving Yards", "Receptions", "Passing Yards")

def squeezed(market, book):
    """FanDuel's implied % as the blend reads it (over side): above PRICE_KNOT it counts at PRICE_SLOPE strength."""
    if book is None or market not in PRICE_MARKETS or book <= PRICE_KNOT: return book
    return PRICE_KNOT + PRICE_SLOPE * (book - PRICE_KNOT)

def shown(p, book, market=None, w=W_MODEL, line=None, proj=None):
    """The shown % for a leg: per-market recalibration where research/recal.py found one (unders use the over side), else shrink().
    line / proj (the X of an X+ rung and the player's projection) switch on the floor cut above; without them the number is the blend
    alone. A short price is read at half strength first (squeezed())."""
    if p is None: return None
    if book is None: return p
    mk = str(market or ""); under = mk.startswith("Under "); base = mk[6:] if under else mk
    if base in RECAL:
        a, b, c = RECAL[base]
        po, bo = (1 - p, 1 - book) if under else (p, book)
        v = 1 / (1 + _m.exp(-(c + a * _lg(po) + b * _lg(bo))))
        return max(0.01, min(0.99, 1 - v if under else v))
    if w == W_MODEL: w = W_MARKET.get(base, w)
    v = shrink(p, book if under else squeezed(base, book), w); cut = floor_cut(base, line, proj)
    if cut: v = max(0.01, min(0.99, v + cut if under else v - cut))   # the under is the other side of the same line
    return v

# ---- owner 11/24 ("Yeah fix that"): the floor cut's upper taper could turn two rungs a yard apart upside down ----
# Stefon Diggs, 11/23: 50+ showed 0.5133 and 51+ showed 0.5146 (projection 57.2). In the 85-90% taper the cut shrinks by c / (0.05 x proj)
# a yard, which can be more than the blended ladder falls over that yard. A higher rung can never be likelier than the rung under it, so
# after the cut a rung that the CUT lifted over the rung beneath it is brought down to it. Only pairs the cut flipped are touched (a pair
# the blend itself had the other way round is the sheet's business, not this rule's); the move is at most the taper's step.
def ladder(rungs, market):
    """rungs: one player's OVER rungs of one market as (line, raw_p, book, proj, shown). Returns {position in rungs: lowered shown}
    for the rungs the floor cut lifted above the rung under them. Empty for markets without a floor cut."""
    if market not in FLOOR_CUT: return {}
    order = sorted((i for i, r in enumerate(rungs) if r[0] is not None and r[1] is not None and r[2] is not None and r[4] is not None), key=lambda i: rungs[i][0])
    out = {}; cur = {i: rungs[i][4] for i in order}
    for a, b in zip(order, order[1:]):
        if rungs[a][0] == rungs[b][0]: continue
        if shown(rungs[a][1], rungs[a][2], market) >= shown(rungs[b][1], rungs[b][2], market) and cur[a] < cur[b]:
            cur[b] = cur[a]; out[b] = cur[a]
    return out

def ladder_legs(legs, player, market, line, raw, book, proj, p, edge=None, nd=4):
    """Apply ladder() across a list of leg dicts in place (field names passed in). Returns how many rungs moved."""
    groups = {}
    for l in legs:
        if l.get(market) in FLOOR_CUT and l.get(p) is not None: groups.setdefault((l.get(player), l.get(market)), []).append(l)
    n = 0
    for (_, mk), xs in groups.items():
        if len(xs) < 2: continue
        for i, v in ladder([(l.get(line), l.get(raw), l.get(book), l.get(proj), l.get(p)) for l in xs], mk).items():
            xs[i][p] = round(v, nd) if nd else v; n += 1
            if edge and xs[i].get(book) is not None: xs[i][edge] = round(xs[i][p] - xs[i][book], nd) if nd else xs[i][p] - xs[i][book]
    return n
