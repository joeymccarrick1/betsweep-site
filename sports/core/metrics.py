"""How a projection or a probability is graded. Same yardsticks as the NFL receipts: error against the box score, Brier / log loss
against what happened, and a calibration table (when we say 60%, does it hit 60%)."""
import numpy as np
import pandas as pd


def mae(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    ok = np.isfinite(a) & np.isfinite(p)
    return float(np.abs(a[ok] - p[ok]).mean()) if ok.any() else float("nan")


def rmse(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    ok = np.isfinite(a) & np.isfinite(p)
    return float(np.sqrt(((a[ok] - p[ok]) ** 2).mean())) if ok.any() else float("nan")


def bias(actual, pred):
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    ok = np.isfinite(a) & np.isfinite(p)
    return float((p[ok] - a[ok]).mean()) if ok.any() else float("nan")


def brier(hit, p):
    h, p = np.asarray(hit, float), np.asarray(p, float)
    ok = np.isfinite(h) & np.isfinite(p)
    return float(((p[ok] - h[ok]) ** 2).mean()) if ok.any() else float("nan")


def logloss(hit, p, eps=1e-6):
    h, p = np.asarray(hit, float), np.clip(np.asarray(p, float), eps, 1 - eps)
    ok = np.isfinite(h) & np.isfinite(p)
    return float(-(h[ok] * np.log(p[ok]) + (1 - h[ok]) * np.log(1 - p[ok])).mean()) if ok.any() else float("nan")


def rps_1x2(p_home, p_draw, p_away, result):
    """Ranked probability score for home/draw/away (lower is better). result: 'H', 'D' or 'A'."""
    ph, pd_, pa = np.asarray(p_home, float), np.asarray(p_draw, float), np.asarray(p_away, float)
    r = np.asarray(result)
    oh, od = (r == "H").astype(float), (r == "D").astype(float)
    c1 = ph - oh
    c2 = (ph + pd_) - (oh + od)
    return float(((c1 ** 2 + c2 ** 2) / 2.0).mean())


def logloss_1x2(p_home, p_draw, p_away, result, eps=1e-6):
    r = np.asarray(result)
    p = np.where(r == "H", p_home, np.where(r == "D", p_draw, p_away))
    return float(-np.log(np.clip(np.asarray(p, float), eps, 1)).mean())


def calibration(hit, p, bins=(0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0001)):
    d = pd.DataFrame({"hit": np.asarray(hit, float), "p": np.asarray(p, float)}).dropna()
    d["bin"] = pd.cut(d.p, bins=list(bins), right=False)
    t = d.groupby("bin", observed=True).agg(n=("hit", "size"), said=("p", "mean"), hit=("hit", "mean")).reset_index()
    t["bin"] = t["bin"].astype(str)
    return t
