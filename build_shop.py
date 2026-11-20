#!/usr/bin/env python3
"""build_shop.py - Line shop, /shop/ (owner 11/10 deep dive: "another book pays better than FanDuel on nearly half our legs").

Measured 11/10: of 266 player legs that had a second price, DraftKings or Hard Rock paid more than FanDuel on 122, by a median of one
point of break-even chance - as much as any edge the model has shown. The builder and the home cards already mark the best book leg by
leg; this page is the list nobody had to assemble by hand: every leg on the board where another book pays more, biggest gap first.

Exact lines only: a book's nearest line is a different bet and is never compared. One rung per player and market (the widest gap).
Gap = FanDuel's break-even chance minus the other book's, in points; a leg is listed from 1.5 points up. Unders and first-TD legs are
left out (no second price is stored for them). Reads out/builder_data.json; writes out/shop.html (a plain page for place_plain) and
out/shop.json (served as /b/shop.json).
"""
import html, json, os, sys
from mktxt import low as _mlow

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); E = html.escape
sys.path.insert(0, HERE)
import booklinks as BL  # noqa: E402

NAMES = {"dk": "DraftKings", "hr": "Hard Rock"}; MIN_GAP = 0.015


def dec(o): o = float(o); return 1 + o / 100 if o > 0 else 1 + 100 / -o
def am(o): o = int(round(float(o))); return f"+{o}" if o > 0 else f"−{-o}"
def at(g): return f"{g['away']} {'vs' if g.get('nt') else '@'} {g['home']}" if g.get("home") and g.get("away") else f"{g['a']} - {g['b']}"


def leg_txt(l):
    if l.get("gl"): return l["pl"]
    if l["m"] == "Anytime TD": return f"{l['pl']} to score"
    return f"{l['pl']} {int(round(l['ln']))}+ {_mlow(l['m'])}"


def rows(BD):
    G = {g["gid"]: g for g in BD["games"]}; best = {}; priced = better = 0
    for l in BD["legs"]:
        if l.get("o") is None or l.get("u") or str(l["m"]).startswith("Under") or l["m"] == "First TD" or l["g"] not in G: continue
        if l.get("gl") and l.get("alt"): continue
        oth = [(b, x) for b, x in (l.get("bks") or {}).items() if b in NAMES and isinstance(x, dict) and x.get("o") is not None]
        if not oth: continue
        priced += 1; fd = 1 / dec(l["o"])
        b, x = max(oth, key=lambda t: dec(t[1]["o"])); gap = fd - 1 / dec(x["o"])
        if gap > 0.0005: better += 1
        if gap < MIN_GAP: continue
        url = x.get("u") or (BL.url([x["s"]], b) if x.get("s") else None)
        if not url: continue
        k = (l["pl"], l["m"]) if not l.get("gl") else (l["g"], l["m"], (l.get("gl") or {}).get("side"))
        r = {"t": leg_txt(l), "pl": "" if l.get("gl") else l["pl"], "m": l["m"], "g": l["g"], "at": at(G[l["g"]]), "ko": G[l["g"]].get("ko") or 0, "fd": int(l["o"]), "b": b, "o": int(x["o"]), "gap": round(gap, 4),
             "p": round(l["p"], 4) if l.get("p") is not None else None, "u": url, "more": round((dec(x["o"]) - 1) / (dec(l["o"]) - 1) - 1, 4)}
        if k not in best or r["gap"] > best[k]["gap"]: best[k] = r
    out = sorted(best.values(), key=lambda r: (-r["gap"], r["t"]))
    return out, priced, better


