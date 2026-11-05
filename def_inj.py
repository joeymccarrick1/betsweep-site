#!/usr/bin/env python3
"""def_inj.py - defensive injuries into the WR-CB coverage read and the game cards (owner 11/4 context desk, item 1).

The availability tab only knows about offensive players. Clay's WR-CB sheet names the corner each receiver is projected to see; if that corner
is Out, the "Tough coverage" read is wrong and the receiver is facing a backup. This script reads this week's injury report for defenders from
  - nflverse injuries_2026.csv (official Wed/Thu/Fri reports; github.com is reachable from the sandbox)
  - the feeds branch injuries.json (ESPN team pages, every 10 min, carries statuses between official reports)
and writes in/ctx_definj.json:
  cbs:     {corner name: {"status": Out|Doubtful|Questionable|IR, "why", "team"}} - flags.py turns the receiver's Coverage flag into 'Corner out'
           (good) or 'Corner questionable' (watch) when his primary corner is on the list
  games:   per game, the defensive starters-level names on the report by unit (secondary / front), for the game card context line
  players: a 'good' note for the opposing QB when 2+ secondary players are Out (thin secondary), info otherwise
Usage: python3 def_inj.py <WEEK>
"""
import csv, io, json, os, re, subprocess, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in")
SITE = "/home/claude/betsweep-site"; RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/"
WRCB_TEAM = {"ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU", "LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
TEAM_OF = {"Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN",
           "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB", "Houston Texans": "HOU", "Indianapolis Colts": "IND",
           "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
           "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
           "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS"}
SECONDARY = {"CB", "S", "SS", "FS", "DB", "NB"}; FRONT = {"DE", "DT", "NT", "EDGE", "OLB", "LB", "ILB", "MLB", "DL"}
def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def fetch_feed(name):
    try: return json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "30", RAW + name], stderr=subprocess.DEVNULL))
    except Exception: pass
    subprocess.run(["git", "-C", SITE, "fetch", "-q", "origin", "feeds"], check=True)
    return json.loads(subprocess.check_output(["git", "-C", SITE, "show", f"FETCH_HEAD:{name}"], stderr=subprocess.DEVNULL))
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d

