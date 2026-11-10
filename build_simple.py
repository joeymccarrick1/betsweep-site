#!/usr/bin/env python3
"""build_simple.py - the Simple view at /simple/ (owner 11/10: casual friends "want to just open up the app and everything they could
want is right there and not have to do any extra reading"; "Just make sure that simple mode stays with the same overall aesthetic.
Let's just push it to the site").

One screen, almost no reading: today's house slip when one is posted, three easy picks behind one FanDuel button, then every game
as a single row (who wins, how likely, the score); a tap opens that game's Sweep says line and best parlay. Nothing here is new
modelling - the numbers are the full site's (out/builder_data.json, out/best_parlays.json, out/promos.json, out/voice.json) with
everything else left out. The page is a plain source like the other small pages: build_site.py wraps it in the site template, so the
header, fonts, colours, dark / light and the playbook background are the site's own.

Full stays the default. A visitor picks Simple with the pill on the home page (or "Make this my home page" here) and the choice is
kept on the device (localStorage bs_view); the home page then opens here until he taps Full.

build_site.py calls build() itself right before placing the page, so it always sees the final promos / voice / best parlays of the run.
Writes out/simple.html and out/simple.json (what the page shows, for the checks).
"""
import json, os, html, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); sys.path.insert(0, HERE)
import sweep as SW
E = html.escape
DAYN = {"Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday", "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday"}
def am(o): return f"+{int(o)}" if o > 0 else str(int(o))
def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / -o
def amd(d): return f"+{round((d - 1) * 100)}" if d >= 2 else f"-{round(100 / (d - 1))}"
def fd_link(legs):
    """FanDuel add-to-betslip link for these builder legs, or "" unless every leg has its ids (a link that drops a leg is worse than none)"""
    ids = [(l["fd"]["m"], l["fd"]["s"]) for l in legs if l and (l.get("fd") or {}).get("m") and l["fd"].get("s")]
    if len(ids) != len(legs) or not ids: return ""
    return "https://sportsbook.fanduel.com/addToBetslip?" + "&".join(f"marketId[{i}]={m}&selectionId[{i}]={s}" for i, (m, s) in enumerate(ids))
def at(g): return f"{g['away']} {'vs' if g.get('nt') else '@'} {g['home']}" if g.get("home") and g.get("away") else f"{g['a']} - {g['b']}"
def leg_txt(l):
    if l.get("gl"): return l["pl"]
    if l["m"] == "Anytime TD": return f"{l['pl']} to score"
    return f"{l['pl']} {int(round(l['ln']))}+ {l['m'].lower()}"
def easy_picks(BD):
    """three favorites (-350..-140) the model has at or within two points of FanDuel's price, no risk flag (house rule: low-risk legs
    only), overs only, one per player, two per game at most, every one with its FanDuel ids"""
    cand = [l for l in BD["legs"] if not l.get("gl") and not l.get("u") and not str(l["m"]).startswith("Under") and l["m"] not in ("First TD", "Longest Reception", "Rushing Yards")
            and l.get("o") is not None and l.get("p") is not None and -350 <= l["o"] <= -140 and l["p"] >= (l.get("bk") or 1) - 0.02
            and SW.risk_score(l, BD) < 2 and (l.get("fd") or {}).get("m") and (l.get("fd") or {}).get("s")]
    cand.sort(key=lambda l: (-l["p"], l["pl"])); out, seen, per = [], set(), {}
    for l in cand:
        if l["pl"] in seen or per.get(l["g"], 0) >= 2: continue
        out.append(l); seen.add(l["pl"]); per[l["g"]] = per.get(l["g"], 0) + 1
        if len(out) == 3: break
    return out if len(out) == 3 else []

