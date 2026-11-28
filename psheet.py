#!/usr/bin/env python3
"""psheet.py - the player sheet (owner 11/27 10:34 PM, with a recording of FanDuel's new "Player Props" sheet: "I want to make sure
we're beating FanDuel's user experience as much as possible. The goal is always to make the best most efficient legs and show them why
as quickly and as best as it can").

FanDuel: tap a name in its Trends list and a sheet slides up with his last five against the line and his prices under the chart. A
price is all each rung gets. Here a tap on a name on any leg card (Today, Model's Best, Trend check) opens a sheet in place - the page
behind keeps its place, its filters and its slip - with, for every stat he is priced in:

  the chart     his last five against the rung, opponent logos under the bars (home.leg_h5 - the card's own chart, so the two agree)
  the reason    one line against and one for (why.py), and the builder's risk tag when the rung has one
  the ladder    every rung FanDuel prices: the model's chance, the win rate the price needs, the edge, and the price as the add button
                (the same link the cards use, so a tap adds it to the slip without leaving the sheet)
A tap on a rung moves the chart's line to it and recounts the five games, so "how often has he cleared 60?" is one tap, not a guess.

Nothing here is new data and nothing changes a projection or a price: every number is a leg the Parlay Builder already carries
(out/builder_data.json). Unders are left to his full page, which the sheet links (why.py gives them no reasons, and the owner's slips
are overs). A player gets a sheet when the cards link his name: single player, game log in the builder's data.

Writes out/psheet/<slug>.json = {"v", "week", "name", "slug", "ko", "html"}; build_site.py copies each beside the player's page as
/player/<slug>/sheet.json. The sheet's script and styles are in home.py (HOME_SLIP_JS, HOME_CSS), which every page with leg cards loads.
Prints "wrote out/psheet: N player sheets, week W".
"""
import html, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
E = html.escape

# a chip a stat: (id, label, markets in ladder order)
STATS = [("pass", "Pass yds", ("Passing Yards",)), ("ptd", "Pass TDs", ("Passing TDs",)), ("rush", "Rush yds", ("Rushing Yards",)), ("rr", "Rush + rec", ("Rush + Rec Yards",)),
         ("recy", "Rec yds", ("Receiving Yards",)), ("rec", "Receptions", ("Receptions",)), ("long", "Long rec", ("Longest Reception",)),
         ("td", "TDs", ("Anytime TD", "2+ TD", "3+ TD", "First TD"))]
STAT = {sid: (lab, ms) for sid, lab, ms in STATS}
STAT_OF = {m: sid for sid, _, ms in STATS for m in ms}
ORDER = {"QB": ["pass", "ptd", "rush", "td"], "RB": ["rush", "rr", "recy", "rec", "td", "long"], "WR": ["recy", "rec", "td", "long", "rush", "rr"], "TE": ["recy", "rec", "td", "long", "rush", "rr"]}
TDLAB = {"Anytime TD": "Anytime", "2+ TD": "2+ TDs", "3+ TD": "3+ TDs", "First TD": "First TD"}


def need_of(m, ln):
    """what a game has to reach for the leg to win; None for First TD, which no game log can grade"""
    if m == "First TD": return None
    return 2 if m == "2+ TD" else 3 if m == "3+ TD" else 1 if str(m).endswith("TD") else float(ln)


def short(m, ln):
    """the rung's name in the ladder: "60+", "Anytime", "2+ TDs" """
    return TDLAB.get(m) or f"{int(math.floor(float(ln) + 0.5))}+"


def cap_lab(m, ln):
    """the words home.leg_h5 puts after "cleared" / "scored" for this rung - the sheet's script rewrites the caption with them"""
    if str(m).endswith("TD"): n = need_of(m, ln); return "a TD" if n == 1 else f"{n}+ TDs"
    return f"{int(math.floor(float(ln) + 0.5))}+"


def season_of(x):
    """("info", "6/10 this season") from the leg's own flags - the pill the cards print under the bars"""
    return next(((h[0], h[1]) for h in (x.get("fh") or []) if h[0] in ("good", "info", "bad") and "/" in str(h[1]) and str(h[1]).endswith("this season")), None)


