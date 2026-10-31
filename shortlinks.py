#!/usr/bin/env python3
"""shortlinks.py - short BetSweep bet links for X / Instagram (owner 10/27: FanDuel's addToBetslip links are 400+ characters,
look cluttered on socials and are too long for an Instagram story sticker).

Every bet gets a landing page at betsweep.co/b/<code>: BetSweep branding, the legs with the model's number on each, the FanDuel
price, one big "Bet it on FanDuel" button (the long link lives here, not in the post), "Load into the builder", and an OG/X card
image so the link unfurls as a BetSweep card.

Two kinds of code:
  w<week>-<slot>   promoted bets from 'PROMO - Promoted Bets' (build_promo.py) - a static page per promo written by build_site.py,
                   OG image = the promo's square poster, so it has a proper X card. This is the link the owner posts.
  <6 chars>        any slip from the Parlay Builder ("Short link" in the slip panel): the legs are stored in Supabase (short_links)
                   and betsweep.co/b/?s=<code> renders them client-side (GitHub Pages is static, so a query string keeps it a real
                   200 page with the BetSweep card; a path would be a 404 to X's crawler). No sign-in needed.

Visits are counted in link_hits (code -> hits) through the link_hit() function - the owner can see which posts drive clicks.

SQL below runs once in the Supabase SQL editor (also gen/shortlinks.sql).
"""
import json, html, os, re

E = html.escape
BASE = "https://betsweep.co"

SQL = r"""-- BetSweep short links: run once in the Supabase SQL editor (Project fuwiqijgkgbzvnfnsans > SQL editor > New query > paste > Run)
create table if not exists public.short_links (
  code text primary key check (code ~ '^[a-z0-9]{5,10}$'),
  week int,
  title text check (title is null or length(title) <= 80),
  legs jsonb not null check (jsonb_typeof(legs) = 'array' and jsonb_array_length(legs) between 1 and 20),
  fd_odds int,
  link text check (link is null or (length(link) <= 4000 and link like 'https://sportsbook.fanduel.com/%')),
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);
alter table public.short_links enable row level security;
drop policy if exists "read links" on public.short_links;
create policy "read links" on public.short_links for select using (true);
drop policy if exists "make links" on public.short_links;
create policy "make links" on public.short_links for insert with check (true);
-- nobody updates or deletes through the API (no policy) - the owner edits in the dashboard

create table if not exists public.link_hits (
  code text primary key,
  hits int not null default 0,
  last_hit timestamptz
);
alter table public.link_hits enable row level security;
drop policy if exists "read hits" on public.link_hits;
create policy "read hits" on public.link_hits for select using (true);
create or replace function public.link_hit(c text) returns void
language sql security definer set search_path = public as $$
  insert into public.link_hits (code, hits, last_hit) values (c, 1, now())
  on conflict (code) do update set hits = public.link_hits.hits + 1, last_hit = now();
$$;
grant execute on function public.link_hit(text) to anon, authenticated;
"""

def promo_code(pr): return f"w{int(pr['week'])}-{int(pr['slot'])}"
def promo_url(pr): return f"{BASE}/b/{promo_code(pr)}"

def odds_str(o):
    if o is None: return ""
    o = int(round(float(o))); return f"+{o}" if o > 0 else str(o)

