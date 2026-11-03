#!/usr/bin/env python3
"""promo_approve.py <promo-drafts clone> [week]   (owner 11/3: "stop retyping promos")

The Wednesday / check runs save drafts to the `promo-drafts` branch as week<W>.json: {"week": W, "promos": [{slot, name, type, game,
legs: [{pl, m, ln, o, p, fd:{m,s}}], link, price_est, caption, post}]}. The owner approves a draft by setting "post": true (GitHub
mobile edit, or by telling a Claude session "approve week 9 <name>"), optionally with "odds": <the FanDuel SGP price he got> and
"link": <his shareCode link>. This script turns every approved draft that is NOT yet on 'PROMO - Promoted Bets' (same week, same
title) into sheet rows and writes out/promo_rows.json = {"range": "'PROMO - Promoted Bets'!A1", "values": [[...], ...]} for the
rebuild to append with append_values, then build_promo.py picks them up as LIVE like any owner-typed row. Nothing is written here.
Reads in/promos.json ('PROMO - Promoted Bets'!A1:N100). Legs are written in the tab's own format: "who | Market N+ | odds".
"""
import json, os, sys, glob, re
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
clone = sys.argv[1]
files = sorted(glob.glob(os.path.join(clone, "week*.json")), key=lambda f: int(re.findall(r"week(\d+)", f)[0]))
if not files: print("no drafts"); sys.exit(0)
if len(sys.argv) > 2: files = [f for f in files if f.endswith(f"week{sys.argv[2]}.json")]
promos = json.load(open(os.path.join(IN, "promos.json")))["values"]; PH = {c.strip().split(" (")[0]: i for i, c in enumerate(promos[0])}
have = {(str(r[PH["Week"]]).strip(), str(r[PH["Title"]]).strip().lower()) for r in promos[1:] if len(r) > PH["Title"]}
def slots(w): return [int(r[PH["Slot"]]) for r in promos[1:] if len(r) > PH["Slot"] and str(r[PH["Week"]]).strip() == str(w) and str(r[PH["Slot"]]).strip().isdigit()]
def leg_txt(l, game=""):
    pl, m, ln, o = l.get("pl", ""), l.get("m", ""), l.get("ln"), l.get("o")
    if m == "Total" and "(" not in pl and game: pl = f"{pl} ({game})"   # grader needs the matchup on totals
    if m in ("Anytime TD", "First TD", "Either TD", "2+ TD", "3+ TD"): mk = m
    elif m in ("Spread", "Moneyline", "Total"): mk = m
    elif ln is not None: mk = f"{m} {int(ln) if float(ln) == int(float(ln)) else ln}+"
    else: mk = m
    od = "" if o in (None, "") else (f"+{int(o)}" if float(o) > 0 else f"{int(o)}")
    return f"{pl} | {mk} | {od}"
rows = []
for f in files:
    d = json.load(open(f)); w = d.get("week")
    nxt = (max(slots(w)) if slots(w) else 0) + 1
    for p in d.get("promos") or []:
        if not p.get("post"): continue
        title = str(p.get("name", "")).strip()
        if not title or (str(w), title.lower()) in have: continue
        legs = "\n".join(leg_txt(l, p.get("game", "")) for l in p.get("legs") or [])
        odds = p.get("odds") or re.sub(r"[^0-9+-]", "", str(p.get("price_est", "")).split(" ")[0]) or ""
        rows.append([str(w), str(nxt), title, legs, str(odds).lstrip("+"), p.get("link", ""), "LIVE", p.get("caption", ""), "", "", "", "",
                     f"Approved draft ({p.get('slot', '')}, {p.get('type', '')}); drafted {d.get('drafted', '')}. Price = {'owner' if p.get('odds') else 'drafted estimate'}.", ""])
        have.add((str(w), title.lower())); nxt += 1
json.dump({"range": "'PROMO - Promoted Bets'!A1", "values": rows}, open(os.path.join(OUT, "promo_rows.json"), "w"), indent=1)
print(f"wrote out/promo_rows.json: {len(rows)} approved drafts to append" + ("" if not rows else " - " + ", ".join(f"wk{r[0]} slot {r[1]} {r[2]}" for r in rows)))
