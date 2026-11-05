#!/usr/bin/env python3
"""faceoff.py - the receiver face-off on each game card: one team's pass catchers side by side, so the reader can tell which
receiver is in line for the big game before picking a ceiling leg.

Owner, 2026-10-22 (TNF Week 7): the model had Luther Burden III and Rome Odunze even (55 vs 53 projected yards, 34% vs 33% to
score) and Odunze's TD rode the slips; Burden went 4-130-1. What separated them before kickoff was already in data we pull but
did not show together: targets per game (7.2 vs 5.5), catch rate (72% vs 61%), yards after the catch per catch (5.1 vs 2.7) and
Mike Clay's corner read (+6% targets / +0.21 points per route vs -2% / -0.10).

Per receiver (WR / TE on the team this week, from the model's leg board):
  usage  - targets per game this season, target share over his last 3 games, catch rate, YAC per catch, aDOT (air yards per target)
           from nflverse stats_player_week_<season>.csv, weeks before this one only (no target-week leakage)
  corner - flags.py WRCB (Clay's T/R and F/R deltas vs his season rates; ▲ / ▼ use the same bar as the Coverage flag)
  ceiling- chance of 80+ and 100+ receiving yards from the model's projection through CURVE (below; fit 2022-24, checked on 2025).
           Blended toward FanDuel's price exactly like every other shown % (calib.shrink) when FanDuel prices that rung; otherwise
           the curve number, marked "est". Anytime TD = the shown leg % and FanDuel's odds.
  big games - games this season with 80+ and 100+ receiving yards (count / games).
Display only: nothing here changes a projection, a leg % or a parlay.

    FO = faceoff.load(IN, WEEK, season)            # downloads (or reuses) in/stats_player_week_<season>.csv
    html = faceoff.block(FO, LEGS, WRCB, a, b)     # LEGS = build_boards.py leg rows; WRCB = flags Engine.WRCB
"""
import csv, os, re, urllib.request
from html import escape as E
import hrswap as HRS
import calib as CALIB

def nn(x): return HRS.normname(x)