CSS = """
.bl{max-width:560px;margin:18px auto 30px;padding:0 0 10px}
.bl .tag{display:inline-block;font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#fff;background:var(--red);padding:3px 10px;border-radius:99px}
.bl .wk{font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);margin-left:8px}
.bl h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:34px;letter-spacing:-.02em;line-height:1;margin:10px 0 6px}
.bl .meta{color:var(--mute);font-size:13px;margin:0 0 14px}
.bl ul.legs{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:12px;background:var(--card);overflow:hidden}
.bl ul.legs li{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding:11px 14px;border-top:1px solid var(--line);align-items:baseline}
.bl ul.legs li:first-child{border-top:0}
.bl ul.legs li b{font-weight:600;font-size:15px} .bl ul.legs li .o{font-family:var(--display);font-weight:700;font-size:18px;font-variant-numeric:tabular-nums}
.bl ul.legs li small{grid-column:1;color:var(--mute);font-size:12px} .bl ul.legs li .mp{grid-column:2;text-align:right;font-size:11.5px;color:var(--good);font-weight:600}
.bl .pf{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:14px 0 6px}
.bl .pf .big{font-family:var(--display);font-weight:800;font-size:44px;line-height:1;font-variant-numeric:tabular-nums} .bl .pf .big small{display:block;font-family:var(--body);font-weight:500;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);margin-bottom:2px}
.bl .pf .md{text-align:right;color:var(--mute);font-size:12.5px;line-height:1.4} .bl .pf .md b{color:var(--ink)}
.bl .go{display:grid;gap:8px;margin:14px 0 10px}
.bl .go a,.bl .go button{display:block;text-align:center;padding:14px 16px;border-radius:10px;font:inherit;font-weight:700;font-size:16px;text-decoration:none;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.bl .go a.fd{background:#1493ff;border-color:#1493ff;color:#fff;font-size:18px}
/* owner 10/30: DraftKings + Hard Rock on every short-link page */
.bl .go .bks{display:grid;grid-template-columns:1fr 1fr;gap:8px} .bl .go .bks[hidden]{display:none} .bl .go .bks a:only-child{grid-column:1/-1}
.bl .go a.dk{background:#53d337;border-color:#53d337;color:#0b1a07} .bl .go a.hr{background:#5b2d8e;border-color:#5b2d8e;color:#fff}
.bl .go .bknote{margin:-2px 0 0;font-size:11.5px;color:var(--mute);line-height:1.4;text-align:center}
.bl .go .row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px} .bl .go button.sv{border-color:var(--red)} .bl .go button.sv.on{background:var(--red);color:#fff}
.bl .svnote{margin:-2px 0 8px;font-size:12.5px;color:var(--mute);text-align:center} .bl .svnote[hidden]{display:none} .bl .go .row a,.bl .go .row button{font-size:14px;padding:11px 10px}
.bl .cap{color:var(--ink);font-size:14px;line-height:1.5;margin:12px 0}
.bl .lk{display:flex;align-items:center;gap:8px;margin:8px 0 0;font-size:13px;color:var(--mute)} .bl .lk code{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:var(--ink);background:var(--chalk);padding:3px 8px;border-radius:6px}
.bl .lk button{font:inherit;font-size:12px;font-weight:600;padding:4px 9px;border-radius:6px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer}
.bl .fn{color:var(--mute);font-size:11.5px;line-height:1.45;margin:14px 0 0}
.bl .none{padding:26px 16px;text-align:center;color:var(--mute);border:1px dashed var(--line);border-radius:12px}
.bl .list{display:grid;gap:10px;margin:12px 0} .bl .list a{display:block;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);text-decoration:none;color:var(--ink)}
.bl .list a b{display:block;font-family:var(--brand);font-style:italic;font-weight:800;font-size:22px;letter-spacing:-.02em} .bl .list a small{color:var(--mute)}
.bl .list a code{float:right;font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--mute)}
.bl .st{font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);margin-left:auto} .bl .st.live{color:var(--red)}
.bl .hd{display:flex;align-items:center}
"""

