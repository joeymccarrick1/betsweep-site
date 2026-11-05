"""'Other books' panel for the slip (builder + boards).

FanDuel stays the reference everywhere (prices, edges, grading, the one-tap betslip link). This adds a way to take the same slip
to another sportsbook: the slip text is copied to the clipboard and the book opens in a new tab, where the user adds the legs
by hand. No other book's odds or IDs are pulled, so nothing else on the site changes. The links are league / lobby pages
that work in every state (the books redirect to the right state site or open their app).
"""
BOOKS = [
    ("DraftKings", "https://sportsbook.draftkings.com/leagues/football/nfl"),
    ("BetMGM", "https://sports.betmgm.com/en/sports/football-11/betting/usa-9/nfl-35"),
    ("Caesars", "https://sportsbook.caesars.com/us/"),
    ("Hard Rock Bet", "https://app.hardrock.bet/"),
    ("ESPN BET", "https://espnbet.com/sport/football/organization/united-states/competition/nfl"),
    ("Fanatics", "https://sportsbook.fanatics.com/"),
    ("bet365", "https://www.bet365.com/"),
]

BOOKS_CSS = r"""
.books{margin:0 14px 10px;border:1px solid var(--line);border-radius:8px;background:var(--chalk);padding:10px 12px}
.books[hidden]{display:none}
.books p{margin:0 0 8px;font-size:12px;color:var(--mute);line-height:1.45}
.books .bkl{display:flex;flex-direction:row;flex-wrap:wrap;gap:6px}
.books .bkl a{display:inline-block;width:auto;font:inherit;font-size:12px;font-weight:700;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:3px;padding:6px 10px;text-decoration:none;cursor:pointer}
.books .bkl a:hover{border-color:var(--red)}
.books .ok{margin:8px 0 0;font-size:12px;color:var(--good)} .books .ok:empty{display:none}
.acts button.obk{border-style:dashed}
"""

def panel_html(pid="books"):
    links = "".join(f'<a href="{u}" target="_blank" rel="noopener" data-book="{n}">{n}</a>' for n, u in BOOKS)
    return (f'<div class="books" id="{pid}" hidden><p>FanDuel fills your betslip in one tap. For another book, tap it below: your slip is copied to the clipboard and the book opens - add the legs there by hand '
            f'(their line and price may differ from the FanDuel price shown here, so the edge there is not the edge shown).</p><div class="bkl">{links}</div><p class="ok"></p></div>')

# attach(button, panel, getText): toggles the panel; each book link copies the slip text (getText()) then opens the book.
BOOKS_JS = r"""
window.BSBooks = { attach: function(btn, panel, getText){
  if(!btn || !panel) return;
  btn.addEventListener('click', function(){ panel.hidden = !panel.hidden; btn.setAttribute('aria-expanded', String(!panel.hidden)); });
  panel.querySelectorAll(".bkl a").forEach(function(a){ a.addEventListener('click', function(){
    var txt = getText ? getText() : ''; var ok = panel.querySelector('.ok');
    var show = function(good){ ok.textContent = good ? 'Slip copied - paste or read it off while you add the legs at ' + a.dataset.book + '.' : 'Could not copy automatically - use Copy slip, then add the legs at ' + a.dataset.book + '.'; setTimeout(function(){ ok.textContent = ''; }, 6000); };
    if(txt && navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(function(){ show(true); }, function(){ show(false); }); else show(false);
  }); });
} };
"""
