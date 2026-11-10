#!/usr/bin/env python3
"""BetSweep legal pages -> out/legal-terms.html, out/legal-privacy.html, out/legal-responsible.html (build_site.py places them at
/terms/, /privacy/, /responsible-gambling/). Plain-English Terms of Use, Privacy Policy and Responsible Gambling + Affiliate Disclosure
for BetSweep LLC. Written for the site as it is today (static pages, optional Supabase accounts, no analytics); update when that changes -
the privacy text was rewritten in the 11/10 audit to cover everything the account features store (see the note above PRIVACY).
Owner-confirmed facts live in LEGAL below (entity, state, contact). v2026-10-19.
"""
import os, datetime, html
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
exec(open(os.path.join(HERE, "brand.py")).read())
E = html.escape
LEGAL = {"entity": "BetSweep LLC", "state": "Tennessee", "contact": "support@betsweep.co", "site": "betsweep.co", "effective": "October 27, 2026", "x": "@bet_sweep"}

CSS = """
.legal{max-width:860px;margin:0 auto;padding:6px 0 30px;font-size:15.5px;line-height:1.6}
.legal h2{font-family:var(--display);font-weight:700;font-size:22px;letter-spacing:.02em;margin:28px 0 8px}
.legal h3{font-family:var(--display);font-weight:700;font-size:17px;margin:18px 0 6px}
.legal p{margin:0 0 12px} .legal ul{margin:0 0 12px 20px;padding:0} .legal li{margin:4px 0}
.legal .eff{color:var(--mute);font-size:13px;margin-bottom:18px}
.legal .box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:14px 0}
.legal .box.red{border-color:color-mix(in srgb,var(--red) 55%,var(--line))}
.legal .help{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0}
.legal .help a{text-decoration:none;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:7px 11px;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.05em;text-transform:uppercase}
.legal a{color:var(--ink)}
.legal .toc{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px} .legal .toc a{font-size:13px;color:var(--mute)}
"""