# owner 10/30: "I want to also save betslips on short links" - Save slip writes the same saved-slip list the Parlay Builder uses (bs_slips_w<W>),
# so the slip shows on My BetSweep (graded after the games), syncs to the account, and gets the slip alerts.
SAVE_JS = r"""<script>(function(){
  function sameSet(a, b){ if(a.length !== b.length) return false; var m = {}; a.forEach(function(k){ m[k] = 1; }); return b.every(function(k){ return m[k]; }); }
  function get(w){ try { var a = JSON.parse(localStorage.getItem('bs_slips_w' + w) || '[]'); return Array.isArray(a) ? a : []; } catch(e){ return []; } }
  function paint(b){ var d = JSON.parse(b.getAttribute('data-slip')); var on = get(d.w).some(function(s){ return s && Array.isArray(s.keys) && sameSet(s.keys, d.k); });
    b.classList.toggle('on', on); b.textContent = on ? 'Saved \u2713' : 'Save slip'; }
  window.bsPaintSave = function(){ document.querySelectorAll('.bl button.sv[data-slip]').forEach(paint); };
  document.addEventListener('click', function(ev){ var b = ev.target.closest('.bl button.sv[data-slip]'); if(!b) return;
    var d = JSON.parse(b.getAttribute('data-slip')); if(!d.w || !d.k || !d.k.length) return;
    var all = get(d.w), i = -1; all.forEach(function(s, j){ if(s && Array.isArray(s.keys) && sameSet(s.keys, d.k)) i = j; });
    if(i >= 0){ all.splice(i, 1); } else { all.push({id: 'b' + Date.now().toString(36), name: d.n || 'Slip', keys: d.k, odds: d.o != null ? d.o : null, stake: 1, fd: d.fd || null, saved: Date.now(), from: 'link'}); }
    try { localStorage.setItem('bs_slips_w' + d.w, JSON.stringify(all)); } catch(e){}
    paint(b);
    var n = document.getElementById('svnote'); if(n){ n.hidden = false; n.innerHTML = i >= 0 ? 'Removed from your saved slips.' : 'Saved to <a href="/me/" style="color:var(--ink);font-weight:700">My BetSweep</a> - graded after the games' + (window.bsAccount && window.bsAccount.user ? ', with slip alerts if you turned them on.' : '. Sign in to keep it on every device and get alerts if a player is ruled out.'); }
  });
  window.bsPaintSave();
})();</script>"""

LAND_JS = r"""<script>(function(){
  var root = document.querySelector('.bl'); if(!root) return;
  var code = root.dataset.code || '', W = root.dataset.week || '';
  // copy the short link
  root.querySelectorAll('[data-copy]').forEach(function(b){ b.addEventListener('click', function(){
    var t = b.dataset.copy; function done(){ var o = b.textContent; b.textContent = 'Copied'; setTimeout(function(){ b.textContent = o; }, 1400); }
    if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, function(){ prompt('Copy this link', t); });
    else prompt('Copy this link', t); }); });
  // count the visit (link_hits) once the Supabase client is on the page - best effort, never blocks anything
  var tries = 0; (function tick(){ var CFG = window.__BS_ACCOUNT || {};
    if(window.supabase && CFG.url){ try { window.supabase.createClient(CFG.url, CFG.key).rpc('link_hit', {c: code}).then(function(){}, function(){}); } catch(e){} return; }
    if(++tries < 60) setTimeout(tick, 100); })();
  // kickoff state: once every leg's game has started the FanDuel button says so
  var last = +root.dataset.lastKo || 0; if(last && Date.now() > last){ var fd = root.querySelector('a.fd'); if(fd){ fd.textContent = 'Games have kicked off - see the live page'; fd.href = '/live/'; } root.querySelectorAll('.go .bks, .go .bknote').forEach(function(x){ x.hidden = true; }); }
})();</script>"""

def leg_rows(legs):
    out = ""
    for l in legs:
        who = l.get("who") or l.get("pl") or ""
        if l.get("disp"):
            ml = l["disp"][len(who):].strip(" ·") if l["disp"].startswith(who) else l["disp"]
        else:
            m = l.get("m") or ""; ln = l.get("ln")
            ml = ("anytime TD" if m == "Anytime TD" else "first TD" if m == "First TD" else m if re.match(r"^\d\+ TD$", m) else f"{re.sub('^Under ', '', (l.get('ms') or m)).lower()} {('under ' + str(ln)) if l.get('u') else (str(int(ln)) + '+' if ln is not None else '')}".strip()) if not l.get("gl") else (l.get("ms") or m)
        sub = " · ".join(x for x in [ml, l.get("kick", ""), (f"vs {l['opp']}" if l.get("opp") and "/" not in str(l.get("tm", "")) else "")] if x)
        mp = f'<span class="mp">model {float(l["p"])*100:.0f}%</span>' if l.get("p") is not None else ""
        out += f'<li><b>{E(who)}</b><span class="o">{E(odds_str(l.get("o")))}</span><small>{E(sub)}</small>{mp}</li>'
    return out

