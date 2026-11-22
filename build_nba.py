#!/usr/bin/env python3
"""NBA Matchup Boards - the first page of BetSweep beyond the NFL (PREVIEW, not in the menu).

Owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl. I want each sport to basically look exactly like everything
we've built for NFL." The same hour he answered three questions: prices - "I will upgrade but start without prices"; the data jobs -
"Yes add them"; college football - "Post season game lines".

    python3 build_nba.py {clone}          the hourly build: reads nba/board.json from the feeds-sports branch through the clone
    python3 build_nba.py --board FILE     a board file on disk (tests, local work)
Writes out/nba-boards.html; build_site.py places it at /nba/. With no board in reach it writes nothing and removes a page left over
from an earlier run, so a dead feed can never leave an old slate looking current.

How it is made to look like the NFL boards: it wears the NFL boards' own stylesheet (the <style> block of template.html, read at build
time) and writes the same markup - section.card, header.hd with the two badges and the score, div.ginfo, ul.col with li.dsum / li.inj /
li.pl > button.prow + div.pdetail, span.sc stat chips coloured by what the defense allows. Only what the NBA needs and the NFL page has
no word for is new (.nb* classes, in NB_CSS, on the site's own colour variables).

What is NOT here yet, and the page says so: FanDuel prices (so no edges, no best parlay, no betslip buttons), and any pick. The numbers
are the model's alone (sports/nba, checked on 2026-27 results in a walk-forward test) and must be graded night by night before any of
them is promoted (that nightly grading is the next thing to build; the page does not claim it) - the owner's own
rule that a new tier starts tracked, not a lead.

The board file is written by sports/nba/publish.py in the feeds-sports job (that is where pandas lives). Every number on the page is
copied from it; this script computes only ranks for display (who is tonight's Nth guard by projected points), bar widths and colours.
"""
import datetime as dt, html, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
E = lambda s: html.escape(str(s), quote=True)
PAGE = os.path.join(OUT, "nba-boards.html")
GRP = {"G": "Guard", "F": "Forward", "C": "Center"}
GRPS = {"G": "guards", "F": "forwards", "C": "centers"}
STATS = [("pts", "points", "Points"), ("reb", "rebounds", "Rebounds"), ("ast", "assists", "Assists"), ("fg3", "threes", "Threes")]
# a nickname that is more than the last word of the team's name (ESPN's short name is used when the mirror carries it)
NICK = {"Portland Trail Blazers": "Trail Blazers"}
SWOOSH = ('<svg class="swoosh" viewBox="0 0 220 22" aria-hidden="true"><circle cx="9" cy="14" r="5.5" fill="none" stroke="#d7332a" stroke-width="3"/>'
          '<path d="M15 14.5 C 60 19, 120 19, 170 13 C 185 11, 196 8, 206 5" fill="none" stroke="#d7332a" stroke-width="3.4" stroke-linecap="round"/>'
          '<path d="M194 2.5 L 209 4.2 L 199 14" fill="none" stroke="#d7332a" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
# team colours when the mirror did not carry them (ESPN's own, 2026-27)
COL = {"ATL": ("c8102e", "fdb927"), "BOS": ("008348", "ffffff"), "BKN": ("000000", "ffffff"), "CHA": ("008ca8", "1d1060"), "CHI": ("ce1141", "000000"), "CLE": ("860038", "bc945c"),
       "DAL": ("0064b1", "bbc4ca"), "DEN": ("0e2240", "fec524"), "DET": ("1d428a", "c8102e"), "GS": ("fdb927", "1d428a"), "HOU": ("ce1141", "000000"), "IND": ("0c2340", "ffd520"),
       "LAC": ("12173f", "c8102e"), "LAL": ("5c2f83", "fdb927"), "MEM": ("5d76a9", "12173f"), "MIA": ("98002e", "000000"), "MIL": ("00471b", "eee1c6"), "MIN": ("266092", "79bc43"),
       "NO": ("0a2240", "b4975a"), "NY": ("1d428a", "f58426"), "OKC": ("007ac1", "ef3b24"), "ORL": ("0150b5", "9ca0a4"), "PHI": ("1d428a", "e01234"), "PHX": ("29127a", "e56020"),
       "POR": ("e03a3e", "000000"), "SAC": ("5a2d81", "6a7a82"), "SA": ("000000", "c4ced4"), "TOR": ("d91244", "000000"), "UTAH": ("4e008e", "79a3dc"), "WSH": ("e31837", "002b5c")}


FORMAT = 2   # sports/nba/publish.py FORMAT: the board shape this page reads


def nba_day(now=None):
    """the NBA day now: the Central date four hours ago, so a game that ends after midnight still belongs to the night it tipped (publish.py picks its day the same way)"""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        d = now.astimezone(ZoneInfo("America/Chicago"))
    except Exception:
        d = now.astimezone(dt.timezone(dt.timedelta(hours=-6)))
    return (d - dt.timedelta(hours=4)).date().isoformat()


def usable(B, now=None, any_day=False):
    """(ok, why not). A board is drawn only if it is in the shape this page reads, has games, and is not for a day already over:
    the feed job keeps its last good board when a run fails, so an old one can sit on the branch looking like today's."""
    if not B or not isinstance(B, dict): return False, "no nba/board.json in reach on the feeds-sports branch"
    if B.get("format") != FORMAT: return False, f"the board is format {B.get('format')!r}, this page reads format {FORMAT} (the feed job has not run with the matching publish.py yet)"
    if not B.get("games") or not B.get("players"): return False, "the board holds no games"
    if not any_day and str(B.get("day")) < nba_day(now): return False, f"the board is for {B.get('day')}, a day already over (today is {nba_day(now)}): the feed job is not producing a new one"
    return True, ""


def load(clone=None, path=None):
    if path:
        return json.load(open(path, encoding="utf-8"))
    if not clone or not os.path.isdir(clone):
        return None
    subprocess.run(["git", "-C", clone, "fetch", "-q", "--depth", "1", "origin", "+feeds-sports:refs/remotes/origin/feeds-sports"], capture_output=True, text=True)
    r = subprocess.run(["git", "-C", clone, "show", "origin/feeds-sports:nba/board.json"], capture_output=True)
    if r.returncode != 0:
        return None
    try: return json.loads(r.stdout)
    except Exception: return None


def lum(h):
    h = h.lstrip("#"); r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]; return 0.2126 * r + 0.7152 * g + 0.0722 * b
