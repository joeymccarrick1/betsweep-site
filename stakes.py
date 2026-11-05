#!/usr/bin/env python3
"""stakes.py - game stakes, schedule spot and referee crew for every game card (owner 11/4 context desk, items 3 and 7).

Source: nflverse schedules games.csv (reachable from the sandbox): scores so far this season (standings, games back), away_rest / home_rest
(short week, off a bye), div_game, weekday / gametime (primetime, early window), location (international), roof, referee. Everything here is
context for the card and a flag where the literature supports one; nothing changes a projection:
  - short rest (<= 5 days, a Thursday after a Sunday) ........ watch note on the game (both teams) - small but real effect on offense
  - long rest (>= 10 days, off a bye) ....................... info
  - West Coast / Mountain team kicking off at 1:00 ET ........ info ("body clock")
  - division game, primetime, international, dome/outdoors .... info
  - standings: record, division place, games back; "eliminated" / "clinched" only when the arithmetic says so; from Week 16 a team that has
    clinched its seed gets a WATCH (starters may rest) and a team eliminated gets an info line (young players get snaps)
  - referee crew: this crew's average total points and overtime rate in games it worked (2023-26, n shown) vs the league - info only;
    dig2/ref_study.py (11/4): crew traits do not persist year to year (penalties r=0.21, DPI r=0.14; 2023-24 crew rankings did not predict
    2025 overs - the hot crews reverted), so the crew is never an input
Writes in/ctx_stakes.json: {"week", "games": {"A-B": [{k, tag, txt}]}, "players": [], "standings": {team: {...}}}
Usage: python3 stakes.py <WEEK>
"""
import csv, io, json, os, subprocess, sys, datetime as dt, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); os.makedirs(IN, exist_ok=True)
DIV = {"BUF": "AFC East", "MIA": "AFC East", "NE": "AFC East", "NYJ": "AFC East", "BAL": "AFC North", "CIN": "AFC North", "CLE": "AFC North", "PIT": "AFC North",
       "HOU": "AFC South", "IND": "AFC South", "JAX": "AFC South", "TEN": "AFC South", "DEN": "AFC West", "KC": "AFC West", "LV": "AFC West", "LAC": "AFC West",
       "DAL": "NFC East", "NYG": "NFC East", "PHI": "NFC East", "WAS": "NFC East", "CHI": "NFC North", "DET": "NFC North", "GB": "NFC North", "MIN": "NFC North",
       "ATL": "NFC South", "CAR": "NFC South", "NO": "NFC South", "TB": "NFC South", "ARI": "NFC West", "LA": "NFC West", "SF": "NFC West", "SEA": "NFC West"}
WEST = {"SEA", "SF", "LA", "LAC", "LV", "ARI", "DEN"}   # Pacific + Mountain body clocks
def load_games():
    txt = subprocess.check_output(["curl", "-fsSL", "--max-time", "60", "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"]).decode()
    return list(csv.DictReader(io.StringIO(txt)))
def num(v):
    try: return float(v)
    except Exception: return None
