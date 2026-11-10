#!/usr/bin/env python3
"""slipgrade.py - grade a slip's legs from the week's game log and final scores (owner 11/10: the chat-built slips in
'ASSIST - Slip Log' were being graded by hand).

    G = Grader(IN, week)                 # in/gamelog.json ('AUTO - Player Game Log') + in/games.csv (finals)
    G.leg("Justin Herbert 175+ pass yds")            -> ("HIT" | "MISS" | "PENDING", "Justin Herbert 262 (hit 175+ pass yds)")
    G.slip("leg | leg | leg", games="BUF-MIN")       -> {"result": "WON" | "LOST" | "PENDING", "hit": 3, "n": 4, "missed": [...], "pending": [...], "notes": "..."}

Same rules as grade_promos.py (which grades the PROMO tab and is left as it is): nothing is invented. A leg whose player has no stat row
that week, or that cannot be read, is PENDING; a slip is LOST as soon as one leg has plainly missed, WON only when every leg has plainly
hit, PENDING otherwise. Names must match the game log (exact, or the same last name with a first name sharing its first three letters);
a bare last name is used only when exactly one player in that week's log carries it.

Legs it reads (one per line, or separated by " | " when the cell has no line breaks):
    Player 175+ pass yds | Player 6+ rec | Player 40+ rec yds | Player 70+ rush yds | Player 2+ pass TDs | Player 90+ rush + rec yds
    Player ATD / anytime TD / TD        A or B TD (either scores)            Player 2+ TDs
    Player U237.5 pass yds / Player under 5.5 rec                            Team ML        Team -3.5        Over 44.5 / Under 49.5 (AAA-BBB)
    and the PROMO tab's own form on a line by itself:  Player | Receiving Yards 40+ | -110     KC -3.5 | Spread     Over 44.5 (BUF-MIN) | Total
A total with no game named takes the row's game when the row names exactly one.
"""
import csv, json, os, re

NICK = {"cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF", "panthers": "CAR", "bears": "CHI", "bengals": "CIN", "browns": "CLE", "cowboys": "DAL", "broncos": "DEN",
        "lions": "DET", "packers": "GB", "texans": "HOU", "colts": "IND", "jaguars": "JAX", "chiefs": "KC", "raiders": "LV", "chargers": "LAC", "rams": "LA", "dolphins": "MIA",
        "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG", "jets": "NYJ", "eagles": "PHI", "steelers": "PIT", "49ers": "SF", "niners": "SF", "seahawks": "SEA",
        "buccaneers": "TB", "bucs": "TB", "titans": "TEN", "commanders": "WAS"}
ALIAS = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
# stat words -> (label, game-log columns summed, or "long" for the longest reception)
STATS = [(r"pass(?:ing)?\s*y(?:ar)?ds?", ("pass yds", ("Pass Yds",))), (r"rush(?:ing)?\s*\+\s*rec(?:eiving)?(?:\s*y(?:ar)?ds?)?", ("rush + rec yds", ("Rush Yds", "Rec Yds"))),
         (r"rush(?:ing)?\s*y(?:ar)?ds?", ("rush yds", ("Rush Yds",))), (r"rec(?:eiving)?\s*y(?:ar)?ds?", ("rec yds", ("Rec Yds",))),
         (r"long(?:est)?\s*rec(?:eption)?", ("longest rec", "long")), (r"pass(?:ing)?\s*tds?", ("pass TDs", ("Pass TD",))), (r"completions", ("completions", ("Completions",))),
         (r"rush(?:ing)?\s*att(?:empts)?|carries", ("carries", ("Rush Att",))), (r"int(?:erception)?s?", ("INTs", ("INT",))),
         (r"rec(?:eptions?)?|catch(?:es)?", ("rec", ("Receptions",))), (r"(?:anytime\s*)?tds?|touchdowns?", ("TDs", ("Rush TD", "Rec TD")))]
STAT_RE = "|".join(f"(?:{p})" for p, _ in STATS)
def _stat(words):
    w = words.strip().lower()
    for p, v in STATS:
        if re.fullmatch(p, w): return v
    return None
def _is_market(txt):
    """the right-hand side of the PROMO tab's "Who | Market" form"""
    t = str(txt).strip().lower()
    if t.startswith(("spread", "total", "moneyline", "first td")) or t in ("ml", "anytime td", "either td", "anytime touchdown", "either/or td"): return True
    m = re.fullmatch(r"(?:under\s+)?(.+?)\s+\d+(?:\.\d+)?\+?", t)
    return bool(m and _stat(m.group(1)))
def _num(x):
    try: return float(str(x).replace("+", "").replace(",", ""))
    except Exception: return None
def norm(n):
    n = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", str(n).strip().lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", n)).strip()