def badge(ab, t):
    p, s = (t.get("color") or COL.get(ab, ("444444", "999999"))[0]), (t.get("alt") or COL.get(ab, ("444444", "999999"))[1])
    if not re.fullmatch(r"[0-9a-fA-F]{6}", str(p)): p = "444444"
    if not re.fullmatch(r"[0-9a-fA-F]{6}", str(s)): s = "999999"
    ink = "#101820" if lum(p) > 0.45 else "#ffffff"
    return f'<span class="badge" style="--p:#{p};--s:#{s};--ink:{ink}">{E(ab)}</span>'
def nick(t):
    n = t.get("name") or ""
    return t.get("short") or NICK.get(n) or (n.split(" ")[-1] if n else "")
def rank_color(r, n=30):
    """the NFL boards' scale, stretched over 30 teams: 1 (allows the most) green -> 30 (allows the least) red"""
    t = (r - 1) / (n - 1)
    if t < 0.5: h = 140 - 95 * (t / 0.5); l = 0.30 + 0.08 * (t / 0.5)
    else: h = 45 - 45 * ((t - 0.5) / 0.5); l = 0.38 - 0.10 * ((t - 0.5) / 0.5)
    return f"hsl({h:.0f} 62% {l * 100:.0f}%)"
def f1(x): return "–" if x is None else f"{x:.1f}"
def pct(p): return f"{round(p * 100)}%"
def ordinal(n): return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def ladder_pick(lad):
    """the rungs worth showing for one stat: at most four, the ones nearest an even chance"""
    return sorted(sorted(lad, key=lambda x: abs(x[1] - 0.5))[:4], key=lambda x: x[0])


