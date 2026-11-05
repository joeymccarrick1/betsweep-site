#!/usr/bin/env python3
"""booklinks.py - DraftKings / Hard Rock betslip links for any set of legs, same rules as the betslips (template.html / build_builder.py).

A leg goes to a book at its exact rung when the book posts it (leg["bks"][book]) and otherwise at the book's nearest line
(leg["ba"][book], from hrswap.py / glbooks.py). If any leg has neither, there is no link for that book.
  DraftKings: https://sportsbook.draftkings.com/?outcomes=<id>+<id>   (ids URL-encoded, joined with '+')
  Hard Rock : one leg  -> https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/<id>
              2+ legs  -> hardrock://betslip/<id>,<id>   (the share link only ever carries one selection - owner-tested 10/21)
links(legs) -> {"dk": {"url", "subs": [...]}, "hr": {...}}   only books that price every leg; subs = human notes for substituted lines.
"""
from urllib.parse import quote

NAMES = {"dk": "DraftKings", "hr": "Hard Rock"}

def _pick(l, b):
    x = (l.get("bks") or {}).get(b)
    if x and x.get("s"): return {"s": x["s"], "o": x.get("o"), "sub": None}
    a = (l.get("ba") or {}).get(b)
    if a and a.get("s"):
        if l.get("gl"):
            side = (l["gl"] or {}).get("side", "")
            ours = l.get("pl") or ""
            theirs = (f"{'Over' if side == 'OVER' else 'Under'} {a['ln']:g}" if l.get("m") == "Total" else f"{side} {a['ln']:+g}")
        else:
            ln = l.get("ln") or 0
            ours = f"{l.get('pl', '')} {int(round(ln))}+"; theirs = f"{l.get('pl', '')} {a['ln']:g}+"
        return {"s": a["s"], "o": a.get("o"), "sub": f"{theirs} for {ours}"}
    return None

def url(ids, b):
    if not ids: return None
    if b == "dk": return "https://sportsbook.draftkings.com/?outcomes=" + "+".join(quote(str(i), safe="") for i in ids)
    return ("https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/" + str(ids[0])) if len(ids) == 1 else ("hardrock://betslip/" + ",".join(str(i) for i in ids))

def links(legs):
    out = {}
    for b in ("dk", "hr"):
        ps = [_pick(l or {}, b) for l in legs]
        if legs and all(ps):
            out[b] = {"url": url([p["s"] for p in ps], b), "subs": [p["sub"] for p in ps if p["sub"]]}
    return out

def _dec(o):
    try: o = float(o)
    except Exception: return None
    if not o: return None
    return 1 + o / 100 if o > 0 else 1 + 100 / -o

def _am(o):
    try: o = int(round(float(o)))
    except Exception: return ""
    return f"+{o}" if o > 0 else f"\u2212{-o}"

def best(leg):
    """Which book pays the most for ONE leg at its exact line: 'fd' (leg['o']), 'dk' or 'hr' (leg['bks'][b]['o']); nearest-line
    substitutes are a different bet and never count. None when FanDuel has no price or nothing beats it; ties go to FanDuel."""
    fd = _dec((leg or {}).get("o"))
    if not fd: return None
    top, book = fd, "fd"
    for b in ("dk", "hr"):
        x = ((leg or {}).get("bks") or {}).get(b)
        d = _dec((x or {}).get("o"))
        if d and d > top + 1e-9: top, book = d, b
    return book

def buttons(legs, cls_dk="dkb", cls_hr="hrb", single=True, price=False):
    """HTML anchors for the books that price every leg; title carries the substitution note.
    price=True (one leg): the button reads 'DK \u2212150' at the book's exact rung (nearest-line substitutes keep the plain label + \u2248,
    their price is for a different line) and the best-paying book gets class 'best' (owner 10/29: show the DK/HR price, not just a link)."""
    from html import escape as E
    h = ""; bb = best(legs[0]) if (price and len(legs) == 1) else None
    for b, v in links(legs).items():
        tip = ("Uses " + NAMES[b] + "'s nearest line: " + "; ".join(v["subs"]) + ". Prices and model % shown are FanDuel's.") if v["subs"] else f"Opens {NAMES[b]} with {'this leg' if len(legs) == 1 else 'these legs'} on the betslip"
        lab = ("DK" if b == "dk" else "HR") if single else "Bet it on " + NAMES[b]
        cls = (cls_dk if b == "dk" else cls_hr)
        if price and len(legs) == 1 and not v["subs"]:
            o = ((legs[0].get("bks") or {}).get(b) or {}).get("o")
            if o is not None: lab += " " + _am(o)
            if bb == b: cls += " best"; tip = "Best price for this leg. " + tip
        h += f'<a class="{cls}" href="{E(v["url"])}" target="_blank" rel="noopener" title="{E(tip)}">{lab}{"\u2248" if v["subs"] else ""}</a>'
    return h

def note(legs):
    """One line listing substituted lines per book (for multi-leg cards)."""
    bits = []
    for b, v in links(legs).items():
        if v["subs"]: bits.append(f"{NAMES[b]} uses its nearest line: " + "; ".join(v["subs"]))
    return (" · ".join(bits) + ". Prices and model % shown are FanDuel's.") if bits else ""
