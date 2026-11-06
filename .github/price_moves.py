"""Price moves on every leg the site tracks (owner 11/4: tier legs; 11/5: "line moves on your legs" - the whole board).

Every 30 minutes (after the sheet mirror): read the site's /b/live-legs.json (every builder leg with the FanDuel price it was built at)
plus /b/plus.json (the tier legs, same shape as before), read the mirror's latest FanDuel pull (links.json for overs / TDs, unders.json
for unders) and write data/price-moves.json:
  {"week": W, "checked": ISO, "legs_checked": N,
   "moves": [{"key": "Player|Market|Line" (the slip key), "pl", "m", "ln", "gid", "ko", "built": -114, "now": -150, "pts": 6.5,
              "dir": "SHORTENED"|"DRIFTED", "tier": "plus"|"", "detail": "..."}]}
A move is 3+ implied points either way (10+ cents on a -110 line). SHORTENED = the price moved toward the model's side; DRIFTED = the
market moved against us. risk.js shows both as chips on every leg button; the slip-alerts Edge Function pushes moves on a subscriber's
own slip legs (10+ cents or a line change) and the tier legs to the owner. Reads only; nothing is written to the sheet.
"""
import json, math, os, sys, time, urllib.request

def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "betsweep-price-moves"}), timeout=60))
def imp(o):
    o = float(o); return 100 / (o + 100) if o > 0 else -o / (-o + 100)
def am(o): o = int(round(float(o))); return f"+{o}" if o > 0 else str(o)
def slipkey(pl, m, ln):
    try: ln = float(ln)
    except Exception: ln = 1.0
    return f"{pl}|{m}|{int(math.floor((ln or 1) + 0.5))}"
SHORT = {"Receiving Yards": "rec yds", "Rushing Yards": "rush yds", "Passing Yards": "pass yds", "Receptions": "rec", "Longest Reception": "long rec",
         "Anytime TD": "anytime TD", "First TD": "first TD", "2+ TD": "2+ TD", "Rush + Rec Yards": "rush+rec"}

