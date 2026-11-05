# BetSweep visual system - working notes (11/5 overnight pass)

Brand board (owner, 11/5): chalkboard navy with chalk play diagrams (X / O / dashed arrows), cream paper, one red;
"BetSweep" in heavy italic sans with the red swoosh (hollow circle -> arrowhead); "BS" monogram; hand-brushed red
stroke under "PICKS. DATA. DRAWS. PROFITS."; turf and cap textures. Sampled: navy #0c1824-#132028, cream #e4d8cc,
black #181818, red #c03c30 (print), swoosh red on screen = site red #d7332a (matches the wordmark PNGs - keep).

## Diagnosis (live site, 11/5, 390x844 + 1280)
- Three page-title styles (condensed caps 16px in the mast; condensed 30px on player/usage/receipts; Barlow italic
  28-30px on home/player page/guide). Section titles = tracked caps 13-15px everywhere, so a title and a data label
  look the same. Home: 39% of text nodes uppercase; boards 21%; fantasy page 7 caps labels on one screen.
- Controls: 5+ button signatures per page; radii 3/4/5/6/7/8/10/99/999; condensed caps vs Plex mixed; the live
  Picks/Every-leg toggle is unstyled (Arial); team tabs square; "→" in button text.
- Cards all the same 1px border + radius, chalk pattern spread over empty space (the Slate summary is 380px tall for
  one number on phones). Secondary pages (receipts, usage, players, social) carry none of the brand.
- Dark bg #0f141c reads near-black; the board's navy is teal-navy.

## Tokens
Color (dark): Chalkboard #0e1820 (bg) · Slate #152230 (card) · Smudge #1c2b3a (chalk) · Line #2a3b4b · Paper #efe9da
(ink) · Mute #97a5b3 · Sweep red #d7332a · Field green #5fcf93 · Flag #ef8a7e · Warn #f2b35a.
Color (light): Paper #efe9da · Card #f7f3e8 · Chalk #e4ddcb · Line #d3cbb8 · Ink #141a24 · Mute #5d6676 · green
#1f7a4d · red-bad #b3372b · warn #a86400. (unchanged - already the board's cream)
Type: Barlow italic 800 = the voice (page titles, team codes, hero numbers' companions); Barlow Condensed 600/700 =
controls, chips, data labels, section titles; IBM Plex Sans = body. Scale: 12 / 13.5 / 15 / 17 / 20 / 24 / 30 / 40 / 56.
Rule: uppercase condensed ONLY for controls (buttons, tabs, chips) and data labels (MODEL / BOOK / EDGE, LIVE / FINAL).
Headings, form labels and body meta are sentence case. That is what makes a title read as a title again.
Radius: controls 8 · cards 14 · inputs 8 · status pills 999. No drop shadows on the chalkboard (the team chip's bottom
stripe is the only "elevation").
Signature (the one bold thing): the red hand stroke - the swoosh under scores (exists) + a short brushed stroke under
section titles (.brush). Nothing else decorative.
Spacing: 8-point scale (8 / 12 / 16 / 24 / 32); chalk plays only in heroes (score strip, player hero, Slate).

## Checked against the generic defaults
- cream + serif + terracotta: no (navy chalkboard, condensed italic sans, true red - the board's own words).
- near-black + one acid accent: moving the bg to the board's teal-navy; red is the brand, not an accent pick.
- SaaS card kit: heroes (chalk) vs lists (hairline rows) vs cards (discrete objects only); two radii, no shadows.
- caps eyebrows / "→" / middle dots: caps limited to controls + data labels; arrows stripped from button text; the
  "· " meta idiom stays where it is the sports line-score convention (kickoff · venue · weather).

## Where it lives
build_site.py BRAND_CSS (shared layer, after every page's own CSS) + wrap() normalisations (h1 markup, tool arrows);
template.html (boards + the header every template page shares), build_builder.py, build_live.py, build_team.py,
build_players.py (player.css), build_today.py, home.py / LANDING_CSS, _simple pages.