def default_rung(ls):
    """the rung a panel opens on: the one priced nearest even money (the lower line on a tie); First TD never"""
    c = [l for l in ls if l["m"] != "First TD"]
    return min(c, key=lambda l: (abs((l.get("bk") if l.get("bk") is not None else 0.5) - 0.5), float(l.get("ln") or 0))) if c else None


def status_text(st):
    """the injury report's line for him in plain words (his game status, else a missed or limited practice); "" when there is nothing to say"""
    if not st: return ""
    rep, prac, inj = (list(st) + ["", "", ""])[:3]
    if rep in ("Out", "Doubtful", "Questionable"): return rep
    pr = str(prac or "").strip().lower()
    if pr.startswith("did not"): return "Did not practice"
    if pr.startswith("limited"): return "Limited in practice"
    return ""


def legs_of(bd):
    """{player: [legs]} - overs and touchdowns of single players the cards link (a game log in the builder's data)"""
    by = {}; gl = bd.get("gl") or {}
    for l in bd.get("legs") or []:
        if l.get("gl") or l.get("u") or str(l.get("m") or "").startswith("Under ") or l.get("m") not in STAT_OF or l.get("pl") not in gl: continue
        by.setdefault(l["pl"], []).append(l)
    return by


def sheet(name, legs, D, G, HOME, HM, WHY, SW, IN_, slug, status=""):
    bd = D["bd"]; pf = HOME._CARD.get("pf"); l0 = legs[0]; tm, opp, gid = l0["tm"], l0["opp"], l0["g"]; g = G.get(gid) or {}
    pos = l0.get("pos") or ""; home = g.get("b") == tm
    order = list(ORDER.get(pos, ORDER["WR"])); order += [sid for sid, _, _ in STATS if sid not in order]
    chips, panels = [], []
    for sid in order:
        lab, ms = STAT[sid]; ls = sorted([l for l in legs if l["m"] in ms], key=lambda l: (ms.index(l["m"]), float(l.get("ln") or 0)))
        if not ls: continue
        d = default_rung(ls); whys = []; rows = []
        for l in ls:
            x = HOME._mb(D, l, G); need = need_of(l["m"], l["ln"]); sn = season_of(x); risk = SW.risk_tag(SW.risk_score(l, bd)) if need is not None else ""
            w = WHY.html(x, pf) if need is not None else ""
            if w and w not in whys: whys.append(w)
            e = x.get("e") or 0; bk = x.get("bk"); er = int(math.floor(abs(e) * 100 + 0.5)) * (1 if e >= 0 else -1)   # the edge in whole points; a rounded zero is no edge either way
            price = (f'<a class="more px" href="{E(HOME.build_href(gid, [(l["pl"], l["m"], l["ln"])]))}" data-px="{E(HOME.odds_str(l["o"]))}" '
                     f'title="Open the parlay builder with this leg in your slip">{E(HOME.odds_str(l["o"]))}</a>')
            name_cell = (f'<button type="button" class="pshln" aria-label="Show {E(HOME.leg_line(l["m"], l["ln"]))} on the chart">{E(short(l["m"], l["ln"]))}</button>' if need is not None
                         else f'<span class="pshln0">{E(short(l["m"], l["ln"]))}</span>')
            rows.append(
                f'<tr class="pshr{" on" if l is d else ""}" data-k="{E(HOME.leg_key(l["pl"], l["m"], l["ln"]))}"'
                + (f' data-need="{need:g}" data-lab="{E(cap_lab(l["m"], l["ln"]))}" data-verb="{"scored" if l["m"].endswith("TD") else "cleared"}"' if need is not None else "")
                + f' data-full="{E(HOME.leg_line(l["m"], l["ln"]))}" data-sn="{E(sn[1]) if sn else ""}" data-snc="{E(sn[0]) if sn else ""}" data-w="{whys.index(w) if w else ""}" data-rk="{E(risk)}">'
                f'<th scope="row">{name_cell}</th><td class="pshm">{x["p"] * 100:.0f}%</td><td class="pshn">{(f"{bk * 100:.0f}%") if bk else "—"}</td>'
                f'<td class="pshe {"pos" if er > 0 else "neg" if er < 0 else ""}">{(f"{er:+d}" if er else "0") if bk else "—"}</td><td class="pshb">{price}</td></tr>')
        head = ""
        if d:
            xd = HOME._mb(D, d, G); rk = SW.risk_tag(SW.risk_score(d, bd)); wd = WHY.html(xd, pf)
            proj = f'<span class="pshproj">proj {float(d["proj"]):.1f}</span>' if (isinstance(d.get("proj"), (int, float)) and not d["m"].endswith("TD")) else ""
            head = (f'<div class="pshsel"><p class="pshmk"><b>{E(HOME.leg_line(d["m"], d["ln"]))}</b>{proj}<span class="pshrk{" hi" if rk == "High risk" else ""}"{"" if rk else " hidden"}>{E(rk)}</span></p>'
                    + HOME.leg_h5(xd, season_of(xd))
                    + "".join(f'<div class="pshwhy" data-w="{i}"{"" if w == wd else " hidden"}>{w}</div>' for i, w in enumerate(whys)) + '</div>')
        chips.append((sid, lab))
        panels.append(f'<section class="pshp" data-st="{sid}" data-mks="{E("|".join(sorted({l["m"] for l in ls})))}"{"" if not panels else " hidden"}>{head}'
                      f'<table class="pshlad"><thead><tr><th scope="col">Line</th><th scope="col">Model</th><th scope="col">Needs</th><th scope="col">Edge</th><th scope="col">FanDuel</th></tr></thead>'
                      f'<tbody>{"".join(rows)}</tbody></table></section>')
    if not panels: return None
    jersey = HM.jersey(tm, HM.num(IN_, name, tm))
    sub = " · ".join(s for s in [E(pos), HM.hm(tm) + E(tm) + (" vs " if home else " @ ") + E(opp), E(g.get("kick", ""))] if s)
    st = f'<span class="pshst">{E(status)}</span>' if status else ""
    chip_html = "".join(f'<button type="button" data-st="{sid}" class="{"on" if i == 0 else ""}" aria-pressed="{"true" if i == 0 else "false"}">{E(lab)}</button>' for i, (sid, lab) in enumerate(chips))
    return (f'<div class="pshroot" data-week="{bd.get("week") or 0}" data-ko="{g.get("ko") or ""}" data-slug="{E(slug)}">'
            f'<header class="pshhd">{jersey}<div class="pshwho"><h2 id="pshname">{E(name)}</h2><p>{sub}</p>{st}</div></header>'
            + (f'<div class="pshchips" role="group" aria-label="Stat">{chip_html}</div>' if len(chips) > 1 else "")
            + "".join(panels)
            + '<p class="pshkonote" hidden>His game has kicked off, so these prices are closed.</p>'
            f'<a class="pshfull" href="/player/{E(slug)}/">His full page: every book\'s price, unders, last 10 and stats</a></div>')


