"""Premier League Matchup Boards at /epl/ - the coming matches as cards, in the NFL boards' own clothes.

Owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl. I want each sport to basically look exactly like everything
we've built for NFL."; 9:32 PM, with the NBA pages up: "Get to what's next".

Where the numbers come from: epl/board.json on the feeds-sports branch, written by sports/epl/publish.py inside the feeds-sports job
(pandas and the data set live there, not here). This script reads it through the clone with git and writes out/epl-boards.html in
plain Python. The look is the NBA page's, which is the NFL boards': template.html's stylesheet, the same card markup, and build_nba's
own extra rules and script (scorecards first, Projections / Who's out, a tap opens a player).

A PREVIEW: not in the menu, not in the sitemap, and it says so. Model numbers only - no FanDuel prices, no edges, no picks. Every
player number is "if he starts": the model does not pick line-ups, and the page shows how often he has started lately beside it.

    python3 build_epl.py <clone>              # the hourly job
    python3 build_epl.py --board FILE         # tests and local work

With no board in reach, one in another shape, one more than a day old, or one whose matches have all kicked off long ago, it writes
nothing and removes what an earlier run left.
"""
import datetime as dt, html, json, os, re, sys
import build_nba as N
import sport_nav

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
PAGE = os.path.join(OUT, "epl-boards.html")
E = html.escape
FORMAT = 1                                   # sports/epl/publish.py FORMAT
POSN = {"GK": "Goalkeeper", "DEF": "Defender", "MID": "Midfielder", "FWD": "Forward"}
POSS = {"GK": "goalkeepers", "DEF": "defenders", "MID": "midfielders", "FWD": "forwards"}
from sports.soccer import roles as RL        # owner 11/23 7:37 AM: specific positions - ST, RW, CAM, CDM, RB ... (plain Python: the hourly build has no pandas)


def spot(p):
    """the position shown beside a player and the one he is ranked among: his specific role when the board has one (ST, RW, CAM, CDM, RB ...),
    else the group the board has always carried (a board built before 11/23, or a player ESPN has not yet drawn in an eleven)"""
    return p.get("role") or p["pos"]


def spot_name(x): return RL.NAMES.get(x) or POSN.get(x, x)
REGULAR = 3                                  # starts in the club's last five that make a player "a regular" on this page
HEADNAME = {"Nott'm Forest": "Forest", "Crystal Palace": "Palace"}     # under the big letters in a card's header there is room for about eleven