def player_li(p, team, top, ranks, B):
    opp = B["teams"][p["team"]]["opp"]; od = B["teams"][p["team"]].get("opp_def", {}).get(p["grp"], {})
    st = p.get("status") or {}
    tag = st.get("tag")
    role = f"~{round(p['min'])} min"
    chips = ""
    for k, lab, _ in STATS:
        r = od.get(k)
        c = rank_color(r[0]) if r else "var(--line)"
        mu = (f'<span class="mu"><i style="background:{c}">{E(opp)} #{r[0]}</i><b>vs</b><i class="nbg">{GRPS[p["grp"]]}</i></span>' if r else "")
        tip = (f"{opp} ranks #{r[0]} of 30 in {lab} allowed to {GRPS[p['grp']]} per minute this season (1 = allows the most)" if r else "")
        avg = p["avg"].get(k); l10 = p["l10"].get(k)
        chips += (f'<span class="sc" style="--c:{c}" title="{E(tip)}"><small>{lab}</small><b>{f1(p["proj"].get(k))}</b>{mu}'
                  f'<span class="fd">avg {f1(avg)}' + (f' <small class="fdo">last 10: {f1(l10)}</small>' if l10 is not None else "") + '</span></span>')
    lad = ""
    for k, lab, cap in STATS:
        rungs = ladder_pick(p["ladder"].get(k) or [])
        if rungs:
            lad += f'<li><span>{cap}</span>' + "".join(f'<em><b>{L}+</b>{pct(pr)}</em>' for L, pr in rungs) + '</li>'
    flags = []
    if tag: flags.append(("watch" if tag in ("Questionable", "Day-to-day") else "info", tag, st.get("why") or "Listed on the injury report."))
    for w in p.get("warn") or []:
        head, _, rest = w.partition(":")
        flags.append(("watch" if w.startswith("Fewer") else "info", head.strip(), (rest.strip().capitalize() + ".") if rest.strip() else "The projection leans on last season until he has played more."))
    fl = ""
    if flags:
        fl = ('<details class="flags"><summary>' + "".join(f'<span class="fg {c}">{E(h)}</span>' for c, h, _ in flags) + '<i class="more">tap for the note ▾</i></summary><ul>'
              + "".join(f'<li class="{c}"><b>{E(h)}</b>{E(t)}</li>' for c, h, t in flags) + '</ul></details>')
    rec = ""
    if p.get("recent"):
        rec = ('<table class="nbl5"><caption>His last ' + str(len(p["recent"])) + ' games</caption><thead><tr><th>Date</th><th>Opp</th><th>Min</th><th>Pts</th><th>Reb</th><th>Ast</th><th>3s</th></tr></thead><tbody>'
               + "".join("<tr>" + "".join(f"<td>{E(c)}</td>" for c in g) + "</tr>" for g in reversed(p["recent"])) + "</tbody></table>")
    rk = ranks.get(p["id"])
    w = 0 if not top else max(4.0, min(100.0, (p["proj"].get("pts") or 0) / top * 100))
    return (f'<li class="pl pos-{p["grp"]}" data-pid="{E(p["id"])}"> <button type="button" class="prow" aria-expanded="false"><span class="pos" title="{GRP[p["grp"]]}">{p["grp"]}</span>'
            f'<span class="who"><span class="nm">{E(p["name"])}' + (f'<i class="nbtag t-{tag[0].lower()}">{E(tag)}</i>' if tag else "") + f'</span><span class="role sn" title="Projected minutes tonight; his recent-games baseline is {f1(p.get("base_min"))}">{role}</span></span> '
            f'<span class="ppr"><span class="v"><small>Proj</small>{f1(p["proj"].get("pts"))}<small>points</small></span><i style="--w:{w:.1f}%"></i><span class="rk">{("#" + str(rk) + " " + p["grp"]) if rk else ""}</span></span><i class="car" aria-hidden="true">▾</i></button> '
            f'<div class="pdetail" hidden><div class="sl">{chips}</div>' + (f'<ul class="nblad" aria-label="Chance of each line, model only">{lad}</ul>' if lad else "") + fl + rec + '</div></li>')


