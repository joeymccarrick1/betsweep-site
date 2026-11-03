#!/usr/bin/env python3
"""BetSweep promoted-bet grader (Tuesdays) — v2026-10-19.
Reads  in/promos.json  ('PROMO - Promoted Bets'!A1:N100) and in/gamelog.json ('AUTO - Player Game Log').
Grades every promo of the target week leg by leg from the game log and writes out/promo_grades.json:
  {"week": W, "updates": [{"range": "'PROMO - Promoted Bets'!I<row>:I<row>", "values": [["Hit"|"Missed"]]},
                          {"range": "'PROMO - Promoted Bets'!M<row>:M<row>", "values": [["<leg-by-leg notes>"]]}], "summary": "..."}
The run then writes each update back with update_values. Nothing is invented: a leg whose player has no stat row that week
is left PENDING unless another leg has already missed (then the slip is Missed regardless); First TD legs cannot be graded
from the game log and leave the slip PENDING for the owner to settle by hand. Rows that already carry a Result are skipped.
Usage: python3 grade_promos.py [week]   (default: the latest week present in the promo tab)
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("+", "").replace(",", ""))
    except Exception: return None
def norm(n):
    n = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", str(n).strip().lower())
    return re.sub(r"[^a-z ]", "", n).replace("  ", " ").strip()

promos = vals("promos.json"); PH = {c.strip().split(" (")[0]: i for i, c in enumerate(promos[0])}   # "Legs (one per line ...)" -> "Legs"
glog = vals("gamelog.json"); GH = {c.strip(): i for i, c in enumerate(glog[0])}
def gcol(r, c): return r[GH[c]] if c in GH and GH[c] < len(r) else ""

week = int(sys.argv[1]) if len(sys.argv) > 1 else max((int(num(r[PH["Week"]]) or 0) for r in promos[1:] if len(r) > PH["Week"] and num(r[PH["Week"]])), default=0)
rows_w = [r for r in glog[1:] if str(gcol(r, "Week")).strip() == str(week)]
if not rows_w:
    print(f"no game-log rows for week {week} yet - promos stay pending"); sys.exit(0)
by_pl = {}
for r in rows_w: by_pl.setdefault(norm(gcol(r, "Player")), []).append(r)
teams_w = {str(gcol(r, "Team")).strip().upper() for r in rows_w}
# finals for game-line legs (owner 11/3: "CHI +7.5 | Spread" and "Rush + Rec Yards" came back "not gradable")
import csv
FIN = {}
try:
    for g in csv.DictReader(open(os.path.join(IN, "games.csv"))):
        if g.get("season") == "2026" and str(g.get("week")) == str(week) and g.get("home_score") not in ("", None, "NA"):
            fix = lambda t: {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}.get(t, t)
            FIN[fix(g["home_team"])] = (float(g["home_score"]), float(g["away_score"]), fix(g["away_team"]))
            FIN[fix(g["away_team"])] = (float(g["away_score"]), float(g["home_score"]), fix(g["home_team"]))
except Exception: pass
NICK = {"cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF", "panthers": "CAR", "bears": "CHI", "bengals": "CIN", "browns": "CLE", "cowboys": "DAL", "broncos": "DEN",
        "lions": "DET", "packers": "GB", "texans": "HOU", "colts": "IND", "jaguars": "JAX", "chiefs": "KC", "raiders": "LV", "chargers": "LAC", "rams": "LA", "dolphins": "MIA",
        "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG", "jets": "NYJ", "eagles": "PHI", "steelers": "PIT", "49ers": "SF", "seahawks": "SEA", "buccaneers": "TB",
        "bucs": "TB", "titans": "TEN", "commanders": "WAS"}
def team_of(tok):
    t = tok.strip().upper().replace("LAR", "LA").replace("WSH", "WAS").replace("JAC", "JAX")
    return t if t in FIN else NICK.get(tok.strip().lower())
def grade_line(who, market):
    ml = market.strip().lower(); w = who.strip()
    if ml.startswith("spread"):
        m = re.match(r"([A-Za-z0-9 .]+?)\s*([+-]\d+(?:\.\d+)?)$", w)
        if not m: return "PENDING", f"{who}: spread leg not parsed"
        t = team_of(m.group(1)); pts = float(m.group(2))
        if not t or t not in FIN: return "PENDING", f"{who}: no final score yet"
        own, opp, o = FIN[t]; margin = own - opp + pts
        return ("HIT" if margin > 0 else "MISS"), f"{t} {own:g}-{opp:g} vs {o} ({'✓' if margin > 0 else '✗'} {t} {pts:+g})"
    if ml.startswith("total"):
        m = re.match(r"(over|under)\s+(\d+(?:\.\d+)?)\s*\(?\s*([A-Z]{2,3})\s*[-@vs.]+\s*([A-Z]{2,3})", w, re.I)
        if not m: return "PENDING", f"{who}: total leg not parsed"
        t = team_of(m.group(3)) or team_of(m.group(4))
        if not t or t not in FIN: return "PENDING", f"{who}: no final score yet"
        own, opp, o = FIN[t]; tot = own + opp; need = float(m.group(2)); over = m.group(1).lower() == "over"
        ok = tot > need if over else tot < need
        return ("HIT" if ok else "MISS"), f"{t}-{o} total {tot:g} ({'✓' if ok else '✗'} {m.group(1).lower()} {need:g})"
    if ml.startswith("money") or ml == "ml" or re.search(r"\bml$", w.lower()):
        t = team_of(re.sub(r"\s*ml$", "", w, flags=re.I))
        if not t or t not in FIN: return "PENDING", f"{who}: no final score yet"
        own, opp, o = FIN[t]
        return ("HIT" if own > opp else "MISS"), f"{t} {own:g}-{opp:g} vs {o} ({'✓' if own > opp else '✗'} {t} wins)"
    return None

def stat(r, c): return num(gcol(r, c)) or 0.0
def player_rows(name):
    """exact normalized match first; else same last name + same first initial + same word count (Gadsden II vs Gadsden, D.J. vs DJ)"""
    key = norm(name); kw = key.split()
    if key in by_pl: return by_pl[key]
    if not kw: return None
    for k, v in by_pl.items():   # suffix/initial spellings only (D.J. vs DJ, Gadsden II): same last name AND first name sharing its first 3 letters
        w = k.split()
        if w and len(w) == len(kw) and w[-1] == kw[-1] and w[0][:3] == kw[0][:3]: return v
    return None

def grade_leg(who, market):
    """returns (status, detail) with status in HIT / MISS / PENDING"""
    mk = market.strip(); ml = mk.lower()
    if ml.startswith("first td"): return "PENDING", f"{who}: first TD needs a hand grade"
    gl = grade_line(who, market)
    if gl: return gl
    names = re.split(r"\s+or\s+|\s*/\s*", who.strip()) if ml.startswith("either") else [who.strip()]
    if ml in ("anytime td", "either td", "anytime touchdown", "either/or td"):
        found = []
        for n in names:
            rs = player_rows(n)
            if rs is None: found.append((n, None)); continue
            found.append((n, sum(stat(r, "Rush TD") + stat(r, "Rec TD") for r in rs)))
        if any(v for _, v in found if v): return "HIT", ", ".join(f"{n} {int(v) if v is not None else '—'} TD" for n, v in found)
        if any(v is None for _, v in found): return "PENDING", ", ".join(f"{n}: no stat row" for n, v in found if v is None)
        return "MISS", ", ".join(f"{n} 0 TD" for n, _ in found)
    m = re.match(r"(receiving yards|rushing yards|passing yards|receptions|longest reception|rush \+ rec yards|rush\+rec yards|rushing \+ receiving yards)\s+(\d+(?:\.\d+)?)\+?", ml)
    if not m: return "PENDING", f"{who}: market '{mk}' not gradable here"
    col = {"receiving yards": "Rec Yds", "rushing yards": "Rush Yds", "passing yards": "Pass Yds", "receptions": "Receptions", "longest reception": "Longest Rec"}.get(m.group(1), "Rush + Rec")
    need = float(m.group(2)); rs = player_rows(names[0])
    if rs is None: return "PENDING", f"{who}: no stat row"
    if col == "Rush + Rec": got = sum(stat(r, "Rush Yds") + stat(r, "Rec Yds") for r in rs)
    else: got = max(stat(r, col) for r in rs) if col == "Longest Rec" else sum(stat(r, col) for r in rs)
    return ("HIT" if got >= need else "MISS"), f"{who} {got:g} ({'✓' if got >= need else '✗'} {need:g}+ {col.lower()})"

updates, lines = [], []
for i, r in enumerate(promos[1:], start=2):
    r = list(r) + [""] * (14 - len(r))
    if str(num(r[PH["Week"]]) or "") != str(float(week)) and str(r[PH["Week"]]).strip() != str(week): continue
    if str(r[PH["Result"]]).strip(): continue
    legs = [l for l in str(r[PH["Legs"]]).split("\n") if l.strip()]
    graded = []
    for l in legs:
        parts = [p.strip() for p in l.split("|")]
        if len(parts) < 2: graded.append(("PENDING", f"unparsed leg: {l}")); continue
        graded.append(grade_leg(parts[0], parts[1]))
    st = {s for s, _ in graded}
    result = "Missed" if "MISS" in st else ("Hit" if st == {"HIT"} else "")   # "Hit" (not "Cashed"): the only win word every reader (build_results, build_season, shortlinks) accepts - 11/3 audit
    hits = sum(1 for s, _ in graded if s == "HIT"); note = f"Auto-graded {hits}/{len(graded)} legs hit: " + "; ".join(d for _, d in graded)
    if result:
        updates.append({"range": f"'PROMO - Promoted Bets'!I{i}:I{i}", "values": [[result]]})
        updates.append({"range": f"'PROMO - Promoted Bets'!G{i}:G{i}", "values": [["HIDDEN"]]})   # graded = finished: off the home page (runbook 10/23 rule)
    updates.append({"range": f"'PROMO - Promoted Bets'!M{i}:M{i}", "values": [[note[:1500]]]})
    lines.append(f"slot {r[PH['Slot']]} {r[PH['Title']]}: {result or 'PENDING'} ({hits}/{len(graded)})")
summary = f"week {week}: " + ("; ".join(lines) if lines else "no ungraded promos")
json.dump({"week": week, "updates": updates, "summary": summary}, open(os.path.join(OUT, "promo_grades.json"), "w"), indent=1)
print(summary); print(f"wrote out/promo_grades.json: {len(updates)} cell updates")
