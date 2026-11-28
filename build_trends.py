#!/usr/bin/env python3
"""build_trends.py - /trends/ : Trend check (owner 11/27 10:34 PM, with two screen recordings of FanDuel's new "Trends" cards: "They've
started adding a lot of what we're doing ... I want to make sure we're beating FanDuel's user experience as much as possible. The goal
is always to make the best most efficient legs and show them why as quickly and as best as it can").

FanDuel's Trends lists, per stat, the players who cleared a line in most of their last five games ("L5 hit rate 80%"), with five bars
and one tap to add. The streak is the whole argument. This page lists the same kind of leg from our own data, the same way (by stat,
by game, one tap to add), and puts beside each streak what FanDuel's card leaves out:

  the chance      the model's number against the win rate the price needs (home.meter)
  the reason      the strongest thing for the leg and the strongest thing against it, a line each (why.py)
  the record      how often streak legs have actually hit. Counted here at every build from the graded pre-kickoff snapshots
                  (in/legsnaps.json, the sheet's 'V2 - FanDuel Leg Snapshots') and nflverse's weekly player stats - never typed.
                  First count, 11/27, Weeks 6-11: 938 legs on a 4-or-5-of-5 run hit 56.3%; their prices needed 62.7%.

A streak leg = a FanDuel over (or touchdown) leg, priced now, whose player has five games logged and cleared this line in at least
four of the last five. One leg per player and market: the highest line that still shows the streak (the rung a trends list shows).
Three groups, by the two tests the site already uses everywhere - nothing new is claimed:
  Clears      no risk tag in the builder (sweep.risk_score under 2) and the model's chance at or above what the price needs
  Priced in   no risk tag, but the price asks for more than the model gives
  Flagged     the builder tags it Some risk or High risk; the card's first line says why
The model does not make streak legs winners: in the same snapshots the streak legs it liked most still lost a little. So the page
shows chance, price and reasons, and never calls a leg safe.

Reads out/builder_data.json (+ in/roster_2026.csv via home.py for the jersey tile). Writes out/trends.json: the page's inner HTML,
its script, the counts, the record, and the one-line door Today shows. build_site.py wraps it as a week page.
"""
import csv, json, math, os, re, sys, time, html
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import home as HOME, sweep as SW
E = html.escape
# the stat filter: (id, label, markets)
STATS = [("rush", "Rush yds", ("Rushing Yards",)), ("recy", "Rec yds", ("Receiving Yards",)), ("rec", "Receptions", ("Receptions",)), ("pass", "Pass yds", ("Passing Yards",)),
         ("ptd", "Pass TDs", ("Passing TDs",)), ("td", "TDs", ("Anytime TD", "2+ TD", "3+ TD")), ("more", "Other", ("Rush + Rec Yards", "Longest Reception"))]
STAT_OF = {m: sid for sid, _, ms in STATS for m in ms}
GROUPS = [("ok", "Clears", "No risk tag in the builder, and the model's chance is at or above what FanDuel's price needs. Not a promise: the record above is for streak legs as a whole."),
          ("mid", "Priced in", "No risk tag, but the price already asks for more than the model gives. The streak is real; you are paying for it."),
          ("no", "Flagged", "The builder tags these Some risk or High risk. The first line on each card is the reason.")]


def pm(x): return ("+" if x > 0 else "−" if x < 0 else "") + f"{abs(x):.1f}"


def need_of(m, ln):
    return 2 if m == "2+ TD" else 3 if m == "3+ TD" else 1 if str(m).endswith("TD") else float(ln)


def streak(l, gl):
    """(hits, games) over the player's last five logged games at this leg's line, or None when it is not an over this page reads"""
    m = str(l.get("m") or ""); sk = l.get("sk")
    if l.get("gl") or l.get("u") or m.startswith("Under ") or m == "First TD" or not sk or m not in STAT_OF: return None
    gs = [g for g in (gl.get(l.get("pl")) or []) if g.get(sk) is not None][:5]
    if len(gs) < 5: return None
    try: need = need_of(m, l.get("ln"))
    except Exception: return None
    return sum(1 for g in gs if float(g.get(sk) or 0) >= need), len(gs)