def build(IN_=IN, OUT_=OUT):
    import home as HOME, helmets as HM, why as WHY, sweep as SW
    D = HOME.load(IN_, OUT_); bd = D["bd"]; W = bd.get("week") or 0; G = {g["gid"]: g for g in bd["games"]}
    try:
        import plydata as PD
        slugify = PD.slugify
        try: PL = {p["name"]: p for p in PD.load(HERE).players.values()}
        except Exception as e: PL = {}; print("note: player sheets built without the injury report line:", e)
    except Exception as e:
        print("note: no player sheets (plydata):", e); return 0
    outd = os.path.join(OUT_, "psheet"); os.makedirs(outd, exist_ok=True)
    for f in os.listdir(outd):
        if f.endswith(".json"): os.remove(os.path.join(outd, f))
    n = 0
    for name, legs in sorted(legs_of(bd).items()):
        p = PL.get(name) or {}; slug = p.get("slug") or slugify(name)
        try: h = sheet(name, legs, D, G, HOME, HM, WHY, SW, IN_, slug, status_text(p.get("status")))
        except Exception as e:
            print(f"note: no sheet for {name}: {e}"); continue
        if not h: continue
        json.dump({"v": 1, "week": W, "name": name, "slug": slug, "ko": (G.get(legs[0]["g"]) or {}).get("ko"), "html": h}, open(os.path.join(outd, slug + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        n += 1
    print(f"wrote out/psheet: {n} player sheets, week {W}")
    return n


if __name__ == "__main__":
    build()