def when(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def usable(B, now=None, any_age=False, sport="epl"):
    """(ok, why not). Drawn only if it is in the shape this page reads, has a match that is not long over, and was built in the last day:
    the feed job keeps its last board when the model step fails, so an old one can sit on the branch."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if not B or not isinstance(B, dict): return False, f"no {sport}/board.json in reach on the feeds-sports branch"
    if B.get("format") != FORMAT or B.get("sport") != sport: return False, f"the board is format {B.get('format')!r} for {B.get('sport')!r}, this page reads format {FORMAT} for {sport!r}"
    if not B.get("matches") or not B.get("players"): return False, "the board holds no matches"
    if any_age: return True, ""
    built = when(B.get("built"))
    if not built or (now - built).total_seconds() > 26 * 3600: return False, f"the board was built {B.get('built')}, more than a day ago: the feed job is not producing a new one"
    last = max((when(m.get("ko")) for m in B["matches"] if when(m.get("ko"))), default=None)
    if not last or (now - last).total_seconds() > 6 * 3600: return False, "every match on the board kicked off more than six hours ago"
    return True, ""


def pct(p): return f"{round(p * 100)}%"
def regular(p): return p.get("xi") == "start" or (p.get("xi") is None and p["starts5"] >= REGULAR)
def allow_rank(r, n): return n + 1 - r          # the board ranks the best defence 1; the card's scale is "1 allows the most"


def player_li(p, top, ranks, B):
    t = B["teams"][p["team"]]; o = B["teams"][p["opp"]]; n = B.get("n_clubs") or 20
    ag, ash = allow_rank(o["def"][0], n), allow_rank(o["shots_against"][0], n)
    cg, cs = N.rank_color(ag, n), N.rank_color(ash, n)
    st = p.get("status") or {}
    tag = st.get("tag")
    xi = p.get("xi")
    role = {"start": "in the eleven", "bench": "on the bench", "no": "not in the squad"}.get(xi) or f"started {p['starts5']} of last 5"
    mu_g = f'<span class="mu"><i style="background:{cg}">{E(p["opp"])} #{ag}</i><b>in</b><i class="nbg">goals allowed</i></span>'
    mu_s = f'<span class="mu"><i style="background:{cs}">{E(p["opp"])} #{ash}</i><b>in</b><i class="nbg">shots allowed</i></span>'
    tip_g = f"{p['opp']} rank #{ag} of {n} in goals allowed, adjusted for opponents (1 = allow the most)"
    tip_s = f"{p['opp']} rank #{ash} of {n} in shots allowed, adjusted for opponents (1 = allow the most)"
    tot = p["tot"]; per = p.get("per90") or {}
    f2 = lambda x: "–" if x is None else f"{x:.2f}"
    chips = (f'<span class="sc" data-k="goal" style="--c:{cg}" title="{E(tip_g)}"><small>To score</small><b>{pct(p["p_goal"])}</b>{mu_g}<span class="fd">{tot["goals"]} goal{"s" if tot["goals"] != 1 else ""} in {p["mins"]} min <small class="fdo">2+: {pct(p["p_goal2"])}</small></span></span>'
             f'<span class="sc" data-k="assist" style="--c:{cg}" title="{E(tip_g)}"><small>An assist</small><b>{pct(p["p_assist"])}</b>{mu_g}<span class="fd">{tot["assists"]} this season</span></span>'
             f'<span class="sc" data-k="shots" style="--c:{cs}" title="{E(tip_s)}"><small>Shots</small><b>{p["shots"]:.1f}</b>{mu_s}<span class="fd">{f2(per.get("shots"))} per 90 <small class="fdo">{tot["shots"]} taken</small></span></span>'
             f'<span class="sc" data-k="sot" style="--c:{cs}" title="{E(tip_s)}"><small>On target</small><b>{p["sot"]:.1f}</b>{mu_s}<span class="fd">{f2(per.get("sot"))} per 90 <small class="fdo">{tot["sot"]} this season</small></span></span>')
    lad = ""
    for k, cap in (("shots", "Shots"), ("sot", "Shots on target")):
        rungs = [r for r in (p["ladder"].get(k) or []) if r[1] >= 0.03]
        if rungs: lad += f'<li><span>{cap}</span>' + "".join(f'<em><b>{L}+</b>{pct(pr)}</em>' for L, pr in rungs) + '</li>'
    flags = []
    if tag: flags.append(("watch", f"{tag} to play" if tag.endswith("%") else tag, st.get("why") or "Listed by the Fantasy Premier League."))
    if xi == "bench": flags.append(("watch", "On the bench", "The confirmed line-up has him among the substitutes. These numbers are for a start."))
    elif xi == "no": flags.append(("watch", "Not in the squad", "He is not in the confirmed line-up or on the bench."))
    elif xi is None and p["starts5"] < REGULAR:
        flags.append(("info", "Not a regular starter", f"He started {p['starts5']} of his club's last 5 matches and played in {p['apps5']}. These numbers are for a start."))
    fl = ""
    if flags:
        fl = ('<details class="flags"><summary>' + "".join(f'<span class="fg {c}">{E(h)}</span>' for c, h, _ in flags) + '<i class="more">tap for the note ▾</i></summary><ul>'
              + "".join(f'<li class="{c}"><b>{E(h)}</b>{E(tx)}</li>' for c, h, tx in flags) + '</ul></details>')
    rec = ""
    if p.get("recent"):
        rec = ('<table class="nbl5"><caption>His last ' + str(len(p["recent"])) + ' appearances</caption><thead><tr><th>Date</th><th>Opp</th><th>Min</th><th>G</th><th>A</th><th>Sh</th><th>On tgt</th></tr></thead><tbody>'
               + "".join("<tr>" + "".join(f"<td>{E(str(c))}</td>" for c in g[:7]) + "</tr>" for g in reversed(p["recent"])) + "</tbody></table>")
    rk = ranks.get((p["id"], p["match"]))
    w = 0 if not top else max(4.0, min(100.0, p["p_goal"] / top * 100))
    tags = (f'<i class="nbtag t-q">{E(tag)}</i>' if tag else "") + ('<i class="nbtag t-p">XI</i>' if xi == "start" else ('<i class="nbtag t-d">Bench</i>' if xi == "bench" else ""))
    return (f'<li class="pl pos-{p["pos"]}{"" if regular(p) else " eplsub"}" data-pid="{E(p["id"])}"> <button type="button" class="prow" aria-expanded="false"><span class="pos" title="{E(spot_name(spot(p)))}">{E(spot(p))}</span>'
            f'<span class="who"><span class="nm">{E(p["name"])}{tags}</span><span class="role sn" title="Starts in his club\'s last five matches; minutes when he starts: about {p["start_min"]}">{E(role)}</span></span> '
            f'<span class="ppr"><span class="v"><small>Scores</small>{pct(p["p_goal"])}<small>if he starts</small></span><i style="--w:{w:.1f}%"></i><span class="rk">{("#" + str(rk) + " " + spot(p)) if rk else ""}</span></span><i class="car" aria-hidden="true">▾</i></button> '
            f'<div class="pdetail" hidden><div class="sl">{chips}</div>' + (f'<ul class="nblad" aria-label="Chance of each line, model only, if he starts">{lad}</ul>' if lad else "") + fl + rec + '</div></li>')


def team_col(ab, m, B, top, ranks):
    t = B["teams"][ab]; opp = m["away"] if m["home"] == ab else m["home"]; o = B["teams"][opp]; n = B.get("n_clubs") or 20
    ag, ash = allow_rank(o["def"][0], n), allow_rank(o["shots_against"][0], n)
    dm = (f'<span class="dm" style="--c:{N.rank_color(ag, n)}" title="{E(opp)} rank #{ag} of {n} in goals allowed, adjusted for opponents (1 = allow the most)"><span class="dl">Goals</span><b>#{ag}</b></span>'
          f'<span class="dm" style="--c:{N.rank_color(ash, n)}" title="{E(opp)} rank #{ash} of {n} in shots allowed, adjusted for opponents (1 = allow the most)"><span class="dl">Shots</span><b>#{ash}</b></span>')
    dsum = f'<li class="dsum">{N.badge(ab, t)}<span>vs {E(opp)} D</span><span class="dgrid">{dm}</span></li>'
    bits = [x for x in ((t.get("record") or ""), (f"form {t['form']}" if t.get("form") else ""), (f"attack #{t['att'][0]}, defence #{t['def'][0]} of {n}")) if x]
    note = f'<li class="nbrest">{E(" · ".join(bits))}</li>'
    inj = (('<li class="inj"><span>Out</span>' + "".join(f'<em>{E(x["name"])} <small>{E((x.get("why") or x["tag"]).split(" - ")[0])}</small></em>' for x in t["out"]) + '</li>') if t.get("out")
           else ('<li class="nbnoout">No injury list is read for this league yet.</li>' if B.get("no_availability") else '<li class="nbnoout">Nobody listed out.</li>'))
    doubt = ('<li class="inj nbback epldoubt"><span>Doubts</span>' + "".join(f'<em>{E(x["name"])} <small>{E(x["tag"])} to play{" · " + E((x.get("why") or "").split(" - ")[0]) if x.get("why") else ""}</small></em>' for x in t["doubt"]) + '</li>') if t.get("doubt") else ""
    ps = sorted([p for p in B["players"] if p["team"] == ab and p["match"] == m["id"]], key=lambda p: (not regular(p), -p["p_goal"], p["name"]))
    if not ps:
        body = '<li class="nbnone">No projections yet for this club.</li>'
    else:
        reg = [p for p in ps if regular(p)]; oth = [p for p in ps if not regular(p)]
        body = "".join(player_li(p, top, ranks, B) for p in reg)
        if oth: body += f'<li class="epldiv">{"Not in the eleven" if m.get("lineups") else "Others who have played lately"} <small>numbers are for a start</small></li>' + "".join(player_li(p, top, ranks, B) for p in oth)
    return f'<ul class="col" data-team="{E(ab)}">{dsum}{note}{inj}{doubt}{body}</ul>'


def match_card(m, B, ranks):
    h, a = m["home"], m["away"]; th, ta = B["teams"][h], B["teams"][a]
    p = m["p"]
    score = (f'<span class="pt">{m["xg"]["home"]:.2f}</span><span class="dash">–</span><span class="pt">{m["xg"]["away"]:.2f}</span>'
             f'<small>{E(h)} {pct(p["home"])} · draw {pct(p["draw"])} · {E(a)} {pct(p["away"])}</small>')
    ko = int(when(m["ko"]).timestamp() * 1000) if when(m["ko"]) else 0
    band = ""
    if m.get("state") in ("in", "post") and m.get("score"):
        head = "Full time" if m["state"] == "post" else "In play"
        band = f'<div class="nbstate s-{m["state"]}"><b>{head}</b><span>{E(h)} {E(str(m["score"].get("home")))} · {E(a)} {E(str(m["score"].get("away")))}</span>' + (f'<small>{E(m.get("detail") or "")} when this page was built</small>' if m["state"] == "in" else "") + '</div>'
    line = m.get("line") or {}
    mk = ""
    if line.get("details") or line.get("total") is not None:
        txt = " · ".join(x for x in ((line.get("details") or ""), (f"O/U {line['total']:g}" if isinstance(line.get("total"), (int, float)) else "")) if x)
        who = (line.get("by") or "the sportsbook ESPN shows").replace("Draft Kings", "DraftKings")
        mk = f'<i>·</i><span class="mkt" title="{E(who)} line as shown by ESPN - not FanDuel">{E(txt)} <small>{E(who)}</small></span>'
    ginfo = f'<div class="ginfo"><span class="gk">{E(m["koct"])} CT</span>' + (f'<i>·</i><span>{E(m["venue"])}</span>' if m.get("venue") else "") + mk + '</div>'
    px = price_strip(m, h, a)
    best = m["scores"][0]
    mkts = (f'<div class="eplmk" aria-label="The model\'s chances for this match"><span><small>Over 2.5</small><b>{pct(p["over25"])}</b></span><span><small>Both score</small><b>{pct(p["btts"])}</b></span>'
            f'<span><small>Likeliest</small><b>{E(best[0])} <i>{pct(best[1])}</i></b></span><span><small>Shots</small><b>{m["shots"]["home"]:.0f}–{m["shots"]["away"]:.0f}</b></span></div>')
    top = max([x["p_goal"] for x in B["players"] if x["match"] == m["id"] and regular(x)] or [x["p_goal"] for x in B["players"] if x["match"] == m["id"]] or [0])
    nout = sum(len(B["teams"][x].get("out") or []) + len(B["teams"][x].get("doubt") or []) for x in (h, a))
    xi = ' <i class="eplxi">line-ups in</i>' if m.get("lineups") else ""
    return (f'<section class="card" id="{E(m["key"])}" data-ko="{ko}"> <header class="hd"> <div class="tm a">{N.badge(h, th)}<b>{E(h)}</b><span>{E(HEADNAME.get(th["name"], th["name"]))}</span></div> '
            f'<div class="score">{score}{N.SWOOSH}</div> <div class="tm b">{N.badge(a, ta)}<b>{E(a)}</b><span>{E(HEADNAME.get(ta["name"], ta["name"]))}</span></div> </header> {band}{ginfo}{mkts}{px}'
            f'<div class="vbtns"><button type="button" class="vbtn" data-view="proj">Projections{xi}</button><button type="button" class="vbtn" data-view="out">Who\'s out <small>{nout}</small></button></div>'
            f'<div class="cols">{team_col(h, m, B, top, ranks)}{team_col(a, m, B, top, ranks)}</div>'
            f'<footer class="nbfoot"><span>The score is each side\'s expected goals; home side first. Bar: chance to score if he starts, scaled to this match\'s likeliest scorer · tap a player for assists, shots and his last five</span></footer> </section>')


def american(v): return ("+" if v > 0 else "−") + str(abs(int(round(v))))


def price_strip(m, h, a):
    """owner 11/24 (three-way prices on the soccer cards): the posted home / draw / away price, what each price says once the book's cut
    is taken out, and the model's chance beside it. Shown only when all three prices are posted. Never an edge and never a pick: the
    record block says which of the two has been closer so far."""
    from sports.epl import grade as G
    line = m.get("line") or {}; mk = G.market(line); p = m.get("p") or {}
    if not mk or not all(isinstance(p.get(k), (int, float)) for k in ("home", "draw", "away")):
        return ""
    who = (line.get("by") or "the sportsbook ESPN shows").replace("Draft Kings", "DraftKings")
    cell = lambda lab, k: (f'<span data-k="{k}"><small>{E(lab)}</small><b>{american(line[k + "_ml"])}</b><i>price {pct(mk[k])}</i><i>model {pct(p[k])}</i></span>')
    return (f'<div class="eplpx" aria-label="The posted price for home, draw and away, and the model beside it">{cell(h, "home")}{cell("Draw", "draw")}{cell(a, "away")}'
            f'<em>Posted price: {E(who)}, as ESPN showed it when this board was built - not FanDuel. "Price" is what it implies with the book\'s cut taken out. Not a pick.</em></div>')


def summary_card(B, ranks):
    key = {m["id"]: m["key"] for m in B["matches"]}
    ml = ""
    for m in B["matches"]:
        p = m["p"]; fav = max((("home", m["home"]), ("draw", "draw"), ("away", m["away"])), key=lambda x: p[x[0]])
        st = "Full time" if m.get("state") == "post" else ("In play" if m.get("state") == "in" else m["koct"])
        ml += (f'<li><span class="bl-p"><a href="#{E(m["key"])}">{E(m["home"])} v {E(m["away"])}</a></span><span class="bl-m">{E(st)} <small>model {m["xg"]["home"]:.1f}–{m["xg"]["away"]:.1f}</small></span>'
               f'<span class="bl-n">{E(fav[1])} {pct(p[fav[0]])}</span></li>')
    reg = [p for p in B["players"] if regular(p)]
    sc = sorted(reg, key=lambda p: (-p["p_goal"], p["name"]))[:6]
    sl = "".join(f'<li><span class="bl-p"><a href="#{E(key[p["match"]])}" data-open="{E(p["id"])}">{E(p["name"])}</a></span><span class="bl-m">{pct(p["p_goal"])} to score <small>{p["shots"]:.1f} shots</small></span><span class="bl-n">{E(p["team"])} <small>{"v" if p["home"] else "at"} {E(p["opp"])}</small></span></li>' for p in sc)
    sh = sorted(reg, key=lambda p: (-p["shots"], p["name"]))[:6]
    hl = "".join(f'<li><span class="bl-p"><a href="#{E(key[p["match"]])}" data-open="{E(p["id"])}">{E(p["name"])}</a></span><span class="bl-m">{p["shots"]:.1f} shots <small>{p["sot"]:.1f} on target</small></span><span class="bl-n">{E(p["team"])} <small>{"v" if p["home"] else "at"} {E(p["opp"])}</small></span></li>' for p in sh)
    n = len(B["matches"])
    return (f'<section class="card summary" id="summary"> <header class="hd"><div class="tm a"><b>Slate</b><span>{E(round_label(B))} at a glance</span></div><div class="score"><span class="pt">{n}</span><small>match{"es" if n != 1 else ""} on the board</small>{N.SWOOSH}</div>'
            f'<div class="tm b"><span>BetSweep model</span></div></header> <div class="sumgrid"> <div><h3>Matches <small>kickoff (CT), expected goals, the likeliest result</small></h3><ul class="bl">{ml}</ul></div> '
            f'<div><h3>Likeliest scorers <small>regular starters, if they start</small></h3><ul class="bl">{sl}</ul></div> <div><h3>Most shots <small>regular starters, if they start</small></h3><ul class="bl">{hl}</ul></div> </div> </section>')


def round_label(B):
    g = B.get("gameweeks") or []
    return ("Gameweek " + str(g[0])) if len(g) == 1 else (f"Gameweeks {g[0]} and {g[-1]}" if g else "Coming up")


def round_name(gw):
    """a row of the grading record, by name: a Premier League gameweek, or - for a league without gameweeks - the week a match was played
    in, which the board names by its Tuesday (20261124: sports/soccer/publish.py week_key)"""
    if not isinstance(gw, int) or gw <= 0: return "Other matches"
    if gw < 1000: return f"Gameweek {gw}"
    try:
        d = dt.date(gw // 10000, gw // 100 % 100, gw % 100)
        return f"Week of {d.strftime('%b')} {d.day}"
    except Exception:
        return "Other matches"


RBAND = ("under 20%", "20 to 40%", "40 to 60%", "60 to 80%", "80% and up")       # sports/epl/grade.py EDGES
GBAND = ("under 5%", "5 to 10%", "10 to 20%", "20 to 30%", "30% and up")        # GOAL_EDGES
EARLY = 60                                   # matches before the record stops calling itself too small (six full rounds)


def record_block(R):
    """The grading record (sports/epl/grade.py), as the page shows it. Three states, each saying only what is true:
    no record file in reach - nothing is shown; a record with no graded match yet - it says how many are locked and waiting;
    graded matches - the model beside "every match alike" on results, totals and both-to-score, the chances it gave against how often
    they happened, then the players who started beside their own season averages, the rounds, and what was left out."""
    if not R or not isinstance(R.get("total"), dict):
        return ""
    from sports.epl import grade as G
    S = G.summary(R)
    missed = len(R.get("missed") or {})
    w, pw = R.get("waiting") or 0, R.get("pwaiting") or 0
    if not S:
        return ('<p class="nbrec none" id="nbrec"><b>Grading has started.</b> '
                + (f'{w} match{"es are" if w != 1 else " is"} locked and waiting for {"their final scores" if w != 1 else "its final score"}; the first results appear here.' if w
                   else 'Each match is locked at kickoff and scored against the final result; the first results appear here.') + '</p>')
    T = G.add(G.empty(), R["total"])
    f1, f2, f3 = (lambda x: f"{x:.1f}"), (lambda x: f"{x:.2f}"), (lambda x: f"{x:.3f}")
    plural = lambda n, one, many: one if n == 1 else many
    res, pl = S.get("res"), S.get("pl")
    head = (f'<summary><b>Graded so far</b><span class="nbrc-n">{S["matches"]} {plural(S["matches"], "match", "matches")}' + (f' · {pl["n"]} starters' if pl else '') + '</span>'
            + (f'<span class="nbrc-l">likeliest result right {res["top"]} of {res["n"]} <i>(the home side every time: {res["btop"]})</i></span>' if res else '') + '</summary>')

    def row(k, lab, x, fmt):
        m, b = fmt(x["model"]), fmt(x["base"])
        who = "same" if m == b else ("model" if x["model"] < x["base"] else "other")
        return (f'<tr data-k="{k}"><th>{lab}</th><td class="{"win" if who == "model" else ""}">{m}</td><td class="{"win" if who == "other" else ""}">{b}</td>'
                f'<td class="nbrc-w">{"model closer" if who == "model" else ("model behind" if who == "other" else "the same")}</td></tr>')
    rows = "".join(row(k, lab, S[k], f2) for k, lab in (("res", "Home, draw or away"), ("o25", "Over 2.5 goals"), ("btts", "Both teams score")) if S.get(k))
    if S.get("goals"): rows += row("goals", "Goals a side <i>(average miss)</i>", S["goals"], f2)
    table = ('<table class="nbrc-t"><thead><tr><th>Miss score, lower is better</th><th>Model</th><th>Every match alike</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>') if rows else ""
    mkt = S.get("mkt"); mtab = ""
    if mkt:
        def mrow(k, lab, x, extra=""):
            m_, p_ = f2(x["model"]), f2(x["price"])
            who = "same" if m_ == p_ else ("model" if x["model"] < x["price"] else "price")
            return (f'<tr data-k="{k}"><th>{lab}</th><td class="{"win" if who == "model" else ""}">{m_}</td><td class="{"win" if who == "price" else ""}">{p_}</td>'
                    f'<td class="nbrc-w">{"model closer" if who == "model" else ("the price closer" if who == "price" else "the same")}{extra}</td></tr>')
        mrows = mrow("mk_res", "Home, draw or away", mkt, f' <i>(likeliest right: model {mkt["mtop"]}, price {mkt["ptop"]} of {mkt["n"]})</i>')
        if mkt.get("o25"): mrows += mrow("mk_o25", f'Over 2.5 goals <i>({mkt["o25"]["n"]} with a 2.5 line)</i>', mkt["o25"])
        mtab = (f'<table class="nbrc-t nbrc-m"><thead><tr><th>Against the posted price <i>({mkt["n"]} {plural(mkt["n"], "match", "matches")} that had one)</i></th><th>Model</th><th>The price</th><th></th></tr></thead><tbody>' + mrows + '</tbody></table>')
    crow = "".join(f'<tr><th>{RBAND[i]}</th><td>{round(100 * c[1] / c[0])}%</td><td>{round(100 * c[2] / c[0])}%</td><td class="nbrc-w">{c[0]} {plural(c[0], "chance", "chances")}</td></tr>' for i, c in enumerate(T["cal"]) if c[0])
    ctab = ('<table class="nbrc-t nbrc-c"><thead><tr><th>Chance the board gave</th><th>Happened</th><th>Board said</th><th></th></tr></thead><tbody>' + crow + '</tbody></table>') if crow else ""
    notes, ptab, gtab = [], "", ""
    if pl:
        prow = "".join(row("p_" + k, lab, pl[k], fmt) for k, lab, fmt in (("goal", "To score <i>(miss score)</i>", f3), ("assist", "An assist <i>(miss score)</i>", f3),
                                                                                             ("shots", "Shots <i>(average miss)</i>", f2), ("sot", "On target <i>(average miss)</i>", f2))
                       if pl.get(k) and pl[k].get("model") is not None and pl[k].get("base") is not None)
        ptab = ('<table class="nbrc-t nbrc-p"><thead><tr><th>Players who started</th><th>Model</th><th>Season avg</th><th></th></tr></thead><tbody>' + prow + '</tbody></table>') if prow else ""
        grow = "".join(f'<tr><th>{GBAND[i]}</th><td>{round(100 * c[1] / c[0])}%</td><td>{round(100 * c[2] / c[0])}%</td><td class="nbrc-w">{c[0]} {plural(c[0], "starter", "starters")}</td></tr>' for i, c in enumerate(T["pl"]["cal"]["goal"]) if c[0])
        gtab = ('<table class="nbrc-t nbrc-c nbrc-g"><thead><tr><th>Chance to score the board gave</th><th>Scored</th><th>Board said</th><th></th></tr></thead><tbody>' + grow + '</tbody></table>') if grow else ""
        g = pl["goal"]
        if g["n"]: notes.append(f'The board expected {f1(g["exp"])} scorers among {g["n"]} starters; {g["hit"]} scored.')
        if pl["reg"]: notes.append(f'Of the {pl["reg"]} players it listed as regulars, {pl["reg_start"]} started.')
        if pl["sub"] or pl["dnp"]: notes.append(f'{pl["sub"]} came on and {pl["dnp"]} did not play: counted here, not graded, because every player number assumes a start.')
        if pl.get("min"): notes.append(f'Starters\' minutes were off by {round(pl["min"]["mae"])} on average.')
    if pw: notes.append(f'Player results for {pw} {plural(pw, "match", "matches")} are still to come.')
    if w: notes.append(f'{w} {plural(w, "match is", "matches are")} locked and waiting for a final score.')
    if missed: notes.append(f'{missed} {plural(missed, "match", "matches")} could not be graded: no board had been built before kickoff.')
    beyond = len(R.get("beyond") or {})
    if beyond: notes.append(f'{beyond} {plural(beyond, "match", "matches")} went to extra time or penalties: graded as the draw {plural(beyond, "it was", "they were")} at ninety minutes, '
                            f'with {plural(beyond, "its", "their")} goals and players left out.')
    rounds = ""
    for r in (R.get("rounds") or [])[-5:][::-1]:
        rr = (r.get("res") or {})
        rounds += (f'<li><b>{round_name(r.get("gw"))}</b> {r.get("matches", 0)} {plural(r.get("matches", 0), "match", "matches")}'
                   + (f', likeliest result right {rr.get("top", 0)} of {rr["n"]}' if rr.get("n") else '') + '</li>')
    early = ('<p class="nbrc-early">Early days: ' + (f'{S["matches"]} matches are' if S["matches"] != 1 else 'one match is') + ' too few to judge a model by. Nothing here is a pick yet.</p>') if S["matches"] < EARLY else ""
    how = ('<p class="nbrc-how">Each match\'s numbers are locked from the last board built before kickoff and are not changed afterwards. '
           '"Every match alike" is the same model given two average sides: what it would say knowing nothing about the clubs. '
           'A miss score is the squared gap between the chance given and what happened, so 0 is perfect. '
           + ('"The price" is the sportsbook price ESPN showed at the lock with the book\'s cut taken out - the bar the model has to beat before anything here is a pick. ' if mkt else '')
           + 'Players are graded only when they started.</p>')
    return (f'<details class="nbrec" id="nbrec">{head}<div class="nbrc-b">{early}{table}{mtab}{ctab}{ptab}{gtab}' + (f'<p class="nbrc-notes">{" ".join(notes)}</p>' if notes else '')
            + (f'<ul class="nbrc-nights">{rounds}</ul>' if rounds else '') + how + '</div></details>')


# Soccer's tile (N.plays_css): a goal from the front with its net, a ball on a dashed line toward it, the centre circle and spot on the
# halfway line, a corner arc with its flag, and the penalty area with its arc and spot. One tile for every soccer league.
PITCH = ('<svg xmlns="http://www.w3.org/2000/svg" width="360" height="130" viewBox="0 0 360 130" fill="none" stroke="INK" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
         '<path d="M10 118h88M24 118V78h60v40"/>'
         '<path d="M36 78v40M48 78v40M60 78v40M72 78v40M24 91h60M24 104h60" stroke-width="0.800"/>'
         '<circle cx="140" cy="38" r="13"/><path d="M140 32.500l5.200 3.800-2 6.100h-6.400l-2-6.100zM140 32.500V25M145.200 36.300l7.200-2.300M143.200 42.400l4.400 6.100M136.800 42.400l-4.400 6.100M134.800 36.300l-7.200-2.300"/>'
         '<path d="M126 46C112 58 104 66 94 78" stroke-dasharray="4 4"/><path d="M103 77l-9 2 2-9.500"/>'
         '<path d="M232 46v64"/><circle cx="232" cy="78" r="17"/><circle cx="232" cy="78" r="1.200"/>'
         '<path d="M296 16h44v32M330 16a10 10 0 0 0 10 10M340 16V5l9 3.500-9 3.500"/>'
         '<path d="M270 124h76M284 124V98h48v26M296 98a13 11 0 0 1 24 0"/><circle cx="308" cy="111" r="1.200"/>'
         '</svg>')
PITCH_CSS = N.plays_css(PITCH)

EPL_CSS = """
.eplmk{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:8px 12px 4px}
.eplmk span{min-width:0;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:10px;padding:5px 8px;background:color-mix(in srgb,var(--ink) 4%,transparent)}
.eplmk small{font-size:11.5px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .eplmk b{font-family:var(--display);font-weight:700;font-size:18px;line-height:1.15;color:var(--ink);white-space:nowrap}
.eplmk i{font-style:normal;font-family:var(--body);font-weight:500;font-size:11.5px;color:var(--mute)}
.eplpx{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:4px 12px 6px}
.eplpx span{min-width:0;display:flex;flex-direction:column;border:1px dashed var(--line);border-radius:10px;padding:5px 8px}
.eplpx small{font-size:11.5px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .eplpx b{font-family:var(--display);font-weight:700;font-size:18px;line-height:1.15;color:var(--ink);white-space:nowrap}
.eplpx i{font-style:normal;font-size:11.5px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .eplpx em{grid-column:1 / -1;font-style:normal;font-size:11.5px;line-height:1.35;color:var(--mute)}
@media (max-width:760px){ .eplpx{gap:4px;padding:4px 10px 6px} .eplpx span{padding:5px 6px} .eplpx b{font-size:16px} .eplpx i{font-size:10.5px} }
body.compact .card:not(.expanded) > .eplmk{display:grid}
@media (max-width:760px){ .eplmk{gap:4px;padding:8px 10px 4px} .eplmk span{padding:5px 6px} .eplmk small{font-size:10.5px} .eplmk b{font-size:16px} .eplmk i{font-size:10.5px} }
.epldiv{list-style:none;margin:10px 0 2px;padding:6px 2px 4px;border-top:1px dashed var(--line);font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute)}
.epldiv small{font-family:var(--body);font-weight:500;font-size:12px;letter-spacing:0;text-transform:none;margin-left:6px}
.card.expanded[data-view="out"] .epldiv{display:none}
li.pl.eplsub .ppr .v{opacity:.72}
.eplxi{font-style:normal;font-family:var(--body);font-size:11px;font-weight:600;letter-spacing:0;text-transform:none;color:var(--good);margin-left:6px}
.pl .pos{min-width:40px}
.nblg{flex:1 0 100%;order:5;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding-bottom:2px} .nblg::-webkit-scrollbar{display:none} .nblg a{flex:0 0 auto;white-space:nowrap}
"""


# On a phone the league row is wider than the screen and scrolls sideways: bring this page's own league into view (MLS is the last pill).
LG_JS = r"""<script>(function(){ var r = document.querySelector('.nblg'), a = r && r.querySelector('a[aria-current]'); if (!a) return;
  r.scrollLeft += a.getBoundingClientRect().left - r.getBoundingClientRect().left - (r.clientWidth - a.offsetWidth) / 2; })();</script>"""


def page(B, nba=False, R=None, have=None, cfg=None):
    cfg = cfg or sport_nav.LEAGUE["epl"]; name = cfg["name"]; epl = cfg["key"] == "epl"
    css = re.search(r"<style[^>]*>(.*?)</style>", open(os.path.join(HERE, "template.html"), encoding="utf-8").read(), re.S).group(1)
    # this round's rank at each position by chance to score, regular starters only (a substitute's "if he starts" number is not ranked)
    ranks = {}
    for pos in sorted({spot(p) for p in B["players"]}):
        for i, p in enumerate(sorted([p for p in B["players"] if spot(p) == pos and regular(p)], key=lambda p: (-p["p_goal"], p["name"]))):
            ranks[(p["id"], p["match"])] = i + 1
    nav = '<a href="#summary">Slate</a> ' + " ".join(f'<a href="#{E(m["key"])}">{E(m["home"])}·{E(m["away"])}</a>' for m in B["matches"])
    n = len(B["matches"]); rl = round_label(B)
    desc = (f"{name} matchup boards, {rl.lower()}: the model's expected goals and result chances for {n} match{'es' if n != 1 else ''}, each regular's chance to score, his shots, "
            "who is out, and what each defence allows. A preview: model numbers only.")
    last = max(when(m["ko"]) for m in B["matches"])
    try:
        from zoneinfo import ZoneInfo
        last_day = last.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
    except Exception:
        last_day = (last - dt.timedelta(hours=6)).date().isoformat()
    rec = record_block(R)
    pre = (f'<div class="nbpre"><b>{E(name)} preview.</b> Model numbers only: no FanDuel prices yet, so no edges or betslip buttons. Where ESPN posts a sportsbook price it is shown beside the model for comparison. '
           'Player numbers assume he starts. ' + ('' if epl else 'This league has no expected-goals data, so a shot-based stand-in is used, and no injury list is read yet. ')
           + ('Nothing here is a pick: every match is locked at kickoff and graded against the result first.' if rec else 'Nothing here is a pick.') + '</div>')
    key = ('<details class="nbkey"><summary aria-label="How to read the board"><span class="nbk-l">How to read the board</span><span class="nbk-s" aria-hidden="true">?</span></summary><dl>'
           '<dt>Score</dt><dd>Each side\'s expected goals, home side first, and under it the chance of a home win, a draw and an away win. The posted line beside the kickoff time is the sportsbook line ESPN shows, named there; it is not FanDuel\'s.</dd>'
           '<dt>Bar and number</dt><dd>A player\'s chance to score <b>if he starts</b>, with the bar scaled to the match\'s likeliest scorer. The tag after it is his place among ' + ("this round\'s" if B.get("gameweeks") else "this board\'s") + ' regular starters at his position.</dd>'
           + (('<dt>Position</dt><dd>Where he usually lines up, read from how ESPN drew his side in his last ten starts: <b>ST</b> striker, <b>LW RW</b> wings, <b>CAM</b> attacking mid, <b>CM</b> center mid, '
               '<b>CDM</b> defensive mid, <b>LM RM</b> wide mids, <b>LB RB</b> full backs, <b>LWB RWB</b> wing-backs, <b>CB</b> center back, <b>GK</b>. Once the elevens are in, it is where he lines up in this match. '
               + ('A player with no start this season keeps the fantasy list\'s group: DEF, MID or FWD.' if epl else '<b>SUB</b>: he has only come off the bench this season, so there is no position to go on.') + '</dd>')
              if any(p.get("role") for p in B["players"]) else "")
           + '<dt>Started N of last 5</dt><dd>The model does not pick line-ups. Players who started three or more of the club\'s last five matches are listed first; the rest sit under a line. When the confirmed elevens are in, about an hour before kickoff, each player is marked in the eleven or on the bench.</dd>'
           '<dt>Chips</dt><dd>Tap a player. Each chip is a projection; its color is how much the opponent allows - goals for scoring and assists, shots for shots - #1 (green) allows the most and #' + str(B.get("n_clubs") or 20) + ' (red) the least.</dd>'
           + ('<dt>Out and doubts</dt><dd>From the official Fantasy Premier League list. A player listed out or suspended has no numbers; a doubt keeps his, with his chance of playing.</dd>' if not B.get("no_availability")
              else '<dt>Who\'s out</dt><dd>No injury list is read for this league yet, so nobody is marked out. Check the team news before trusting a player\'s number; the confirmed elevens still mark who starts.</dd>')
           + '</dl></details>')
    chk = ("".join(f"<li>{E(c)}</li>" for c in B.get("checks") or []))
    stamp_epl = (f'<p class="nbstamp">Built {N.fmt_ct(B.get("built"))} from {B.get("played")} matches through {E(B.get("data_through") or "?")}. Match data: the public FPL-Elo-Insights data set; fixtures, kickoff times and line-ups: ESPN; availability: the official Fantasy Premier League list'
             + (f' as of {N.fmt_ct(B.get("fpl_at"))}' if B.get("fpl_at") else '') + '. Every fixture is checked against ESPN before it is shown. '
             'Projections: BetSweep\'s Premier League model (an attack and a defence rating for every club, fitted on expected goals and goals; players by minutes and per-90 rates against what the opponent allows). '
             'In tests its home / draw / away chances were level with a plain Elo rating and well ahead of flat rates; its totals were no better than last season\'s flat rate; its scorer and shots numbers beat a player\'s own hit rate on about 100 matches of 2026-27. '
             'That is thin evidence: a first look, not a record. For entertainment; not betting advice.</p>'
             + (f'<ul class="nbstamp eplchk">{chk}</ul>' if chk else ""))
    st = B.get("standin") or {}
    wp, npl = B.get("with_players"), B.get("played") or 0
    part = (f' Player lines are in for {wp} of those matches so far, so the player numbers rest on part of the season.' if isinstance(wp, int) and wp < 0.95 * npl else '')
    stamp_other = (f'<p class="nbstamp">Built {N.fmt_ct(B.get("built"))} from {B.get("played")} matches through {E(B.get("data_through") or "?")}.{part} Results, shots, player lines, fixtures, line-ups and the posted prices: ESPN'
                   + (f' as of {N.fmt_ct(B.get("espn_at"))}' if B.get("espn_at") else '') + '. '
                   'Projections: the Premier League model on this league\'s own matches (an attack and a defence rating for every club; players by minutes and per-90 rates against what the opponent allows). '
                   'One difference matters: there are no expected goals for this league, so a shot-based stand-in is used in their place'
                   + (f' (a shot on target counts {st["on_target"]:.2f} of a goal, one off target {st["off_target"]:.2f})' if st else '') + '. '
                   'That is weaker evidence than expected goals and it has not been tested on past seasons here, so treat every number as a first look. No injury list is read for this league yet. '
                   'For entertainment; not betting advice.</p>' + (f'<ul class="nbstamp eplchk">{chk}</ul>' if chk else ""))
    stamp = stamp_epl if epl else stamp_other
    cards = "\n".join(match_card(m, B, ranks) for m in B["matches"])
    hv = have if have is not None else ({"nba": True} if nba else {})
    sw = sport_nav.switch(cfg["key"], hv) + sport_nav.leagues(cfg["key"], hv)      # NFL | CFB | NBA | Soccer, then the leagues: only pages in this build
    return (f'<title>BetSweep · {E(name)} Matchup Boards</title>\n<style>{css}</style>\n<style>{N.NB_CSS}</style>\n<style>{EPL_CSS}</style>\n<style>{PITCH_CSS}</style>\n'
            f'<div class="top">\n  <div class="mast">\n    <h1><small>{E(name)} · {E(rl)}</small><b>Matchup Boards</b></h1>\n    <p>{E(desc)}</p>\n  </div>\n  <nav class="nav" aria-label="jump to match">{nav}</nav>\n</div>\n'
            f'<div class="nbbar">{sw}{key}</div>\n{pre}\n{rec}\n'
            f'<div class="nbold" id="nbold" hidden><b>Every match on this board has kicked off.</b> A newer board is not up yet, so the numbers below are from before those matches.</div>\n'
            f'<div class="grid" data-day="{E(last_day)}">\n{summary_card(B, ranks)}\n{cards}\n</div>\n{stamp}\n{N.NB_JS}\n{LG_JS}\n')


def line_sig(line):
    """the posted line as a visitor would notice it change: which side is favored, and the total. Not the price ticking from -145 to -150:
    with five leagues that would send a page out every hour for nothing (each publish stays in the site's history for good)."""
    d = str((line or {}).get("details") or "")
    return [d.split(" ")[0] if d else None, (line or {}).get("total")]


def signature(B, R=None):
    """what a visitor would notice changing: the matches and their state, each posted line's favorite and total, each side's expected goals to a tenth, who is
    out or doubtful, whether the elevens are in, each player's chance to score to the whole percent - and the grading record's size (a newly graded match is news)"""
    tot = (R or {}).get("total") if isinstance((R or {}).get("total"), dict) else None
    return json.dumps([([tot.get("matches"), tot.get("pmatches"), (R or {}).get("waiting"), (R or {}).get("pwaiting"), len((R or {}).get("missed") or {}), len((R or {}).get("beyond") or {})] if tot else None),
                       [(m["key"], m.get("state"), line_sig(m.get("line")), round(m["xg"]["home"], 1), round(m["xg"]["away"], 1), bool(m.get("lineups"))) for m in B["matches"]],
                       sorted((ab, sorted(o["name"] for o in t.get("out") or []), sorted((o["name"], o["tag"]) for o in t.get("doubt") or [])) for ab, t in B["teams"].items()),
                       sorted((p["id"], p["match"], round(p["p_goal"] * 100), p.get("xi")) for p in B["players"])], sort_keys=True)


def main():
    a = sys.argv[1:]
    named = "--board" in a
    R = None
    if named:
        B = N.load(path=a[a.index("--board") + 1]); have = sport_nav.local(a, OUT); nba = bool(have.get("nba"))   # --nba / --with nba,cfb: draw those links (local work)
        if "--record" in a:
            try: R = json.load(open(a[a.index("--record") + 1], encoding="utf-8"))
            except Exception: R = None
    else:
        have = sport_nav.available(a[0] if a else None)       # fetches the branch; each sport's own rule says whether its page will be there to link to
        B = N.feed_file(a[0] if a else None, "epl/board.json"); nba = bool(have.get("nba"))
        R = N.feed_file(a[0] if a else None, "epl/record.json")      # the grading record (sports/epl/grade.py); None until the job has written one
    if not isinstance(R, dict) or R.get("sport") != "epl" or not isinstance(R.get("total"), dict):
        R = None
    ok, why = usable(B, any_age=named)
    outs = (PAGE, os.path.join(OUT, "epl_board.json"), os.path.join(OUT, "epl_sig.json"), os.path.join(OUT, "epl_record.json"))
    if not ok:
        for f in outs:
            if os.path.exists(f): os.remove(f)
        print(f"epl: no page written - {why}")
        return
    os.makedirs(OUT, exist_ok=True)
    open(PAGE, "w", encoding="utf-8").write(page(B, nba, R, have))
    json.dump(B, open(outs[1], "w"), separators=(",", ":"))
    json.dump({"built": B.get("built"), "sig": signature(B, R) + "|nav:" + ",".join(sorted(have))}, open(outs[2], "w"))
    if R: json.dump(R, open(outs[3], "w"), separators=(",", ":"))
    elif os.path.exists(outs[3]): os.remove(outs[3])
    T = (R or {}).get("total") or {}
    print(f"epl boards: {round_label(B)}, {len(B['matches'])} matches, {len(B['players'])} player rows, {sum(len(t.get('out') or []) for t in B['teams'].values())} out, "
          f"{sum(len(t.get('doubt') or []) for t in B['teams'].values())} doubts; board built {N.fmt_ct(B.get('built'))}; "
          + (f"record: {T.get('matches', 0)} matches graded, players of {T.get('pmatches', 0)}, {R.get('waiting', 0)} waiting; " if R else "no grading record in reach; ")
          + f"{os.path.getsize(PAGE) // 1024} KB -> {PAGE}")


if __name__ == "__main__":
    main()