def pick(bd, now_ms=None):
    """this week's streak legs: one per player and market (the highest line still on a 4-of-5 run), games that have not kicked off"""
    now = now_ms if now_ms is not None else time.time() * 1000
    ko = {g["gid"]: g.get("ko") for g in bd.get("games") or []}; gl = bd.get("gl") or {}; top = {}
    for l in bd.get("legs") or []:
        s = streak(l, gl)
        if not s or s[0] < 4 or not (ko.get(l.get("g")) or 0) > now: continue
        k = (l["pl"], l["m"])
        if k not in top or float(l["ln"]) > float(top[k][0]["ln"]): top[k] = (l, s[0])
    out = []
    for l, h in top.values():
        score = SW.risk_score(l, bd); tag = SW.risk_tag(score)
        out.append({"l": l, "h": h, "risk": tag, "score": score, "grp": "no" if tag else ("ok" if float(l.get("e") or 0) >= 0 else "mid")})
    out.sort(key=lambda r: (r["score"] if r["grp"] == "no" else 0, -float(r["l"].get("e") or 0), r["l"]["pl"]))
    return out


def _pkey(n): return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", str(n).lower().replace(".", "")))).strip()


def record(IN_, season=2026):
    """How streak legs have actually done: the graded pre-kickoff snapshots, each leg's last five games before its week from nflverse's
    weekly stats, one leg per player, market and week (the highest line on a 4-of-5 run). None when either file is missing or thin."""
    try:
        v = json.load(open(os.path.join(IN_, "legsnaps.json")))["values"]; H = {c: i for i, c in enumerate(v[0])}
        col = {"Receiving Yards": "receiving_yards", "Receptions": "receptions", "Rushing Yards": "rushing_yards", "Passing Yards": "passing_yards"}
        log = {}
        with open(os.path.join(IN_, f"stats_player_week_{season}.csv"), newline="") as f:
            for r in csv.DictReader(f):
                if r.get("season_type", "REG") != "REG" or not r.get("player_display_name"): continue
                num = lambda x: float(x or 0)
                row = {m: num(r.get(c)) for m, c in col.items()}; row["Anytime TD"] = num(r.get("rushing_tds")) + num(r.get("receiving_tds"))
                log.setdefault(_pkey(r["player_display_name"]), {})[int(r["week"])] = row
        top = {}
        for r in v[1:]:
            r = list(r) + [""] * (len(v[0]) - len(r)); m = r[H["Market"]]
            if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS") or (m not in col and m != "Anytime TD"): continue
            try: w = int(float(r[H["Week"]])); ln = float(r[H["Line (X+)"]]); p = float(r[H["Model % (hist-adj)"]]); bk = float(r[H["Book implied %"]]); o = int(float(str(r[H["FanDuel odds"]]).replace("+", "")))
            except Exception: continue
            g = log.get(_pkey(r[H["Player"]])) or {}
            prev = [g[x] for x in sorted(g) if x < w][-5:]
            if len(prev) < 5: continue
            need = 1 if m == "Anytime TD" else ln; h5 = sum(1 for x in prev if x[m] >= need)
            if h5 < 4: continue
            k = (w, r[H["Player"]], m)
            if k not in top or ln > top[k]["ln"]: top[k] = {"w": w, "ln": ln, "p": p, "bk": bk, "o": o, "hit": r[H["Result"]] == "HIT", "h5": h5}
        xs = list(top.values()); n = len(xs)
        if n < 100: return None
        weeks = sorted({x["w"] for x in xs}); pay = lambda o: o / 100 if o > 0 else 100 / -o
        return {"n": n, "weeks": [weeks[0], weeks[-1]], "hit": round(sum(x["hit"] for x in xs) / n, 4), "need": round(sum(x["bk"] for x in xs) / n, 4), "model": round(sum(x["p"] for x in xs) / n, 4),
                "l5": round(sum(x["h5"] for x in xs) / n / 5, 4), "roi": round(sum(pay(x["o"]) if x["hit"] else -1 for x in xs) / n, 4),
                "n5": sum(1 for x in xs if x["h5"] == 5), "hit5": round(sum(x["hit"] for x in xs if x["h5"] == 5) / max(1, sum(1 for x in xs if x["h5"] == 5)), 4)}
    except Exception as e:
        print("trend check: no record -", type(e).__name__, e); return None