def main():
    RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site"
    try: plus = get(f"{RAW}/main/b/plus.json")
    except Exception as e: print("plus.json:", e); plus = {"legs": []}
    try: live = get(f"{RAW}/main/b/live-legs.json")
    except Exception as e: print("live-legs.json:", e); live = {"legs": [], "games": []}
    links = get(f"{RAW}/sheet-mirror/in/links.json")["values"]; H = {c: i for i, c in enumerate(links[0])}
    now_px = {}
    for r in links[1:]:
        if len(r) <= H["FanDuel odds"]: continue
        try: now_px[str(r[H["Key"]]).strip().lower()] = (float(r[H["FanDuel odds"]]), r[H["Updated"]] if "Updated" in H and len(r) > H["Updated"] else "")
        except Exception: pass
    under_px = {}
    try:
        und = get(f"{RAW}/sheet-mirror/in/unders.json")["values"]; U = {c: i for i, c in enumerate(und[0])}
        for r in und[1:]:
            if len(r) <= U["Under odds"]: continue
            try: under_px[str(r[U["Key"]]).strip().lower()] = (float(r[U["Under odds"]]), r[U["Pulled (CT)"]] if "Pulled (CT)" in U and len(r) > U["Pulled (CT)"] else "")
            except Exception: pass
    except Exception as e: print("unders mirror:", e)
    ko_of = {g["gid"]: g.get("ko") for g in live.get("games", [])}
    tier = {l["key"]: l.get("tier", "plus") for l in plus.get("legs", [])}
    nowms = time.time() * 1000; moves = []; n_seen = 0; seen_keys = set()
    def line_s(ln):
        try: f = float(ln)
        except Exception: return str(ln)
        return str(int(f)) if f == int(f) else str(f)
    cands = []
    for l in live.get("legs", []):
        m = l.get("m", ""); under = m.startswith("Under ")
        fdkey = f"{l['pl']}|{m[6:] if under else m}|{line_s(l.get('ln'))}".lower()   # the mirror keys are lower-cased whole
        cur = under_px.get(fdkey) if under else now_px.get(fdkey)
        cands.append((l, cur, l.get("g"), ko_of.get(l.get("g"))))
    for l in plus.get("legs", []):   # the tier legs carry their own fdkey; keep them even if the live list missed them
        k = slipkey(l["pl"], l["m"], l.get("ln"))
        if any(slipkey(x[0]["pl"], x[0]["m"], x[0].get("ln")) == k for x in cands): continue
        cands.append((l, now_px.get(str(l.get("fdkey", "")).lower()), l.get("gid"), l.get("ko")))
    for l, cur, gid, ko in cands:
        if ko and ko <= nowms: continue
        if not cur or l.get("o") is None: continue
        key = slipkey(l["pl"], l["m"], l.get("ln"))
        if key in seen_keys: continue
        seen_keys.add(key); n_seen += 1
        d = (imp(cur[0]) - imp(l["o"])) * 100
        if abs(d) < 3: continue
        m = l["m"]; under = m.startswith("Under ")
        short = ("under " if under else "") + SHORT.get(m[6:] if under else m, m[6:] if under else m)
        line = "" if m in ("Anytime TD", "First TD", "2+ TD", "3+ TD") else (f" {line_s(l.get('ln'))}" if under else f" {int(math.floor(float(l.get('ln') or 1) + 0.5))}+")
        moves.append({"key": key, "pl": l["pl"], "m": m, "ln": l.get("ln"), "gid": gid, "ko": ko, "built": l["o"], "now": cur[0], "pts": round(d, 1),
                      "dir": "SHORTENED" if d > 0 else "DRIFTED", "tier": tier.get(key, ""), "pulled": cur[1],
                      "detail": f"{l['pl']} {short}{line}: FanDuel {am(l['o'])} at build -> {am(cur[0])} now ({d:+.1f} implied pts {'toward the model' if d > 0 else 'against us'})"})
    moves.sort(key=lambda m: -abs(m["pts"]))
    out = {"week": live.get("week") or plus.get("week"), "built": live.get("built") or plus.get("built"), "checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "legs_checked": n_seen, "moves": moves}
    os.makedirs("data", exist_ok=True); json.dump(out, open("data/price-moves.json", "w"), indent=1)
    print(f"price moves: {len(moves)} of {n_seen} legs moved 3+ pts ({sum(1 for m in moves if m['dir'] == 'SHORTENED')} toward us; {sum(1 for m in moves if m['tier'])} tier legs)")
    for m in moves[:12]: print(" ", m["dir"], m["detail"])
    return 0


# ---- closing lines (owner 11/5 "do all of these"): 'V2 - Closing Lines' needed an Apps Script that was never installed, so the tab stayed
# empty and the season page's CLV card never filled. This keeps, for every frozen leg (legsnaps, Latest Snapshot TRUE), the newest FanDuel
# price from the mirror that was PULLED BEFORE that leg's kickoff - so the last write before kickoff is the closing price. Stored in
# data/closing-w<W>.json; sheets_pull.py turns it into in/closing.json (same columns as the tab) when the tab is empty.
def closing():
    import datetime as dt, re
    RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site"
    snaps = get(f"{RAW}/sheet-mirror/in/legsnaps.json")["values"]; S = {c: i for i, c in enumerate(snaps[0])}
    links = get(f"{RAW}/sheet-mirror/in/links.json")["values"]; H = {c: i for i, c in enumerate(links[0])}
    px = {}
    for r in links[1:]:
        if len(r) <= H["Updated"]: continue
        try: px[str(r[H["Key"]]).strip().lower()] = (float(r[H["FanDuel odds"]]), str(r[H["Updated"]]))
        except Exception: pass
    def ko_of(txt, year):   # 'Thu 11/5 7:15 PM' (CT) -> 'YYYY-MM-DD HH:MM'
        m = re.match(r"\w+ (\d+)/(\d+) (\d+):(\d+) (AM|PM)", str(txt or "").strip())
        if not m: return None
        mo, d, h, mi, ap = int(m[1]), int(m[2]), int(m[3]) % 12, int(m[4]), m[5]
        return f"{year}-{mo:02d}-{d:02d} {h + (12 if ap == 'PM' else 0):02d}:{mi:02d}"
    ct = dt.datetime.now(dt.timezone(dt.timedelta(hours=-6))); cap = ct.strftime("%Y-%m-%d %H:%M")
    weeks = {}
    for r in snaps[1:]:
        r = r + [""] * (len(snaps[0]) - len(r))
        if str(r[S["Latest Snapshot"]]).upper() != "TRUE": continue
        try: w = int(float(r[0]))
        except Exception: continue
        weeks.setdefault(w, []).append(r)
    if not weeks: return
    W = max(weeks); path = f"data/closing-w{W}.json"
    try: cur = json.load(open(path))
    except Exception: cur = {"week": W, "rows": {}}
    rows = cur["rows"]; n_new = 0
    for r in weeks[W]:
        ln = r[S["Line (X+)"]]
        try: f = float(ln); ln = str(int(f)) if f == int(f) else str(f)
        except Exception: pass
        key = f"{str(r[S['Player']]).strip()}|{r[S['Market']]}|{ln}".lower()
        p = px.get(key); ko = ko_of(r[S["Kickoff (CT)"]], ct.year)
        if not p or not ko or not p[1] or p[1][:16] >= ko: continue          # only prices pulled before kickoff
        if p[1][:16] <= str(r[S["Frozen At"]])[:16]: continue                # and after our freeze (otherwise it is the freeze price)
        old = rows.get(key)
        if old and old["pulled"] >= p[1][:16]: continue
        rows[key] = {"pl": r[S["Player"]], "m": r[S["Market"]], "ln": ln, "o": p[0], "imp": round(imp(p[0]), 4), "pulled": p[1][:16], "ko": ko, "cap": cap}; n_new += 1
    cur["updated"] = cap; json.dump(cur, open(path, "w"), indent=0)
    print(f"closing lines week {W}: {len(rows)} legs ({n_new} new/updated)")

if __name__ == "__main__":
    try: closing()
    except Exception as e: print("closing lines skipped:", e)
    sys.exit(main())