def team_col(ab, B, top, ranks):
    t = B["teams"][ab]; opp = t["opp"]; od = t.get("opp_def") or {}
    dm = ""
    for g in ("G", "F", "C"):
        r = (od.get(g) or {}).get("pts")
        if r: dm += f'<span class="dm" style="--c:{rank_color(r[0])}" title="{E(opp)} ranks #{r[0]} of 30 in points allowed to {GRPS[g]} per minute this season (1 = allows the most)"><span class="dl">{g}</span><b>#{r[0]}</b></span>'
    rest = t.get("rest")
    restn = "" if rest is None else ("Second night of a back-to-back" if rest == 1 else (f"{rest - 1} day{'s' if rest - 1 != 1 else ''} of rest"))
    dsum = f'<li class="dsum">{badge(ab, t)}<span>vs {E(opp)} D</span><span class="dgrid">{dm}</span></li>'
    inj = ""
    if t.get("out"):
        inj = '<li class="inj"><span>Out tonight</span>' + "".join(f'<em>{E(o["name"])} <small>{E((o.get("note") or "").strip() or "injury report")}{" · doubtful" if o.get("tag") == "Doubtful" else ""}</small></em>' for o in t["out"]) + '</li>'
    back = f'<li class="inj nbback"><span>Back in the rotation</span>' + "".join(f"<em>{E(n)} <small>sat out the last game, not listed out</small></em>" for n in t["back"]) + "</li>" if t.get("back") else ""
    if not t.get("out"): inj = '<li class="nbnoout">Nobody listed out.</li>'
    note = f'<li class="nbrest">{E(restn)}{" · " + E(t["record"]) if t.get("record") else ""}</li>' if (restn or t.get("record")) else ""
    ps = [p for p in B["players"] if p["team"] == ab]
    if not ps:
        body = '<li class="nbnone">No projections yet for this team.</li>'
    else:
        body = "".join(player_li(p, t, top, ranks, B) for p in sorted(ps, key=lambda p: -(p["proj"].get("pts") or 0)))
    return f'<ul class="col" data-team="{E(ab)}">{dsum}{note}{inj}{back}{body}</ul>'


def game_card(g, B, ranks):
    a, h = g["away"], g["home"]; ta, th = B["teams"][a], B["teams"][h]
    pa, ph = g["proj"].get(a), g["proj"].get(h)
    if pa is not None and ph is not None:
        fav, by = (a, pa - ph) if pa >= ph else (h, ph - pa)
        score = (f'<span class="pt">{pa:.1f}</span><span class="dash">–</span><span class="pt">{ph:.1f}</span><small>total {pa + ph:.1f} · ' + ("even" if round(by, 1) == 0 else f"{E(fav)} by {by:.1f}") + "</small>")
    else:
        score = '<span class="pt">–</span><span class="dash">–</span><span class="pt">–</span><small>no model score yet</small>'
    try: ko = int(dt.datetime.fromisoformat(g["tip"]).timestamp() * 1000)
    except Exception: ko = 0
    band = ""
    if g.get("state") in ("in", "post") and g.get("score"):
        sa, sh = g["score"].get(a), g["score"].get(h)
        head = "Final" if g["state"] == "post" else "In progress"
        band = f'<div class="nbstate s-{g["state"]}"><b>{head}</b><span>{E(a)} {E(sa)} · {E(h)} {E(sh)}</span>' + (f'<small>{E(g.get("detail") or "")} when this page was built</small>' if g["state"] == "in" else "") + '</div>'
    line = g.get("line") or {}
    mk = ""
    if line.get("details") or line.get("total") is not None:
        txt = " · ".join(x for x in ((line.get("details") or ""), (f"O/U {line['total']:g}" if isinstance(line.get("total"), (int, float)) else "")) if x)
        cls = "mkt"
        if pa is not None and ph is not None and isinstance(line.get("total"), (int, float)):
            cls += " agree" if abs((pa + ph) - line["total"]) <= 6 else " off"
        who = (line.get("by") or "the sportsbook ESPN shows").replace("Draft Kings", "DraftKings")
        mk = f'<i>·</i><span class="{cls}" title="{E(who)} line as shown by ESPN - not FanDuel. The model: total {(pa or 0) + (ph or 0):.1f}.">{E(txt)} <small>{E(who)}</small></span>'
    ginfo = f'<div class="ginfo"><span class="gk">{E(g["tipct"])} CT</span>' + (f'<i>·</i><span>{E(g["venue"])}</span>' if g.get("venue") else "") + mk + '</div>'
    top = max([p["proj"].get("pts") or 0 for p in B["players"] if p["game"] == g["id"]] or [0])
    return (f'<section class="card" id="{E(g["key"])}" data-ko="{ko}"> <header class="hd"> <div class="tm a">{badge(a, ta)}<b>{E(a)}</b><span>{E(nick(ta))}</span></div> '
            f'<div class="score">{score}{SWOOSH}</div> <div class="tm b">{badge(h, th)}<b>{E(h)}</b><span>{E(nick(th))}</span></div> </header> {band}{ginfo}'
            f'<div class="vbtns"><button type="button" class="vbtn" data-view="proj">Projections</button><button type="button" class="vbtn" data-view="out">Who\'s out <small>{len(ta.get("out") or []) + len(th.get("out") or [])}</small></button></div>'
            f'<div class="cols">{team_col(a, B, top, ranks)}{team_col(h, B, top, ranks)}</div>'
            f'<footer class="nbfoot"><span>Bar: projected points, scaled to this game\'s top scorer · tap a player for rebounds, assists, threes and the chance of each line</span></footer> </section>')


