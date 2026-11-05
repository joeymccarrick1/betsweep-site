#!/usr/bin/env python3
"""build_guide.py - /guide/ "How to read BetSweep" (owner 10/30): one page that explains every symbol on the site for someone landing
from a social post. Static text plus small live examples drawn with the site's own colour scale; no inputs.
Writes out/guide.html; prints "wrote out/guide.html".
Keep it in step with the pages: when a page's colours, grades or tiers change, change the matching paragraph here (RUNBOOK says so).
"""
import os, html
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
E = html.escape

def rank_color(r):
    t = (r - 1) / 31
    if t < 0.5: h = 140 - 95 * (t / 0.5); l = 0.30 + 0.08 * (t / 0.5)
    else: h = 45 - 45 * ((t - 0.5) / 0.5); l = 0.38 - 0.10 * ((t - 0.5) / 0.5)
    return f"hsl({h:.0f} 62% {l*100:.0f}%)"
def pill(a, o, b, d): return f'<span class="mup"><i style="background:{rank_color(o)}">{a} #{o}</i><b>vs</b><i style="background:{rank_color(d)}">{b} #{d}</i></span>'
scale = "".join(f'<i style="background:{rank_color(r)}" title="#{r}"></i>' for r in range(1, 33))

CSS = """
.gd{max-width:880px;margin:18px auto 40px;line-height:1.6}
.gd a{color:var(--ink)}
.gd h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:clamp(30px,5vw,42px);margin:0 0 6px;letter-spacing:-.01em}
.gd .lede{color:var(--mute);font-size:16px;margin:0 0 16px}
.gd nav.toc{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 18px}
.gd nav.toc a{font-size:12.5px;font-weight:600;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:5px 11px;background:var(--card)}
.gd nav.toc a:hover{border-color:var(--red)}
.gd section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin:0 0 14px;scroll-margin-top:80px}
.gd h2{font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:17px;margin:0 0 8px;color:var(--ink)}
.gd h2::before{content:"";display:inline-block;width:10px;height:10px;background:var(--red);margin-right:8px;transform:skewX(-12deg)}
.gd p{margin:6px 0} .gd ul{margin:6px 0;padding-left:20px} .gd li{margin:3px 0}
.gd .ex{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin:10px 0;padding:10px 12px;background:var(--chalk);border-radius:8px;font-size:13px}
.gd .scale{display:flex;height:12px;border-radius:3px;overflow:hidden;flex:1 1 260px;min-width:200px} .gd .scale i{flex:1}
.gd .ends{display:flex;justify-content:space-between;font-size:11.5px;color:var(--mute);flex-basis:100%}
.gd .mup{display:inline-flex;align-items:center;gap:3px;font-size:12px;font-weight:700} .gd .mup i{font-style:normal;color:#fff;padding:2px 7px;border-radius:3px} .gd .mup b{color:var(--mute);font-weight:600}
.gd .chip{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11.5px;font-weight:700;border:1px solid}
.gd .chip.good{color:var(--good);border-color:var(--good)} .gd .chip.bad{color:var(--bad);border-color:var(--bad)} .gd .chip.watch{color:var(--warn);border-color:var(--warn)}
.gd .cg{display:inline-block;font-weight:800;font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding:2px 8px;border-radius:3px;color:#0f141c}
.gd table{border-collapse:collapse;font-size:13.5px;margin:8px 0;width:100%} .gd td,.gd th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.gd th{font-family:var(--display);letter-spacing:.06em;text-transform:uppercase;font-size:12px;color:var(--mute)}
.gd .bk{display:inline-block;font-size:12px;font-weight:700;padding:3px 9px;border-radius:4px;color:#fff;background:#1493ff} .gd .bk.dk{background:#53d337;color:#0b1a07} .gd .bk.hr{background:#5b2d8e}
.gd .small{font-size:12.5px;color:var(--mute)}
"""

