"""landing_merge.py - the home page (owner 11/5: "We can probably just merge Today and the Home Screen together"; owner 11/10 9:39 PM:
"Let's compact the home page a little bit. There's just a lot going on. Maybe some things can move to different or new pages. Slate
probably doesn't need to be on the home page. The first section with today's game looks really good though. Just make it better").

merge(today_html, parts) takes build_today.py's page (already given LANDING_CSS + HOME_CSS + LIVE_CSS by build_site.py) and the pieces
home.py and build_site.py made, and returns one page body. Since 11/10 evening the page is a short one:

  Today's head, the Daily Sweep, today's game cards            (build_today.py)
  posted promos, Model's Best as three cards, the lead parlay   (home.py BLOCKS: promos / best_teaser / parlay_lead)
  You today, three news notes, Ask the model, Track record     (build_today.py)
  Where to next (eight doors), latest posts, the footer         (build_site.py)

What left the page has its own address: the whole Model's Best list, top plays, next man up, the radar and every game's parlay are
/best/; the week's games are /slate/; every news note is /news/; the trade desk is /targets/. Until 11/10 the page ran about 15,700px
on a phone (18 screens) and carried home.py's script twice - the second copy undid every "+ Slip" tap the first one made.
"""
import re

def _drop_section(h, sid):
    """remove <section ... id="sid"> ... </section> (sections in home.py do not nest)"""
    m = re.search(r'<section[^>]*\bid="%s"[^>]*>' % re.escape(sid), h)
    if not m: return h
    end = h.find("</section>", m.end())
    return h[:m.start()] + h[end + len("</section>"):] if end > 0 else h

FOOT = ('<p class="hfoot">BetSweep™ · Picks. Data. Edge. Sweep. Information and analysis only, not betting advice; no outcome is guaranteed. 21+. '
        'If you or someone you know has a gambling problem, call 1-800-GAMBLER. <a href="/how/">How BetSweep picks</a> · <a href="/guide/">How to read it</a> · '
        '<a href="/terms/">Terms</a> · <a href="/privacy/">Privacy</a> · <a href="/responsible-gambling/">Responsible gambling</a></p>\n')

def merge(today, parts):
    B = parts.get("blocks") or {}
    week = "\n".join(x for x in (B.get("promos", ""), B.get("best_teaser", ""), B.get("parlay_lead", "")) if x)
    # 1. the week's short blocks go after today's games, before "You today"
    anchor = re.search(r'<section class="sec" id="tdyou"', today)
    if not anchor: raise ValueError("Today page has no #tdyou section")
    body = today[:anchor.start()] + week + "\n" + today[anchor.start():]
    # 2. the doors, the posts and the footer after the track record, before the first script that follows it
    rec = body.find('id="record"')
    sc = body.find("<script>", rec if rec > 0 else 0)
    if sc < 0: sc = len(body)
    extra = ((parts.get("doors") or "")
             + (('<section class="sec" id="posts"><h2 class="t">Latest from @bet_sweep</h2><div class="feed"><div class="wrap">' + parts["gal"] + '</div></div></section>\n') if parts.get("gal") else "")
             + FOOT)
    body = body[:sc] + extra + body[sc:]
    body = body.replace("<title>Today · BetSweep</title>", "<title>BetSweep</title>", 1)
    # build_today.py's page already carries home.py's two scripts (kickoff state + the "+ Slip" bar) - once is the right number
    return body