def _model_line(p, fair):
    if p is None: return "Model price not available for every leg"
    if p < 0.03: return f'<b>Longshot</b> · model {"under 1" if p < 0.01 else format(p*100, ".0f")}% to hit - a small-stake swing, not a value bet'
    return f'<b>Model {p*100:.1f}%</b> to hit' + (f" · fair {E(fair)}" if fair else "")

NAMES = {"dk": "DraftKings", "hr": "Hard Rock"}
def book_buttons(books):
    """owner 10/30: 'add draftkings and hardrock as options on all the short link landing pages'. books = {"dk"|"hr": {"url", "subs"}}
    (booklinks.links, the same rules as every betslip: exact line, else the book's nearest line - named under the buttons)."""
    bs = [(b, books[b]) for b in ("dk", "hr") if (books.get(b) or {}).get("url")]
    if not bs: return ""
    h = '<div class="bks">' + "".join(f'<a class="{b}" href="{E(v["url"])}" target="_blank" rel="noopener">Bet it on {NAMES[b]}</a>' for b, v in bs) + '</div>'
    subs = [f'{NAMES[b]} uses its nearest line: ' + "; ".join(v["subs"]) for b, v in bs if v.get("subs")]
    note = (" ".join(s + "." for s in subs) + " " if subs else "") + "Prices shown are FanDuel's; the other books price the parlay themselves."
    return h + f'<p class="bknote">{E(note)}</p>'

def books_map(builder_data):
    """/b/books.json - this week's DraftKings / Hard Rock ids per leg key ("player|market|line", line rounded like JS), so short links
    made before the ids were stored with the link still get DK / HR buttons. {"week": W, "m": {key: {"dk": [id, odds, nearest line or null], ...}}}"""
    import math
    m = {}
    for l in builder_data.get("legs", []):
        k = f'{l.get("pl")}|{l.get("m")}|{int(math.floor(float(l.get("ln") or 1) + 0.5))}'
        e = {}
        for b in ("dk", "hr"):
            x = (l.get("bks") or {}).get(b); a = (l.get("ba") or {}).get(b)
            if x and x.get("s"): e[b] = [x["s"], x.get("o"), None]
            elif a and a.get("s"): e[b] = [a["s"], a.get("o"), a.get("ln")]
        if e and k not in m: m[k] = e
    return {"week": builder_data.get("week"), "m": m}

