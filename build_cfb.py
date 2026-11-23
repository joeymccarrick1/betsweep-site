#!/usr/bin/env python3
"""College football postseason boards at /cfb/ (a preview): the title games, bowls and playoff games, in the NFL boards' clothes.

Owner 11/22: college football means "Post season game lines". 11/23 1:10 AM: "get to work on the next thing which I suppose is college
football". Game lines only: Tennessee does not allow bets on individual college athletes.

Reads cfb/board.json from the feeds-sports branch (sports/cfb/publish.py writes it inside the feeds-sports job) through the clone, in plain
Python, and writes out/cfb-boards.html for build_site.py to place. Same stylesheet as the NFL boards (template.html) with the NBA page's
rules and script on top (build_nba.NB_CSS / NB_JS); the background is the NFL's own Xs and Os - it is football.

THE LINE LEADS. A card's big numbers are what the posted spread and total imply each side scores, because on 751 games this season the
book's spread was closer than our rating (11.9 points off against 13.3). Our rating sits beside the line as a second opinion and is
tracked; nothing on the page is a pick, and it says so. A game with no line yet shows our rating's numbers, marked as ours.

    python3 build_cfb.py <clone>                              (the hourly job)
    python3 build_cfb.py --board FILE [--with nba,epl]        (local work: any age of board is drawn)
"""
import datetime as dt
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
import build_nba as N
import sport_nav

OUT = N.OUT
PAGE = os.path.join(OUT, "cfb-boards.html")
FORMAT = 1
E = html.escape
NEAR = 3.0          # our rating within this many points of the spread counts as agreeing with it
NEAR_TOTAL = 4.0


