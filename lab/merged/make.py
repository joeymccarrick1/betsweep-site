#!/usr/bin/env python3
"""make.py - stitches lab/merged/index.html (the 'Game Desk' concept: Matchup Boards + Parlay Builder on one page) from the live
Parlay Builder page's shell (same <head>, site nav, masthead, theme toggle, bottom tabs) plus desk.html (this folder: the page body, CSS and JS).
Run from the repo root after a rebuild if the shell changes:  python3 lab/merged/make.py
Concept only - not linked from the menu, noindex. Owner decides whether it replaces the two pages."""
import re, os, sys
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = open(os.path.join(root, "build", "index.html"), encoding="utf-8").read()
desk = open(os.path.join(root, "lab", "merged", "desk.html"), encoding="utf-8").read()
b = src.index("<body"); head, body = src[:b], src[b:]
week = re.search(r"Week (\d+)", head).group(1)
# head: keep styles, fonts, icons and the account/risk scripts; drop the builder's data script and page meta
head = re.sub(r"<script[^>]*src=\"/build/data-[^\"]+\"></script>", "", head)
head = re.sub(r"<title>.*?</title>", "<title>BetSweep Game Desk (concept)</title>", head, flags=re.S)
head = re.sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="Concept: the Matchup Boards and the Parlay Builder on one page."><meta name="robots" content="noindex">', head)
head = re.sub(r'<link rel="canonical" href="[^"]*">', '', head)
head = re.sub(r'<meta (property="og:[^"]+"|name="twitter:[^"]+") content="[^"]*">', '', head)
# body shell: site nav + its scripts, then the masthead; the bottom tabs + footer scripts from the end of the page
nav_end = body.index("</nav>") + 6
p = nav_end
for _ in range(2): p = body.index("</script>", p) + 9
shell_top = body[:p]
top = body.index('<div class="top">', p); top_end = body.index("</div>\n\n", body.index('<nav class="nav"', top)) + 6
mast = body[top:top_end]
mast = re.sub(r"<h1>.*?</h1>", f"<h1>Week {week} · <b>Game Desk</b> <small style=\"font-family:var(--body);font-weight:500;font-size:12px;letter-spacing:0;color:var(--mute)\">concept</small></h1>", mast, flags=re.S)
mast = re.sub(r"<p>.*?</p>", "<p>The Matchup Boards and the Parlay Builder on one page: pick a game, read its board, tap legs, and your slip rides at the bottom. A preview - the live pages are unchanged.</p>", mast, flags=re.S)
mast = re.sub(r'<nav class="nav"[^>]*>.*?</nav>', '<nav class="nav" aria-label="related"><a href="/boards/">← Matchup Boards</a><a href="/build/">Parlay Builder →</a></nav>', mast, flags=re.S)
tabs = body.index('<nav class="bstabs"') if '<nav class="bstabs"' in body else body.rfind("<nav ")
shell_bottom = body[tabs:]
page = head + shell_top + "\n" + mast + "\n" + desk + "\n" + shell_bottom
page = page.replace("{{WEEK}}", week)
open(os.path.join(root, "lab", "merged", "index.html"), "w", encoding="utf-8").write(page)
print(f"wrote lab/merged/index.html for week {week}: {len(page)//1024} KB")