def summary_card(B, ranks):
    gl = ""
    for g in B["games"]:
        a, h = g["away"], g["home"]; pa, ph = g["proj"].get(a), g["proj"].get(h)
        line = (g.get("line") or {}).get("details") or ""
        st = "Final" if g.get("state") == "post" else ("Live" if g.get("state") == "in" else g["tipct"].split(" ", 2)[-1])
        gl += (f'<li><span class="bl-p"><a href="#{E(g["key"])}">{E(a)} · {E(h)}</a></span><span class="bl-m">{E(st)}' + (f' <small>model {pa:.0f}–{ph:.0f}</small>' if pa is not None and ph is not None else "") + '</span>'
               f'<span class="bl-n">{E(line)}</span></li>')
    top = sorted(B["players"], key=lambda p: -(p["proj"].get("pts") or 0))[:6]
    tl = "".join(f'<li><span class="bl-p"><a href="#{E(key_of(p, B))}" data-open="{E(p["id"])}">{E(p["name"])}</a></span><span class="bl-m">{f1(p["proj"].get("pts"))} points <small>{round(p["min"])} min</small></span><span class="bl-n">{E(p["team"])} <small>vs {E(p["opp"])}</small></span></li>' for p in top)
    up = sorted([p for p in B["players"] if p.get("base_min") and p["min"] - p["base_min"] >= 1.5], key=lambda p: -(p["min"] - p["base_min"]))[:6]
    ul = "".join(f'<li><span class="bl-p"><a href="#{E(key_of(p, B))}" data-open="{E(p["id"])}">{E(p["name"])}</a></span><span class="bl-m">{round(p["min"])} min <small>usually {round(p["base_min"])}</small></span><span class="bl-n">{E(p["team"])}</span><b class="pos">+{p["min"] - p["base_min"]:.0f}</b></li>' for p in up) \
         or "<li class='none'>Nobody's minutes move much tonight.</li>"
    n = len(B["games"])
    return (f'<section class="card summary" id="summary"> <header class="hd"><div class="tm a"><b>Slate</b><span>{E(B["day_label"])} at a glance</span></div><div class="score"><span class="pt">{n}</span><small>game{"s" if n != 1 else ""} on the board</small>{SWOOSH}</div>'
            f'<div class="tm b"><span>BetSweep model</span></div></header> <div class="sumgrid"> <div><h3>Tonight <small>tip time (CT), the model\'s score, the posted line</small></h3><ul class="bl">{gl}</ul></div> '
            f'<div><h3>Top projected scorers <small>points tonight</small></h3><ul class="bl">{tl}</ul></div> <div><h3>More minutes tonight <small>teammates are out</small></h3><ul class="bl">{ul}</ul></div> </div> </section>')


def key_of(p, B):
    return next((g["key"] for g in B["games"] if g["id"] == p["game"]), "summary")