def page(title, desc, body, slug):
    stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
    t = (open(os.path.join(HERE, "template.html")).read()
         .replace("<title>BetSweep Matchup Boards</title>", f"<title>BetSweep {title}</title>")
         .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", f"<h1>BetSweep · <b>{E(title)}</b></h1>")
         .replace("{{DESC}}", desc)
         .replace("{{NAV}}", '<a href="/terms/">Terms of Use</a><a href="/privacy/">Privacy</a><a href="/responsible-gambling/">Responsible gambling &amp; disclosures</a>')
         .replace("{{CARDS}}", f'<style>{CSS}</style><article class="legal">{body}</article>')
         .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", "").replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
    import re
    t = re.sub(r'<div class="key">.*?</div>\n', '', t, count=1, flags=re.S)
    open(os.path.join(OUT, f"legal-{slug}.html"), "w").write(t)

L = LEGAL
eff = f'<p class="eff">Effective {L["effective"]} · {L["entity"]} · <a href="mailto:{L["contact"]}">{L["contact"]}</a></p>'

TERMS = eff + f"""
<p>These are the terms for using {L["site"]} and the BetSweep posts, cards and tools that link back to it. Short version: this is information, not advice; you are responsible for your own bets and for following the law where you live; and we can be wrong.</p>
<h2>1. What BetSweep is</h2>
<p>{L["entity"]} ("BetSweep", "we") publishes NFL projections, matchups, parlay-building tools, fantasy tools and commentary. Everything on the site is generated from a statistical model and public data, then graded publicly after the games. It is informational and for entertainment. It is not betting, financial, legal or tax advice, and nothing here is a recommendation to place any wager.</p>
<h2>2. Who may use it</h2>
<p>You must be of legal age to view sports-betting content where you live (21+ in most U.S. states, 18+ in some). You are responsible for knowing whether sports betting is legal in your jurisdiction and for complying with the rules of any sportsbook you use. BetSweep does not accept wagers, hold funds, or place bets for anyone.</p>
<h2>3. No guarantees</h2>
<p>Projections are estimates. Probabilities on the site are the model's view, not promises. Past results, including the graded record on our Receipts pages, do not guarantee future results. We publish our misses alongside our hits precisely because the model is often wrong. You bet at your own risk, and you should never bet money you cannot afford to lose.</p>
<h2>4. Sportsbook links and prices</h2>
<p>Buttons such as "Add to FanDuel", "Send to FanDuel" and "Bet it on FanDuel" open a third-party sportsbook with selections pre-filled. The sportsbook, not BetSweep, controls what it offers and at what price. Prices on our pages are snapshots from the time the page was built and move constantly; always check the price on the sportsbook before you confirm. Some links are affiliate links: see our <a href="/responsible-gambling/">disclosures</a>.</p>
<h2>5. Tools that run in your browser</h2>
<p>The Parlay Builder, Live, Fantasy, Trade and DFS pages keep your slips, rosters, scenarios and settings in your own browser's storage. Unless you sign in, they are not sent to us, and clearing your browser data clears them. Signing in is optional; with an account the same items are stored with your account so they follow you between devices, as described in the Privacy Policy, and you may delete the account at any time. The Fantasy page can read a Sleeper account you name through Sleeper's public API; we do not store that data.</p>
<h2>5a. Posting on BetSweep Social</h2>
<p>Signed-in users can post betslips to the Social page under a handle they choose; others can see, upvote, tail and report them. A post shows your handle, optional title, the legs and the price you entered - never your email. Posts are your own picks, not BetSweep's, are not checked or endorsed by the model, and are not advice. Do not post anything unlawful, hateful, harassing, sexual, spammy or promotional, other people's personal information, or anything you do not have the right to share. You keep ownership of what you post and give {L["entity"]} a non-exclusive, royalty-free licence to display it on BetSweep and in shares of BetSweep pages. We may remove any post or handle and suspend posting at our discretion; a post reported by three accounts is hidden automatically until reviewed. Posts leave the feed once a leg loses or every game in them is over, and you can delete your own at any time.</p>
<h2>6. Our content</h2>
<p>BetSweep™ is a trademark of {L["entity"]} (U.S. trademark application Serial No. 50169404). The BetSweep name, logo, model outputs, page designs and written content belong to {L["entity"]}. You may share screenshots and links freely with credit. You may not scrape, resell or republish the projections or tools as your own, or use them to build a competing service, without written permission.</p>
<h2>7. Third-party data and marks</h2>
<p>BetSweep is not affiliated with, endorsed by or sponsored by FanDuel, DraftKings, any other sportsbook, Sleeper, Action Network / Playbook, or the National Football League or its teams. Team and player names are used for identification only. Statistics come from public sources such as nflverse and may contain errors.</p>
<h2>8. Liability</h2>
<p>To the fullest extent the law allows, {L["entity"]} and its owners are not liable for any loss, including betting losses, arising from use of the site, its content, its tools or its links. The site is provided "as is", without warranties of any kind, and may be unavailable or contain mistakes. Where liability cannot be excluded, it is limited to the amount you paid BetSweep for the content in question, which today is nothing.</p>
<h2>9. Changes</h2>
<p>We may change the site and these terms at any time; the effective date above tells you when they last changed. Continuing to use the site after a change means you accept it.</p>
<h2>10. Law and contact</h2>
<p>These terms are governed by the laws of {("the State of " + L["state"]) if L["state"] else "the U.S. state in which " + L["entity"] + " is organized"}, without regard to conflict-of-law rules. Questions, corrections and takedown requests: <a href="mailto:{L["contact"]}">{L["contact"]}</a>.</p>
"""

# audit 11/10: the policy still said "no accounts", "we hold no account data" and "pages load web fonts from Google Fonts ... cdnjs", and did not
# mention alerts, the email brief, pick'em, Ask the model, short links, sweat rooms or the jsDelivr / ESPN requests. Rewritten to match what
# the site stores today (tables: user_state, push_subs, email_prefs, fantasy_rosters, beat_picks, ask_log, short_links + link_hits, feed_*,
# sweat_*). The owner should read it and have counsel look at it; when a feature starts storing something new, add it HERE first.
PRIVACY_UPDATED = "November 10, 2026"
PRIVACY = eff.replace("</p>", f" · Privacy Policy last updated {PRIVACY_UPDATED}</p>") + f"""
<p>Short version: {L["site"]} works without an account, runs no ad trackers and no analytics scripts, and keeps your slips and settings in your browser. If you choose to sign in (optional), we store your email address and the things you build, post or switch on, so they follow you between devices and the features you asked for can work - nothing else.</p>
<h2>What we collect</h2>
<ul>
<li><b>Unless you sign in, post or make a short link, nothing you type on the site is sent to us.</b> Parlay slips, Fantasy rosters, DFS lineups, your bankroll plan and your settings are stored in your browser's local storage on your device and never leave it except when you choose to open a sportsbook link or share something.</li>
<li><b>Sleeper usernames.</b> If you enter a Sleeper username on the Fantasy page, your browser asks Sleeper's public API for that account's leagues and rosters directly. Unless you are signed in, BetSweep's servers are not involved and we do not see or store it.</li>
<li><b>Roster screenshots.</b> If you import a roster from a screenshot, the picture is read in your browser and is not uploaded to us. The reader is open-source software that your browser loads from the jsDelivr network when you use it.</li>
<li><b>Optional accounts.</b> If you sign in, we store your email address, the time you accepted these terms and confirmed you are 21 or older, and the items you build on the site (saved betslips, the builder slip, hand-built fantasy teams, DFS lineups, trade scenarios, your bankroll plan, the Sleeper username and league you entered, and your fantasy roster so alerts can cover your players). They are kept with our authentication and database provider, Supabase (servers in the United States), tied to your account and readable only by you and by us for support. Signing out leaves a copy in your browser; to delete the account and everything stored with it, email <a href="mailto:{L["contact"]}">{L["contact"]}</a> from the signed-in address and it is removed within 30 days. We do not sell or share it.</li>
<li><b>Alerts.</b> If you turn on notifications, we store the push address and keys your browser gives us (your browser maker's push service - Apple, Google or Mozilla - delivers the message), a short description of the browser, and your alert settings. Turning alerts off removes them.</li>
<li><b>The game-day email.</b> If you switch on the email brief on My BetSweep, we store that choice with your email address and send the brief through Resend, our email provider. You can switch it off there at any time. We send no other marketing email.</li>
<li><b>Beat the model.</b> Your five picks each week, the display name you chose and how the picks graded are stored with your account. The leaderboard shows that name, your graded picks and your record - never your email.</li>
<li><b>Ask the model.</b> A question you type there (signed-in users) is sent to our server and on to Anthropic, the AI provider that writes the answer, together with the model's numbers for the players you named - not your name, your email or your slips. We keep your questions and the answers with your account to enforce the daily limit and to improve the feature.</li>
<li><b>Short links.</b> When you make a short link for a slip, its legs and price are stored under the link's code, and anyone who has the link can see them; if you are signed in, the link is recorded as yours. We count how many times each link is opened, not who opened it.</li>
<li><b>Social posts.</b> If you post a slip to the Social page, the handle, title, legs and price you entered, the time, and the upvotes and reports on it are stored with Supabase and shown publicly (your email is not). Upvotes and reports record which account made them so each account counts once. Deleting a post removes it; deleting your account removes your posts, votes and reports.</li>
<li><b>Sweat rooms.</b> On the Live page, tapping "I'm on it" or a reaction stores that leg, the reaction and the time with your account. Other people see the totals and the reactions - never who.</li>
<li><b>Email.</b> If you write to <a href="mailto:{L["contact"]}">{L["contact"]}</a> we keep the message so we can answer it and fix what you reported.</li>
<li><b>Server logs.</b> The site is hosted on GitHub Pages, which, like any web host, may log IP addresses and request details for security and operations under <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>. We do not receive or use those logs.</li>
</ul>
<h2>Cookies and tracking</h2>
<p>We set no advertising or analytics cookies and run no trackers. If you sign in, your browser keeps a sign-in token in its own storage so you stay signed in. Fonts and page scripts are served from {L["site"]} itself, with two exceptions: the sign-in library (and the screenshot reader, when you use it) loads from the jsDelivr network, and live scores, box scores and team logos come straight from ESPN's public data. Those providers see the ordinary request data a browser sends when it fetches a file. When you tap a sportsbook button you leave our site; the sportsbook's own privacy policy applies from there, and if the link is an affiliate link the sportsbook or its network may record that you arrived from BetSweep (see <a href="/responsible-gambling/">disclosures</a>).</p>
<h2>The installable app</h2>
<p>Adding BetSweep to your home screen installs a service worker that caches pages on your device for offline use. It stores nothing about you and can be removed by deleting the app or clearing site data.</p>
<h2>Children</h2>
<p>The site is for adults of legal betting age. We do not knowingly collect information from anyone under 18, and the site is not directed at them.</p>
<h2>Your choices</h2>
<p>Clear your browser's site data to remove everything BetSweep stored on your device. If you have an account, you can delete your posts and switch off alerts and the email brief on the site, and you can email us from the signed-in address to get a copy of what is stored with the account or to have the account and everything stored with it deleted within 30 days. Email us to have any message you sent deleted.</p>
<h2>Changes and contact</h2>
<p>When what we collect changes - a new feature that stores something, payments, analytics or an email list - this page is updated first and the date at the top changes. Questions: <a href="mailto:{L["contact"]}">{L["contact"]}</a>. {L["entity"]}{(", " + L["state"]) if L["state"] else ""}.</p>
"""

RESP = eff + f"""
<div class="box red"><b>If gambling is a problem for you or someone you know, help is free and confidential.</b>
<div class="help"><a href="tel:18004262537">Call 1-800-GAMBLER</a><a href="sms:800426" rel="noopener">Text 800GAM</a><a href="https://www.ncpgambling.org/help-treatment/" rel="noopener">ncpgambling.org</a><a href="https://www.gamblersanonymous.org" rel="noopener">Gamblers Anonymous</a><a href="tel:18008899789">Tennessee REDLINE 800-889-9789</a></div>
<p style="margin:10px 0 0;font-size:13.5px;color:var(--mute)">Most states also offer self-exclusion programs and deposit limits through the sportsbook apps themselves. Use them.</p></div>
<h2>How to use BetSweep responsibly</h2>
<ul>
<li>Treat every number here as an estimate. The model is graded in public every Tuesday because it misses often; a 70% leg loses three times in ten.</li>
<li>Bet only what you can afford to lose, with money that is not needed for anything else. Parlays and "moonshot" slips are entertainment with long odds, and we say so on them.</li>
<li>Never chase losses, bet while upset or impaired, or bet to pay for something.</li>
<li>Know your local law. Sports betting is legal in many U.S. states and not in others; age limits are 21+ in most and 18+ in a few. Our content is informational wherever you are, and it is on you to follow the rules where you live.</li>
<li>BetSweep does not take bets, hold money, or place bets for anyone, and nobody from BetSweep will ever ask you for money or account details. Our only email is <a href="mailto:{L["contact"]}">{L["contact"]}</a>.</li>
</ul>
<h2>Affiliate disclosure</h2>
<div class="box"><p><b>BetSweep may earn a commission when you open an account or place bets through links on this site or in our posts.</b> That includes "Add to FanDuel" / "Send to FanDuel" buttons, promoted-bet links, links generated by third-party tools such as Playbook, and any other sportsbook links we publish. Commissions do not change which legs the model picks, the prices we show, or how we grade results: every projection is frozen before kickoff and graded after, and that record is public on the Receipts pages whether or not a link paid us. We show FanDuel prices because that is the book our model prices against, not because of how it pays.</p>
<p>This disclosure is here because the Federal Trade Commission requires it, and because you should know. If a specific link is a paid affiliate link we mark it as such where the page allows.</p></div>
<h2>Not affiliated</h2>
<p>{L["entity"]} is independent. It is not affiliated with, endorsed by or sponsored by FanDuel, DraftKings, BetMGM, Caesars, any other sportsbook, Sleeper, Action Network or Playbook, nflverse, or the National Football League or any of its teams. Names and marks belong to their owners and are used only to identify the games, players and books being discussed.</p>
<h2>Data and corrections</h2>
<p>Projections, lines and results come from public data and third-party feeds and can be wrong or late. If a leg was graded wrong, a line is stale or a player is listed on the wrong team, email <a href="mailto:{L["contact"]}">{L["contact"]}</a> and we will check it against the frozen snapshot and fix the record.</p>
<p>See also the <a href="/terms/">Terms of Use</a> and <a href="/privacy/">Privacy Policy</a>.</p>
"""

page("Terms of Use", "The plain-English terms for using betsweep.co: information only, not betting advice; you are responsible for your own bets and for the law where you live.", TERMS, "terms")
page("Privacy Policy", "What betsweep.co collects: nothing unless you sign in, post or make a link; no ad or analytics trackers; slips and settings stay in your browser. An optional account stores what you build and switch on.", PRIVACY, "privacy")
page("Responsible Gambling", "Help lines, how to use BetSweep responsibly, the affiliate disclosure, and who BetSweep is and is not affiliated with.", RESP, "responsible")
print("wrote out/legal-terms.html, out/legal-privacy.html, out/legal-responsible.html")
