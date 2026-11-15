"""The grid, schedule-adjusted.

BetSweep's NFL model started as an x/y grid: every team down one side, every team across the top, what each offense averages and what
each defense allows. This is that grid solved properly for uneven schedules (who you played matters a lot in college football and early
in any season):

    expected(team vs opp) = league average  x  home edge  x  OFFENSE[team]  x  DEFENSE-ALLOWED[opp]

OFFENSE 1.20 = scores 20% more than an average team would against the same opponents; DEFENSE 0.85 = allows 15% less.
Recent games count more (half-life in days), and each team is pulled toward a prior worth `k_games` games so three games do not
swing a rating (the sheet's 'PPG base (shrunk)' and TD regression do the same job).
"""
import numpy as np


def decay_weights(days_ago, half_life_days):
    d = np.asarray(days_ago, dtype=float)
    return np.power(0.5, d / float(half_life_days)) if half_life_days else np.ones_like(d)


def fit_grid(team, opp, y, n_teams, home=None, w=None, k_games=3.0, prior_o=None, prior_d=None, iters=80, tol=1e-7):
    """team, opp: integer codes per row (one row per team per game); y: what the team produced; home: +1 home, -1 away, 0 neutral.
    Returns dict(L, H, O, D)."""
    team = np.asarray(team, dtype=int)
    opp = np.asarray(opp, dtype=int)
    y = np.asarray(y, dtype=float)
    w = np.ones_like(y) if w is None else np.asarray(w, dtype=float)
    s = np.zeros_like(y) if home is None else np.asarray(home, dtype=float)
    po = np.ones(n_teams) if prior_o is None else np.asarray(prior_o, dtype=float)
    pd_ = np.ones(n_teams) if prior_d is None else np.asarray(prior_d, dtype=float)
    O, Dv, H = po.copy(), pd_.copy(), 1.0
    sw = w.sum()
    if sw <= 0 or len(y) == 0:
        return {"L": float("nan"), "H": 1.0, "O": O, "D": Dv}
    L = float((w * y).sum() / sw)
    k = k_games * L                                         # prior strength in the stat's own units
    for _ in range(iters):
        Hs = np.power(H, s)
        O_new = (np.bincount(team, w * y, n_teams) + k * po) / (np.bincount(team, w * L * Hs * Dv[opp], n_teams) + k)
        D_new = (np.bincount(opp, w * y, n_teams) + k * pd_) / (np.bincount(opp, w * L * Hs * O_new[team], n_teams) + k)
        base = w * O_new[team] * D_new[opp]
        L_new = float((w * y).sum() / (base * Hs).sum())
        if home is not None and (s > 0).any() and (s < 0).any():
            rh = (w * y)[s > 0].sum() / (L_new * base[s > 0]).sum()
            ra = (w * y)[s < 0].sum() / (L_new * base[s < 0]).sum()
            H_new = float(np.sqrt(rh / ra)) if rh > 0 and ra > 0 else 1.0
        else:
            H_new = 1.0
        done = max(np.abs(O_new - O).max(), np.abs(D_new - Dv).max(), abs(H_new - H)) < tol
        O, Dv, L, H = O_new, D_new, L_new, H_new
        if done:
            break
    return {"L": L, "H": H, "O": O, "D": Dv}


def expect(g, team, opp, home=0):
    """What the grid expects `team` to produce against `opp` (home: +1 at home, -1 away, 0 neutral)."""
    return g["L"] * np.power(g["H"], home) * g["O"][team] * g["D"][opp]