NB_CSS = """
/* NBA additions to the NFL boards' stylesheet (build_nba.py). Site colour variables only. */
.nbbar{display:flex;flex-wrap:wrap;align-items:flex-start;gap:8px 10px;margin:10px 0 0;padding:0 2px} .nbsw{display:flex;gap:6px} .nbsw a{display:inline-flex;align-items:center;min-height:36px;padding:0 14px;border:1.5px solid var(--line);border-radius:999px;font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);text-decoration:none}
.nbsw a[aria-current]{background:var(--ink);border-color:var(--ink);color:var(--bg)} .nbsw a:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.nbpre{margin:10px 0 12px;border:1px dashed color-mix(in srgb,var(--red) 55%,var(--line));border-radius:12px;padding:10px 12px;font-size:13.5px;line-height:1.45;color:var(--mute)} .nbpre b{color:var(--ink)}
.nbold{margin:10px 0 12px;border:1.5px solid var(--bad);border-radius:12px;padding:10px 12px;font-size:14px;line-height:1.45;color:var(--ink);background:color-mix(in srgb,var(--bad) 10%,transparent)} .nbold[hidden]{display:none}
.nbstate{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;padding:9px 14px;border-top:1px solid var(--line);font-size:14px} .nbstate b{font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--red)}
.nbstate.s-post b{color:var(--mute)} .nbstate span{font-weight:600;color:var(--ink)} .nbstate small{color:var(--mute);font-size:12px}
.ginfo .mkt small{color:var(--mute);font-size:11px;margin-left:3px} .ginfo .mkt.off{color:var(--warn,#c98a1b)}
.col .nbrest{list-style:none;padding:0 14px 6px;font-size:12px;color:var(--mute)} .col .nbnone{list-style:none;padding:10px 14px;font-size:13px;color:var(--mute)}
.col .inj.nbback span{color:var(--good)}
.nm .nbtag{display:inline-block;margin-left:6px;padding:1px 6px;border-radius:999px;border:1px solid var(--line);font-style:normal;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);vertical-align:middle}
.nm .nbtag.t-q,.nm .nbtag.t-d{border-color:var(--warn,#c98a1b);color:var(--warn,#c98a1b)}
.sl .mu .nbg{background:none !important;color:var(--mute);padding-left:0}
.nblad{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:5px} .nblad li{display:flex;flex-wrap:wrap;align-items:center;gap:5px;font-size:12.5px}
.nblad li > span{flex:0 0 100%;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.05em;color:var(--mute)} .nblad em{font-style:normal;display:inline-flex;gap:5px;align-items:baseline;border:1px solid var(--line);border-radius:8px;padding:3px 7px;color:var(--ink);font-variant-numeric:tabular-nums}
.nblad em b{font-weight:700;color:var(--mute)}
.nbl5{width:100%;border-collapse:collapse;margin:10px 0 2px;font-size:12.5px;font-variant-numeric:tabular-nums} .nbl5 caption{text-align:left;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.05em;color:var(--mute);padding:0 0 4px}
.nbl5 th,.nbl5 td{padding:4px 6px;text-align:right;border-top:1px solid var(--line)} .nbl5 th{font-weight:600;color:var(--mute);border-top:0} .nbl5 th:nth-child(-n+2),.nbl5 td:nth-child(-n+2){text-align:left}
.nbfoot{padding:8px 14px 12px;font-size:11.5px;color:var(--mute);line-height:1.4}
.nbkey{margin:0 0 0 auto} .nbkey[open]{flex:1 0 100%;margin:0 0 4px} .nbkey summary{cursor:pointer;display:inline-flex;align-items:center;min-height:36px;padding:0 14px;border:1px solid var(--line);border-radius:999px;font-size:13.5px;color:var(--mute);list-style:none} .nbkey summary::-webkit-details-marker{display:none}
.nbkey dl{margin:10px 2px 0;font-size:13.5px;line-height:1.5;color:var(--mute)} .nbkey dt{font-weight:700;color:var(--ink);margin-top:8px} .nbkey dd{margin:2px 0 0}
.nbstamp{margin:18px 2px 0;font-size:12px;line-height:1.5;color:var(--mute);max-width:860px}
body.compact .card:not(.expanded) > .nbstate{display:flex;border-top:0;padding:0 12px 8px}
.vbtn small{font-family:var(--body);font-weight:600;font-size:12px;letter-spacing:0;color:var(--mute);margin-left:4px} .card[data-view="out"] .vbtn[data-view="out"]{background:var(--ink);border-color:var(--ink);color:var(--bg)} .card[data-view="out"] .vbtn[data-view="out"] small{color:var(--bg)}
.card.expanded[data-view="out"] .col .pl,.card.expanded[data-view="out"] .nbfoot{display:none} .col .nbnoout{list-style:none;padding:4px 14px 8px;font-size:13px;color:var(--mute);display:none} .card.expanded[data-view="out"] .col .nbnoout{display:block}
"""

