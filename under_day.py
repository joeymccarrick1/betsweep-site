#!/usr/bin/env python3
"""under_day.py - Under of the day (owner 11/10 deep dive: "Under of the day from the model's 55%+ unders").

Why: on the same main lines in Week 9, unders hit 53.1% and lost 0.9 units per 100 staked while overs hit 46.9% and lost 10.6; where
the model had the under at 55% or better it hit 55.9% and made 2.7 per 100 (research/two_way.py). Overs are the side the public
bets and the side that has been losing on our own log, so the site names one under per game day and keeps score.

The pick, per game day (Central time): the under on the builder board (FanDuel main line, both sides priced) with the widest gap
between the chance the site shows and the price's break-even, among unders shown at 55% or better and at or above break-even, with
FanDuel ids, for a player who is not tagged questionable (a scratch voids the bet). No risk screen: the risk flags describe overs
(a tough matchup hurts an over and helps an under). No pick clears the bar -> no card that day.

The log lives on the site (data/under-day.json, kept across builds). A day's entry follows the board until that day's first kickoff
among the pick's game, then it is frozen; frozen entries are graded from the game log (in/gamelog.json) when their week is in it.
A player with no row that week did not play: VOID, not a loss.

  build(in_dir, out_dir, clone) -> out/under_day.json {"week", "picks": [{date, day, ...}], "record": {...}} + out/data/under-day.json
  card(pick, record, variant)   -> the HTML card ("home" for the Today page, "short" for the Short view)
"""
import datetime, html, json, os
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago"); E = html.escape
STAT = {"Under Receptions": ("Receptions", "receptions"), "Under Receiving Yards": ("Rec Yds", "receiving yards"),
        "Under Rushing Yards": ("Rush Yds", "rushing yards"), "Under Passing Yards": ("Pass Yds", "passing yards")}
MIN_P = 0.55


def dec(o): o = float(o); return 1 + o / 100 if o > 0 else 1 + 100 / -o
def am(o): o = int(round(float(o))); return f"+{o}" if o > 0 else f"−{-o}"
def day_of(ko_ms): return datetime.datetime.fromtimestamp(ko_ms / 1000, CT).strftime("%Y-%m-%d")


def soft_draws(in_dir, week):
    """receivers the week's WR-CB chart gives a soft corner (Clay +8% targets a route and +0.15 points a route or better - the boards'
    green arrow), or that the sheet's CB Matchup Flag calls FAVORABLE. Owner 11/11 4:57 PM, on Chase under 7.5 receptions against his soft draw: "I'd skip it if coverage disagrees"."""
    out = set()
    try:
        d = json.load(open(os.path.join(in_dir, "wrcb.json"))); v = d["values"] if isinstance(d, dict) else d; H = {c: i for i, c in enumerate(v[0])}
        def num(x):
            x = str(x).strip()
            try: return float(x.rstrip("%")) / 100 if x.endswith("%") else float(x)
            except Exception: return None
        for r in v[1:]:
            r = r + [""] * (len(v[0]) - len(r))
            if str(r[H["Week"]]).strip() != str(week): continue
            a, b = num(r[H["Clay Matchup T/R delta"]]), num(r[H["Clay Matchup F/R delta"]])
            if a is not None and abs(a) > 1: a /= 100
            flag = str(r[H["CB Matchup Flag"]]).strip().upper() if "CB Matchup Flag" in H else ""      # the sheet's own read - the one that graded with signal
            if (a is not None and b is not None and a >= 0.08 and b >= 0.15) or flag == "FAVORABLE": out.add(str(r[H["WR"]]).strip().lower())
    except Exception as e: print("note: WR-CB chart not read for Under of the day:", e)
    return out