def main(week):
    week = int(week); G = load_games(); now = dt.datetime.now()
    season = [g for g in G if g["season"] == "2026" and g["game_type"] == "REG"]
    # standings from completed games
    rec = {t: {"w": 0, "l": 0, "t": 0, "pf": 0, "pa": 0} for t in DIV}
    for g in season:
        a, h = g["away_team"], g["home_team"]; asc, hsc = num(g["away_score"]), num(g["home_score"])
        if asc is None or hsc is None or a not in rec or h not in rec: continue
        rec[a]["pf"] += asc; rec[a]["pa"] += hsc; rec[h]["pf"] += hsc; rec[h]["pa"] += asc
        if asc > hsc: rec[a]["w"] += 1; rec[h]["l"] += 1
        elif hsc > asc: rec[h]["w"] += 1; rec[a]["l"] += 1
        else: rec[a]["t"] += 1; rec[h]["t"] += 1
    def pct(r): n = r["w"] + r["l"] + r["t"]; return (r["w"] + 0.5 * r["t"]) / n if n else 0
    stand = {}
    for d in set(DIV.values()):
        tms = sorted([t for t in DIV if DIV[t] == d], key=lambda t: (-pct(rec[t]), -(rec[t]["pf"] - rec[t]["pa"])))
        lead = rec[tms[0]]
        for i, t in enumerate(tms):
            r = rec[t]; gb = ((lead["w"] - r["w"]) + (r["l"] - lead["l"])) / 2
            left = 17 - (r["w"] + r["l"] + r["t"])
            stand[t] = {"rec": f"{r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else ""), "div": d, "place": i + 1, "gb": gb, "left": left, "pf": r["pf"], "pa": r["pa"],
                        "elim_div": gb > left, "clinched_div": i == 0 and len(tms) > 1 and (gb_second := (((r["w"] - rec[tms[1]]["w"]) + (rec[tms[1]]["l"] - r["l"])) / 2)) > (17 - (rec[tms[1]]["w"] + rec[tms[1]]["l"] + rec[tms[1]]["t"]))}
    # referee crews: total points + OT in games worked 2023-2026
    refs = {}
    allt = []
    for g in G:
        if g["season"] not in ("2023", "2024", "2025", "2026") or g["game_type"] != "REG": continue
        tot = num(g.get("total")); ref = (g.get("referee") or "").strip()
        if tot is None or not ref: continue
        refs.setdefault(ref, {"tot": [], "ot": 0}); refs[ref]["tot"].append(tot); refs[ref]["ot"] += 1 if (g.get("overtime") or "0") in ("1", "1.0", "True", "TRUE") else 0; allt.append(tot)
    lg = statistics.mean(allt) if allt else 0
    games = {}
    def note(gid, k, tag, txt): games.setdefault(gid, []).append({"k": k, "tag": tag, "txt": txt})
    for g in season:
        if g["week"] != str(week): continue
        a, h = g["away_team"], g["home_team"]; gid = "-".join(sorted([a, h]))
        sa, sh = stand.get(a), stand.get(h)
        if sa and sh:
            def line(t, s):
                x = f"{t} {s['rec']}, {['1st', '2nd', '3rd', '4th'][s['place'] - 1]} in the {s['div']}" + (f" ({s['gb']:g} back)" if s["gb"] else "")
                if s["elim_div"]: x += " - out of the division race"
                return x
            note(gid, "info", "Standings", line(a, sa) + "; " + line(h, sh) + ".")
            if week >= 16:
                for t, s in ((a, sa), (h, sh)):
                    if s["clinched_div"]: note(gid, "watch", "Resting risk", f"{t} has clinched its division - check the inactives and the beat for starters sitting.")
        ar, hr = num(g.get("away_rest")), num(g.get("home_rest"))
        if g.get("div_game") in ("1", "1.0", "True", "TRUE"): note(gid, "info", "Division game", f"{a} at {h} is a division game - familiarity tends to tighten margins; nothing in our data says it changes player volume.")
        if ar is not None and hr is not None and ar <= 5 and hr <= 5: note(gid, "watch", "Short week", f"Both teams on {int(ar)} days' rest (Thursday after a Sunday). Offenses score a little less on short rest - unders and lower-ceiling calls run better in these spots; totals already price some of it.")
        else:
            for t, rst, ot in ((a, ar, h), (h, hr, a)):
                if rst is not None and rst <= 5: note(gid, "watch", "Short week", f"{t} is on {int(rst)} days' rest (short week) against a {ot} side with {int(hr if t == a else ar) if (hr if t == a else ar) is not None else '?'} days. Offenses score a little less on short rest.")
                elif rst is not None and rst >= 10: note(gid, "info", "Off a bye", f"{t} has {int(rst)} days' rest (off a bye / long week).")
        try: hour = int((g.get("gametime") or "0:00").split(":")[0])
        except Exception: hour = 0
        if g.get("weekday") in ("Monday", "Thursday") or hour >= 19: note(gid, "info", "Primetime", f"{g.get('weekday')} {g.get('gametime')} ET kickoff - standalone window.")
        if hour == 13:
            for t in (a, h):
                if t in WEST: note(gid, "info", "Body clock", f"{t} kicks off at 1:00 ET (10:00 am body clock for a West Coast / Mountain team).")
        if (g.get("location") or "Home") != "Home": note(gid, "info", "Neutral site", f"Played at {g.get('stadium') or 'a neutral site'}; both teams travel.")
        if g.get("roof") in ("dome", "closed"): note(gid, "info", "Indoors", f"{g.get('stadium') or 'Dome'} - no weather.")
        ref = (g.get("referee") or "").strip(); rr = refs.get(ref)
        if ref and rr and len(rr["tot"]) >= 12:
            m = statistics.mean(rr["tot"]); d = m - lg
            note(gid, "info", "Referee", f"{ref}'s crew: games average {m:.1f} points ({d:+.1f} vs the league's {lg:.1f}, n={len(rr['tot'])} since 2023), {rr['ot']} went to overtime. For the record only: our 2023-25 check found a crew's penalty, DPI and scoring rates do not carry from one season to the next (r = 0.1-0.2), so this is not a reason to move a total.")
    out = {"week": week, "built": now.isoformat(), "games": games, "players": [], "standings": stand}
    json.dump(out, open(os.path.join(IN, "ctx_stakes.json"), "w"), indent=1)
    print(f"stakes week {week}: {len(games)} games, {sum(len(v) for v in games.values())} notes; league avg total {lg:.1f}")
    for gid, ns in sorted(games.items()):
        print(" ", gid, "|", " · ".join(n["tag"] for n in ns))
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else 9)
