#!/usr/bin/env python3
"""stale_lines.py - "lines to check": a starter is ruled out and his teammates' prices on the site are older than the news
(owner 11/10 deep dive: "stale-line alerts: a starter is ruled out and his teammates' lines haven't moved yet").

What the site can and cannot know. The news desk reads ESPN / RotoWire / Yahoo every 10 minutes (the feeds branch). FanDuel's
player props reach the sheet on the sheet's own schedule - on 11/10 one pull a day, 6:24 AM ('AUTO - FanDuel Links' column Updated).
So between pulls the site cannot say whether FanDuel has moved a line; what it CAN say, exactly, is which of the prices it is showing
were pulled BEFORE a teammate was ruled out. Those are the legs worth opening in the app first: if FanDuel still shows the old
number, the line has not caught up with the news.

A leg is listed when:
  - the news desk has a player OUT (bucket OUT, a 'bad' note) with a timestamp after the last props pull and within 48 hours,
  - that player mattered: FanDuel priced him on this week's board or in either of the last two graded weeks,
  - the leg belongs to a teammate in the same position room (RB with RB; WR and TE together), is an over, has FanDuel ids, and is the
    rung closest to even money for receptions / receiving yards (WR, TE) or rushing / rush + receiving yards (RB), or his anytime TD.
A quarterback going out is not listed: that moves every pass-catcher DOWN, which is not a line to chase.

  build(in_dir, out_dir) -> out/stale.json {"week", "pulled", "items": [{out: {...}, legs: [...]}]} and a one-line summary
  card(out_dir)          -> the home-page block, or "" when there is nothing to check
"""
import datetime, html, json, os
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago"); E = html.escape
ROOM = {"RB": {"RB"}, "WR": {"WR", "TE"}, "TE": {"WR", "TE"}}
MK = {"RB": ("Rushing Yards", "Rush + Rec Yards", "Anytime TD"), "WR": ("Receptions", "Receiving Yards", "Anytime TD"), "TE": ("Receptions", "Receiving Yards", "Anytime TD")}


def _vals(in_dir, n):
    try:
        d = json.load(open(os.path.join(in_dir, n))); return d.get("values", d) if isinstance(d, dict) else d
    except Exception: return []


def dec(o): o = float(o); return 1 + o / 100 if o > 0 else 1 + 100 / -o
def am(o): o = int(round(float(o))); return f"+{o}" if o > 0 else f"−{-o}"
def norm(n): return "".join(ch for ch in str(n).lower().replace(" jr", "").replace(" sr", "").replace(" iii", "").replace(" ii", "") if ch.isalpha() or ch == " ").strip()


def last_pull(in_dir):
    """the newest 'Updated' stamp on the FanDuel links tab (Central time) -> aware datetime, or None"""
    best = None
    for r in _vals(in_dir, "links.json")[1:]:
        if len(r) < 10 or not r[9]: continue
        for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                t = datetime.datetime.strptime(str(r[9]).strip(), f).replace(tzinfo=CT)
                if best is None or t > best: best = t
                break
            except Exception: pass
    return best


def pulls_by_player(in_dir):
    """11/10 evening: FanDuelOdds.gs v2026-11-10 refreshes only the day's games between the fixed windows, so the rows of the links
    tab no longer share one stamp. normalised player name -> the newest 'Updated' among his rows."""
    out = {}
    for r in _vals(in_dir, "links.json")[1:]:
        if len(r) < 10 or not r[9] or not r[1]: continue
        for f in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                t = datetime.datetime.strptime(str(r[9]).strip(), f).replace(tzinfo=CT); k = norm(r[1])
                if k not in out or t > out[k]: out[k] = t
                break
            except Exception: pass
    return out


def leg_txt(l):
    if l["m"] == "Anytime TD": return f"{l['pl']} to score"
    return f"{l['pl']} {int(round(l['ln']))}+ {l['m'].lower()}"