def build(out_dir=OUT):
    BD = json.load(open(os.path.join(out_dir, "builder_data.json"))); R, priced, better = rows(BD)
    json.dump({"week": BD.get("week"), "built": BD.get("built"), "priced": priced, "better": better, "rows": R}, open(os.path.join(out_dir, "shop.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    try:
        import account as ACCT; _link, _base = ACCT._base_css()
    except Exception: _link, _base = "", ""
    # 11/17 (page pass): 60 cards with a full-width button each ran 14 phone screens. A row is now three short lines with the better
    # price on its button, the first 15 show (the rest behind one button), and a book switch keeps only the book a visitor has.
    SHORT = {"dk": "DK", "hr": "HR"}
    items = "".join(
        f'<li data-ko="{r["ko"]}" data-b="{r["b"]}"' + (f' data-rk="{E(r["pl"])}|{E(r["m"])}"' if r.get("pl") else "") + f'><div class="lg"><b data-rkn>{E(r["t"])}</b><small>{E(r["at"])}' + (f' · model {r["p"] * 100:.0f}%' if r["p"] is not None else "") + '</small></div>'
        f'<div class="px"><span>FanDuel <b>{am(r["fd"])}</b></span><em>pays {r["more"] * 100:.0f}% more</em></div>'
        f'<a class="bsbtn" href="{E(r["u"])}" target="_blank" rel="noopener" aria-label="Bet {E(r["t"])} at {NAMES[r["b"]]}, {am(r["o"])}"><span class="bkl">{NAMES[r["b"]]}</span><span class="bks">{SHORT[r["b"]]}</span> <b>{am(r["o"])}</b></a></li>' for r in R[:60])
    _nb = {b: sum(1 for r in R[:60] if r["b"] == b) for b in NAMES}
    books = ('<div class="tabs shbk" id="shbk" role="group" aria-label="Which book">'
             f'<button type="button" class="tab on" data-b="">All <small>{min(60, len(R))}</small></button>'
             + "".join(f'<button type="button" class="tab" data-b="{b}">{NAMES[b]} <small>{_nb[b]}</small></button>' for b in NAMES if _nb[b]) + '</div>') if sum(1 for b in NAMES if _nb[b]) > 1 else ""
    lead = (f"Another book pays more than FanDuel on <b>{better} of the {priced}</b> legs that have a second price right now." if priced else "No second prices on the board yet.")
    page = f"""<title>Line shop · BetSweep</title>
<meta name="description" content="Same leg, better price: every NFL Week {E(str(BD.get('week')))} leg where DraftKings or Hard Rock pays more than FanDuel, biggest gap first.">
{_link}
<style>{_base}
{CSS}</style>
<div class="shp">
<div class="shhead"><h1>Line shop</h1><span class="sub">Week {E(str(BD.get("week")))}. Same leg, better price. {lead}</span></div>
{(books + '<ul class="shl" id="shl">' + items + '</ul><p class="shmorep" id="shmorep" hidden><button type="button" class="bsbtn sec" id="shmore">Show all</button></p>') if items else '<p class="none">Nothing on the board pays 1.5 points better anywhere else right now. Check back as more props post.</p>'}
<p class="none" id="shnone" hidden>Every listed game has kicked off.</p>
<p class="foot">Exact lines only: a book's nearest line is a different bet and is not compared. Prices as of {E(str(BD.get("built", "")))} CT and they move, so check the number before you bet. 21+ | Gamble responsibly.</p>
</div>
<script>(function(){{ var CAP = 15, all = false, bk = '', mp = document.getElementById('shmorep'), mb = document.getElementById('shmore');
  function t(){{ var n = Date.now(), left = 0, any = 0; document.querySelectorAll('.shl li').forEach(function(e){{ var k = +e.getAttribute('data-ko');
    /* bsr-out (11/17): risk.js marks a row whose player the live injury list has ruled out - a better price on a bet the book will void is no use */
    var ok = !((k && n >= k) || e.classList.contains('bsr-out')); if(ok) any++;
    if(ok && bk && e.getAttribute('data-b') !== bk) ok = false; if(ok) left++;
    e.hidden = !ok || (!all && left > CAP); }});
  if(mp){{ mp.hidden = all || left <= CAP; mb.textContent = 'Show all ' + left; }}
  var no = document.getElementById('shnone'); if(no && document.getElementById('shl')) no.hidden = !!any; }}
  if(mb) mb.addEventListener('click', function(){{ all = true; t(); }});
  var bx = document.getElementById('shbk'); if(bx) bx.addEventListener('click', function(e){{ var b = e.target.closest('.tab'); if(!b) return; bk = b.getAttribute('data-b') || ''; all = false;
    [].forEach.call(bx.children, function(x){{ x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }}); t(); }});
  t(); setInterval(t, 60000); document.addEventListener('bs-risk', t); }})();</script>
"""
    open(os.path.join(out_dir, "shop.html"), "w").write(page)
    top = f'; widest: {R[0]["t"]} FanDuel {am(R[0]["fd"])} vs {NAMES[R[0]["b"]]} {am(R[0]["o"])}' if R else ""
    return f"wrote out/shop.html + shop.json: {better} of {priced} legs pay more at another book, {len(R)} listed at 1.5+ points{top}"


CSS = """
.shp{max-width:720px;margin:14px auto 40px;padding:0 12px}
.shp .shhead{margin:0 4px 14px} .shp h1{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:40px;letter-spacing:-.02em;line-height:1}
.shp .sub{display:block;margin-top:6px;color:var(--mute);font-size:14px;line-height:1.45} .shp .sub b{color:var(--ink);font-weight:700}
.shp .shbk{display:flex;gap:6px;margin:0 0 10px;overflow-x:auto;scrollbar-width:none} .shp .shbk::-webkit-scrollbar{display:none}
.shp .shbk .tab{flex:1 0 auto;white-space:nowrap;min-height:40px} .shp .shbk .tab small{font:inherit;font-size:11.5px;opacity:.75}
.shp .shl{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:14px;background:var(--card);overflow:hidden}
.shp .shl li{padding:10px 12px 10px 14px;border-bottom:1px solid var(--line);display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;align-items:center}
.shp .shl li:last-child{border-bottom:0}
.shp .shl li[hidden]{display:none}
.shp .lg{grid-column:1} .shp .lg b{display:block;font-weight:600;font-size:15.5px;line-height:1.25} .shp .lg small{display:block;color:var(--mute);font-size:12.5px;line-height:1.4}
.shp .px{grid-column:1;display:flex;flex-wrap:wrap;gap:0 10px;align-items:baseline;font-size:12.5px;line-height:1.4;color:var(--mute)}
.shp .px b{font-family:var(--display);font-weight:800;font-size:14.5px;color:var(--ink)} .shp .px em{font-style:normal;color:var(--good)}
.shp a.bsbtn{text-decoration:none;grid-row:1 / 3;grid-column:2;white-space:nowrap;align-self:center;min-height:44px;display:inline-flex;align-items:center;gap:6px}
.shp a.bsbtn b{font-family:var(--display);font-weight:800;font-size:16px;letter-spacing:0} .shp a.bsbtn .bks{display:none}
.shp .shmorep{margin:10px 0 0} .shp .shmorep[hidden]{display:none} .shp .shmorep .bsbtn{width:100%}
.shp .none{color:var(--mute);font-size:15px;line-height:1.5;margin:8px 4px}
.shp .foot{margin:18px 4px 0;color:var(--mute);font-size:12px;line-height:1.5}
@media (max-width:480px){ .shp h1{font-size:34px} .shp a.bsbtn{padding-left:12px;padding-right:12px} .shp a.bsbtn .bkl{display:none} .shp a.bsbtn .bks{display:inline} }
"""

if __name__ == "__main__":
    print(build())
