"""The baseline, leak-free: every number for a game is built only from games BEFORE it.

This is the NFL sheet's recipe (AUTO - Settings) in code:
  season average  +  recent games (Last-N weight)  +  early-season pull toward a prior (TD regression / efficiency confidence)
  x the literal matchup (what this opponent allows vs the league, Matchup Weight)
"""
import numpy as np
import pandas as pd


def prior_sum(df, by, col):
    """Sum of `col` over the group's earlier rows (rows must already be in time order)."""
    g = df.groupby(by, sort=False)[col]
    return g.cumsum() - df[col]


def prior_count(df, by):
    """How many earlier rows the group has."""
    return df.groupby(by, sort=False).cumcount()


def prior_mean(df, by, col):
    n = prior_count(df, by)
    s = prior_sum(df, by, col)
    return (s / n.where(n > 0)).astype(float)


def prior_roll_mean(df, by, col, n):
    """Mean of the group's last n earlier rows (fewer when fewer exist)."""
    return df.groupby(by, sort=False)[col].transform(lambda s: s.shift(1).rolling(n, min_periods=1).mean())


def prior_roll_sum(df, by, col, n):
    return df.groupby(by, sort=False)[col].transform(lambda s: s.shift(1).rolling(n, min_periods=1).sum())


def shrink(mean, n, prior, k):
    """(n * mean + k * prior) / (n + k): with few games the prior leads, with many the player's own number does."""
    mean = pd.Series(mean, dtype=float) if not isinstance(mean, pd.Series) else mean.astype(float)
    n = n.astype(float) if isinstance(n, pd.Series) else float(n)
    out = (mean.fillna(0.0) * n + k * prior) / (n + k)
    return out.where(~pd.isna(prior), mean)


def blend(a, b, w_b):
    """(1 - w) * a + w * b; falls back to whichever side exists."""
    a = a.astype(float)
    b = b.astype(float)
    out = (1.0 - w_b) * a + w_b * b
    return out.where(a.notna() & b.notna(), a.fillna(b))


def matchup_factor(allowed, league, weight=1.0, lo=0.7, hi=1.4):
    """Opponent's allowed number vs the league's, raised to a weight (0 = ignore the matchup, 1 = take it in full)."""
    f = (allowed / league).clip(lower=lo, upper=hi).fillna(1.0)
    return np.power(f, weight)