def promo_page(pr):
    """inner HTML (wrap() adds the site chrome and OG tags) for one promoted bet's landing page"""
    code = promo_code(pr); url = promo_url(pr); n = len(pr["legs"])
    keys = [l.get("key") for l in pr["legs"] if l.get("key")]
    from urllib.parse import quote
    build = "/build/?" + "&".join("add=" + quote(k, safe="") for k in keys) if keys and len(keys) == n else "/build/"
    res = (pr.get("result") or "").upper()
    st = '<span class="st">Cashed</span>' if res in ("W", "WIN", "HIT", "CASHED") else ('<span class="st">Missed</span>' if res in ("L", "LOSS", "MISS", "MISSED") else '<span class="st live">Pregame</span>')
    tweet = f'{pr["title"]} · {n}-leg parlay · FanDuel {odds_str(pr["fd"]) if pr.get("fd") else ""}\n{url}'
    share = "https://twitter.com/intent/tweet?text=" + quote(tweet)
    cap = f'<p class="cap">{E(pr["caption"])}</p>' if pr.get("caption") else ""
    fdbtn = f'<a class="fd" href="{E(pr["link"])}" target="_blank" rel="noopener">Bet it on FanDuel{(" · " + E(odds_str(pr["fd"]))) if pr.get("fd") else ""}</a>' if pr.get("link") else ""
    fdbtn += book_buttons(pr.get("books") or {})
    return f'''<div class="bl" data-code="{E(code)}" data-week="{pr["week"]}" data-last-ko="{pr.get("last_ko") or ""}">
<div class="hd"><span class="tag">Promoted</span><span class="wk">Week {pr["week"]}</span>{st}</div>
<h1>{E(pr["title"])}</h1><div class="meta">{n} legs · one tap on FanDuel · snapshot at post time, prices move</div>
<ul class="legs">{leg_rows(pr["legs"])}</ul>
<div class="pf"><div class="big"><small>FanDuel</small>{E(odds_str(pr["fd"])) if pr.get("fd") else '<span style="font-size:16px;font-weight:600">price on FanDuel</span>'}</div><div class="md">{_model_line(pr.get("p"), pr.get("fair"))}</div></div>
<div class="go">{fdbtn}<div class="row"><button type="button" class="sv" data-slip="{E(json.dumps({"w": int(pr["week"]), "n": pr["title"], "k": keys, "o": pr.get("fd"), "fd": pr.get("link")}))}"{"" if keys and len(keys) == n else " hidden"}>Save slip</button><a href="{E(build)}">Load into the builder</a><a href="{E(share)}" target="_blank" rel="noopener">Share on X</a></div></div>
<p class="svnote" id="svnote" hidden></p>
{cap}
<div class="lk">Short link <code>{E(url.replace("https://", ""))}</code><button type="button" data-copy="{E(url)}">Copy</button></div>
<p class="fn">Graded on the <a href="/receipts/" style="color:var(--ink)">receipts</a> Tuesday like everything else. 21+ · information, not advice · 1-800-GAMBLER.</p>
</div>{LAND_JS}{SAVE_JS}'''