NB_JS = r"""<script>
(function(){
  /* the NFL boards' behaviours this page needs, and nothing that reads NFL data (template.html's own script is not loaded here):
     scorecards first with a tap to open one, the two view buttons, a player's row, the Slate card, and jumps from a chip or a Slate list */
  var cards = document.querySelectorAll('.card[id]:not(.summary)');
  if(cards.length > 1) document.body.classList.add('compact');
  function row(btn, on){
    var d = btn.parentNode.querySelector('.pdetail'); if(!d) return;
    var open = on == null ? btn.getAttribute('aria-expanded') !== 'true' : on;
    btn.setAttribute('aria-expanded', open ? 'true' : 'false'); d.hidden = !open;
  }
  function show(card, view){
    if(card.classList.contains('expanded') && card.getAttribute('data-view') === view){ card.classList.remove('expanded'); card.removeAttribute('data-view'); card.scrollIntoView({block: 'nearest'}); return; }
    card.setAttribute('data-view', view); card.classList.add('expanded'); card.scrollIntoView({block: 'start'});
  }
  function openHash(){
    var h = location.hash && document.getElementById(location.hash.slice(1));
    if(h && h.classList.contains('card')){ if(!h.classList.contains('summary') && !h.classList.contains('expanded')){ h.setAttribute('data-view', 'proj'); h.classList.add('expanded'); } h.scrollIntoView({block: 'start'}); }
  }
  document.addEventListener('click', function(e){
    var t = e.target, b;
    if(!t.closest) return;
    if((b = t.closest('.prow'))){ row(b); return; }
    if((b = t.closest('.vbtn[data-view]'))){ show(b.closest('.card'), b.getAttribute('data-view')); return; }
    if((b = t.closest('a[data-open]'))){
      var li = document.querySelector('.pl[data-pid="' + b.getAttribute('data-open') + '"]');
      if(li){ e.preventDefault(); var c = li.closest('.card'); c.setAttribute('data-view', 'proj'); c.classList.add('expanded'); row(li.querySelector('.prow'), true); li.scrollIntoView({block: 'center'}); }
      return;
    }
    if(t.closest('a,button')) return;
    if((b = t.closest('.card.summary .hd'))){ var s = b.parentNode; s.classList.toggle('expanded'); b.setAttribute('aria-expanded', s.classList.contains('expanded') ? 'true' : 'false'); return; }
    if((b = t.closest('.card[id] .hd')) && document.body.classList.contains('compact')) show(b.parentNode, b.parentNode.getAttribute('data-view') || 'proj');
  });
  document.querySelectorAll('.card .hd').forEach(function(hd){
    hd.setAttribute('role', 'button'); hd.setAttribute('tabindex', '0');
    hd.addEventListener('keydown', function(e){ if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); hd.click(); } });
  });
  window.addEventListener('hashchange', openHash); openHash();
  /* read on a later day than the board was made for (the build has not run since, or the feed stopped): say so at the top instead of looking like tonight's.
     The NBA day is the Central date four hours ago, as in the build. */
  var grid = document.querySelector('.grid[data-day]'), old = document.getElementById('nbold');
  if(grid && old){ try{
    var today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/Chicago', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date(Date.now() - 4 * 3600000));
    if(today > grid.getAttribute('data-day')) old.hidden = false;
  }catch(e){} }
})();
</script>"""


