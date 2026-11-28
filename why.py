"""why.py - a leg's reasons, short enough to read at a glance (owner 11/27 10:34 PM, after FanDuel shipped its "Trends" cards: "The goal
is always to make the best most efficient legs and show them why as quickly and as best as it can").

The model already writes its reasons on every leg: the leg's own flags (builder data "fh": [kind, tag, full sentence]) and the player's
flags (builder data "pf"[player]). On the builder they open on a tap. This module picks the one that argues hardest FOR the leg and the
one that argues hardest AGAINST it and says each in a line, for the cards that have no room for a tap: Today's looks, Model's Best and
the Trend check page. Nothing is computed here and nothing is invented: every line is a shortening of a sentence the model wrote.

Rules, so a line is never off the point:
  - a tag the graded record demoted (sweep.TAG_W weight 0) is not a reason; nor is a headline (the "News: ..." tags carry the story's
    title, not a reason), a bare role signal ("Model role signal: ..."), or "Reliable" (its own sentence says it has not carried over)
  - a player-level flag written about one stat (a rushing trend, a targets trend, a script note about carries) is only used on a leg
    priced on that stat
  - the order within each side is fixed below: the things that have cost the most first (a stand-in quarterback, the losing side of a
    blowout, a fringe role), small print last

  reasons(leg, pf)  ->  [(side, label, line), ...]   side is "good" or "bad"; at most one of each; the against line leads when the
                                                      model's chance is under the price's, else the for line leads
  html(leg, pf)     ->  the <ul class="legwhy"> block, or "" when the model has nothing to say either way
  css()             ->  the block's styles (build_site.py adds them to the shared sheet)
"""
import html as _html, re
import sweep as SW

E = _html.escape
AGAINST = ["Avoid (BetSweep)", "Backup QB", "QB out", "Losing side", "Trail script", "Blowout script", "Blowout rest risk", "Fringe role", "Target squeeze", "Rising", "Depth chart: demoted",
           "Losing zone", "Near-zero risk", "Tough matchup", "Snaps down", "Targets down", "Carries down", "Attempts down", "Cold", "Target competition", "Returns", "Tough coverage", "Rain", "Wind",
           "Turnover risk", "Fill-in fading", "First game back", "Back from absence", "Questionable", "Team under its prices", "Market disagrees", "Price gap", "Corner questionable", "Quiet games",
           "One big game", "Boom/bust", "Low total", "Season", "This defense", "Role rising", "Model disagrees with consensus", "Sample"]
FOR = ["Corner out", "Coverage edge", "Room thinned", "Fill-in volume", "Depth chart: promoted", "Depth chart: starter", "Snaps up", "Targets up", "Carries up", "Attempts up", "Hot", "Proven zone",
       "Lead script", "Trail script", "Rain = run game", "Wind = run game", "Steady floor", "Season", "This defense", "Team hitting its prices", "Soft matchup here"]
SKIP = {"Reliable", "Role Up", "Role Down", "Limited", "Volatile", "Soft matchup", "Auto Qb Succession", "Manual Role Override", "Healthy again", "QB still out", "Matchup shifting", "Price check", "Price",
        "FanDuel", "Consensus price", "Under", "How it is priced", "Combined", "Red-zone model", "Near-zero games", "Better price elsewhere", "Coverage", "Model above consensus", "Snaps falling", "Role up"}
# which stat words a player-level sentence may mention for it to bear on a leg priced in this market
STAT = {"Rushing Yards": ("rush yds", "carries"), "Receiving Yards": ("rec yds", "targets"), "Receptions": ("targets", "rec yds", "catch"), "Longest Reception": ("rec yds", "targets"),
        "Passing Yards": ("pass yds", "attempts"), "Passing TDs": ("pass yds", "attempts"), "Rush + Rec Yards": ("rush yds", "rec yds", "carries", "targets")}
ALLSTAT = ("rush yds", "rec yds", "pass yds", "carries", "targets", "attempts", "catch")
RUSHM = ("Rushing Yards", "Rush + Rec Yards", "Anytime TD", "2+ TD", "3+ TD", "First TD")
PASSM = ("Receiving Yards", "Receptions", "Longest Reception", "Passing Yards", "Passing TDs")
TDM = ("Anytime TD", "2+ TD", "3+ TD", "First TD")
# the stat a consensus note names -> the markets it says something about (his own yards and catches also speak to his touchdown chance)
CONS = {"rec yds": ("Receiving Yards", "Longest Reception", "Rush + Rec Yards", "Receptions") + TDM, "receptions": ("Receptions", "Receiving Yards") + TDM,
        "rush yds": ("Rushing Yards", "Rush + Rec Yards") + TDM, "pass yds": ("Passing Yards",), "pass td": ("Passing TDs",), "rush td": TDM, "rec td": TDM}


