"""landing_merge.py - the merged home page (owner 11/5: "We can probably just merge Today and the Home Screen together").

merge(today_html, parts) takes build_today.py's page (already given LANDING_CSS + HOME_CSS + LIVE_CSS by build_site.py) and the landing
page's pieces (home.py sections + JS, the tiles, the posts gallery) and returns one page body:

  Today's head + looks + today's games                     (what matters right now)
  home.py's week sections: promos, Model's Best, plays...  (the week: promos first so posted bets sit near the top)
  Today's You / Ask / News / Trade desk / rest of the week / track record
  Everything on BetSweep tiles, latest posts, how it works
  scripts: Today's, then home.py's

home.py's own Track record section is dropped (Today already has one with the same ids).
"""
import re

HOW = ('<section class="sec"><h2 class="t">How it works</h2><div class="how">'
       '<div><h3>Model first</h3><p>Projections come from usage, matchups, game script and injuries - the price is only used to find where FanDuel is off. Odds are never the input.</p></div>'
       '<div><h3>Edge, not hype</h3><p>Every leg shows the model\'s hit rate next to what the price requires. The difference is the edge; +2 is value, +5 is strong. Nothing is called a lock.</p></div>'
       '<div><h3>Frozen, then graded</h3><p>Projections and legs are snapshotted before kickoff and graded after. The receipts page is the scoreboard - including the misses.</p></div>'
       '<div><h3>Built to bet from</h3><p>Fade lines, set a target payout, check a player\'s last five and the defense\'s, then send the slip to FanDuel in one tap.</p></div>'
       '</div></section>')

def _drop_section(h, sid):
    """remove <section ... id="sid"> ... </section> (sections in home.py do not nest)"""
    m = re.search(r'<section[^>]*\bid="%s"[^>]*>' % re.escape(sid), h)
    if not m: return h
    end = h.find("</section>", m.end())
    return h[:m.start()] + h[end + len("</section>"):] if end > 0 else h

def merge(today, parts):
    home_html = _drop_section(parts["home_html"], "record")
    # 1. week sections go after today's games, before "You today"
    anchor = re.search(r'<section class="sec" id="tdyou"', today)
    if not anchor: raise ValueError("Today page has no #tdyou section")
    body = today[:anchor.start()] + home_html + "\n" + today[anchor.start():]
    # 2. tiles / posts / how it works after the last section, before the first script that follows the track record
    rec = body.find('id="record"')
    sc = body.find("<script>", rec if rec > 0 else 0)
    if sc < 0: sc = len(body)
    extra = ('<section class="sec"><h2 class="t">Everything on BetSweep</h2><div class="tiles">' + parts["tiles"] + '</div></section>\n'
             + (('<section class="sec"><h2 class="t">Latest from @bet_sweep</h2><div class="feed"><div class="wrap">' + parts["gal"] + '</div></div></section>\n') if parts.get("gal") else "")
             + HOW + '\n<p style="max-width:1360px;margin:10px auto 40px;padding:0 16px;color:var(--mute);font-size:12px;line-height:1.5">BetSweep\u2122 · Picks. Data. Edge. Sweep. Information and analysis only, not betting advice; no outcome is guaranteed. 21+. If you or someone you know has a gambling problem, call 1-800-GAMBLER.</p>\n')
    body = body[:sc] + extra + body[sc:]
    # 3. home.py's script last (its record bar / slate code looks elements up by id and skips what is missing)
    body = body.replace("<title>Today · BetSweep</title>", "<title>BetSweep</title>", 1)
    return body + "\n" + parts["home_js"]