SECTIONS = [
("start", "Start here", f"""
<p>BetSweep projects every NFL skill player from usage, matchups, game script and injuries, then prices every FanDuel prop against that projection. The price is never an input to the projection - it is only what we compare against.</p>
<ul><li><b>Matchup Boards</b> - one card per game: projected score, how the game is likely to go, every player's projected stats colored by the matchup, and a model-priced same-game slip.</li>
<li><b>Parlay Builder</b> - every FanDuel prop on the slate with the model's chance; build a slip and send it to FanDuel, DraftKings or Hard Rock.</li>
<li><b>Players</b> - one page per player: his lines at all three books, how often he has cleared them, matchup, snap share and game log.</li>
<li><b>Receipts</b> - everything is frozen before kickoff and graded after. The misses stay up.</li></ul>"""),
("colors", "The color scale", f"""
<p>Every rank on the site uses one scale, from <b>green</b> (good for the over) to <b>red</b> (bad for the over). Ranks run 1-32.</p>
<div class="ex"><div class="scale">{scale}</div><div class="ends"><span>#1 - green: allows the most / produces the most</span><span>#32 - red: allows the least / produces the least</span></div></div>
<ul><li><b>Defense rank</b>: #1 = the defense that <i>allows</i> the most of that stat to the position (a soft matchup). From the sheet's matchup tab, season and last 3 weeks.</li>
<li><b>Offense rank</b>: #1 = the offense whose players at that position <i>produce</i> the most of that stat.</li>
<li>Roughly: <b>1-10</b> green, <b>11-21</b> gray / neutral, <b>22-32</b> red.</li></ul>"""),
("matchup", "Reading a matchup", f"""
<div class="ex">{pill("GB", 32, "CAR", 1)} <span>Green Bay's RBs rank #32 in rushing yards produced; Carolina's defense allows the #1 most to RBs.</span></div>
<p>The left side is <b>his offense</b>, the right side is the <b>defense he faces</b>, both for the stat in question. Green on both sides is the friendliest spot for an over; red on both, the toughest. A player can be in a soft matchup (green right side) on an offense that doesn't produce that stat (red left side) - the pill shows both so you can see that tension.</p>
<p>The Parlay Builder's player panel and each board's <b>Matchup by stat</b> section show every stat separately, season and last 3 weeks. The builder's <b>green matchups</b> filter keeps overs where both sides are top 10 (or the offense is middle of the pack and the defense is top 5). It is optional: in our backtest, hot players in green spots went over an average-based projection slightly <i>less</i> often, so it is a filter you choose, not a pick.</p>"""),
("numbers", "Model %, book %, edge", """
<table><tr><th>Number</th><th>What it means</th></tr>
<tr><td><b>Model %</b></td><td>The chance the leg hits as the site shows it: the model's raw number blended 50/50 with FanDuel's price. Blending keeps the number honest - raw model chances at the extremes graded too confident.</td></tr>
<tr><td><b>Book %</b></td><td>The chance FanDuel's price implies (including its margin). A -150 price is 60%.</td></tr>
<tr><td><b>Edge</b></td><td>Model % minus book %, in points. Positive means the model thinks the price is too long. Because of the blend, a +2.5 edge on the site is a +5 gap between the raw model and the book.</td></tr>
<tr><td><b>This season</b></td><td>On player pages: how many of his games this season cleared that exact line.</td></tr></table>
<p>Nothing is called a lock. A 60% leg loses 4 times in 10.</p>"""),
("flags", "Flags and chips", """
<div class="ex"><span class="chip good">Soft matchup</span><span class="chip bad">Trending down</span><span class="chip watch">Love returns</span></div>
<ul><li><span class="chip good">Green</span> chips help the over: a soft matchup, a growing role, a high game total.</li>
<li><span class="chip bad">Red</span> chips hurt it: falling usage, a tough matchup, a line he has rarely cleared.</li>
<li><span class="chip watch">Amber</span> chips are things to check: a teammate returning, a questionable tag, a role that grew only because someone else was hurt.</li></ul>
<p>Tap a chip row for the full sentence. On the betslip, the amber <b>!</b> next to a leg opens the same notes; legs with a risk flag are never used in our listed parlays.</p>"""),
("games", "Game cards: script and confidence", """
<p>The colored bar under each scoreboard splits the game into four likely endings (for example "close, low scoring" or "home team by 10+") with the chance of each. Tap a segment to see the plays that fit that ending.</p>
<p><span class="cg" style="background:var(--good)">High</span> <span class="cg" style="background:var(--warn)">Medium</span> <span class="cg" style="background:var(--red);color:#fff">Low</span> <b>Confidence</b> grades how much can go wrong with our read of the game: a big gap to the betting line, the line moving during the week, a quarterback change, a key player newly out. Low-confidence games open with the reasons showing.</p>
<p><b>Best parlay</b> on each card is the 2-4 leg FanDuel slip, priced between -110 and +500, that the model thinks is most likely to cash.</p>"""),
("tiers", "Model's Best, top plays, promoted bets", """
<ul><li><b>Model's Best</b> - three tiers tracked separately: <i>even</i> (prices near even money where the model is 8+ points off the price), <i>TD</i> (anytime TDs at +200 or shorter where the raw model beats the price) and <i>safer</i> (calibrated 65%+). Each is graded on the season page.</li>
<li><b>Promoted bets</b> on the home page are slips BetSweep posts. They are graded at the posted price on the receipts.</li></ul>"""),
("slip", "The betslip", """
<p>The <b>+</b> next to any leg adds it to one slip shared by every page. The slip shows the parlay's FanDuel price next to the model's chance and edge.</p>
<div class="ex"><span class="bk">FanDuel</span><span class="bk dk">DraftKings</span><span class="bk hr">Hard Rock</span><span class="small">opens that book with the legs on its betslip; ≈ means the book uses its nearest line</span></div>
<ul><li><b>Save slip</b> keeps it on <a href="/me/">My BetSweep</a>, graded after the games.</li><li><b>Post to BetSweep Social</b> shares it on the <a href="/social/">Social</a> feed; <b>Short link</b> copies a link anyone can open.</li>
<li>Signed in, your slips follow you to every device - and you can turn on alerts when a player on a saved slip is ruled out.</li></ul>"""),
("pages", "The other pages", """
<ul><li><a href="/live/">Live</a> - during games: the legs that have not happened yet against the live box score.</li>
<li><a href="/usage/">Usage trends</a> - whose snaps and targets are rising or falling, with injury context.</li>
<li><a href="/benefits/">Who benefits</a> - when a starter is out, where his work went in the games he missed.</li>
<li><a href="/team/">Fantasy</a>, <a href="/trade/">Trade</a>, <a href="/dfs/">DFS</a>, <a href="/firsttd/">First TD</a> - the same projections for fantasy lineups, trades, DFS and first-touchdown odds.</li>
<li><a href="/receipts/">Receipts</a> and <a href="/season/">Season</a> - the record, graded from the box scores.</li></ul>"""),
("rg", "Bet responsibly", """
<p>BetSweep is information and analysis, not betting advice; no outcome is guaranteed. 21+ (18+ where permitted). If gambling is a problem for you or someone you know, call <b>1-800-GAMBLER</b>. More on our <a href="/responsible-gambling/">responsible gambling page</a>.</p>"""),
]

def build():
    link, base = __import__("account")._base_css()
    toc = "".join(f'<a href="#{k}">{E(t)}</a>' for k, t, _ in SECTIONS)
    body = "".join(f'<section id="{k}"><h2>{E(t)}</h2>{h}</section>' for k, t, h in SECTIONS)
    page = (f'<title>How to read BetSweep</title>\n<meta name="description" content="What every color, rank, percentage and chip on BetSweep means: matchups, model % vs book %, edge, confidence, flags and the betslip.">\n'
            f'{link}\n<style>{base}{CSS}</style>\n<div class="gd"><h1>How to read BetSweep</h1><p class="lede">What every color, number and chip on the site means - in about three minutes.</p>'
            f'<nav class="toc" aria-label="sections">{toc}</nav>{body}</div>')
    open(os.path.join(OUT, "guide.html"), "w").write(page)
    print("wrote out/guide.html")

if __name__ == "__main__":
    build()
