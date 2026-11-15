"""Projection -> chance of clearing a line (the 'X+' ladders FanDuel sells).

Counts (points, rebounds, assists, threes, shots, goals) use a negative binomial: a Poisson with extra spread, one spread number per
stat fitted on past projection errors ("qp": variance = phi x mean). Margins and totals use a normal curve. The NFL build does the same job with probit curves
fitted by role and stat (probit.json); the fit here is refreshed from each sport's own walk-forward errors.
"""
import numpy as np
from scipy import stats
from scipy.optimize import minimize_scalar


def p_at_least(line, mean, dist="nb", size=None, sd=None, phi=None):
    """P(X >= line). line may be a half (17.5) or a whole number (20 means '20+')."""
    mean = np.asarray(mean, dtype=float)
    line = np.asarray(line, dtype=float)
    k = np.ceil(line)                      # smallest whole number that clears the line
    m = np.clip(mean, 1e-6, None)
    if dist == "poisson":
        return stats.poisson.sf(k - 1, m)
    if dist == "nb":
        r = float(size)
        return stats.nbinom.sf(k - 1, r, r / (r + m))
    if dist == "qp":                       # variance = phi x mean: one spread number per stat (best on the NBA holdout)
        r = m / max(float(phi) - 1.0, 1e-6)
        return stats.nbinom.sf(k - 1, r, r / (r + m))
    if dist == "normal":
        return stats.norm.sf((k - 0.5 - mean) / np.asarray(sd, dtype=float))
    raise ValueError(dist)


def fit_phi(actual, proj):
    """Spread number phi (variance = phi x mean) that makes the past projection errors most likely."""
    y = np.asarray(actual, dtype=float)
    m = np.clip(np.asarray(proj, dtype=float), 1e-6, None)
    ok = np.isfinite(y) & np.isfinite(m)
    y, m = y[ok], m[ok]

    def nll(lp):
        r = m / np.exp(lp)
        return -stats.nbinom.logpmf(y, r, r / (r + m)).sum()

    res = minimize_scalar(nll, bounds=(-5.0, 3.5), method="bounded")
    return float(1.0 + np.exp(res.x))


def fit_nb_size(actual, proj):
    """Spread number r (variance = mean + mean^2 / r) that makes the past projection errors most likely."""
    y = np.asarray(actual, dtype=float)
    m = np.clip(np.asarray(proj, dtype=float), 1e-6, None)
    ok = np.isfinite(y) & np.isfinite(m)
    y, m = y[ok], m[ok]

    def nll(logr):
        r = np.exp(logr)
        return -stats.nbinom.logpmf(y, r, r / (r + m)).sum()

    res = minimize_scalar(nll, bounds=(np.log(0.3), np.log(500.0)), method="bounded")
    return float(np.exp(res.x))


def scoreline_matrix(lam_home, lam_away, rho=0.0, max_goals=10):
    """Soccer: chance of every score from two Poisson goal rates, with the Dixon-Coles fix for 0-0 / 1-0 / 0-1 / 1-1."""
    i = np.arange(max_goals + 1)
    ph = stats.poisson.pmf(i, lam_home)[:, None]
    pa = stats.poisson.pmf(i, lam_away)[None, :]
    m = ph * pa
    if rho:
        m[0, 0] *= 1 - lam_home * lam_away * rho
        m[0, 1] *= 1 + lam_home * rho
        m[1, 0] *= 1 + lam_away * rho
        m[1, 1] *= 1 - rho
        m = np.clip(m, 0, None)
    return m / m.sum()


def soccer_markets(lam_home, lam_away, rho=0.0):
    m = scoreline_matrix(lam_home, lam_away, rho)
    n = m.shape[0]
    idx = np.add.outer(np.arange(n), np.arange(n))
    return {
        "home": float(np.tril(m, -1).sum()), "draw": float(np.trace(m)), "away": float(np.triu(m, 1).sum()),
        "over15": float(m[idx >= 2].sum()), "over25": float(m[idx >= 3].sum()), "over35": float(m[idx >= 4].sum()),
        "btts": float(m[1:, 1:].sum()),
    }