def norm(tag):
    """a flag's tag as the name it is ranked and shown by"""
    t = str(tag or "").strip()
    if re.match(r"^\d+/\d+ this season$", t): return "Season"
    if t.startswith("vs ") and re.search(r"\d+/\d+", t): return "This defense"
    if t.startswith("Rising:"): return "Rising"
    if t.endswith(" returns") or t.endswith(" may return"): return "Returns"
    if t.startswith("O/U "): return "Low total"
    if t.startswith("Cold L"): return "Cold"
    if t.startswith("Hot L"): return "Hot"
    if t.startswith("Soft vs "): return "Soft matchup here"
    if re.match(r"^\d+ game sample$", t): return "Sample"
    if t.startswith("FD "): return "FD line"
    return t


LABEL = {"Rising": "Role at risk", "Returns": "Teammate back", "Cold": "Trending down", "Hot": "Trending up", "Soft matchup here": "Soft matchup", "Sample": "Small sample", "Losing side": "Losing side",
         "Depth chart: demoted": "Depth chart", "Depth chart: promoted": "Depth chart", "Depth chart: starter": "Depth chart", "Blowout rest risk": "Blowout risk", "Model disagrees with consensus": "Consensus",
         "Rain = run game": "Rain", "Wind = run game": "Wind", "QB out": "QB change", "Fill-in volume": "More work", "Room thinned": "More work"}


def _clip(s, n=104):
    s = re.sub(r"\s+", " ", str(s or "")).strip().rstrip(".;,: ")
    if len(s) > n: s = s[:n].rsplit(" ", 1)[0].rstrip(",;:(- ") + "…"
    while s.count("(") > s.count(")"):          # never leave a bracket open
        s = s[:s.rindex("(")].rstrip(" ,;:-") + ("…" if not s.endswith("…") else "")
    return s


def _first(txt):
    """the first clause of a model sentence: up to the first full stop that ends a sentence, a semicolon, or a spaced dash"""
    return re.split(r"(?<=[a-z0-9%)+])\.\s|;\s|\s-\s", str(txt or "").strip(), 1)[0]