def build(in_dir="in", out_dir="out", now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    bd = json.load(open(os.path.join(out_dir, "builder_data.json"))); W = int(bd.get("week") or 0)
    G = {g["gid"]: g for g in bd.get("games") or []}; now_ms = now.timestamp() * 1000
    pulled = last_pull(in_dir); PULL = pulls_by_player(in_dir)
    try: news = json.load(open(os.path.join(in_dir, "ctx_news.json"))).get("players") or []
    except Exception: news = []
    priced = {norm(l["pl"]) for l in bd.get("legs") or [] if not l.get("gl")}
    snaps = _vals(in_dir, "legsnaps.json")
    if snaps:
        H = {c: i for i, c in enumerate(snaps[0])}
        for r in snaps[1:]:
            try:
                if int(float(r[H["Week"]])) in (W - 1, W - 2): priced.add(norm(r[H["Player"]]))
            except Exception: pass
    items = []
    for n in news:
        if n.get("bucket") != "OUT" or n.get("k") != "bad" or not str(n.get("tag", "")).startswith("News: out"): continue
        pos = n.get("pos"); tm = n.get("team")
        if pos not in ROOM or not tm or norm(n.get("player")) not in priced: continue
        try: ts = datetime.datetime.fromisoformat(str(n.get("ts")))
        except Exception: continue
        if ts.tzinfo is None: ts = ts.replace(tzinfo=datetime.timezone.utc)
        if (now - ts).total_seconds() > 48 * 3600: continue
        by = {}
        for l in bd.get("legs") or []:
            if l.get("gl") or l.get("u") or l.get("tm") != tm or l.get("pos") not in ROOM[pos] or norm(l["pl"]) == norm(n["player"]): continue
            if l.get("m") not in MK[l["pos"]] or l.get("o") is None or l.get("p") is None: continue
            fd = l.get("fd") or {}; g = G.get(l["g"]) or {}
            if not (fd.get("m") and fd.get("s")) or not g.get("ko") or g["ko"] <= now_ms: continue
            k = (l["pl"], l["m"])
            if k not in by or abs(dec(l["o"]) - 2) < abs(dec(by[k]["o"]) - 2): by[k] = l
        if not by: continue
        # the price that matters is the teammates' own: were THEIR lines pulled after the news? (one stamp for the whole tab until 11/10)
        room = [PULL[norm(pl)] for (pl, _) in by if norm(pl) in PULL]; room_pull = max(room) if room else pulled
        if room_pull and ts <= room_pull: continue
        mates = {}
        for (pl, _), l in by.items(): mates.setdefault(pl, []).append(l)
        order = sorted(mates, key=lambda pl: -max((x.get("proj") or 0) for x in mates[pl] if x["m"] != "Anytime TD") if any(x["m"] != "Anytime TD" for x in mates[pl]) else 0)[:3]
        legs = []
        for pl in order:
            for l in sorted(mates[pl], key=lambda x: MK[x["pos"]].index(x["m"]))[:2]:
                legs.append({"t": leg_txt(l), "pl": l["pl"], "m": l["m"], "ln": l["ln"], "o": int(l["o"]), "p": round(l["p"], 4), "g": l["g"], "ko": G[l["g"]]["ko"],
                             "u": f"https://sportsbook.fanduel.com/addToBetslip?marketId={l['fd']['m']}&selectionId={l['fd']['s']}"})
        items.append({"out": {"pl": n["player"], "tm": tm, "pos": pos, "ts": ts.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "when": ts.astimezone(CT).strftime("%a %-I:%M %p"), "txt": str(n.get("txt") or "")[:220], "src": n.get("src")}, "legs": legs})
    items.sort(key=lambda x: x["out"]["ts"], reverse=True)
    data = {"week": W, "pulled": pulled.astimezone(CT).strftime("%a %-I:%M %p") if pulled else None, "pulled_utc": pulled.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if pulled else None, "items": items}
    json.dump(data, open(os.path.join(out_dir, "stale.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    return (f"lines to check: {len(items)} player(s) ruled out since the last FanDuel props pull ({data['pulled'] or 'unknown'}), {sum(len(i['legs']) for i in items)} teammate legs"
            + (": " + "; ".join(f"{i['out']['pl']} ({i['out']['tm']} {i['out']['pos']}, {i['out']['when']})" for i in items[:4]) if items else ""))


CSS = """
.stsec{max-width:1360px;margin:14px auto 0;padding:0 16px}
.stbox{border:1px solid var(--line);border-radius:14px;background:var(--card);padding:13px 14px 6px}
.stbox h2{margin:0 0 4px;font-family:var(--display);font-weight:800;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--redtxt,var(--red))}
.stbox .stsub{margin:0 0 8px;color:var(--mute);font-size:12.5px;line-height:1.4}
.stit{border-top:1px solid var(--line);padding:9px 0}
.stit .who{margin:0 0 6px;font-size:14.5px;line-height:1.35} .stit .who b{font-weight:700} .stit .who small{color:var(--mute)}
.stit ul{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.stit li{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:14.5px} .stit li[hidden]{display:none}
.stit li span{min-width:0} .stit li small{display:block;color:var(--mute);font-size:12px}
.stit li a{flex:none;font-family:var(--display);font-weight:800;font-size:13px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--red);white-space:nowrap}
"""
JS = ("(function(){function t(){var n=Date.now(),any=false;document.querySelectorAll('#bsstale li[data-ko]').forEach(function(e){var live=+e.getAttribute('data-ko')>n;e.hidden=!live;if(live)any=true;});"
      "document.querySelectorAll('#bsstale .stit').forEach(function(it){it.hidden=!it.querySelector('li:not([hidden])');});var w=document.getElementById('bsstale');if(w)w.hidden=!any;}"
      "t();setInterval(t,60000);})();")


def card(out_dir="out"):
    try: d = json.load(open(os.path.join(out_dir, "stale.json")))
    except Exception: return ""
    its = [i for i in d.get("items") or [] if i.get("legs")]
    if not its: return ""
    h = []
    for i in its[:4]:
        o = i["out"]
        rows = "".join(f'<li data-ko="{l["ko"]}"><span>{E(l["t"])}<small>our price {am(l["o"])}, pulled before the news · model {l["p"] * 100:.0f}%</small></span>'
                       f'<a href="{E(l["u"])}" target="_blank" rel="noopener">Check FanDuel</a></li>' for l in i["legs"])
        h.append(f'<div class="stit"><p class="who"><b>{E(o["pl"])} is out</b> <small>{E(o["tm"])} {E(o["pos"])} · {E(o["when"])} CT · {E(str(o.get("src") or ""))}</small></p><ul>{rows}</ul></div>')
    return (f'<style>{CSS}</style><section class="stsec" id="bsstale" hidden><div class="stbox"><h2>Lines to check</h2>'
            f'<p class="stsub">Ruled out since our last FanDuel price pull ({E(str(d.get("pulled") or ""))} CT). If the app still shows these prices, the line has not caught up with the news.</p>'
            + "".join(h) + f'</div></section><script>{JS}</script>')


if __name__ == "__main__":
    print(build())
