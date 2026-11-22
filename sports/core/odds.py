"""Prices. Same conventions as the NFL generators (calib.py / build_promo.py): American odds, implied %, model blended with the book."""
import math


def implied(american):
    """American odds -> the chance the price needs (vig included)."""
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def american(p):
    """Chance -> fair American odds (rounded). None outside (0, 1)."""
    if p is None or not (0.0 < p < 1.0):
        return None
    return int(round((1.0 / p - 1.0) * 100)) if p < 0.5 else -int(round(p / (1.0 - p) * 100))


def decimal(american_odds):
    a = float(american_odds)
    return 1.0 + a / 100.0 if a > 0 else 1.0 + 100.0 / -a


def devig(*implieds):
    """Strip the book's margin from a full market (both sides of an over/under, or home/draw/away)."""
    s = sum(implieds)
    return [x / s for x in implieds] if s > 0 else list(implieds)


def blend(model_p, book_p, w_model=0.5):
    """What the site shows: w * model + (1 - w) * book. NFL finding (calib.py): the raw model ran overconfident where it
    disagreed with the price, so every new sport starts at 50/50 and moves only when graded legs say so."""
    if model_p is None:
        return None
    if book_p is None:
        return model_p
    return max(0.01, min(0.99, w_model * model_p + (1.0 - w_model) * book_p))


def edge(shown_p, book_p):
    return None if shown_p is None or book_p is None else shown_p - book_p


def parlay_american(american_list):
    d = 1.0
    for a in american_list:
        d *= decimal(a)
    return int(round((d - 1.0) * 100)) if d >= 2.0 else -int(round(100.0 / (d - 1.0)))
