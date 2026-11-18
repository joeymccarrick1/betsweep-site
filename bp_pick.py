#!/usr/bin/env python3
"""bp_pick.py - which candidate slip a game card shows as its Best parlay (build_boards.best_parlay calls it; tests/bp_pick.py).

A candidate is a tuple that starts (pj, ev, ...): the model's chance the whole slip hits, and what it is worth per $1 at FanDuel's
same-game price (an ESTIMATE of FanDuel's quote - sgp.py; its median miss on short slips is about 3% of the price).

  1. Slips at fair or better (ev >= 0): the most likely to hit.
  2. Else slips within NEAR (5 cents) of fair: the most likely to hit.
  3. Else nothing is close to fair. Until 11/17 this took the best ev outright. On a card with only game lines to work with every
     pair sits 6 to 11 cents under fair (FanDuel's same-game discount on two coin flips), and "best ev" was settled by a cent or
     two - less than the price estimate itself misses by, and at the 3,000 draws used for the first pass less than the
     simulation moves a slip. Now: slips within TIE (3 cents) of the best ev count as tied; among them a slip with a player leg
     beats one without (owner 11/17: he wants a real parlay on the card, not two game lines), then the most likely to hit wins,
     then ev. build_boards re-prices the candidates with the card's own draws before it asks (so the tie is judged on the
     numbers the card prints). Week 11 Tuesday, precise numbers: LAC-NYJ LAC -3.5 + Over 41.5 (24%, -8.2c) over Jets ML + Over
     (19%, -6.0c); MIN-SF 49ers ML + Over 46.5 (29%, -9.5c) over MIN +3 + Over (24%, -7.4c).

The other half of the same fix lives in build_boards.best_parlay (dogml): a card parlay carries no moneyline the model itself
has under a coin flip, unless Sweep says calls that side. That, not the tie, is what moved PHI-PIT off Eagles ML + Over 38.5
(+423, 18%, -6.8c) under a line reading "Model has PIT 21.5-17" to PIT -4.5 + Under 38.5 (25%, -10.2c): the two were 3.4 cents
apart. The owner had flagged the same shape on 11/10 (BUF-MIN: "MIN ML + Over 45.5" as Best parlay).
"""
NEAR = 0.05   # "within 5 cents of fair"
TIE = 0.03    # rule 3: this close to the best ev = tied (the same-game price estimate misses by about this much on short slips)


def pick(priced, has_player=None):
    """-> (choice, plus, near, rule). priced: non-empty list of tuples starting (pj, ev, ...). has_player(x) -> bool (optional)."""
    plus = [x for x in priced if x[1] >= 0]
    near = [x for x in priced if x[1] >= -NEAR]
    pool = plus or near
    if pool: return max(pool, key=lambda x: (x[0], x[1])), plus, near, (1 if plus else 2)
    best = max(x[1] for x in priced)
    tied = [x for x in priced if x[1] >= best - TIE]
    hp = has_player or (lambda x: False)
    return max(tied, key=lambda x: (1 if hp(x) else 0, x[0], x[1])), plus, near, 3


def fit_note(p, g):
    """The home page's reason line for its lead parlay. "Built for the game's most likely script" only when the ending the slip
    leans on IS the model's most likely one - until 11/17 the page printed the slip's own best ending under that name whatever its
    odds (true for BUF-MIA that day; 11 of the 13 cards' slips leaned on another ending). p = the card's record (a, b, fit);
    g = the game (probs in build_boards.SC_LABEL order: a by 10+, close and low, shootout, b by 10+)."""
    fit = p.get("fit") or ""; lab = [f"{p.get('a')} by 10+", "close, low", "shootout", f"{p.get('b')} by 10+"]; pr = g.get("probs") or []
    if not fit: return ""
    if fit not in lab or len(pr) != 4 or any(x is None for x in pr): return f"Does best if the game ends {fit}"
    k = lab.index(fit)
    if pr[k] >= max(pr): return f"Built for the game's most likely script ({fit})"
    how = {1: "the game stays close and low-scoring", 2: "the game turns into a shootout"}.get(k, f"{fit.split(' by ')[0]} wins by 10 or more")
    return f"Does best if {how} ({pr[k]:.0f}% likely)"


if __name__ == "__main__":
    demo = [(0.177, -0.074, "Over 38.5 + Eagles ML"), (0.175, -0.085, "Under 38.5 + Eagles ML"), (0.247, -0.098, "PIT -4.5 + Under 38.5"),
            (0.246, -0.099, "Over 38.5 + PHI +4.5"), (0.246, -0.100, "PIT -4.5 + Over 38.5"), (0.243, -0.110, "Under 38.5 + PHI +4.5")]
    print(pick(demo)[0], "rule", pick(demo)[3])