def main(week):
    week = int(week); now = dt.datetime.now(dt.timezone.utc)
    DEF = {}   # nn(name) -> {name, team, pos, status, why, src}
    rank = {"IR": 5, "Out": 4, "Doubtful": 3, "Questionable": 2}
    def put(name, team, pos, status, why, src):
        if not name or status not in rank: return
        k = nn(name); cur = DEF.get(k)
        if cur and rank[cur["status"]] >= rank[status]: return
        DEF[k] = {"name": name, "team": team, "pos": pos, "status": status, "why": why, "src": src}
    # official reports (nflverse)
    try:
        csvt = subprocess.check_output(["curl", "-fsSL", "--max-time", "40", "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv"]).decode()
        n = 0
        for r in csv.DictReader(io.StringIO(csvt)):
            if r.get("week") != str(week) or r.get("position") not in SECONDARY | FRONT: continue
            st = (r.get("report_status") or "").strip(); prac = (r.get("practice_status") or "")
            if not st and "Did Not Participate" in prac: st = "Questionable"   # no designation yet (Wed/Thu), DNP
            if st: put(r["full_name"], r["team"], r["position"], st, (r.get("report_primary_injury") or r.get("practice_primary_injury") or "").lower(), "official report"); n += 1
        print(f"def_inj: nflverse week {week}: {n} defensive report rows")
    except Exception as e: print("def_inj: nflverse injuries skipped", e)
    # ESPN team pages (positions are not in the feed: we take the names Clay's sheet knows as corners, plus any 'cornerback'/'safety' in the comment)
    try:
        for tm in fetch_feed("injuries.json").get("injuries", []):
            team = TEAM_OF.get((tm.get("team") or {}).get("displayName") or "", "")
            for e in tm.get("injuries") or []:
                nm = (e.get("athlete") or {}).get("displayName"); st = (e.get("status") or "").strip(); cm = (e.get("shortComment") or "")
                st = {"Injured Reserve": "IR", "Out": "Out", "Doubtful": "Doubtful", "Questionable": "Questionable"}.get(st)
                if not st: continue
                pos = "CB" if re.search(r"\bcornerback|\bcorner\b|\bCB\b", cm) else "S" if re.search(r"\bsafety\b", cm) else "DL" if re.search(r"defensive (end|tackle|lineman)|linebacker|edge rusher|pass rusher", cm, re.I) else None
                put(nm, team, pos or "?", st, ((e.get("details") or {}).get("type") or "").lower(), "ESPN team report")
    except Exception as e: print("def_inj: feeds injuries.json skipped", e)
    # Clay's corners this week
    rows = vals("wrcb.json"); H = {c: i for i, c in enumerate(rows[0])} if rows else {}
    cbs = {}; games = {}; by_team_sec = {}
    def cell(r, c):
        i = H.get(c); return r[i] if i is not None and i < len(r) else ""
    corners = {}
    for r in rows[1:]:
        try:
            if int(float(cell(r, "Week"))) != week: continue
        except Exception: continue
        cb = cell(r, "Primary CB"); cbt = WRCB_TEAM.get(cell(r, "CB Team"), cell(r, "CB Team")); wt = WRCB_TEAM.get(cell(r, "WR Team"), cell(r, "WR Team"))
        if cb: corners[nn(cb)] = (cb, cbt, wt)
    for k, (cb, cbt, wt) in corners.items():
        d = DEF.get(k)
        if d: cbs[cb] = {"status": d["status"], "why": d["why"], "team": cbt, "src": d["src"]}; print(f"  corner {cb} ({cbt}) {d['status']} - {d['why']} [{d['src']}] -> receivers of {wt}")
    # game-level: defenders on the report by team
    sched = {}
    for r in vals("boards.json") or []: pass
    for d in DEF.values():
        if d["team"] and d["pos"] != "?": by_team_sec.setdefault(d["team"], []).append(d)
    # opponents from the WR-CB sheet (receiver team -> corner team)
    opp = {}
    for cb, cbt, wt in corners.values(): opp[wt] = cbt; opp[cbt] = wt
    players = []
    for team, ds in by_team_sec.items():
        sec = [d for d in ds if d["pos"] in SECONDARY or d["pos"] == "CB" or d["pos"] == "S"]; fr = [d for d in ds if d["pos"] in FRONT or d["pos"] == "DL"]
        txt = "; ".join(f"{d['name']} ({d['pos']}, {d['status']}{', ' + d['why'] if d['why'] else ''})" for d in sorted(ds, key=lambda d: -rank[d['status']]))
        o = opp.get(team)
        gid = "-".join(sorted([team, o])) if o else None
        if gid: games.setdefault(gid, []).append({"k": "info", "tag": f"{team} defense", "txt": f"On the injury report: {txt}."})
        outs = [d for d in sec if d["status"] in ("Out", "IR", "Doubtful")]
        if len(outs) >= 2 and o:
            players.append({"player": "__TEAM_QB__", "team": o, "k": "good", "tag": "Thin secondary", "txt": f"{team} is missing {len(outs)} secondary players ({', '.join(d['name'] for d in outs)}) - a softer look for {o}'s passing game than the season ranks say."})
    # resolve __TEAM_QB__ to the model's QB1 for that team (proj_qb.json col A/B; the first listed is fine - the forced-role QB1 is handled by flags via avail)
    qbs = {}
    for r in vals("proj_qb.json")[1:]:
        if len(r) > 1 and r[0] and r[1] and r[1] not in qbs: qbs[r[1]] = r[0]
    for p in players:
        if p["player"] == "__TEAM_QB__": p["player"] = qbs.get(p["team"], "")
    players = [p for p in players if p["player"]]
    out = {"week": week, "built": now.isoformat(), "cbs": cbs, "games": games, "players": players}
    json.dump(out, open(os.path.join(IN, "ctx_definj.json"), "w"), indent=1)
    print(f"def_inj week {week}: {len(DEF)} defenders on reports, {len(cbs)} of Clay's primary corners affected, {len(games)} games with defensive report lines, {len(players)} thin-secondary notes")
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else 9)