def when(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def usable(B, now=None, any_age=False):
    """(ok, why not). Drawn only if it is in the shape this page reads, lists a postseason game that is not long over, and was built in the
    last day: the feed job keeps its last board when the model step fails, so an old one can sit on the branch."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if not B or not isinstance(B, dict): return False, "no cfb/board.json in reach on the feeds-sports branch"
    if B.get("format") != FORMAT or B.get("sport") != "cfb": return False, f"the board is format {B.get('format')!r}, this page reads format {FORMAT}"
    if not B.get("games"): return False, "the board lists no postseason game with both teams known"
    if any_age: return True, ""
    built = when(B.get("built"))
    if not built or (now - built).total_seconds() > 26 * 3600: return False, f"the board was built {B.get('built')}, more than a day ago: the feed job is not producing a new one"
    last = max((when(x.get("ko")) for x in (B["games"] + (B.get("tbd") or [])) if when(x.get("ko"))), default=None)
    if not last or (now - last).total_seconds() > 6 * 3600: return False, "every game on the board kicked off more than six hours ago"
    return True, ""


def num(x): return f"{x:.1f}".rstrip("0").rstrip(".") if isinstance(x, (int, float)) else ""
def signed(x): return ("+" if x > 0 else "−" if x < 0 else "") + num(abs(x))


def side_line(g, side):
    """the posted spread as that side sees it: 'MIA −2.5' / 'WAKE +2.5' / 'MIA pick'"""
    sp = g["line"]["spread"]
    v = sp if side == "home" else -sp
    return f'{g[side]} {"pick" if v == 0 else signed(v)}'


def by_text(margin, home, away):
    """a margin from the home side's view, in words: 'MIA by 2.5' / 'WAKE by 4' / 'even'"""
    if abs(margin) < 0.05: return "even"
    return f'{home if margin > 0 else away} by {num(abs(margin))}'


def rank_name(t):
    return (f'#{t["rank"]} ' if t.get("rank") else "") + (t.get("short") or t.get("abbr") or "")


def round_label(B):
    names = [x.get("name") or "" for x in B["games"] + (B.get("tbd") or [])]
    bowls = any(x.get("stype") == 3 for x in B["games"]) or any(re.search(r"bowl|playoff|semifinal|quarterfinal|national", n, re.I) for n in names)
    titles = any(re.search(r"championship", n, re.I) and not re.search(r"national", n, re.I) for n in names)
    return "Conference championships" if titles and not bowls else ("Championships, bowls and the playoff" if titles else "Bowls and the playoff")


def round_short(B):
    rl = round_label(B)
    return "Title games" if rl == "Conference championships" else ("Bowl season" if rl == "Bowls and the playoff" else "The postseason")


def gap_line(g):
    """one plain sentence on where our rating stands against the posted line; '' when there is no line"""
    if not g.get("mkt"): return ""
    gm, gt = g["gap"]["margin"], g["gap"]["total"]
    h, a = g["home"], g["away"]
    side = (f'<b>{num(abs(gm))} points toward {E(h if gm > 0 else a)}</b> of the spread' if abs(gm) >= NEAR else 'within a field goal of the spread')
    tot = (f'<b>{num(abs(gt))} {"higher" if gt > 0 else "lower"}</b> than the posted total' if abs(gt) >= NEAR_TOTAL else 'close to the posted total')
    return f'<p class="cfgap">Our rating is {side} and {tot}. It is tracked, not a pick.</p>'


def team_col(ab, g, B):
    t = B["teams"][ab]; n = B.get("n_teams") or 0
    home = g["home"] == ab
    where = "neutral site" if g.get("neutral") else ("home" if home else "away")
    head = f'<li class="dsum">{N.badge(ab, t)}<span>{E(rank_name(t))}</span><span class="cfrec">{E(t.get("record") or "")} <small>{E(where)}</small></span></li>'
    chips = ""
    if t.get("ppg") is not None:
        chips += f'<span><small>Scores</small><b>{t["ppg"]:.1f}</b></span><span><small>Allows</small><b>{t["papg"]:.1f}</b></span>'
    if t.get("off") and t.get("def"):
        chips += (f'<span style="--c:{N.rank_color(t["off"][0], n)}" title="Offense rank #{t["off"][0]} of {n}, adjusted for the opponents it has played"><small>Offense</small><b class="rk">#{t["off"][0]}</b></span>'
                  f'<span style="--c:{N.rank_color(t["def"][0], n)}" title="Defense rank #{t["def"][0]} of {n}, adjusted for the opponents it has played (1 = allows the least)"><small>Defense</small><b class="rk">#{t["def"][0]}</b></span>')
    elif not t.get("fbs"):
        chips += '<span class="cfwide"><small>Too few games this season to rank</small><b>—</b></span>'
    stats = f'<li class="cfst">{chips}</li>' if chips else ""
    rows = ""
    for r in t.get("last") or []:
        try: d = dt.date.fromisoformat(r["d"]); ds = f"{d.month}/{d.day}"
        except Exception: ds = ""
        rows += f'<li class="cfg res-{E(r["res"])}"><b>{E(r["res"])}</b><span>{r["pf"]}–{r["pa"]}</span><span class="cfo">{E(r["ha"])} {E(r["opp"])}</span><small>{E(ds)}</small></li>'
    last = (f'<li class="cfh">Last {len(t["last"])} <small>{E(t.get("streak") or "")}</small></li>' + rows) if rows else '<li class="nbnone">No finals on file for this team.</li>'
    return f'<ul class="col cfteam" data-team="{E(ab)}">{head}{stats}{last}</ul>'


def game_card(g, B):
    h, a = g["home"], g["away"]; th, ta = B["teams"][h], B["teams"][a]
    mkt, model = g.get("mkt"), g["model"]
    src = mkt or model
    sub = (f'{E(side_line(g, "home" if g["line"]["spread"] <= 0 else "away"))} · total {num(g["line"]["total"])}' if mkt else f'our rating: {E(by_text(model["margin"], h, a))} · no line posted yet')
    score = f'<span class="pt">{src["away"]:.1f}</span><span class="dash">–</span><span class="pt">{src["home"]:.1f}</span><small>{sub}</small>'
    ko = int(when(g["ko"]).timestamp() * 1000) if when(g["ko"]) else 0
    band = ""
    if g.get("state") in ("in", "post") and g.get("score"):
        head = "Final" if g["state"] == "post" else "In play"
        band = (f'<div class="nbstate s-{g["state"]}"><b>{head}</b><span>{E(a)} {g["score"]["away"]} · {E(h)} {g["score"]["home"]}</span>'
                + (f'<small>{E(g.get("detail") or "")} when this page was built</small>' if g["state"] == "in" else "") + '</div>')
    bits = [f'<span class="gk">{E(g["koct"])} CT</span>'] + [f'<span>{E(x)}</span>' for x in ((g.get("venue") or ""), ("neutral site" if g.get("neutral") else ""), " / ".join(g.get("tv") or [])) if x]
    who = (g.get("line") or {}).get("by") or "the sportsbook ESPN shows"
    if g.get("mkt"): bits.append(f'<span class="mkt" title="{E(who)} line as shown by ESPN - not FanDuel">line: <small>{E(who)}</small></span>')
    ginfo = '<div class="ginfo">' + "<i>·</i>".join(bits) + '</div>'
    if mkt:
        fav = "home" if g["line"]["spread"] <= 0 else "away"
        tiles = (f'<span title="{E(who)} line as shown by ESPN - not FanDuel"><small>Spread</small><b>{E(side_line(g, fav))}</b></span>'
                 f'<span title="{E(who)} line as shown by ESPN - not FanDuel"><small>Total</small><b>{num(g["line"]["total"])}</b></span>'
                 f'<span><small>Our rating</small><b>{E(by_text(model["margin"], h, a))}</b></span><span><small>Our total</small><b>{model["total"]:.1f}</b></span>')
    else:
        tiles = (f'<span><small>Spread</small><b>—</b></span><span><small>Total</small><b>—</b></span>'
                 f'<span><small>Our rating</small><b>{E(by_text(model["margin"], h, a))}</b></span><span><small>Our total</small><b>{model["total"]:.1f}</b></span>')
    mk = f'<div class="eplmk cfmk" aria-label="The posted line and our rating">{tiles}</div>'
    return (f'<section class="card" id="{E(g["key"])}" data-ko="{ko}"> <header class="hd"> <div class="tm a">{N.badge(a, ta)}<b>{E(a)}</b><span>{E(rank_name(ta))}</span></div> '
            f'<div class="score">{score}{N.SWOOSH}</div> <div class="tm b">{N.badge(h, th)}<b>{E(h)}</b><span>{E(rank_name(th))}</span></div> </header> '
            f'<div class="cfname">{E(g["name"])}</div>{band}{ginfo}{mk}{gap_line(g)}'
            f'<div class="vbtns"><button type="button" class="vbtn" data-view="proj">How they got here</button></div>'
            f'<div class="cols">{team_col(a, g, B)}{team_col(h, g, B)}</div>'
            f'<footer class="nbfoot"><span>{"The score is what the posted spread and total imply each side scores" if mkt else "No line is posted yet, so the score is our own rating"}; '
            f'visiting side first. Offense and defense ranks are adjusted for the opponents each team has played.</span></footer> </section>')


def summary_card(B):
    gl = ""
    for g in B["games"]:
        st = "Final" if g.get("state") == "post" else ("In play" if g.get("state") == "in" else g["koct"])
        ln = (f'{E(side_line(g, "home" if g["line"]["spread"] <= 0 else "away"))} <small>total {num(g["line"]["total"])}</small>' if g.get("mkt") else '<small>no line yet</small>')
        gl += (f'<li><span class="bl-p"><a href="#{E(g["key"])}">{E(g["away"])} {"vs" if g.get("neutral") else "at"} {E(g["home"])}</a></span><span class="bl-m">{E(g["name"])} <small>{E(st)}</small></span>'
               f'<span class="bl-n">{ln}</span></li>')
    tl = ""
    for x in B.get("tbd") or []:
        known = (" and ".join(x["known"]) + " in, one to come") if x.get("known") else "teams not set"
        tl += f'<li><span class="bl-p">{E(x["name"])}</span><span class="bl-m">{E(x["koct"])} CT <small>{E(x.get("venue") or "site to be set")}</small></span><span class="bl-n"><small>{E(known)}</small></span></li>'
    n = len(B["games"])
    return (f'<section class="card summary" id="summary"> <header class="hd"><div class="tm a"><b>Slate</b><span>{E(round_short(B))} at a glance</span></div><div class="score"><span class="pt">{n}</span>'
            f'<small>game{"s" if n != 1 else ""} on the board</small>{N.SWOOSH}</div><div class="tm b"><span>The posted line</span></div></header> <div class="sumgrid"> '
            f'<div><h3>Games <small>kickoff (CT) and the posted line</small></h3><ul class="bl">{gl}</ul></div> '
            + (f'<div><h3>Still to be decided <small>the game is set, its teams are not</small></h3><ul class="bl">{tl}</ul></div> ' if tl else '') + '</div> </section>')


CF_CSS = """
.cfname{padding:8px 14px 0;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}
body.compact .card:not(.expanded) > .cfname{display:block}
.cfmk small i{font-style:normal;opacity:.8;margin-left:3px}
.cfgap{margin:8px 12px 2px;padding:8px 10px;border-left:3px solid var(--line);border-radius:0 6px 6px 0;background:color-mix(in srgb,var(--chalk) 55%,transparent);font-size:13.5px;line-height:1.4;color:var(--mute)}
.cfgap b{color:var(--ink);font-weight:600}
body.compact .card:not(.expanded) > .cfgap{display:block}
.cfteam .dsum{grid-template-columns:auto 1fr auto} .cfrec{font-family:var(--display);font-weight:700;font-size:15px;color:var(--ink);white-space:nowrap} .cfrec small{font-family:var(--body);font-weight:500;font-size:11.5px;color:var(--mute);margin-left:4px}
.cfst{list-style:none;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:8px 14px 4px;padding:0}
.cfst span{min-width:0;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:10px;padding:5px 8px} .cfst small{font-size:11px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cfst b{font-family:var(--display);font-weight:700;font-size:17px;line-height:1.15;color:var(--ink)} .cfst b.rk{color:var(--c,var(--ink))} .cfst .cfwide{grid-column:span 2}
.cfh{list-style:none;margin:10px 14px 2px;padding:6px 0 4px;border-top:1px dashed var(--line);font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute)}
.cfh small{font-family:var(--body);font-weight:600;font-size:12px;letter-spacing:0;text-transform:none;margin-left:6px;color:var(--ink)}
.cfg{list-style:none;display:grid;grid-template-columns:20px 58px 1fr auto;gap:8px;align-items:baseline;margin:0 14px;padding:5px 0;border-bottom:1px solid color-mix(in srgb,var(--line) 60%,transparent);font-size:14px;font-variant-numeric:tabular-nums}
.cfg b{font-family:var(--display);font-weight:700} .cfg.res-W b{color:var(--good)} .cfg.res-L b{color:var(--bad)} .cfg .cfo{color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .cfg small{color:var(--mute);font-size:12px}
@media (max-width:760px){ .cfst{gap:4px} .cfst span{padding:5px 6px} .cfst b{font-size:15.5px} .cfst small{font-size:10.5px} }
"""


def page(B, have=None):
    css = re.search(r"<style[^>]*>(.*?)</style>", open(os.path.join(HERE, "template.html"), encoding="utf-8").read(), re.S).group(1)
    n = len(B["games"]); rl = round_label(B); T = B.get("test") or {}
    nav = '<a href="#summary">Slate</a> ' + " ".join(f'<a href="#{E(g["key"])}">{E(g["away"])}·{E(g["home"])}</a>' for g in B["games"])
    desc = (f"College football matchup boards, {rl.lower()}: the posted spread and total for {n} game{'s' if n != 1 else ''} and what they imply each side scores, "
            "with BetSweep's own rating beside the line. A preview: game lines only.")
    last = max(when(x["ko"]) for x in B["games"] + (B.get("tbd") or []))
    try:
        from zoneinfo import ZoneInfo
        last_day = last.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
    except Exception:
        last_day = (last - dt.timedelta(hours=6)).date().isoformat()
    pre = ('<div class="nbpre"><b>College football preview.</b> Game lines only: Tennessee does not allow bets on individual college athletes. '
           'The line is the one ESPN posts, not FanDuel\'s. Our rating sits beside it as a second opinion: this season the book has been the closer of the two, so nothing here is a pick.</div>')
    key = ('<details class="nbkey"><summary aria-label="How to read the board"><span class="nbk-l">How to read the board</span><span class="nbk-s" aria-hidden="true">?</span></summary><dl>'
           '<dt>Score</dt><dd>What the posted spread and total imply each side scores, visiting side first. A spread of −7 with a total of 55 is a 31–24 game. With no line posted yet, the score is our own rating and says so.</dd>'
           '<dt>Spread and total</dt><dd>The sportsbook line ESPN shows, with the book named. It is not FanDuel\'s.</dd>'
           '<dt>Our rating</dt><dd>An offense and a defense rating for every team, adjusted for who it has played, turned into a margin and a total. The sentence under the tiles says how far it sits from the line.</dd>'
           '<dt>Offense and defense</dt><dd>Each team\'s rank among the teams rated, adjusted for schedule: #1 on offense scores the most, #1 on defense allows the least. Scores and Allows are plain points a game.</dd></dl></details>')
    chk = "".join(f"<li>{E(c)}</li>" for c in B.get("checks") or [])
    ats = T.get("ats") or [0, 0]
    stamp = (f'<p class="nbstamp">Built {N.fmt_ct(B.get("built"))} from {B.get("played")} finals through {E(B.get("data_through") or "?")}. Scores: the public ESPN schedule file kept by sportsdataverse, and ESPN\'s scoreboard'
             + (f' as of {N.fmt_ct(B.get("espn_at"))}' if B.get("espn_at") else '') + '. The line: the sportsbook ESPN names on each game. '
             f'Our rating: BetSweep\'s college model (an offense and a defense rating for each of {B.get("n_teams")} teams, fitted on points and adjusted for schedule). '
             + (f'Checked on {T["games"]} games of {T["season"]}: the book\'s spread missed the final margin by {T["book_miss"]:.1f} points on average and our rating by {T["model_miss"]:.1f}; '
                f'taking our rating\'s side against the spread went {ats[0]}–{ats[1]}. That is why the line leads on this page. ' if T.get("games") else '')
             + 'For entertainment; not betting advice.</p>' + (f'<ul class="nbstamp eplchk">{chk}</ul>' if chk else ""))
    cards = "\n".join(game_card(g, B) for g in B["games"])
    sw = sport_nav.switch("cfb", have or {})
    return (f'<title>BetSweep · College Football Matchup Boards</title>\n<style>{css}</style>\n<style>{N.NB_CSS}</style>\n<style>{EPL_MK}</style>\n<style>{CF_CSS}</style>\n'
            f'<div class="top">\n  <div class="mast">\n    <h1><small>College Football · {E(rl)}</small><b>Matchup Boards</b></h1>\n    <p>{E(desc)}</p>\n  </div>\n  <nav class="nav" aria-label="jump to game">{nav}</nav>\n</div>\n'
            f'<div class="nbbar">{sw}{key}</div>\n{pre}\n'
            f'<div class="nbold" id="nbold" hidden><b>Every game on this board has kicked off.</b> A newer board is not up yet, so the numbers below are from before those games.</div>\n'
            f'<div class="grid" data-day="{E(last_day)}">\n{summary_card(B)}\n{cards}\n</div>\n{stamp}\n{N.NB_JS}\n')


# the four-tile strip under a card's head: the soccer pages' own rule, so the two sports stay alike
EPL_MK = """
.eplmk{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:8px 12px 4px}
.eplmk span{min-width:0;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:10px;padding:5px 8px;background:color-mix(in srgb,var(--ink) 4%,transparent)}
.eplmk small{font-size:11.5px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .eplmk b{font-family:var(--display);font-weight:700;font-size:18px;line-height:1.15;color:var(--ink);white-space:nowrap}
body.compact .card:not(.expanded) > .eplmk{display:grid}
@media (max-width:760px){ .eplmk{gap:4px;padding:8px 10px 4px} .eplmk span{padding:5px 6px} .eplmk small{font-size:10.5px} .eplmk b{font-size:15px} }
"""


def signature(B):
    """what a visitor would notice changing: the games and their state, each posted line, our rating to the whole point, the games still to be
    decided and which of their teams are known, each team's rank and record"""
    return json.dumps([[(g["key"], g["name"], g["ko"], g.get("state"), (g.get("score") or None), ((g["line"]["spread"], g["line"]["total"]) if g.get("mkt") else None),
                         round(g["model"]["margin"]), round(g["model"]["total"])) for g in B["games"]],
                       [(x["name"], x["ko"], x.get("known")) for x in B.get("tbd") or []],
                       sorted((ab, t.get("rank"), t.get("record")) for ab, t in B["teams"].items())], sort_keys=True)


def main():
    a = sys.argv[1:]
    named = "--board" in a
    if named:
        B = N.load(path=a[a.index("--board") + 1]); have = sport_nav.available(only=sport_nav.named(a))
    else:
        clone = a[0] if a else None
        have = sport_nav.available(clone)                   # fetches the branch
        B = N.feed_file(clone, "cfb/board.json")
    ok, why = usable(B, any_age=named)
    outs = (PAGE, os.path.join(OUT, "cfb_board.json"), os.path.join(OUT, "cfb_sig.json"))
    if not ok:
        for f in outs:
            if os.path.exists(f): os.remove(f)
        print(f"cfb: no page written - {why}")
        return
    os.makedirs(OUT, exist_ok=True)
    open(PAGE, "w", encoding="utf-8").write(page(B, have))
    json.dump(B, open(outs[1], "w"), separators=(",", ":"))
    json.dump({"built": B.get("built"), "sig": signature(B) + "|nav:" + ",".join(sorted(have))}, open(outs[2], "w"))
    print(f"cfb boards: {round_label(B)}, {len(B['games'])} games ({sum(1 for g in B['games'] if g.get('mkt'))} with a posted line), {len(B.get('tbd') or [])} still to be decided; "
          f"board built {N.fmt_ct(B.get('built'))}; {os.path.getsize(PAGE) // 1024} KB -> {PAGE}")


if __name__ == "__main__":
    main()
