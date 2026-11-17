"""FanDuel's same-game price, estimated.

FanDuel does not pay the legs multiplied on a same-game parlay. research/sgp_discount.py measures what it does pay from FanDuel's own
quotes on the same-game slips we posted (re-run on Tuesdays; it writes research/sgp_discount.json). The estimate for n legs in one game:

    price = exp(-c * (n - 1)^p) / joint          joint = FanDuel's implied chances for the legs, joined with our same-game correlations

One leg per game is still the legs multiplied. Used by build_builder.py (the slip panel, "Build me a +N", saved slips) and
build_boards.py (the game-card best parlay). Always shown with an "about" mark: it is an estimate, the quote on FanDuel is the price.
"""
import json, math, os
_HERE = os.path.dirname(os.path.abspath(__file__))
C_DEFAULT, P_DEFAULT = 0.00146, 3.0          # the 11/17 fit (30 quotes, Weeks 7-10), used when the research file is missing or unreadable

def load():
    try:
        o = json.load(open(os.path.join(_HERE, "research", "sgp_discount.json")))
        c = float(o["c"]); p = float(o.get("p") or 2.0)
        if not (0 <= c <= 0.05 and 1.5 <= p <= 3.5): raise ValueError("fit out of range")
        return {"c": c, "p": p, "quotes": int(o.get("quotes") or 0), "weeks": o.get("weeks") or [],
                "bands": [{"legs": b["legs"], "quotes": b["quotes"], "median": b["median"]} for b in o.get("bands", []) if b.get("quotes")]}
    except Exception:
        return {"c": C_DEFAULT, "p": P_DEFAULT, "quotes": 0, "weeks": [], "bands": []}

def k(n, s): return math.exp(-s["c"] * (n - 1) ** s.get("p", 2.0)) if n > 1 else 1.0
def price(n, joint_book, s):
    """decimal price for n legs in ONE game whose FanDuel-implied chances join to joint_book; s = load()"""
    return max(1.01, k(n, s) / max(joint_book, 1e-7))
def note(s):
    """one plain sentence on the measured discount, for the pages"""
    b = [x for x in s.get("bands", []) if x["quotes"] >= 3]
    if not b: return "FanDuel prices same-game legs together, so it pays less than the legs multiplied."
    parts = [f"{round(x['median'] * 100)}% at {x['legs']}" for x in b]
    txt = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return (f"FanDuel prices same-game legs together. On {s['quotes']} same-game slips it has priced for us, its payout ran about "
            + txt.replace("% at", "% of the legs multiplied at", 1) + ".")

if __name__ == "__main__":
    s = load(); print(s); print(note(s)); print({n: round(k(n, s), 3) for n in range(1, 10)})