def _say(key, tag, txt):
    """one flag as one short line (its label is added by the caller); "" = nothing worth a line"""
    t = str(txt or "")
    m = re.match(r"^(.+?) is the projected quarterback in place of (.+?)(?: \(|,| and )", t)
    if key == "Backup QB" and m: return f"{m.group(1)} starts in place of {m.group(2)}"
    m = re.match(r"^Starting-QB change: (.+?) is out", t)
    if key == "QB out" and m: return f"{m.group(1)} is out, so this passing game carries extra uncertainty"
    m = re.match(r"^(.+?) is at quarterback for \w+ in place of (.+?)\.", t)
    if key == "Turnover risk" and m: return f"{m.group(1)} is in for {m.group(2)}: stand-in quarterbacks give the ball away more"
    m = re.search(r"most likely ending is ([A-Z]{2,3} by 10\+)", t)
    if key == "Losing side" and m: return f"likeliest ending is {m.group(1)}; floors on that side have run under their prices"
    m = re.search(r"likeliest ending is ([A-Z]{2,3} by 10\+)", t)
    if key == "Blowout script" and m: return f"likeliest ending is {m.group(1)}: a back's catches drop when his team is far ahead"
    m = re.match(r"^([A-Z]{2,3}) is a ([\d.]+)-point favorite", t)
    if key == "Blowout rest risk" and m: return f"{m.group(1)} is a {m.group(2)}-point favorite: receivers on big favorites lose snaps late"
    m = re.match(r"^([A-Z]{2,3}) ranks #(\d+) of 32 in (.+?) allowed to (\w+)", t)
    if key == "Tough matchup" and m: return f"{m.group(1)} is #{m.group(2)} of 32 in {m.group(3)} allowed to {m.group(4)} (1 allows the most)"
    m = re.match(r"^Model edges in (.+?) at (.+?): ([+-]?\d+)% ROI over (\d+) graded legs", t)
    if key in ("Losing zone", "Proven zone") and m: return f"{m.group(1).lower()} at {m.group(2)} have returned {m.group(3).replace('-', '−')}% over {m.group(4)} graded legs"
    m = re.match(r"^Finished under half this line \(([\d.]+)\) in (\d+) of (\d+) games", t)
    if key == "Near-zero risk" and m: return f"finished under half this line in {m.group(2)} of {m.group(3)} games"
    m = re.match(r"^([A-Z]{2,3}) (.+?) legs have hit (\d+) of (\d+) \((\d+)%\) against (\d+)% priced", t)
    if key in ("Team under its prices", "Team hitting its prices") and m: return f"{m.group(1)} {m.group(2)} legs have hit {m.group(5)}% against {m.group(6)}% priced ({m.group(3)} of {m.group(4)})"
    m = re.match(r"^(.+?) is Out this week(?: \((.+?)\))?", t)
    if key == "Corner out" and m: return f"his corner, {m.group(1)}, is out" + (f" ({m.group(2)})" if m.group(2) else "")
    m = re.match(r"^(.+?) is Questionable(?: \((.+?)\))?", t)
    if key == "Corner questionable" and m: return f"his corner, {m.group(1)}, is questionable" + (f" ({m.group(2)})" if m.group(2) else "")
    m = re.match(r"^Projected to see (.+?) on about (\d+)% of routes", t)
    if key in ("Coverage edge", "Tough coverage") and m:
        d = re.search(r"targets ([+-]\d+)%", t)
        return f"sees {m.group(1)} on about {m.group(2)}% of routes" + (f" (targets {d.group(1).replace('-', '−')}% against his usual)" if d else "")
    m = re.match(r"^The model says (\d+)% but FanDuel's price implies (\d+)%", t)
    if key == "Market disagrees" and m: return f"model {m.group(1)}%, price {m.group(2)}%: when they are this far apart the book has usually been closer"
    m = re.match(r"^Model (\d+)% vs FanDuel (\d+)%", t)
    if key == "Price gap" and m: return f"model {m.group(1)}%, price {m.group(2)}%: on a floor leg the book has usually been closer"
    m = re.match(r"^Has (cleared|scored) (.+?) in (only )?(\d+) of (\d+) games this season", t)
    if key == "Season" and m: return f"{m.group(1)} {m.group(2)} in {'only ' if m.group(3) else ''}{m.group(4)} of {m.group(5)} games this season"
    m = re.match(r"^([A-Z]{2,3}) vs (\w+?)s? \((.+?)\): (\d+)/(\d+) beat their average", t)
    if key == "This defense" and m: return f"{m.group(4)} of {m.group(5)} {m.group(2)}s have beaten their average against {m.group(1)}"
    m = re.match(r"^Next man up: (.+?) is taking this role - (.+?)[,.]", t)
    if key == "Rising" and m: return f"{m.group(1)} is taking this role ({m.group(2)})"
    m = re.match(r"^Teammate (?:returning|may return): (.+?) missed last week and is (back|Questionable)", t)
    if key == "Returns" and m: return f"{m.group(1)} {'is back' if m.group(2) == 'back' else 'may be back'}, so the work that flowed to others shrinks"
    m = re.match(r"^Next man up(?: \(#\d in line\))?: (.+?) out = (.+?) vacated", t)
    if key == "Room thinned" and m: return f"{m.group(1)} out: {m.group(2)} vacated"
    m = re.match(r"^Steps into vacated work: out this week - (.+?)(?:\. The model|\.$)", t)
    if key == "Fill-in volume" and m: return f"steps into the work of {m.group(1)}"
    m = re.search(r"about (\d+)% less than their healthy-game average", t)
    if key == "First game back" and m: return f"coming back from an injury-limited game; the first two games back have run about {m.group(1)}% under"
    m = re.match(r"^Did not play the last (\d+) games? \(last logged Week (\d+)\)", t)
    if key == "Back from absence" and m: return f"did not play the last {m.group(1)} game{'s' if m.group(1) != '1' else ''}; a first game back is often a lighter workload"
    m = re.match(r"^Low market total \(([\d.]+)\)", t)
    if key == "Low total" and m: return f"market total of {m.group(1)}: fewer plays and scoring chances"
    m = re.match(r"^Only (\d+) games? logged this season", t)
    if key == "Sample" and m: return f"only {m.group(1)} game{'s' if m.group(1) != '1' else ''} logged this season"
    if t.startswith("Model role signal"): return ""
    return re.sub(r"^(Trending (?:up|down)|Usage (?:rising|falling)|Snap share (?:growing|slipping)|Target competition): ", lambda q: "" if q.group(1).startswith(("Trending", "Target")) else q.group(0), _first(t))


def _weight(kind, tag):
    if tag in SW.TAG_W: return SW.TAG_W[tag]
    return {"bad": 3, "watch": 1, "good": -1}.get(kind, 0)


