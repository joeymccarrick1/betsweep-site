#!/usr/bin/env python3
"""build_targets.py - the Tuesday trade desk: buy-low and sell-high fantasy targets (11/5 out-of-the-box batch).

A buy-low is a player whose last three box scores sit well under his season average while his role is intact (snap share steady or
rising, no injury), ideally with the softest schedule left; the manager who owns him is looking at a cold streak, the model is looking
at the same snaps and targets. A sell-high is the mirror: three hot weeks above the season number on a role that is flat or shrinking,
or into the hardest schedule left. Where FantasyCalc market values are in the sheet ('AUTO - Market Values'), the gap between the
market's rank and the model's rank at his position is the strongest signal of all and is weighed first.

Reads: out/trade_values.json (build_trade.py: season averages, last-3, snaps, market values, remaining games), in/ctx_role.json (role
notes), in/ranks.json (defensive stat ranks; rank 1 = the defense that allows the most), in/games.csv (remaining opponents).
Writes: out/targets.json {week, built, buy:[...], sell:[...], post} - build_today.py renders it as the Trade desk section and the
post text is the week's social line (also out/social_targets.txt).
"""
import json, os, csv, statistics, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
TV = json.load(open(os.path.join(OUT, "trade_values.json"))); W = int(TV["week"])
def ppr(a): return 0.04 * a["py"] + 4 * a["ptd"] - 2 * a["int"] + 0.1 * a["ry"] + 6 * a["rtd"] + a["rec"] + 0.1 * a["recy"] + 6 * a["rectd"]
# ---- remaining schedule ease per team and position: mean defensive rank of the opponents left (rank 1 = allows the most = easiest) ----
RK = {}
for r in json.load(open(os.path.join(IN, "ranks.json")))["values"]:
    if not r or r[0] in ("Defense", "") or str(r[0]).startswith("LAST 3"): continue
    if RK.get(r[0]): continue   # season block first; the LAST 3 block repeats the teams
    try: RK[r[0]] = {"QB": float(r[1]), "RB": float(r[3]), "WR": float(r[5]), "TE": float(r[6])}
    except (ValueError, IndexError): pass
LEFT = {}
with open(os.path.join(IN, "games.csv"), newline="") as f:
    for g in csv.DictReader(f):
        if g.get("game_type") != "REG" or not g.get("week", "").isdigit() or int(g["week"]) < W or int(g["week"]) > 17: continue
        LEFT.setdefault(g["home_team"], []).append(g["away_team"]); LEFT.setdefault(g["away_team"], []).append(g["home_team"])
def ease(tm, pos):
    opps = [RK[o][pos] for o in LEFT.get(tm, []) if o in RK]
    return round(16.5 - statistics.mean(opps), 1) if opps else 0.0   # + = easier than average, - = harder
# ---- role notes ----
ROLE = {}
try:
    for p in json.load(open(os.path.join(IN, "ctx_role.json"))).get("players", []): ROLE[p["player"]] = p
except Exception: pass
# ---- score ----
rows = []
for p in TV["players"]:
    if p["pos"] not in ("QB", "RB", "WR", "TE") or p["g"] < 3 or p.get("Re", 0) < 3: continue
    if str(p.get("st", "")).upper() in ("OUT", "IR", "PUP", "NFI", "SUSP") or p.get("l3") is None: continue
    S = ppr(p["a"]); L3 = p["l3"]
    if S < 8: continue
    rows.append({"n": p["n"], "pos": p["pos"], "tm": p["tm"], "S": round(S, 1), "l3": L3, "d": round(L3 - S, 1), "snap": p.get("snap"), "l2": p.get("l2"), "sig": p.get("sig") or "",
                 "ease": ease(p["tm"], p["pos"]), "mkt": (p.get("mkt") or {}).get("r1"), "role": ROLE.get(p["n"]), "st": p.get("st", ""), "why_st": p.get("why", "")})
# ranks within position: model (season blended with the last three) and market (FantasyCalc redraft, when the sheet has it)
for pos in ("QB", "RB", "WR", "TE"):
    grp = [r for r in rows if r["pos"] == pos]
    grp.sort(key=lambda r: -(0.65 * r["S"] + 0.35 * r["l3"]))
    for i, r in enumerate(grp): r["mrank"] = i + 1
    mk = sorted([r for r in grp if r["mkt"]], key=lambda r: -r["mkt"])
    for i, r in enumerate(mk): r["krank"] = i + 1
def gap(r): return (r["krank"] - r["mrank"]) if r.get("krank") else 0   # + = market ranks him lower than the model (cheap)
def snap_txt(r): return f"{r['snap']*100:.0f}% of snaps" + (f" (last two {r['l2']*100:.0f}%)" if r.get("l2") and abs(r["l2"] - r["snap"]) >= 0.05 else "") if r.get("snap") else "no snap data"
def sched_txt(r):
    e = r["ease"]
    return "the softest schedule left at his position" if e >= 4 else ("a soft schedule left" if e >= 2 else ("the hardest schedule left" if e <= -4 else ("a tough schedule left" if e <= -2 else "an average schedule left")))