# owner 11/13, after Austin Ekeler under 1.5 receptions (the 11/12 Under of the day, and nearly a Daily Sweep leg) lost with 4 catches:
# "Need to be more cognizant about legs like that". He carried Fill-in volume, Role Up and Healthy again - every one a reason to like the
# OVER, and the risk score counts them as good flags whatever side the leg is on. An under is skipped when the player's own flags say his
# role is growing or his matchup is soft for that stat: the site's read disagrees with the under, the same idea as the coverage skip.
GROWING = ("Role Up", "Fill-in volume", "Snaps up", "News: role up", "Depth chart: promoted", "Room thinned", "Healthy again", "Hot L3", "Soft matchup")
AGAINST = {"rec": GROWING + ("Targets up", "Trail script", "Soft vs RB targets", "Thin secondary"),
           "rush": GROWING + ("Carries up", "Lead script", "Soft vs QB runs"),
           "pass": GROWING + ("Trail script", "Thin secondary")}

def role_against(l, pf):
    """the flags on this player or leg that argue for the over, [] when none"""
    m = l.get("m") or ""; k = "rec" if "Recept" in m or "Receiving" in m else "rush" if "Rush" in m else "pass" if "Pass" in m else None
    if not k: return []
    fl = list(pf.get(l.get("pl")) or []) + list(l.get("fh") or [])
    return sorted({str(f[1]) for f in fl if isinstance(f, (list, tuple)) and len(f) > 1 and f[0] == "good" and str(f[1]).startswith(AGAINST[k])})


def candidates(bd, soft=()):
    out = []; pf = bd.get("pf") or {}
    for l in bd.get("legs") or []:
        if l.get("m") not in STAT or l.get("o") is None or l.get("p") is None: continue
        if l.get("m") in ("Under Receptions", "Under Receiving Yards") and str(l.get("pl", "")).strip().lower() in soft: continue   # coverage disagrees with the under
        if role_against(l, pf): continue   # his role or matchup argues for the over
        fd = l.get("fd") or {}
        if not (fd.get("m") and fd.get("s")): continue
        if any(isinstance(f, (list, tuple)) and len(f) > 1 and str(f[1]).startswith(("Q ", "Q·", "Questionable", "Doubtful", "OUT")) for f in l.get("fh") or []): continue
        be = 1 / dec(l["o"])
        # a leg the site itself tags "Market disagrees" (model 10+ points off the book: the book has usually been closer) goes behind
        # every under without that tag, however wide its gap looks
        far = any(isinstance(f, (list, tuple)) and len(f) > 1 and str(f[1]).startswith("Market disagrees") for f in l.get("fh") or [])
        if l["p"] >= MIN_P and l["p"] >= be: out.append((far, round(l["p"] - be, 4), l))
    # owner 11/11 (after the Weeks 6-9 grade): a receptions under comes first. That is the market where the model's under number has been
    # right - its 60-70% unders hit 61.5% (n=122), its 70%+ hit 69.8% (n=53). Rushing unders win as a class (57% of 312) but the model's
    # own rushing number does not sort them, so they carry the flat rate (build_builder.py) and come after; receiving yards (model says
    # 64%, got 54%) and passing yards come last.
    rank = {"Under Receptions": 0, "Under Rushing Yards": 1}
    out.sort(key=lambda x: (x[0], rank.get(x[2]["m"], 2), -x[1], -x[2]["p"], x[2]["pl"]))
    return [l for _, _, l in out]


def choose(bd, now_ms, soft=()):
    """{date: entry} - the best under for every game day that still has the pick's game ahead of it."""
    G = {g["gid"]: g for g in bd.get("games") or []}; picks = {}
    for l in candidates(bd, soft):
        g = G.get(l["g"]) or {}; ko = g.get("ko") or 0
        if not ko or ko <= now_ms: continue
        d = day_of(ko)
        if d in picks: continue
        home, away = g.get("home"), g.get("away")
        picks[d] = {"date": d, "week": bd.get("week"), "gid": l["g"], "pl": l["pl"], "tm": l.get("tm"), "opp": l.get("opp"), "pos": l.get("pos"),
                    "m": l["m"], "ln": l["ln"], "o": l["o"], "p": round(l["p"], 4), "fdm": l["fd"]["m"], "fds": l["fd"]["s"], "ko": ko,
                    "kick": g.get("kick", ""), "at": (f"{away} {'vs' if g.get('nt') else '@'} {home}" if home and away else l["g"]), "res": None}
    return picks