def _bears(key, txt, market, player_level):
    """does this sentence bear on a leg priced in this market?"""
    if not player_level: return True
    low = str(txt).lower()
    if key in ("Trail script", "Lead script"):
        run = "carries" in low
        return market in RUSHM if run else market in PASSM
    if key in ("Rain = run game", "Wind = run game"): return market in RUSHM
    if key in ("Rain", "Wind", "QB out"): return market not in ("Rushing Yards",)
    if key in ("Consensus", "Model disagrees with consensus"):
        # the note names the one stat the two projections disagree on ("...Sleeper + ESPN: pass TD 1.3 vs 1.9 consensus"): it bears on legs
        # in that stat, not on his others (11/28: a pass-TD note was showing against a passing-yards leg, a rush-TD note against catches)
        m = re.search(r"espn: (.+?) -?[0-9.]+ vs", low)
        if m and m.group(1).strip() in CONS: return market in CONS[m.group(1).strip()]
    named = [w for w in ALLSTAT if w in low]
    if key in ("Cold", "Hot", "Targets down", "Targets up", "Carries down", "Carries up", "Attempts down", "Attempts up", "Boom/bust", "Steady floor", "Quiet games", "One big game", "Consensus",
               "Model disagrees with consensus", "Fringe role", "Target squeeze", "Target competition", "Soft matchup here", "Tough matchup"):
        want = STAT.get(market)
        if want is None: return True                       # touchdown markets: any workload note bears on them
        return any(w in low for w in want) if named else True
    return True


def reasons(leg, pf=None):
    market = str(leg.get("m") or "")
    if market.startswith("Under "): return []           # these sentences are written for the over side
    fl = [(f, False) for f in (leg.get("fh") or [])] + [(f, True) for f in ((pf or {}).get(leg.get("pl")) or [])]
    seen = set(); bad, good = [], []
    for f, plv in fl:
        if not isinstance(f, (list, tuple)) or len(f) < 3: continue
        kind, tag, txt = f[0], str(f[1]), f[2]
        key = norm(tag)
        if key in seen or key in SKIP or tag in SKIP or tag.startswith("News:") or key == "FD line" or tag.startswith("Proj "): continue
        if SW.TAG_W.get(tag) == 0: continue
        w = _weight(kind, tag); helps = tag.endswith("(helps)"); hurts = tag.endswith("(hurts)")
        if not _bears(key, txt, market, plv): continue
        if (kind in ("bad", "watch") and w > 0) or hurts:
            seen.add(key); bad.append((AGAINST.index(key) if key in AGAINST else len(AGAINST) + (0 if kind == "bad" else 1), key, tag, txt))
        elif (kind == "good" and w < 0) or helps or (kind == "info" and key == "Team hitting its prices"):
            seen.add(key); good.append((FOR.index(key) if key in FOR else len(FOR), key, tag, txt))
    out = []
    for side, pool in (("bad", bad), ("good", good)):
        for _, key, tag, txt in sorted(pool, key=lambda x: x[0]):
            line = _say(key, tag, txt)
            if not line: continue
            lab = LABEL.get(key, key); out.append((side, lab, _clip(line[:1].upper() + line[1:], max(56, 90 - len(lab))))); break
    try: under = float(leg.get("p") or 0) < float(leg.get("bk") or 0)
    except Exception: under = False
    out.sort(key=lambda r: (r[0] != ("bad" if under else "good")))
    return out


def html(leg, pf=None, cls=""):
    rs = reasons(leg, pf)
    if not rs: return ""
    return (f'<ul class="legwhy{(" " + cls) if cls else ""}">' + "".join(f'<li class="{k}"><i aria-hidden="true">{"✓" if k == "good" else "✗"}</i><span><b>{E(tag)}</b> {E(line)}</span></li>' for k, tag, line in rs) + '</ul>')


def css():
    return "\n".join([
        "/* a leg's reasons in two lines (why.py): the strongest for, the strongest against */",
        ".legwhy{list-style:none;margin:0;padding:0;display:grid;gap:5px;font-size:12.5px;line-height:1.35;color:var(--mute)}",
        ".legwhy li{display:grid;grid-template-columns:16px minmax(0,1fr);gap:6px;align-items:start}",
        ".legwhy li i{font-style:normal;font-weight:700;font-size:12px;line-height:1.35;text-align:center}",
        ".legwhy li.good i{color:var(--good)} .legwhy li.bad i{color:var(--bad,#e07070)}",
        ".legwhy li span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}",
        ".legwhy li b{font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.02em;color:var(--ink);margin-right:2px}",
    ]) + "\n"