INDEX_JS = r"""<script>(function(){
  var root = document.querySelector('.bl'); if(!root) return;
  var code = (new URLSearchParams(location.search).get('s') || location.hash.replace(/^#/, '') || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  if(!code) return;
  var box = document.getElementById('blDyn'), list = document.getElementById('blStatic'); if(list) list.hidden = true; box.hidden = false;
  box.innerHTML = '<div class="none">Loading the slip…</div>';
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function am(o){ if(o == null) return ''; o = Math.round(o); return o > 0 ? '+' + o : String(o); }
  function lnTxt(l){ if(l.gl) return l.ms || l.m; if(l.m === 'Anytime TD') return 'anytime TD'; if(l.m === 'First TD') return 'first TD'; if(/^\d\+ TD$/.test(l.m)) return l.m; var n = l.ln == null ? '' : (l.u ? 'under ' + l.ln : Math.round(l.ln) + '+'); return ((l.ms || l.m || '').replace(/^Under /i, '').toLowerCase() + ' ' + n).trim(); }
  var BN = {dk: 'DraftKings', hr: 'Hard Rock'};
  function bookUrl(ids, b){ if(!ids.length) return null; if(b === 'dk') return 'https://sportsbook.draftkings.com/?outcomes=' + ids.map(encodeURIComponent).join('+'); return ids.length > 1 ? 'hardrock://betslip/' + ids.join(',') : 'https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/' + ids[0]; }
  function bookBtns(legs, map){   // stored ids first (links made from 10/30 on), else this week's ids from /b/books.json
    var out = '', notes = [];
    ['dk', 'hr'].forEach(function(b){ var ids = [], subs = [];
      var ok = legs.every(function(l){ var x = l[b], q = !x && map && map[l.k] && map[l.k][b] ? {s: map[l.k][b][0], ln: map[l.k][b][2]} : x; if(!q || !q.s) return false; ids.push(q.s); if(q.ln != null) subs.push((l.pl || '') + ' ' + q.ln + (l.gl ? '' : '+')); return true; });
      if(ok && ids.length){ out += '<a class="' + b + '" href="' + esc(bookUrl(ids, b)) + '" target="_blank" rel="noopener">Bet it on ' + BN[b] + '</a>'; if(subs.length) notes.push(BN[b] + ' uses its nearest line: ' + subs.join('; ') + '.'); } });
    if(!out) return '';
    return '<div class="bks">' + out + '</div><p class="bknote">' + esc(notes.join(' ') + (notes.length ? ' ' : '') + 'Prices shown are FanDuel\'s; the other books price the parlay themselves.') + '</p>';
  }
  var BMAP = null;
  function withMap(r, cb){ var legs = r.legs || [];
    if(legs.every(function(l){ return l.dk && l.hr; })) return cb(null);
    fetch('/b/books.json', {cache: 'no-cache'}).then(function(x){ return x.json(); }).then(function(j){ cb(j && String(j.week) === String(r.week) ? j.m : null); }, function(){ cb(null); }); }
  function render(r, map){
    var legs = r.legs || [], W = r.week || '';
    var dec = legs.reduce(function(a, l){ return a * (l.o > 0 ? 1 + l.o / 100 : 1 + 100 / -l.o); }, 1);
    var odds = r.fd_odds != null ? r.fd_odds : (legs.every(function(l){ return l.o != null; }) ? Math.round(dec >= 2 ? (dec - 1) * 100 : -100 / (dec - 1)) : null);
    var p = legs.every(function(l){ return l.p != null; }) ? legs.reduce(function(a, l){ return a * l.p; }, 1) : null;
    var keys = legs.map(function(l){ return l.k; }).filter(Boolean); var build = keys.length === legs.length ? '/build/?' + keys.map(function(k){ return 'add=' + encodeURIComponent(k); }).join('&') : '/build/';
    var last = Math.max.apply(null, legs.map(function(l){ return +l.ko || 0; }));
    var url = 'https://betsweep.co/b/?s=' + code;
    var share = 'https://twitter.com/intent/tweet?text=' + encodeURIComponent((r.title ? r.title + ' · ' : '') + legs.length + '-leg parlay' + (odds != null ? ' · FanDuel ' + am(odds) : '') + '\n' + url);
    var fd = r.link ? '<a class="fd" href="' + esc(r.link) + '" target="_blank" rel="noopener">Bet it on FanDuel' + (odds != null ? ' · ' + am(odds) : '') + '</a>' : '';
    box.innerHTML = '<div class="hd"><span class="tag">Betslip</span><span class="wk">Week ' + esc(W) + '</span>' + (last && Date.now() > last ? '<span class="st">Started</span>' : '<span class="st live">Pregame</span>') + '</div>'
      + '<h1>' + esc(r.title || (legs.length + '-leg parlay')) + '</h1><div class="meta">' + legs.length + ' legs · priced by the BetSweep model · snapshot when the link was made, prices move</div>'
      + '<ul class="legs">' + legs.map(function(l){ var sub = [lnTxt(l), l.opp && !/\//.test(l.tm || '') ? 'vs ' + l.opp : ''].filter(Boolean).join(' · ');
          return '<li><b>' + esc(l.pl) + '</b><span class="o">' + am(l.o) + '</span><small>' + esc(sub) + '</small>' + (l.p != null ? '<span class="mp">model ' + Math.round(l.p * 100) + '%</span>' : '') + '</li>'; }).join('') + '</ul>'
      + '<div class="pf"><div class="big"><small>FanDuel</small>' + (odds != null ? am(odds) : '<span style="font-size:16px;font-weight:600">price on FanDuel</span>') + '</div><div class="md">' + (p == null ? 'Model price not available for every leg' : p < 0.03 ? '<b>Longshot</b> · model ' + (p < 0.01 ? 'under 1' : Math.round(p * 100)) + '% to hit' : '<b>Model ' + (p * 100).toFixed(1) + '%</b> to hit (legs multiplied)') + '</div></div>'
      + '<div class="go">' + fd + (last && Date.now() > last ? '' : bookBtns(legs, map)) + '<div class="row">' + (keys.length === legs.length ? '<button type="button" class="sv" data-slip="' + esc(JSON.stringify({w: +W, n: r.title || (legs.length + '-leg parlay'), k: keys, o: odds, fd: r.link || null})) + '">Save slip</button>' : '') + '<a href="' + esc(build) + '">Load into the builder</a><a href="' + share + '" target="_blank" rel="noopener">Share on X</a></div></div>'
      + '<p class="svnote" id="svnote" hidden></p><div class="lk">Short link <code>betsweep.co/b/?s=' + esc(code) + '</code><button type="button" data-copy="' + esc(url) + '">Copy</button></div>'
      + '<p class="fn">Made with the <a href="/build/" style="color:var(--ink)">Parlay Builder</a>. 21+ · information, not advice · 1-800-GAMBLER.</p>';
    root.dataset.code = code; root.dataset.lastKo = last || ''; if(window.bsPaintSave) window.bsPaintSave();
    box.querySelectorAll('[data-copy]').forEach(function(b){ b.addEventListener('click', function(){ var t = b.dataset.copy; function done(){ b.textContent = 'Copied'; setTimeout(function(){ b.textContent = 'Copy'; }, 1400); }
      if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, function(){ prompt('Copy this link', t); }); else prompt('Copy this link', t); }); });
    try { var CFG = window.__BS_ACCOUNT || {}; if(window.supabase && CFG.url) window.supabase.createClient(CFG.url, CFG.key).rpc('link_hit', {c: code}).then(function(){}, function(){}); } catch(e){}
  }
  var tries = 0; (function tick(){ var CFG = window.__BS_ACCOUNT || {};
    if(window.supabase && CFG.url){
      var sb = window.supabase.createClient(CFG.url, CFG.key);
      sb.from('short_links').select('code,week,title,legs,fd_odds,link').eq('code', code).maybeSingle().then(function(r){
        if(r.error){ box.innerHTML = '<div class="none">' + (/relation|does not exist/i.test(r.error.message) ? 'Short links are still being set up - try again soon.' : esc(r.error.message)) + '</div>'; return; }
        if(!r.data){ box.innerHTML = '<div class="none">No slip at this link. <a href="/build/" style="color:var(--ink)">Build one →</a></div>'; return; }
        withMap(r.data, function(m){ render(r.data, m); });
      }); return; }
    if(++tries < 60) setTimeout(tick, 100); else box.innerHTML = '<div class="none">Could not load the slip - check your connection and reload.</div>'; })();
})();</script>"""