def grade(entry, gamelog):
    """HIT / MISS / VOID / None (not in the game log yet)."""
    if not gamelog or len(gamelog) < 2: return None, None
    H = {c: i for i, c in enumerate(gamelog[0])}; col = STAT[entry["m"]][0]
    if col not in H: return None, None
    wk = str(entry.get("week")); rows = [r for r in gamelog[1:] if r and str(r[H["Week"]]) == wk]
    if not rows: return None, None                       # that week is not in the log yet
    mine = [r for r in rows if str(r[H["Player"]]).strip().lower() == entry["pl"].strip().lower()]
    if not mine: return "VOID", None
    try: v = float(mine[0][H[col]] or 0)
    except Exception: return None, None
    return ("HIT" if v < float(entry["ln"]) else "MISS"), v


def build(in_dir="in", out_dir="out", clone=None, now_ms=None):
    now_ms = now_ms or int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    bd = json.load(open(os.path.join(out_dir, "builder_data.json")))
    clone = clone or os.environ.get("BS_SITE") or "/home/claude/betsweep-site"
    log = []
    for p in (os.path.join(clone, "data", "under-day.json"), os.path.join(out_dir, "data", "under-day.json")):
        try:
            log = json.load(open(p)); log = log if isinstance(log, list) else []
            if log: break
        except Exception: pass
    soft = soft_draws(in_dir, bd.get("week")); picks = choose(bd, now_ms, soft); keep = [e for e in log if (e.get("ko") or 0) <= now_ms]      # kicked off = frozen
    frozen_days = {e["date"] for e in keep}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for d, e in sorted(picks.items()):
        if d in frozen_days: continue
        e["at_utc"] = stamp; keep.append(e)
    try: gl = json.load(open(os.path.join(in_dir, "gamelog.json"))); gl = gl.get("values", gl) if isinstance(gl, dict) else gl
    except Exception: gl = None
    for e in keep:
        if e.get("res") in ("HIT", "MISS", "VOID") or (e.get("ko") or 0) > now_ms: continue
        r, v = grade(e, gl)
        if r: e["res"] = r; e["actual"] = v
    keep.sort(key=lambda e: (e["date"], e.get("ko") or 0))
    w = sum(1 for e in keep if e.get("res") == "HIT"); l = sum(1 for e in keep if e.get("res") == "MISS")
    units = sum((dec(e["o"]) - 1) if e["res"] == "HIT" else -1 for e in keep if e.get("res") in ("HIT", "MISS"))
    rec = {"w": w, "l": l, "units": round(units, 2), "void": sum(1 for e in keep if e.get("res") == "VOID")}
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    json.dump(keep, open(os.path.join(out_dir, "data", "under-day.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    live = [e for e in keep if (e.get("ko") or 0) > now_ms]
    json.dump({"week": bd.get("week"), "picks": live, "record": rec}, open(os.path.join(out_dir, "under_day.json"), "w"), ensure_ascii=False)
    return (f"under of the day: {len(live)} game day(s) with a pick" + (" (" + "; ".join(f"{e['date']} {e['pl']} under {e['ln']:g} {STAT[e['m']][1]} {am(e['o'])}, {e['p'] * 100:.0f}%" for e in live) + ")" if live else "")
            + f"; record {w}-{l}" + (f", {units:+.2f}u" if w + l else "") + f"; log {len(keep)} entries")


def record_text(rec):
    if not rec or not (rec.get("w") or rec.get("l")): return "First one on the record this week"
    return f"Record {rec['w']}–{rec['l']} · {rec['units']:+.1f}u"


DAYN = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}

CSS_HOME = """
.udsec{max-width:1360px;margin:14px auto 0;padding:0 16px}
.udcard{border:1px solid var(--line);border-left:4px solid var(--red);border-radius:14px;background:var(--card);padding:13px 14px 12px;display:grid;grid-template-columns:1fr auto;gap:6px 14px;align-items:center}
.udcard[hidden]{display:none}
.udk{font-family:var(--display);font-weight:800;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--redtxt,var(--red))}
.udk small{margin-left:8px;color:var(--mute);font-weight:700;letter-spacing:.08em}
.udrec{justify-self:end;color:var(--mute);font-size:12.5px;white-space:nowrap}
.udleg{grid-column:1 / -1;margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:22px;line-height:1.15;letter-spacing:-.01em}
.udleg span{display:block;margin-top:3px;font-family:var(--body);font-style:normal;font-weight:500;font-size:13px;letter-spacing:0;color:var(--mute)}
.udwhy{margin:0;color:var(--ink);font-size:14px;line-height:1.4} .udwhy b{font-weight:700}
.udcard a.bsbtn{text-decoration:none;justify-self:end;white-space:nowrap}
@media (max-width:560px){ .udcard{grid-template-columns:1fr} .udrec{justify-self:start} .udcard a.bsbtn{justify-self:stretch;text-align:center;justify-content:center;min-height:46px} }
"""
JS = ("(function(){var c=[].slice.call(document.querySelectorAll('.udcard[data-ko]')),s=false;function t(){var n=Date.now();s=false;c.forEach(function(e){"
      "var live=+e.getAttribute('data-ko')>n;e.hidden=!(live&&!s);if(live&&!s)s=true;});var w=document.getElementById('bsunder');if(w)w.hidden=!s;}"
      "t();setInterval(t,60000);document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible')t();});})();")


def _cards(picks, rec):
    out = []
    for e in picks:
        stat = STAT[e["m"]][1]; be = 1 / dec(e["o"]); day = DAYN.get(str(e.get("kick", "")).split(" ")[0], "")
        url = f"https://sportsbook.fanduel.com/addToBetslip?marketId={e['fdm']}&selectionId={e['fds']}"
        out.append(f'<div class="udcard" data-ko="{e["ko"]}" data-pl="{E(e["pl"])}" data-m="{E(e["m"])}" data-ln="{e["ln"]:g}" hidden>'
                   f'<span class="udk">Under of the day{"<small>" + E(day) + "</small>" if day else ""}</span><span class="udrec">{E(record_text(rec))}</span>'
                   f'<p class="udleg">{E(e["pl"])} under {e["ln"]:g} {E(stat)}<span>{E(e.get("at") or e["gid"])} · {E(e.get("kick", ""))} CT</span></p>'
                   f'<p class="udwhy">The model has him under <b>{e["p"] * 100:.0f}%</b> of the time. The price needs {be * 100:.0f}%.</p>'
                   f'<a class="bsbtn" href="{E(url)}" target="_blank" rel="noopener">Bet the under {am(e["o"])}</a></div>')
    return "".join(out)


def card(out_dir="out", variant="home"):
    """The card(s) for the page, or "" when there is no pick ahead. One card per game day; the page's script shows the next one."""
    try: d = json.load(open(os.path.join(out_dir, "under_day.json")))
    except Exception: return ""
    picks = d.get("picks") or []
    if not picks: return ""
    inner = _cards(picks, d.get("record"))
    if variant == "short":
        return f'<section class="card udshort" id="bsunder" hidden>{inner}</section><script>{JS}</script>'
    return f'<style>{CSS_HOME}</style><section class="udsec" id="bsunder" hidden>{inner}</section><script>{JS}</script>'


CSS_SHORT = """
.sv .udshort{padding:0;border:0;background:transparent}
.sv .udshort .udcard{border:1px solid var(--line);border-left:4px solid var(--red);border-radius:14px;background:var(--card);padding:14px 14px 12px;display:grid;grid-template-columns:1fr;gap:6px}
.sv .udshort .udcard[hidden]{display:none}
.sv .udk{font-family:var(--display);font-weight:800;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--redtxt,var(--red))} .sv .udk small{margin-left:8px;color:var(--mute);font-weight:700;letter-spacing:.08em}
.sv .udrec{color:var(--mute);font-size:12.5px}
.sv .udleg{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:22px;line-height:1.15;letter-spacing:-.01em} .sv .udleg span{display:block;margin-top:3px;font-family:var(--body);font-style:normal;font-weight:500;font-size:13px;color:var(--mute)}
.sv .udwhy{margin:0 0 6px;font-size:14.5px;line-height:1.4} .sv .udwhy b{font-weight:700}
.sv .udshort a.bsbtn{display:flex;width:100%;min-height:48px;font-size:16px;padding:13px 16px;box-sizing:border-box;justify-content:center}
"""

if __name__ == "__main__":
    print(build())