def build(IN_=IN, OUT_=OUT):
    D = HOME.load(IN_, OUT_); bd = D["bd"]; W = bd.get("week") or 0; G = {g["gid"]: g for g in bd["games"]}
    now_ms = int(time.time() * 1000); rows = pick(bd, now_ms); rec = record(IN_)
    by = {gid: [r for r in rows if r["grp"] == gid] for gid, _, _ in GROUPS}
    def card(r):
        l = r["l"]; x = HOME._mb(D, l, G)
        badge = f'<span class="trk{" hi" if r["risk"] == "High risk" else ""}">{E(r["risk"])}</span>' if r["risk"] else ""
        c = HOME.play_card(x, cls="trc", badge=badge)
        return c.replace('<article class="play trc"', f'<article class="play trc" data-k="{E(HOME.leg_key(l["pl"], l["m"], l["ln"]))}" data-st="{STAT_OF[l["m"]]}" data-h="{r["h"]}"', 1)
    games = [g for g in sorted(bd["games"], key=lambda g: g.get("ko") or 0) if any(r["l"]["g"] == g["gid"] for r in rows)]
    def sides(g):   # away, home when the schedule says so (home.at prints the same order)
        return (g["away"], g["home"], "@") if (g.get("home") and g.get("away") and not g.get("nt")) else (g["a"], g["b"], "vs")
    gchips = "".join(f'<button type="button" data-g="{E(g["gid"])}">{HOME.HM.hm(sides(g)[0])}<span>{E(sides(g)[0])} {sides(g)[2]} {E(sides(g)[1])}</span>{HOME.HM.hm(sides(g)[1])}</button>' for g in games)
    schips = "".join(f'<button type="button" data-s="{sid}">{E(lab)}</button>' for sid, lab, ms in STATS if any(STAT_OF[r["l"]["m"]] == sid for r in rows))
    base = ""
    if rec:
        base = (f'<div class="trbase" id="trbase"><div><b>{rec["l5"] * 100:.0f}%</b><span>what the streak says</span></div>'
                f'<div class="act"><b>{rec["hit"] * 100:.0f}%</b><span>how often they hit</span></div>'
                f'<div><b>{rec["need"] * 100:.0f}%</b><span>what the price needed</span></div>'
                f'<p>{rec["n"]:,} graded FanDuel legs on a 4-or-5-of-5 run, Weeks {rec["weeks"][0]}–{rec["weeks"][1]}. A unit on each returned {pm(rec["roi"] * 100)}%. '
                f'The model\'s average on them was {rec["model"] * 100:.0f}%. 5-of-5 streaks hit {rec["hit5"] * 100:.0f}%.</p></div>')
    # 11/28: the page is built the way it opens - the first group that has a card on screen, twelve cards a group - instead of every
    # card of every group, which the script then put away. The browser laid out and painted all 172 cards first: a third of a second
    # of layout on a desktop processor, well over a second on a phone, and a long page that jumped shut. `trw` (waiting) is dropped by
    # the script's first pass, which then shows and hides cards as before; with scripts off every card and every group shows.
    assert f"PAGE = {PAGE}," in TRENDS_JS, "the page's script opens a group on a different number of cards than the build marks"
    def waiting(h, i): return h.replace('<article class="', '<article class="trw ', 1) if i >= PAGE else h
    first = next((gid for gid, _, _ in GROUPS if by[gid]), GROUPS[0][0])
    groups = "".join(f'<div class="trgrp{"" if gid == first else " fxoff"}" data-tab="{gid}" data-label="{E(lab)}"><p class="nwcap">{E(cap)}</p><div class="plays trplays">{"".join(waiting(card(r), i) for i, r in enumerate(by[gid]))}</div>'
                     f'<p class="none tre" hidden>Nothing in this group for that filter.</p><button type="button" class="trmore" hidden></button></div>' for gid, lab, cap in GROUPS)
    groups += '<noscript><style>.fxoff{display:block!important} .trplays .play.trw{display:revert}</style></noscript>'
    inner = (f'<section class="sec" id="trends" data-week="{E(str(W))}" data-built="{now_ms}">{base}<div id="wktabs"></div>'
             f'<div class="nwf trf" id="trs" aria-label="Stat"><button type="button" data-s="" class="on">All stats</button>{schips}</div>'
             f'<div class="nwf trf trg" id="trg" aria-label="Game"><button type="button" data-g="" class="on">All games</button>{gchips}</div>'
             f'{groups}<p class="none" id="trnone" hidden>No streak legs for that filter.</p>'
             f'<p class="none trnote">A streak here means the player cleared this exact line in at least 4 of his last 5 games (the bars, oldest first). One leg per player and stat: the highest FanDuel line still on the run. '
             f'Cards leave when their game kicks off. <a href="/how/">How BetSweep picks</a></p></section>')
    n = len(rows); cnt = {gid: len(by[gid]) for gid, _, _ in GROUPS}
    door = ""
    if n:
        lead = (f'{rec["hit"] * 100:.0f}% is how often streak legs have hit since Week {rec["weeks"][0]}; their prices needed {rec["need"] * 100:.0f}%.' if rec else "See the model's chance and the reason beside each streak.")
        door = (f'<section class="sec" id="trdoor"><a class="trdoor" href="/trends/"><span class="trd1"><b>Trend check</b><em>{n} legs are on a 4-of-5 run this week. {cnt["ok"]} clear{"s" if cnt["ok"] == 1 else ""} the model\'s check.</em></span>'
                f'<span class="trd2">{E(lead)}</span><i aria-hidden="true">→</i></a></section>')
    out = {"week": W, "n": n, "counts": cnt, "record": rec, "html": inner, "js": TRENDS_JS, "css": TRENDS_CSS, "door": door, "door_css": DOOR_CSS,
           "legs": [{"k": HOME.leg_key(r["l"]["pl"], r["l"]["m"], r["l"]["ln"]), "g": r["l"]["g"], "grp": r["grp"], "h": r["h"], "risk": r["risk"]} for r in rows]}
    json.dump(out, open(os.path.join(OUT_, "trends.json"), "w"))
    return f"trend check: week {W}, {n} streak legs ({cnt['ok']} clear, {cnt['mid']} priced in, {cnt['no']} flagged)" + (f"; record {rec['hit'] * 100:.1f}% hit vs {rec['need'] * 100:.1f}% needed over {rec['n']} legs" if rec else "; no record yet")