def index_page(promos, week):
    """/b/ - with ?s=<code> it renders a builder slip from Supabase; without, this week's promoted bets"""
    live = [p for p in promos if p.get("status", "LIVE") == "LIVE" and not (p.get("checks") or {}).get("block")]
    items = "".join(f'<a href="/b/{promo_code(p)}"><code>betsweep.co/b/{promo_code(p)}</code><b>{E(p["title"])}</b><small>Week {p["week"]} · {len(p["legs"])} legs · FanDuel {E(odds_str(p["fd"])) if p.get("fd") else "—"}</small></a>' for p in live)
    static = f'<div class="hd"><span class="tag">Bet links</span><span class="wk">Week {week}</span></div><h1>This week\'s bets</h1><div class="meta">Every bet BetSweep posts has a short link - the legs, the model\'s number and one tap to FanDuel.</div>' \
             + (f'<div class="list">{items}</div>' if items else '<div class="none">Nothing posted for this week yet.</div>') \
             + '<p class="fn">Make your own from the <a href="/build/" style="color:var(--ink)">Parlay Builder</a>: build a slip, tap <b>Short link</b>, paste it anywhere.</p>'
    return f'<div class="bl" data-code="" data-week="{week}"><div id="blStatic">{static}</div><div id="blDyn" hidden></div></div>{INDEX_JS}{SAVE_JS}'