CAP = {"QB": 24, "RB": 40, "WR": 48, "TE": 18}
buy, sell = [], []
for r in rows:
    if r["mrank"] > CAP[r["pos"]]: continue
    cold, hot = max(0.0, -r["d"]), max(0.0, r["d"])
    g = gap(r)
    role_up = r["sig"] == "SNAPS UP" or (r["role"] and r["role"].get("k") == "good")
    role_dn = r["sig"] == "SNAPS DOWN" or (r["role"] and "falling" in r["role"].get("tag", "").lower()) or (r["role"] and "demoted" in r["role"].get("tag", "").lower())
    # buy low: cold stretch on an intact role, or the market simply has him too low
    if not role_dn and (cold >= 2.5 or g >= 6 or (role_up and cold >= 1)):
        sc = min(cold, 10) / 3 + (1.2 if role_up else 0) + r["ease"] / 6 + g / 5
        why = []
        if cold >= 2.5: why.append(f"averaging {r['S']} a game this season, {r['l3']} over the last three")
        if role_up: why.append("the role is growing: " + snap_txt(r) + ((" - " + r["role"]["txt"].split(". ")[0].rstrip(".").lower()) if r["role"] and r["role"].get("k") == "good" else ""))
        elif r.get("snap"): why.append("on " + snap_txt(r) + " - the role is intact")
        if g >= 6: why.append(f"the market has him {r['pos']}{r['krank']}, the model {r['pos']}{r['mrank']}")
        if abs(r["ease"]) >= 2: why.append(sched_txt(r))
        buy.append({**{k: r[k] for k in ("n", "pos", "tm", "S", "l3", "snap", "sig", "ease", "mrank")}, "krank": r.get("krank"), "score": round(sc, 2), "why": "; ".join(why).capitalize() + "."})
    # sell high: hot stretch on a flat or shrinking role, into a hard schedule, or the market has him too high
    if not role_up and (hot >= 3.5 or g <= -6 or (role_dn and hot >= 1.5)):
        sc = min(hot, 12) / 3 + (1.2 if role_dn else 0) - r["ease"] / 6 - g / 5
        why = []
        if hot >= 3.5: why.append(f"{r['l3']} a game over the last three against a season average of {r['S']}")
        if role_dn: why.append("the role is shrinking: " + snap_txt(r) + ((" - " + r["role"]["txt"].split(". ")[0].rstrip(".").lower()) if r["role"] and r["role"].get("txt") else ""))
        elif r.get("snap"): why.append("on " + snap_txt(r) + " - nothing in the role explains the jump")
        if g <= -6: why.append(f"the market has him {r['pos']}{r['krank']}, the model {r['pos']}{r['mrank']}")
        if abs(r["ease"]) >= 2: why.append(sched_txt(r))
        sell.append({**{k: r[k] for k in ("n", "pos", "tm", "S", "l3", "snap", "sig", "ease", "mrank")}, "krank": r.get("krank"), "score": round(sc, 2), "why": "; ".join(why).capitalize() + "."})
def spread(lst, n=8, per_pos=3):
    lst.sort(key=lambda r: -r["score"]); out = []; cnt = {}
    for r in lst:
        if cnt.get(r["pos"], 0) >= per_pos: continue
        out.append(r); cnt[r["pos"]] = cnt.get(r["pos"], 0) + 1
        if len(out) >= n: break
    return out
buy, sell = spread(buy), spread(sell)
post = ""
if buy or sell:
    post = f"Week {W} trade desk. " + (("Buy low: " + ", ".join(f"{r['n']} ({r['pos']}, {r['tm']})" for r in buy[:3]) + ". ") if buy else "") + (("Sell high: " + ", ".join(f"{r['n']} ({r['pos']}, {r['tm']})" for r in sell[:3]) + ". ") if sell else "") + "Snaps, targets and the schedule left, not the box score. betsweep.co/today/"
json.dump({"week": W, "built": dt.datetime.now(dt.timezone.utc).isoformat(), "buy": buy, "sell": sell, "post": post, "market": bool(any(r.get("krank") for r in rows))}, open(os.path.join(OUT, "targets.json"), "w"), indent=0)
open(os.path.join(OUT, "social_targets.txt"), "w").write(post + "\n")
print(f"wrote out/targets.json: {len(buy)} buy-low, {len(sell)} sell-high for week {W} (market values {'on' if any(r.get('krank') for r in rows) else 'off'}); {len(rows)} players screened")
for r in buy[:4]: print("  BUY ", r["n"], r["pos"], r["tm"], r["score"], "-", r["why"][:120])
for r in sell[:4]: print("  SELL", r["n"], r["pos"], r["tm"], r["score"], "-", r["why"][:120])
