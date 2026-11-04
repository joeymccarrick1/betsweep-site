"""Price moves on the Model's Best plus-money / TD legs (owner 11/4: "price-move alerts on plus-tier legs").

Every 30 minutes (after the sheet mirror): read the site's /b/plus.json (the tier legs and the FanDuel price they were built at), read the
mirror's links.json (the sheet's latest FanDuel pull, one price per key), and write data/price-moves.json:
  {"week": W, "checked": ISO, "moves": [{"key", "pl", "m", "ln", "gid", "ko", "built": -114, "now": -150, "pts": 6.5, "dir": "SHORTENED"|"DRIFTED", "detail": "..."}]}
A move is 3+ implied points either way. SHORTENED = the price moved toward the model's side (market agrees; the leg is going away) - the
slip-alerts Edge Function pushes those to the owner once per key; DRIFTED = the market moved against us (longer price, bigger payout, but
the market disagrees). The builder/boards show both as chips (risk.js). Reads only; nothing is written to the sheet.
"""
import json, os, subprocess, sys, time, urllib.request

def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "betsweep-price-moves"}), timeout=60))
def imp(o):
    o = float(o); return 100 / (o + 100) if o > 0 else -o / (-o + 100)
def am(o): o = int(round(float(o))); return f"+{o}" if o > 0 else str(o)

def main():
    plus = get("https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/main/b/plus.json")
    links = get("https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/sheet-mirror/in/links.json")["values"]
    H = {c: i for i, c in enumerate(links[0])}
    now_px = {}
    for r in links[1:]:
        if len(r) <= H["FanDuel odds"]: continue
        try: now_px[str(r[H["Key"]]).strip().lower()] = (float(r[H["FanDuel odds"]]), r[H["Updated"]] if "Updated" in H and len(r) > H["Updated"] else "")
        except Exception: pass
    nowms = time.time() * 1000; moves = []; n_seen = 0
    for l in plus.get("legs", []):
        if l.get("ko") and l["ko"] <= nowms: continue
        cur = now_px.get(str(l.get("fdkey", "")).lower())
        if not cur or l.get("o") is None: continue
        n_seen += 1
        d = (imp(cur[0]) - imp(l["o"])) * 100
        if abs(d) < 3: continue
        short = {"Receiving Yards": "rec yds", "Rushing Yards": "rush yds", "Passing Yards": "pass yds", "Receptions": "rec", "Longest Reception": "long rec", "Anytime TD": "anytime TD"}.get(l["m"], l["m"])
        line = "" if l["m"] == "Anytime TD" else f" {int(round(l['ln']))}+"
        moves.append({"key": l["key"], "pl": l["pl"], "m": l["m"], "ln": l.get("ln"), "gid": l.get("gid"), "ko": l.get("ko"), "built": l["o"], "now": cur[0], "pts": round(d, 1),
                      "dir": "SHORTENED" if d > 0 else "DRIFTED", "pulled": cur[1],
                      "detail": f"{l['pl']} {short}{line}: FanDuel {am(l['o'])} at build -> {am(cur[0])} now ({d:+.1f} implied pts {'toward the model' if d > 0 else 'against us'})"})
    moves.sort(key=lambda m: -abs(m["pts"]))
    out = {"week": plus.get("week"), "built": plus.get("built"), "checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "legs_checked": n_seen, "moves": moves}
    os.makedirs("data", exist_ok=True); json.dump(out, open("data/price-moves.json", "w"), indent=1)
    print(f"price moves: {len(moves)} of {n_seen} tier legs moved 3+ pts ({sum(1 for m in moves if m['dir'] == 'SHORTENED')} toward us)")
    for m in moves[:12]: print(" ", m["dir"], m["detail"])
    return 0

if __name__ == "__main__": sys.exit(main())