# ---- Parlay Builder: "Short link" in the slip panel ----
BTN_HTML = '<button type="button" class="pri" id="shortl" title="A short betsweep.co link for this slip - paste it on X or an Instagram story">Short link</button>'
BTN_JS = r"""<script>(function(){
  var btn = document.getElementById('shortl'); if(!btn) return;
  function flags(t){ var f = document.getElementById('flags') || document.getElementById('bslipFlags'); if(f){ f.innerHTML = t; } }
  function code(){ var a = 'abcdefghjkmnpqrstuvwxyz23456789', s = ''; var r = new Uint32Array(6); (window.crypto || {}).getRandomValues ? crypto.getRandomValues(r) : r.forEach(function(_, i){ r[i] = Math.floor(Math.random() * 1e9); }); for(var i = 0; i < 6; i++) s += a[r[i] % a.length]; return s; }
  function bk(l, b){ var x = l.bks && l.bks[b], a = l.ba && l.ba[b]; if(x && x.s) return {s: x.s, o: x.o}; if(a && a.s) return {s: a.s, o: a.o, ln: a.ln}; return null; }   // DraftKings / Hard Rock ids (owner 10/30)
  btn.addEventListener('click', function(){
    var ls = window.bsSlipLegs ? window.bsSlipLegs() : []; if(!ls.length){ flags('⚠ Add some legs first.'); return; }
    var CFG = window.__BS_ACCOUNT || {}; if(!(window.supabase && CFG.url)){ flags('⚠ Short links are not available right now.'); return; }
    var sb = (window.bsAccount && window.bsAccount.client) || window.supabase.createClient(CFG.url, CFG.key);
    var legs = ls.map(function(l){ return {k: l.pl + '|' + l.m + '|' + Math.round(l.ln || 1), pl: l.pl, m: l.m, ms: l.ms, ln: l.ln, u: l.u ? 1 : 0, o: l.o, p: l.p, g: l.g, tm: l.tm, opp: l.opp,
      fd: l.fd && l.fd.m && l.fd.s ? {m: l.fd.m, s: l.fd.s} : null, dk: bk(l, 'dk'), hr: bk(l, 'hr'), gl: l.gl ? {k: l.gl.k, side: l.gl.side} : null, ko: window.bsGameKo ? window.bsGameKo(l.g) : null}; });
    var fdl = legs.every(function(l){ return l.fd; }) ? 'https://sportsbook.fanduel.com/addToBetslip?' + legs.map(function(l, i){ return 'marketId[' + i + ']=' + l.fd.m + '&selectionId[' + i + ']=' + l.fd.s; }).join('&') : null;
    var dec = ls.reduce(function(a, l){ return a * (l.o > 0 ? 1 + l.o / 100 : 1 + 100 / -l.o); }, 1);
    var row = {code: code(), week: ((window.__BS || {}).week || (window.__BSL || {}).week || +window.__BSW || null), title: null, legs: legs, fd_odds: Math.round(dec >= 2 ? (dec - 1) * 100 : -100 / (dec - 1)), link: fdl};
    btn.disabled = true; var o = btn.textContent; btn.textContent = 'Making link…';
    sb.from('short_links').insert(row).then(function(r){
      btn.disabled = false; btn.textContent = o;
      if(r.error){ flags('⚠ ' + (/relation|does not exist/i.test(r.error.message) ? 'Short links are still being set up - try again soon.' : r.error.message)); return; }
      var url = 'https://betsweep.co/b/?s=' + row.code;
      function show(copied){ flags((copied ? 'Copied: ' : 'Your link: ') + '<a href="' + url + '" target="_blank" rel="noopener" style="color:var(--ink);font-weight:700">' + url.replace('https://', '') + '</a>' + (fdl ? '' : ' (no FanDuel button - a leg has no FanDuel id)')); }
      if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function(){ show(true); }, function(){ show(false); }); else show(false);
    });
  });
})();</script>"""

if __name__ == "__main__":
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shortlinks.sql"), "w").write(SQL); print("wrote shortlinks.sql")
