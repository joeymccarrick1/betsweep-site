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
def shown(p, book, market=None, w=W_MODEL):
    """The shown % for a leg: per-market recalibration where research/recal.py found one (unders use the over side), else shrink()."""
    if p is None: return None
    if book is None: return p
    mk = str(market or ""); under = mk.startswith("Under "); base = mk[6:] if under else mk
    if base in RECAL:
        a, b, c = RECAL[base]
        po, bo = (1 - p, 1 - book) if under else (p, book)
        v = 1 / (1 + _m.exp(-(c + a * _lg(po) + b * _lg(bo))))
        return max(0.01, min(0.99, 1 - v if under else v))
    return shrink(p, book, w)
