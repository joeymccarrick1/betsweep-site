"""Team budgets: the NFL sheet's vacated-targets idea, made general.

A team has a fixed amount of something to hand out each game (240 minutes in the NBA, a team's targets or carries in football,
its shots in soccer). Each active player starts from his own baseline. When someone is out, the active baselines add up to less than
the budget and the gap is shared out; when someone returns, they add up to more and everyone gives a little back.
`c` is the transfer coefficient the walk-forward test picks (the sheet's "RB Missing-Starter Carry Transfer 0.5" is the same knob).
"""
import numpy as np
import pandas as pd


def rebalance(base, groups, total, c=1.0, cap=None, power=1.0):
    """base: each active player's baseline (Series); groups: team-game key per row; total: the team budget (number or Series).
    Returns the adjusted Series. Shortfalls are shared in proportion to base**power x headroom under `cap` (bench players can absorb more
    than a starter already near the cap); surpluses are taken back in proportion to base."""
    base = base.astype(float)
    tot = total if isinstance(total, pd.Series) else pd.Series(float(total), index=base.index)
    s = base.groupby(groups, sort=False).transform("sum")
    gap = (tot - s) * c
    if cap is None:
        w_up = np.power(base.clip(lower=0), power)
    else:
        w_up = np.power(base.clip(lower=0), power) * (cap - base).clip(lower=0)
    w_dn = base.clip(lower=0)
    su = w_up.groupby(groups, sort=False).transform("sum")
    sd = w_dn.groupby(groups, sort=False).transform("sum")
    up = gap * (w_up / su.where(su > 0))
    dn = gap * (w_dn / sd.where(sd > 0))
    adj = base + np.where(gap >= 0, up.fillna(0.0), dn.fillna(0.0))
    if cap is not None:
        adj = adj.clip(upper=cap)
    return adj.clip(lower=0)


def scale_to_total(expected, groups, total, u=1.0, lo=0.6, hi=1.6):
    """Multiplier for each active player's rate so the team's expected sum moves a fraction `u` of the way to `total`."""
    s = expected.groupby(groups, sort=False).transform("sum")
    tot = total if isinstance(total, pd.Series) else pd.Series(float(total), index=expected.index)
    ratio = (tot / s.where(s > 0)).clip(lower=lo, upper=hi).fillna(1.0)
    return 1.0 + u * (ratio - 1.0)