def load(IN, WEEK, season=2026):
    dst = os.path.join(IN, f"stats_player_week_{season}.csv")
    try: urllib.request.urlretrieve(f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv", dst)
    except Exception as e: print("note: nflverse weekly stats download failed" + (", using cached file" if os.path.exists(dst) else " - no receiver face-off"), e)
    if not os.path.exists(dst): return {}
    g = {}
    with open(dst, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("season_type", "REG") != "REG": continue
            try: wk = int(r["week"])
            except Exception: continue
            if wk >= int(WEEK): continue
            def x(c):
                try: return float(r.get(c) or 0)
                except Exception: return 0.0
            ts = r.get("target_share")
            g.setdefault(nn(r["player_display_name"]), []).append({"w": wk, "team": r.get("team", ""), "pos": r.get("position", ""), "tgt": x("targets"), "rec": x("receptions"),
                "yds": x("receiving_yards"), "td": x("receiving_tds"), "air": x("receiving_air_yards"), "yac": x("receiving_yards_after_catch"),
                "ts": float(ts) if ts not in (None, "", "NA") else None})
    out = {}
    for k, gs in g.items():
        gs.sort(key=lambda z: z["w"]); n = len(gs)
        tg = sum(z["tgt"] for z in gs); rc = sum(z["rec"] for z in gs)
        l3 = [z["ts"] for z in gs[-3:] if z["ts"] is not None]
        out[k] = {"g": n, "tpg": tg / n if n else None, "ts3": (sum(l3) / len(l3)) if l3 else None, "cr": (rc / tg) if tg else None,
                  "yac": (sum(z["yac"] for z in gs) / rc) if rc else None, "adot": (sum(z["air"] for z in gs) / tg) if tg else None,
                  "b80": sum(1 for z in gs if z["yds"] >= 80), "b100": sum(1 for z in gs if z["yds"] >= 100), "pos": gs[-1]["pos"], "team": gs[-1]["team"]}
    return out

# Ceiling curve: P(receiving yards >= T) from the projection, logistic in log(projection). Fit on 2022-24 WR/TE games (predictor = the
# player's average in his earlier games that season, 3+ games, avg >= 5) and checked out of sample on 2025 (by projection band
# 5-20 / 20-35 / 35-50 / 50-65 / 65-80 / 80+: 80+ yds predicted 1/6/13/22/31/46% vs actual 2/4/13/23/28/46%; 100+ predicted
# 0.4/2/6/11/18/30% vs actual 0.5/1/6/11/13/31%). The ladder's normal fit was not used here: it gave tails far too thin
# (e.g. 1% for an 80-yard game from a TE who had one in five games).
CURVE = {80: (-9.7980, 2.1115), 100: (-11.7451, 2.3934)}
def p_ceiling(proj, T):
    import math
    if not proj or proj <= 0: return None
    a, b = CURVE[T]; return 1 / (1 + math.exp(-(a + b * math.log(proj))))

def _ceiling(LEGS, name, proj):
    out = {}
    for t in (80, 100):
        raw = p_ceiling(proj, t)
        if raw is None: continue
        fd = next((l for l in LEGS if l["player"] == name and l["market"] == "Receiving Yards" and l.get("line") == t and l.get("book") is not None), None)
        out[t] = (CALIB.shrink(raw, fd["book"]), fd["odds"], True) if fd else (raw, None, False)
    return out

def _odds(o):
    if o is None: return ""
    return f"+{int(o)}" if o > 0 else f"{int(o)}"

def rows_for(FO, LEGS, WRCB, team):
    names = {}
    for l in LEGS:
        if l.get("team") != team or l.get("status") in ("OUT", "BYE") or "/" in str(l["player"]): continue
        if l["market"] in ("Receiving Yards", "Receptions", "Anytime TD"): names.setdefault(l["player"], l)
    rows = []
    for name, l0 in names.items():
        st = FO.get(nn(name)) or {}
        pos = st.get("pos") or ""
        c = WRCB.get(nn(name)) or WRCB.get(re.sub(r"[^a-z ]", "", nn(name))) or {}
        if pos not in ("WR", "TE") and not c: continue
        if (st.get("tpg") or 0) < 2 and not c: continue
        proj = next((l["proj"] for l in LEGS if l["player"] == name and l["market"] == "Receiving Yards" and l.get("proj")), None)
        td = next((l for l in LEGS if l["player"] == name and l["market"] == "Anytime TD" and l.get("p") is not None), None)
        dtr, dfr = c.get("d_tr"), c.get("d_fr")
        if dtr is not None and abs(dtr) > 1: dtr = dtr / 100.0
        rows.append({"name": name, "pos": pos or "WR", "st": st, "proj": proj, "ceil": _ceiling(LEGS, name, proj), "td": td,
                     "cb": c.get("cb"), "dtr": dtr, "dfr": dfr})
    rows.sort(key=lambda r: -((r["st"].get("tpg") or 0) + (r["proj"] or 0) / 100))
    return rows[:6]

def _cell_best(rows, key, hi=True):
    vals = [key(r) for r in rows if key(r) is not None]
    if len(vals) < 2: return None
    return max(vals) if hi else min(vals)

def table(FO, LEGS, WRCB, team):
    """Players across, metrics down (fits a phone: up to 5 receivers side by side)."""
    rows = rows_for(FO, LEGS, WRCB, team)[:5]
    if not rows: return ""
    K = {"tpg": lambda r: r["st"].get("tpg"), "ts3": lambda r: r["st"].get("ts3"), "cr": lambda r: r["st"].get("cr"), "yac": lambda r: r["st"].get("yac"),
         "adot": lambda r: r["st"].get("adot"), "cov": lambda r: (r["dtr"] + r["dfr"]) if r["dtr"] is not None and r["dfr"] is not None else None,
         "big": lambda r: (r["st"].get("b80", 0) / r["st"]["g"]) if r["st"].get("g") else None,
         "c80": lambda r: (r["ceil"].get(80) or (None,))[0], "c100": lambda r: (r["ceil"].get(100) or (None,))[0], "td": lambda r: r["td"]["p"] if r["td"] else None}
    best = {k: _cell_best(rows, f) for k, f in K.items()}
    def cell(k, r, txt, tip=""):
        v = K[k](r); b = best.get(k)
        cls = "bst" if (b is not None and v is not None and abs(v - b) < 1e-9) else ""
        return f'<td class="{cls}"' + (f' title="{E(tip)}"' if tip else "") + f'>{txt}</td>'
    def cov(r):
        if not r["cb"]: return "—", ""
        if r["dtr"] is None or r["dfr"] is None: return f'· <small>{E(r["cb"].split(" ")[-1])}</small>', f"vs {r['cb']}"
        t = r["dtr"] + r["dfr"]
        ar = "▲" if (r["dtr"] >= 0.08 and r["dfr"] >= 0.15) else ("▼" if (r["dtr"] <= -0.08 and r["dfr"] <= -0.15) else ("△" if t > 0.1 else ("▽" if t < -0.1 else "·")))
        return f'{ar}<small>{E(r["cb"].split(" ")[-1])}</small>', f"vs {r['cb']} · Clay: targets {r['dtr']*100:+.0f}%, points per route {r['dfr']:+.2f} vs his season rates"
    def ce(r, t):
        x = r["ceil"].get(t)
        if not x: return "—"
        p, o, priced = x
        return f'{p*100:.0f}%' + (f'<small>{_odds(o)}</small>' if priced else '<small class="est">est</small>')
    M = [("Targets / game", "tpg", lambda r: f'{r["st"]["tpg"]:.1f}' if r["st"].get("tpg") is not None else "—", "this season"),
         ("Share, last 3", "ts3", lambda r: f'{r["st"]["ts3"]*100:.0f}%' if r["st"].get("ts3") is not None else "—", "share of the team's targets over his last 3 games"),
         ("Catch rate", "cr", lambda r: f'{r["st"]["cr"]*100:.0f}%' if r["st"].get("cr") is not None else "—", "catches per target"),
         ("YAC / catch", "yac", lambda r: f'{r["st"]["yac"]:.1f}' if r["st"].get("yac") is not None else "—", "yards after the catch per catch"),
         ("aDOT", "adot", lambda r: f'{r["st"]["adot"]:.1f}' if r["st"].get("adot") is not None else "—", "average depth of target (air yards per target)"),
         ("Corner", "cov", None, "Mike Clay's corner read: ▲/▼ clear edge (the Coverage flag bar), △/▽ leaning"),
         ("80+ yd games", "big", lambda r: f'{r["st"].get("b80", 0)}/{r["st"]["g"]}' if r["st"].get("g") else "—", "games this season with 80+ receiving yards"),
         ("80+ yds", "c80", lambda r: ce(r, 80), "chance of 80+ receiving yards (FanDuel odds when FanDuel prices that line; est = model only)"),
         ("100+ yds", "c100", lambda r: ce(r, 100), "chance of 100+ receiving yards"),
         ("TD", "td", lambda r: (f'{r["td"]["p"]*100:.0f}%<small>{_odds(r["td"].get("odds"))}</small>' if r["td"] else "—"), "chance to score (shown % and FanDuel odds)")]
    def short(n):
        w = n.split(" "); return w[-2] if len(w) > 1 and w[-1] in ("Jr.", "Jr", "III", "II", "IV", "Sr.") else w[-1]
    head = "".join(f'<th title="{E(r["name"])}"{" class=lg" if len(short(r["name"])) >= 10 else ""}>{E(short(r["name"]))}<small>{E(r["pos"])}</small></th>' for r in rows)
    body = ""
    for lab, k, fmt, tip in M:
        tds = ""
        for r in rows:
            if k == "cov": txt, ctip = cov(r); tds += cell(k, r, txt, ctip)
            else: tds += cell(k, r, fmt(r))
        body += f'<tr><th title="{E(tip)}">{E(lab)}</th>{tds}</tr>'
    return f'<div class="fotbl"><table><thead><tr><th class="fot">{E(team)}</th>{head}</tr></thead><tbody>{body}</tbody></table></div>'

def block(FO, LEGS, WRCB, a, b):
    ta, tb = table(FO, LEGS, WRCB, a), table(FO, LEGS, WRCB, b)
    if not (ta or tb): return ""
    return (f'<details class="faceoff"><summary><span class="lt">Receiver face-off <small>who is in line for the big game · tap to open</small></span></summary>{ta}{tb}'
            f'<p class="fonote">Usage from this season\'s games (nflverse), corner read from Mike Clay\'s WR-CB chart, ceiling % from the model\'s projection (a curve fit on 2022-24 and checked on 2025). Bold = best in the room. '
            f'"est" = no FanDuel line at that number, model estimate only. Display only - it does not change any projection or parlay.</p></details>')