def page(B):
    css = re.search(r"<style[^>]*>(.*?)</style>", open(os.path.join(HERE, "template.html"), encoding="utf-8").read(), re.S).group(1)
    # tonight's rank at each position group by projected points (the NFL card's "#14 QB")
    ranks = {}
    for g in ("G", "F", "C"):
        for i, p in enumerate(sorted([p for p in B["players"] if p["grp"] == g], key=lambda p: -(p["proj"].get("pts") or 0))):
            ranks[p["id"]] = i + 1
    nav = '<a href="#summary">Slate</a> ' + " ".join(f'<a href="#{E(g["key"])}">{E(g["away"])}·{E(g["home"])}</a>' for g in B["games"])
    n = len(B["games"])
    desc = (f"NBA matchup boards for {B['day_label']}: the model's minutes, points, rebounds, assists and threes for every rotation player in tonight's {n} game{'s' if n != 1 else ''}, "
            "who is out, and what each defense allows. A preview: model numbers only.")
    inj = ("the injury report as of " + fmt_ct(B.get("injuries_at"))) if B.get("injuries") else "no injury report was in reach, so each team is the players of its last game"
    pre = ('<div class="nbpre"><b>NBA preview.</b> Model numbers only: FanDuel prices are not connected yet, so there are no edges or betslip buttons. '
           'Nothing here is a pick: the projections have to be graded against results first.</div>')
    key = ('<details class="nbkey"><summary>How to read the board</summary><dl>'
           '<dt>Score</dt><dd>The model\'s points for each team tonight. The posted line beside the tip time is the sportsbook line ESPN shows, named there; it is not FanDuel\'s.</dd>'
           '<dt>Bar and number</dt><dd>Projected points, with the bar scaled to the game\'s top scorer. The tag after it is his place among tonight\'s guards, forwards or centers.</dd>'
           '<dt>Minutes</dt><dd>The model starts from minutes. Each team has 240 to hand out, so when players are out their minutes go to the ones who are left. That is the biggest thing the test results rewarded.</dd>'
           '<dt>Stat chips</dt><dd>Tap a player. Each chip is a projection; its color is how much the opponent allows to his position in that stat, #1 (green) allows the most and #30 (red) the least.</dd>'
           '<dt>Chance of each line</dt><dd>How often the model expects him to reach that many. There is no price beside it yet, so it cannot say whether a bet is good value.</dd>'
           '<dt>Out tonight</dt><dd>From ESPN\'s injury report. A player listed doubtful is treated as out; questionable and probable players stay in, tagged.</dd></dl></details>')
    stamp = (f'<p class="nbstamp">Built {fmt_ct(B.get("built"))} from games through {E(B.get("data_through") or "?")}; {E(inj)}. Projections: BetSweep\'s NBA model (minutes and per-minute rates, fitted to each team\'s 240 minutes among the active players, '
             'adjusted for what the opponent allows by position). In a test on 2026-27 games through mid-November (2,877 player-games) it was about 7% closer than a player\'s season average on points, rebounds and assists. For entertainment; not betting advice.</p>')
    cards = "\n".join(game_card(g, B, ranks) for g in B["games"])
    return (f'<title>BetSweep · NBA Matchup Boards</title>\n<style>{css}</style>\n<style>{NB_CSS}</style>\n'
            f'<div class="top">\n  <div class="mast">\n    <h1><small>NBA · {E(B["day_label"])}</small><b>Matchup Boards</b></h1>\n    <p>{E(desc)}</p>\n  </div>\n  <nav class="nav" aria-label="jump to game">{nav}</nav>\n</div>\n'
            f'<div class="nbbar"><div class="nbsw" role="group" aria-label="Sport"><a href="/boards/">NFL</a><a href="/nba/" aria-current="page">NBA</a></div>{key}</div>\n{pre}\n'
            f'<div class="nbold" id="nbold" hidden><b>This board is for {E(B["day_label"])}.</b> A newer one is not up yet, so every number below is from that day.</div>\n'
            f'<div class="grid" data-day="{E(B["day"])}">\n{summary_card(B, ranks)}\n{cards}\n</div>\n{stamp}\n{NB_JS}\n')


def fmt_ct(iso):
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        try:
            from zoneinfo import ZoneInfo
            d = d.astimezone(ZoneInfo("America/Chicago"))
        except Exception:
            d = d.astimezone(dt.timezone(dt.timedelta(hours=-6)))
        return d.strftime("%a %-m/%d %-I:%M %p CT")
    except Exception:
        return "?"


def signature(B):
    """what a visitor would notice changing: the day, the games and their state, who is out, each player's points to the whole number"""
    return json.dumps([B.get("day"), [(g["key"], g.get("state"), (g.get("line") or {}).get("details")) for g in B["games"]], sorted((ab, sorted(o["name"] for o in t.get("out") or [])) for ab, t in B["teams"].items()),
                       sorted((p["id"], round(p["proj"].get("pts") or 0)) for p in B["players"])], sort_keys=True)


def main():
    a = sys.argv[1:]
    B = load(path=a[a.index("--board") + 1]) if "--board" in a else load(clone=(a[0] if a else None))
    ok, why = usable(B, any_day="--board" in a)   # a board file named by hand is drawn whatever its day (tests, local work)
    if not ok:
        for f in (PAGE, os.path.join(OUT, "nba_board.json"), os.path.join(OUT, "nba_sig.json")):
            if os.path.exists(f): os.remove(f)
        print(f"nba: no page written - {why}")
        return
    os.makedirs(OUT, exist_ok=True)
    open(PAGE, "w", encoding="utf-8").write(page(B))
    # beside the page: the board it was drawn from (tests redo the page from it; later pages will read it) and the signature the hourly
    # job compares with the live one to decide whether the NBA page alone is worth a publish (reprice.nba_changed)
    json.dump(B, open(os.path.join(OUT, "nba_board.json"), "w"), separators=(",", ":"))
    json.dump({"day": B.get("day"), "built": B.get("built"), "sig": signature(B)}, open(os.path.join(OUT, "nba_sig.json"), "w"))
    print(f"nba boards: {B['day_label']}, {len(B['games'])} games, {len(B['players'])} players, {sum(len(t.get('out') or []) for t in B['teams'].values())} out; board built {fmt_ct(B.get('built'))}; {os.path.getsize(PAGE) // 1024} KB -> {PAGE}")


if __name__ == "__main__":
    main()
