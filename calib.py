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