CSS = """
/* Simple view. Everything here leans on the site's own system: the palette and type variables of the template, the brand layer's
   segmented control (.seg), primary button (.bsbtn) and brushed section title (.brush), the home page's card and Sweep says shapes. */
.sv{max-width:720px;margin:14px auto 40px;padding:0 12px}
.sv .svhead{margin:0 4px 10px}
.sv h1{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:40px;letter-spacing:-.02em;line-height:1}
.sv .sub{display:block;margin-top:6px;color:var(--mute);font-size:14px;line-height:1.4}
.sv .svbar{display:flex;align-items:center;justify-content:space-between;gap:8px 12px;flex-wrap:wrap;margin:0 4px 16px}
.sv .keep{margin:0;color:var(--mute);font-size:13.5px} .sv .keep button{all:unset;cursor:pointer;color:var(--ink);font-weight:600;text-decoration:underline;text-underline-offset:3px}
.sv .card{border:1px solid var(--line);border-radius:14px;background:var(--card);padding:14px 14px 12px;margin-bottom:12px}
.sv .card.hero{border:2px solid var(--red)}
.sv h2{font-family:var(--display);font-weight:700;letter-spacing:.01em;font-size:22px;line-height:1.1;color:var(--ink);margin:0 0 10px;display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 10px}
.sv h2 small{font-family:var(--body);font-weight:500;font-size:13.5px;letter-spacing:0;color:var(--mute)}
.sv h2.out{margin:22px 4px 12px}
.sv h3{margin:16px 4px 8px;font-family:var(--display);font-weight:800;font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--mute)}
.sv .nm{margin:0 0 6px;font-family:var(--brand);font-style:italic;font-weight:800;font-size:24px;line-height:1.1;letter-spacing:-.01em}
.sv .legs{list-style:none;margin:0 0 12px;padding:0}
.sv .legs li{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:9px 0;border-top:1px solid var(--line);font-size:15.5px;line-height:1.3}
.sv .legs li:first-child{border-top:0} .sv .legs b{font-weight:600} .sv .legs span{color:var(--mute);white-space:nowrap;font-size:14px}
.sv .legs li.gone b{text-decoration:line-through;color:var(--mute)}
.sv a.bsbtn{text-decoration:none;gap:8px;align-items:center;flex:none;line-height:1.1}
.sv a.bsbtn.wide{display:flex;width:100%;min-height:48px;font-size:16px;padding:13px 16px;box-sizing:border-box}
.sv a.bsbtn small{font-family:var(--body);font-weight:600;font-size:13px;letter-spacing:0;text-transform:none;opacity:.92}
.sv .fine{margin:9px 0 0;color:var(--mute);font-size:12.5px;line-height:1.45}
.sv .gm{border:1px solid var(--line);border-radius:14px;background:var(--card);margin-bottom:8px;overflow:hidden}
.sv .gm summary{list-style:none;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 14px;cursor:pointer}
.sv .gm summary::-webkit-details-marker{display:none}
.sv .mt{font-family:var(--display);font-weight:800;font-size:19px;letter-spacing:.02em;line-height:1.1} .sv .mt small{display:block;margin-top:3px;font-family:var(--body);font-weight:500;color:var(--mute);font-size:12.5px;letter-spacing:0}
.sv .pk{text-align:right;font-size:14.5px;line-height:1.25} .sv .pk b{font-weight:700} .sv .pk i{font-style:normal;color:var(--good);font-weight:700} .sv .pk .sc{display:block;margin-top:2px;color:var(--mute);font-size:12.5px}
.sv .gmin{padding:0 14px 12px;display:grid;gap:10px}
.sv .sweepsays{margin:0;position:relative;background:var(--chalk);border-radius:10px;padding:10px 12px 10px 14px;font-size:15px;line-height:1.4;font-weight:500;color:var(--ink)}
.sv .sweepsays i{display:block;font-style:normal;font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--redtxt,var(--red));margin-bottom:3px}
.sv .bp{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:14.5px;line-height:1.35}
.sv .bp small{flex-basis:100%;font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--mute)}
.sv .bp span{flex:1;min-width:0;font-weight:500} .sv .bp em{font-style:normal;font-family:var(--display);font-weight:800;font-size:17px}
.sv .more{color:var(--ink);font-family:var(--ctl,var(--display));font-weight:700;font-size:13px;letter-spacing:.05em;text-transform:uppercase;text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--red)}
.sv .none{color:var(--mute);font-size:15px;line-height:1.5;margin:8px 4px}
.sv .foot{margin:18px 4px 0;color:var(--mute);font-size:12px;line-height:1.5}
@media (max-width:380px){.sv h1{font-size:34px}.sv .mt{font-size:17px}}
"""
JS = r"""
(function(){
  var $ = function(i){ return document.getElementById(i); };
  function pref(){ try{ return localStorage.getItem('bs_view'); }catch(e){ return null; } }
  function setPref(v){ try{ localStorage.setItem('bs_view', v); }catch(e){} }
  // kicked-off games leave the page; a day with nothing left loses its heading; the easy picks go once one of their games has started
  function clock(){ var n = Date.now(), left = 0;
    document.querySelectorAll('.sv .gm').forEach(function(e){ var k = +e.getAttribute('data-ko'); if(k && n >= k) e.hidden = true; else left++; });
    document.querySelectorAll('.sv h3[data-day]').forEach(function(h){ var any = false, s = h.nextElementSibling; while(s && s.tagName !== 'H3'){ if(s.classList.contains('gm') && !s.hidden) any = true; s = s.nextElementSibling; } h.hidden = !any; });
    var ez = $('sveasy'); if(ez){ var k = +ez.getAttribute('data-ko'); if(k && n >= k) ez.hidden = true; }
    var hs = $('svslip'); if(hs){ var k2 = +hs.getAttribute('data-ko'); if(k2 && n >= k2) hs.hidden = true; }
    var gh = $('svgames'), no = $('svnone'); if(gh) gh.hidden = !left; if(no) no.hidden = !!left; }
  clock(); setInterval(clock, 60000); document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'visible') clock(); });
  // a player ruled out since the build: his pick is struck and the one-tap button goes, because its link still carries him
  function risk(){ var ez = $('sveasy'); if(!ez || !window.BSRisk) return; var bad = false;
    ez.querySelectorAll('li[data-pl]').forEach(function(li){ var v = null; try{ v = window.BSRisk.verdict(li.getAttribute('data-pl'), li.getAttribute('data-m')); }catch(e){}
      var out = !!(v && v.level === 'block'); li.classList.toggle('gone', out); if(out) bad = true; });
    var go = ez.querySelector('.bsbtn'), fn = $('sveasyfn'); if(go) go.hidden = bad; if(fn && bad) fn.textContent = 'One of these players has been ruled out since this was built. Fresh picks come with the next update.'; }
  document.addEventListener('bs-risk', risk); risk();
  // Simple / Full: the choice is kept on this device
  var full = $('svfull'); if(full) full.addEventListener('click', function(){ setPref('full'); location.href = '/'; });
  var keep = $('svkeep'); function keepLine(){ if(!keep) return; if(pref() === 'simple'){ keep.innerHTML = 'Simple is your home page on this device.'; } else { keep.innerHTML = 'Like it short? <button type="button" id="svkeepb">Make this my home page</button>'; var b = $('svkeepb'); if(b) b.addEventListener('click', function(){ setPref('simple'); keepLine(); }); } }
  keepLine();
})();
"""
def build(out_dir=OUT):
    def load(n, d):
        try: return json.load(open(os.path.join(out_dir, n)))
        except Exception: return d
    BD = load("builder_data.json", None)
    if not BD: raise SystemExit("build_simple.py needs out/builder_data.json (run build_builder.py first)")
    WEEK = BD.get("week"); GAMES = BD["games"]; LEGS = BD["legs"]; BP = {b["gid"]: b for b in load("best_parlays.json", [])}
    VOICE = load("voice.json", {}); SAY = (VOICE.get("games") or {}) if str(VOICE.get("week")) == str(WEEK) else {}
    PROMOS = load("promos.json", []); PROMOS = PROMOS if isinstance(PROMOS, list) else PROMOS.get("promos", [])
    ko_of = {g["gid"]: g.get("ko") or 0 for g in GAMES}
    # ---- three easy picks ----
    easy = easy_picks(BD); easy_html = ""; easy_link = ""
    if easy:
        d = 1.0
        for l in easy: d *= dec(l["o"])
        easy_link = fd_link(easy)
        rows = "".join(f'<li data-pl="{E(l["pl"])}" data-m="{E(l["m"])}"><b>{E(leg_txt(l))}</b><span>{l["p"] * 100:.0f}% · {am(l["o"])}</span></li>' for l in easy)
        easy_html = (f'<section class="card" id="sveasy" data-ko="{min(ko_of.get(l["g"], 0) for l in easy)}"><h2 class="brush">3 easy picks</h2><ul class="legs">{rows}</ul>'
                     + (f'<a class="bsbtn wide" href="{E(easy_link)}" target="_blank" rel="noopener">Bet all 3 on FanDuel <small>about {amd(d)}</small></a>' if easy_link else "")
                     + '<p class="fine" id="sveasyfn">Three favorites the model has at or near the FanDuel price, none with a risk flag. Check the lines on FanDuel before you place it.</p></section>')
    # ---- the house slip of the day, when one is posted and not yet settled ----
    sw = next((p for p in PROMOS if p.get("sweep") and str(p.get("status", "LIVE")).upper() == "LIVE" and not p.get("result")), None)
    sweep_html = ""
    if sw:
        kos = [l.get("ko") for l in sw.get("legs", []) if l.get("ko")]
        rows = "".join(f'<li><b>{E(str(l.get("disp") or l.get("who") or ""))}</b></li>' for l in sw.get("legs", []))
        price = ""
        try: price = am(float(sw["fd"]))
        except Exception: pass
        sweep_html = (f'<section class="card hero" id="svslip" data-ko="{min(kos) if kos else 0}"><h2 class="brush">Today\'s slip <small>The Daily Sweep</small></h2><p class="nm">{E(str(sw.get("name") or sw.get("title") or ""))}</p><ul class="legs">{rows}</ul>'
                      + (f'<a class="bsbtn wide" href="{E(sw["link"])}" target="_blank" rel="noopener">Bet it on FanDuel{" <small>" + E(price) + "</small>" if price else ""}</a>' if sw.get("link") else "") + '</section>')
    # ---- every game on one row ----
    ML = {}
    for l in LEGS:
        if l["m"] == "Moneyline" and not l.get("alt"): ML.setdefault(l["g"], {})[l["tm"]] = l
    BYK = {}
    for l in LEGS: BYK.setdefault((l["g"], l["pl"], l["m"]), l)
    days, rows_json = {}, []
    for g in sorted(GAMES, key=lambda g: g.get("sort", "")):
        a, b = g["a"], g["b"]; ml = ML.get(g["gid"], {}); pa = (ml.get(a) or {}).get("p"); pb = (ml.get(b) or {}).get("p")
        if pa is not None and pb is not None: win, wp = (a, pa) if pa >= pb else (b, pb)
        else: win, wp = (a if (g.get("pa") or 0) >= (g.get("pb") or 0) else b), None
        sw_, sl_ = ((g.get("pa") or 0), (g.get("pb") or 0)) if win == a else ((g.get("pb") or 0), (g.get("pa") or 0))
        close = wp is not None and wp < 0.55
        score = f'{round(sw_)}-{round(sl_)}' if round(sw_) > round(sl_) else ""   # never print a score that contradicts the pick
        pick = f'<b>{E(win)}</b> {"by a hair" if close else "to win"}' + (f' <i>{wp * 100:.0f}%</i>' if wp is not None else "") + (f'<span class="sc">{score}</span>' if score else "")
        bp = BP.get(g["gid"]); bp_html = ""; bp_link = ""
        if bp:
            legs = [BYK.get((g["gid"], x[0], x[1])) for x in bp["legs"]]; bp_link = fd_link(legs)
            bp_html = ('<div class="bp"><small>Best parlay</small><span>' + " + ".join(E(leg_txt(l) if l else str(x[0])) for l, x in zip(legs, bp["legs"])) + '</span>'
                       + (f'<a class="bsbtn" href="{E(bp_link)}" target="_blank" rel="noopener">Bet {amd(bp["dec"])}</a>' if bp_link else f'<em>{amd(bp["dec"])}</em>') + '</div>')
        say = SAY.get(g["gid"]); day = (g.get("kick") or "").split(" ")[0]
        days.setdefault(day, []).append(
            f'<details class="gm" data-g="{E(g["gid"])}" data-ko="{g.get("ko") or 0}"><summary><span class="mt">{E(at(g))}<small>{E(g.get("kick", ""))} CT</small></span><span class="pk">{pick}</span></summary>'
            + '<div class="gmin">' + (f'<p class="sweepsays"><i>Sweep says</i>{E(say)}</p>' if say else "") + bp_html + f'<a class="more" href="/boards/#{E(g["gid"])}">Full board for this game</a></div></details>')
        rows_json.append({"gid": g["gid"], "label": at(g), "ko": g.get("ko"), "win": win, "p": wp, "score": score, "say": bool(say), "bp": [x[:3] for x in bp["legs"]] if bp else None, "bp_link": bp_link})
    games_html = "".join(f'<h3 data-day="{E(d)}">{E(DAYN.get(d, d))}</h3>' + "".join(v) for d, v in days.items())
    try:
        import account as ACCT; _link, _base = ACCT._base_css()
    except Exception: _link, _base = "", ""
    page = f"""<title>BetSweep, the short version</title>
<meta name="description" content="BetSweep in one screen: today's slip, three easy picks, and who wins every NFL game this week. Tap a game for its best parlay.">
{_link}
<style>{_base}
{CSS}</style>
<div class="sv">
<div class="svhead"><h1>The short version</h1><span class="sub">Week {E(str(WEEK))}. Picks first, reading optional.</span></div>
<div class="svbar"><div class="seg" role="group" aria-label="View"><button type="button" class="on" aria-pressed="true">Simple</button><button type="button" id="svfull" aria-pressed="false">Full</button></div><p class="keep" id="svkeep"></p></div>
{sweep_html}{easy_html}
<h2 id="svgames" class="brush out">Who wins <small>tap a game for its best parlay</small></h2>
{games_html}
<p class="none" id="svnone" hidden>Every game this week has kicked off. Next week's picks land Tuesday. <a href="/live/" style="color:var(--ink)">Follow the games live</a></p>
<p class="foot">The model's picks, not guarantees. Want the reasons, every prop and the receipts? Tap Full. 21+ | Gamble responsibly.</p>
</div>
<script>{JS}</script>
"""
    open(os.path.join(out_dir, "simple.html"), "w").write(page)
    json.dump({"week": WEEK, "easy": [{"pl": l["pl"], "m": l["m"], "ln": l["ln"], "o": l["o"], "p": l["p"], "g": l["g"], "fd": [l["fd"]["m"], l["fd"]["s"]]} for l in easy], "easy_link": easy_link,
               "slip": (sw.get("title") if sw else None), "games": rows_json}, open(os.path.join(out_dir, "simple.json"), "w"))
    return f"wrote out/simple.html (Simple view, /simple/): week {WEEK}, {len(GAMES)} games, {len(easy)} easy picks, house slip {'yes' if sw else 'none posted'}, Sweep says lines {sum(1 for r in rows_json if r['say'])}"

if __name__ == "__main__":
    print(build())