TRENDS_CSS = r"""
/* Trend check (build_trends.py) */
.trbase{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:0 0 14px}
.trbase > div{padding:10px 12px 9px;display:flex;flex-direction:column;gap:3px;min-width:0} .trbase > div + div{border-left:1px solid var(--line)}
.trbase b{font-family:var(--display);font-weight:800;font-size:34px;line-height:1;font-variant-numeric:tabular-nums;color:var(--mute)} .trbase .act b{color:var(--ink)}
.trbase span{font-size:12px;line-height:1.3;color:var(--mute)} .trbase .act span{color:var(--ink);font-weight:600}
.trbase p{grid-column:1 / -1;margin:0;padding:8px 12px;border-top:1px solid var(--line);background:var(--chalk);font-size:12px;line-height:1.45;color:var(--mute)}
.trf{padding-bottom:8px} .trf button{display:inline-flex;align-items:center;gap:5px} .trg button i.hm{height:18px;margin:0;vertical-align:0} .trg button.on i.hm{filter:none}
.trgrp .nwcap{margin:2px 0 10px;color:var(--mute);font-size:12.5px;line-height:1.45;max-width:70ch}
.trplays.plays{grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
.trplays .play[hidden],.trplays .play.trw{display:none}
.play .ptop .trk{margin-left:auto;flex:none;align-self:flex-start;font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);border-radius:999px;padding:2px 8px;color:var(--mute);white-space:nowrap}
.play .ptop .trk.hi{border-color:var(--bad,#e07070);color:var(--bad,#e07070)}
.trmore{display:flex;align-items:center;justify-content:center;width:100%;min-height:46px;margin-top:12px;font:inherit;font-family:var(--display);font-weight:700;font-size:14px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink);background:transparent;border:1.5px solid var(--line);border-radius:10px;cursor:pointer}
.trmore[hidden],.tre[hidden]{display:none} .trnote{margin-top:14px;font-size:12.5px;line-height:1.5;max-width:74ch} .trnote a{color:var(--ink)}
@media (max-width:560px){ .trbase b{font-size:28px} .trbase > div{padding:9px 10px 8px} .trbase span{font-size:11.5px} .wk .wkh .lead{font-size:14px} }
"""
DOOR_CSS = r"""
.trdoor{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:13px 14px;text-decoration:none;color:var(--ink)}
.trdoor:hover{border-color:var(--red)} .trdoor .trd1 b{display:block;font-family:var(--brand);font-style:italic;font-weight:800;font-size:22px;line-height:1.1;letter-spacing:-.01em}
.trdoor .trd1 em{display:block;font-style:normal;font-size:14px;line-height:1.4;margin-top:3px} .trdoor .trd2{grid-column:1;font-size:12.5px;line-height:1.4;color:var(--mute)}
.trdoor i{grid-column:2;grid-row:1 / span 2;font-style:normal;font-family:var(--display);font-weight:800;font-size:22px;color:var(--red)}
"""
PAGE = 12   # cards a group opens on (the script's own PAGE; build() checks they agree)
TRENDS_JS = r"""(function(){
  var sec = document.getElementById('trends'), host = document.getElementById('wktabs'); if(!sec || !host || !window.bsTabs) return;
  var grps = [].slice.call(sec.querySelectorAll('.trgrp')), fs = document.getElementById('trs'), fg = document.getElementById('trg'), none = document.getElementById('trnone');
  var stat = '', game = '', PAGE = 12, open = {};
  try { var q = new URLSearchParams(location.search); if(q.get('g')) game = q.get('g'); if(q.get('s')) stat = q.get('s'); } catch(e){}
  var T = null; T = bsTabs.mount(host, grps.map(function(g){ return { id: g.getAttribute('data-tab'), label: g.getAttribute('data-label') }; }), { root: sec, key: 'bs_tab_trends', onShow: function(){ apply(true); } });
  function live(c){ return !c.classList.contains('started'); }
  function apply(keep){ if(!T) return; var total = 0, first = null, cur = T.cur(), curN = 0;
    grps.forEach(function(g){ var id = g.getAttribute('data-tab'), n = 0, shown = 0, cap = open[id] ? 1e9 : PAGE;
      [].forEach.call(g.querySelectorAll('.trplays > .play'), function(c){ c.classList.remove('trw');   /* as built: waiting beyond the first twelve */
        var on = live(c) && (!stat || c.getAttribute('data-st') === stat) && (!game || c.getAttribute('data-gid') === game);
        if(on) n++; c.hidden = !(on && n <= cap); if(on && n <= cap) shown++; });
      var more = g.querySelector('.trmore'); more.hidden = n <= shown; more.textContent = 'Show all ' + n; more.setAttribute('data-n', n);
      g.querySelector('.tre').hidden = n > 0; T.count(id, n); var b = host.querySelector('[data-t="' + id + '"]'); if(b) b.classList.toggle('zero', !n);
      total += n; if(n && !first) first = id; if(id === cur) curN = n; });
    none.hidden = total > 0;
    if(!keep && !curN && first) T.show(first, true); }
  function pickBtn(row, attr, val){ [].forEach.call(row.children, function(x){ x.classList.toggle('on', (x.getAttribute(attr) || '') === val); }); }
  fs.addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return; stat = b.getAttribute('data-s') || ''; pickBtn(fs, 'data-s', stat); open = {}; apply(); });
  fg.addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return; game = b.getAttribute('data-g') || ''; pickBtn(fg, 'data-g', game); open = {}; apply(); });
  sec.addEventListener('click', function(e){ var b = e.target.closest('.trmore'); if(!b) return; open[b.parentNode.getAttribute('data-tab')] = 1; apply(true); });
  pickBtn(fs, 'data-s', stat); pickBtn(fg, 'data-g', game);
  // the first group with anything in it opens first, unless the reader chose a tab earlier in this visit
  var had = null; try { had = sessionStorage.getItem('bs_tab_trends'); } catch(e){}
  apply(!!had); setTimeout(function(){ apply(true); }, 1500); setInterval(function(){ apply(true); }, 60000);
  document.addEventListener('bs-live', function(){ apply(true); });   // a game kicked off: its cards have just left
})();"""

if __name__ == "__main__":
    print(build())