class Grader:
    def __init__(self, IN, week):
        self.week = int(week); self.by = {}; self.last = {}; self.fin = {}   # last: last name -> every player carrying it in the season's log
        try: g = json.load(open(os.path.join(IN, "gamelog.json")))["values"]
        except Exception: g = [[]]
        H = {c.strip(): i for i, c in enumerate(g[0])} if g and g[0] else {}
        self.H = H
        for r in g[1:]:
            if "Week" not in H or "Player" not in H or len(r) <= max(H["Week"], H["Player"]): continue
            k = norm(r[H["Player"]])
            if k: self.last.setdefault(k.split()[-1], set()).add(k)
            if str(r[H["Week"]]).strip() == str(self.week): self.by.setdefault(k, []).append(r)
        try:
            for x in csv.DictReader(open(os.path.join(IN, "games.csv"), newline="")):
                if x.get("season") == "2026" and x.get("game_type", "REG") == "REG" and str(x.get("week")) == str(self.week) and _num(x.get("home_score")) is not None and _num(x.get("away_score")) is not None:
                    h, a = ALIAS.get(x["home_team"], x["home_team"]), ALIAS.get(x["away_team"], x["away_team"])
                    self.fin[h] = (_num(x["home_score"]), _num(x["away_score"]), a); self.fin[a] = (_num(x["away_score"]), _num(x["home_score"]), h)
        except Exception: pass
    @property
    def ready(self): return bool(self.by)
    def team(self, tok):
        t = ALIAS.get(str(tok).strip().upper(), str(tok).strip().upper())
        if t in self.fin or re.fullmatch(r"[A-Z]{2,3}", t) and t in set(NICK.values()): return t
        return NICK.get(str(tok).strip().lower())
    def rows(self, name):
        """-> (rows, None) or (None, why)"""
        k = norm(name); kw = k.split()
        if not kw: return None, "no name"
        if k in self.by: return self.by[k], None
        if len(kw) == 1:   # a bare last name: only when one player in the whole season's log carries it
            c = self.last.get(kw[0], set())
            if len(c) == 1: return (self.by[next(iter(c))], None) if next(iter(c)) in self.by else (None, "no stat row")
            return None, (f"'{name.strip()}' fits {len(c)} players - write the full name" if c else "no stat row")
        for kk, v in self.by.items():
            w = kk.split()
            if w and len(w) == len(kw) and w[-1] == kw[-1] and w[0][:3] == kw[0][:3]: return v, None
        return None, "no stat row"
    def got(self, rs, cols):
        v = lambda r, c: (_num(r[self.H[c]]) or 0.0) if c in self.H and self.H[c] < len(r) else 0.0
        if cols == "long": return max(v(r, "Longest Rec") for r in rs)
        return sum(v(r, c) for r in rs for c in cols)
    # ---- one leg ----
    def leg(self, text, games=""):
        t = re.sub(r"\s+", " ", str(text)).strip().strip(".")
        if not t: return "PENDING", "empty leg"
        # the PROMO tab's own form: "Who | Market N+"
        if "|" in t:
            who, mk = [x.strip() for x in t.split("|")][:2]; ml = mk.lower()   # a third field is the price
            if ml.startswith("first td"): return "PENDING", f"{who}: first TD needs a hand grade"
            if ml.startswith(("spread", "money")) or ml == "ml": return self.leg(who if not ml.startswith("money") and ml != "ml" or re.search(r"\bml$", who, re.I) else who + " ML", games)
            if ml.startswith("total"): return self.leg(who, games)
            if ml in ("anytime td", "either td", "anytime touchdown", "either/or td"): return self.leg(who + " TD", games)
            m = re.fullmatch(r"(under\s+)?(.+?)\s+(\d+(?:\.\d+)?)\+?", mk, re.I)
            if m and _stat(m.group(2)): return self.leg(f"{who} {'under ' if m.group(1) else ''}{m.group(3)}{'' if m.group(1) else '+'} {m.group(2)}", games)
            return "PENDING", f"{who}: market '{mk}' not read"
        tl = t.lower()
        if re.search(r"\bfirst td\b|\b1st td\b", tl): return "PENDING", f"{t}: first TD needs a hand grade"
        # game total
        m = re.fullmatch(r"(over|under)\s+(\d+(?:\.\d+)?)(?:\s*(?:points|pts))?(?:\s*\(?\s*([A-Za-z0-9]{2,3})\s*(?:-|@|vs\.?|at)\s*([A-Za-z0-9]{2,3})\s*\)?)?", t, re.I)
        if m:
            tm = self.team(m.group(3)) if m.group(3) else None
            if not tm:
                gs = re.findall(r"\b([A-Z]{2,3})\s*[-@]\s*([A-Z]{2,3})\b", str(games))
                if len(gs) == 1: tm = self.team(gs[0][0])
            if not tm: return "PENDING", f"{t}: which game?"
            if tm not in self.fin: return "PENDING", f"{t}: no final score yet"
            own, opp, o = self.fin[tm]; tot = own + opp; need = float(m.group(2)); over = m.group(1).lower() == "over"
            ok = tot > need if over else tot < need
            if tot == need: return "PENDING", f"{tm}-{o} total {tot:g} (push on {need:g})"
            return ("HIT" if ok else "MISS"), f"{tm}-{o} total {tot:g} ({'hit' if ok else 'missed'} {m.group(1).lower()} {need:g})"
        # moneyline
        m = re.fullmatch(r"(.+?)\s+(?:ml|moneyline|to win)", t, re.I)
        if m:
            tm = self.team(m.group(1))
            if not tm: return "PENDING", f"{t}: team not read"
            if tm not in self.fin: return "PENDING", f"{t}: no final score yet"
            own, opp, o = self.fin[tm]
            if own == opp: return "PENDING", f"{tm} {own:g}-{opp:g} vs {o} (tie)"
            return ("HIT" if own > opp else "MISS"), f"{tm} {own:g}-{opp:g} vs {o} ({'hit' if own > opp else 'missed'} {tm} ML)"
        # spread
        m = re.fullmatch(r"([A-Za-z0-9 .]+?)\s*([+-]\d+(?:\.\d+)?)", t)
        if m and self.team(m.group(1)):
            tm = self.team(m.group(1)); pts = float(m.group(2))
            if tm not in self.fin: return "PENDING", f"{t}: no final score yet"
            own, opp, o = self.fin[tm]; mar = own - opp + pts
            if mar == 0: return "PENDING", f"{tm} {own:g}-{opp:g} vs {o} (push on {pts:+g})"
            return ("HIT" if mar > 0 else "MISS"), f"{tm} {own:g}-{opp:g} vs {o} ({'hit' if mar > 0 else 'missed'} {tm} {pts:+g})"
        # under: "Player U237.5 pass yds" / "Player under 5.5 rec"
        m = re.fullmatch(rf"(.+?)\s+(?:u|under)\s*(\d+(?:\.\d+)?)\s*({STAT_RE})", t, re.I)
        if m:
            st = _stat(m.group(3)); rs, why = self.rows(m.group(1))
            if rs is None: return "PENDING", f"{m.group(1).strip()}: {why}"
            v = self.got(rs, st[1]); need = float(m.group(2))
            if v == need: return "PENDING", f"{m.group(1).strip()} {v:g} (push on {need:g} {st[0]})"
            return ("HIT" if v < need else "MISS"), f"{m.group(1).strip()} {v:g} ({'hit' if v < need else 'missed'} under {need:g} {st[0]})"
        # over rung: "Player 175+ pass yds"
        m = re.fullmatch(rf"(.+?)\s+(\d+(?:\.\d+)?)\+\s*({STAT_RE})", t, re.I)
        if m:
            st = _stat(m.group(3)); rs, why = self.rows(m.group(1))
            if rs is None: return "PENDING", f"{m.group(1).strip()}: {why}"
            v = self.got(rs, st[1]); need = float(m.group(2))
            return ("HIT" if v >= need else "MISS"), f"{m.group(1).strip()} {v:g} ({'hit' if v >= need else 'missed'} {need:g}+ {st[0]})"
        # either-or touchdown: "A or B TD"
        m = re.fullmatch(r"(.+?)\s+or\s+(.+?)\s+(?:atd|anytime td|td|to score|either td)", t, re.I)
        if m:
            res = []
            for n in (m.group(1), m.group(2)):
                rs, why = self.rows(n); res.append((n.strip(), self.got(rs, ("Rush TD", "Rec TD")) if rs else None, why))
            txt = ", ".join(f"{n} {int(v)} TD" if v is not None else f"{n}: {why}" for n, v, why in res)
            if any(v for _, v, _ in res if v): return "HIT", txt + " (hit either-or)"
            if any(v is None for _, v, _ in res): return "PENDING", txt
            return "MISS", txt + " (missed either-or)"
        # anytime touchdown: "Player ATD"
        m = re.fullmatch(r"(.+?)\s+(?:atd|anytime td|anytime touchdown|td|to score)", t, re.I)
        if m:
            rs, why = self.rows(m.group(1))
            if rs is None: return "PENDING", f"{m.group(1).strip()}: {why}"
            v = self.got(rs, ("Rush TD", "Rec TD"))
            return ("HIT" if v >= 1 else "MISS"), f"{m.group(1).strip()} {int(v)} TD ({'hit' if v >= 1 else 'missed'} anytime TD)"
        return "PENDING", f"not read: {t[:60]}"
    # ---- a whole slip ----
    def slip(self, legs_text, games=""):
        s = str(legs_text or "")
        parts = [x.strip() for x in s.split(" | ") if x.strip()]
        if "\n" in s.strip(): legs = [x.strip() for x in s.split("\n") if x.strip()]
        elif len(parts) in (2, 3) and _is_market(parts[1]): legs = [s.strip()]   # one leg in the PROMO tab's form (who | market | price)
        else: legs = parts
        g = [self.leg(l, games) for l in legs]
        hit = sum(1 for st, _ in g if st == "HIT"); miss = [d for st, d in g if st == "MISS"]; pend = [d for st, d in g if st == "PENDING"]
        res = "LOST" if miss else ("WON" if g and not pend else "PENDING")
        return {"result": res, "hit": hit, "n": len(g), "missed": miss, "pending": pend, "legs": g,
                "notes": f"{hit}/{len(g)} legs" + (". Missed: " + "; ".join(miss) if miss else "") + (". Not graded: " + "; ".join(pend) if pend else "") + ("" if miss or pend else ". " + "; ".join(d for _, d in g))}
