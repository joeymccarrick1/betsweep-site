#!/usr/bin/env python3
"""depth_check.py - ESPN depth charts vs the model's roles (owner 11/4: Emanuel Wilson lost his job when Charbonnet and Price came back and the
model still had him as the RB1 off his fill-in weeks).

Input: feeds-branch depthcharts.json (.github/feeds.py, hourly: ESPN core-API depth chart per team, RB / WR / TE / QB order with each
player's ESPN injury status), in/proj_*.json (the model's Weekly Depth Role / Effective Weekly Role per player), in/avail.json.

For every team and position group it compares ESPN's order of HEALTHY players with the model's role:
  RB  model RB1 who is ESPN RB3 or lower, healthy ........ propose Forced Role "RB3 / SPECIALIST" (or "DEPTH / CONTEXT" if RB4+) + WATCH flag "Depth chart: demoted"
      model RB2 who is ESPN RB4 or lower .................. propose "DEPTH / CONTEXT"
      ESPN RB1 whom the model has RB3 / DEPTH, healthy ...... propose Forced Role "RB1" + GOOD flag "Depth chart: promoted"; ESPN RB2 held as DEPTH -> "RB2"
  QB  ESPN QB1 (healthy) who is not the model's QB1 ........ propose Forced Role "QB1" (the model's QB1 to "DEPTH / CONTEXT" is left to the rebuild session: an injury OUT may already cover it)
  WR / TE  the model has no forced WR roles; a WR the model projects for 15%+ targets who is ESPN WR4 or lower (healthy) gets a WATCH flag; an ESPN
      WR1/WR2 the model projects under 8% targets gets an INFO flag "Depth chart: higher than our numbers"
Never sets OUT. Every proposal carries "ESPN depth chart <mirror time>" as its source. The rebuild session appends the rows (RUNBOOK Step 2a)
unless the player already has a Forced Role row this week.
Writes in/ctx_depth.json (flags) and out/depth_rows.json (proposed availability rows). Usage: python3 depth_check.py <WEEK>
"""
import json, os, re, subprocess, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SITE = "/home/claude/betsweep-site"; RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/"
ESPN_TEAM = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def num(v):
    try: return float(str(v).replace("%", ""))
    except Exception: return None
def fetch(name):
    try: return json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "30", RAW + name], stderr=subprocess.DEVNULL))
    except Exception: pass
    subprocess.run(["git", "-C", SITE, "fetch", "-q", "origin", "feeds"], check=True)
    return json.loads(subprocess.check_output(["git", "-C", SITE, "show", f"FETCH_HEAD:{name}"], stderr=subprocess.DEVNULL))
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
def main(week):
    week = int(week); now = dt.datetime.now()
    DC = fetch("depthcharts.json"); when = DC.get("mirrored", "")[:16].replace("T", " ")
    # model roles
    M = {}   # (team, pos) -> list of (name, role, tgt_share)
    for f, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
        rows = vals(f)
        if not rows: continue
        H = {c: i for i, c in enumerate(rows[0])}
        rc = H.get("Effective Weekly Role") if pos == "QB" else (H.get("Weekly Depth Role") if "Weekly Depth Role" in H else H.get("Effective Weekly Role"))
        tc = H.get("Targets Avg"); oc = H.get("Opponent")
        for r in rows[1:]:
            if not r or not r[0] or len(r) < 3: continue
            if oc is not None and oc < len(r) and str(r[oc]).upper() == "BYE": continue
            role = r[rc] if rc is not None and rc < len(r) else ""
            M.setdefault((r[1], pos), []).append({"name": r[0], "role": role, "tgt": num(r[tc]) if tc is not None and tc < len(r) else None, "k": nn(r[0])})
    # targets per game -> share of the team's receiving targets in the model (WR/TE depth read)
    for (team, pos), lst in list(M.items()):
        if pos in ("WR", "TE"):
            tot = sum(x["tgt"] or 0 for p2 in ("WR", "TE", "RB") for x in M.get((team, p2), []))
            for x in lst: x["tgt"] = (x["tgt"] / tot) if (x["tgt"] is not None and tot) else None
    AV = {}
    for r in vals("avail.json")[1:]:
        if len(r) > 6 and str(r[0]) == str(week): AV[nn(r[1])] = {"status": (r[4] or "").strip().upper(), "forced": (r[6] or "").strip()}
    notes = []; rows = []
    def propose(name, team, pos, forced, why):
        cur = AV.get(nn(name), {})
        if cur.get("forced") or cur.get("status") in ("OUT", "IR"): return
        rows.append([str(week), name, team, pos, "", "", forced, "", "", f"DEPTH CHART: {why}", f"ESPN depth chart {when} (feeds depthcharts.json)", now.strftime("%Y-%m-%d"), ""])
    for ab, t in (DC.get("teams") or {}).items():
        team = ESPN_TEAM.get(ab, ab); chart = t.get("chart") or {}
        for grp in ("RB", "QB", "WR", "TE"):
            espn = [x for x in chart.get(grp, []) if x.get("name")]
            healthy = [x for x in espn if not any(s in ("Out", "Injured Reserve", "Doubtful", "Suspension", "Physically Unable to Perform") for s in (x.get("inj") or []))]
            erank = {nn(x["name"]): i + 1 for i, x in enumerate(healthy)}   # order among healthy players
            erank_all = {nn(x["name"]): i + 1 for i, x in enumerate(espn)}
            model = M.get((team, grp), [])
            for m in model:
                er = erank.get(m["k"]); ea = erank_all.get(m["k"]); role = (m["role"] or "").upper()
                if ea is None or role in ("OUT",) or AV.get(m["k"], {}).get("status") in ("OUT", "IR"): continue
                if er is None: continue   # ESPN lists him hurt: the injury layer owns that
                if grp == "RB":
                    if role == "RB1" and er >= 3:
                        forced = "RB3 / SPECIALIST" if er == 3 else "DEPTH / CONTEXT"
                        ahead = ", ".join(x["name"] for x in healthy[:er - 1])
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "watch", "tag": "Depth chart: demoted", "txt": f"ESPN's depth chart has him RB{er} behind {ahead}; the model still carries him as the RB1 off his recent games. Role forced down for this week (ESPN chart {when})."})
                        propose(m["name"], team, grp, forced, f"model RB1, ESPN RB{er} behind {ahead}")
                    elif role == "RB2" and er >= 4:
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "watch", "tag": "Depth chart: demoted", "txt": f"ESPN's depth chart has him RB{er}; the model has him RB2. Role forced to depth (ESPN chart {when})."})
                        propose(m["name"], team, grp, "DEPTH / CONTEXT", f"model RB2, ESPN RB{er}")
                    elif er == 1 and role in ("RB3 / SPECIALIST", "DEPTH / CONTEXT", ""):
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "good", "tag": "Depth chart: promoted", "txt": f"ESPN's depth chart lists him as the RB1; the model had him as {role.title() or 'depth'} off a small sample. Role forced up for this week (ESPN chart {when})."})
                        propose(m["name"], team, grp, "RB1", f"ESPN RB1, model {role or 'depth'}")
                    elif er == 2 and role in ("DEPTH / CONTEXT",):
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "good", "tag": "Depth chart: promoted", "txt": f"ESPN's depth chart lists him as the RB2; the model had him as depth. Role forced to RB2 (ESPN chart {when})."})
                        propose(m["name"], team, grp, "RB2", f"ESPN RB2, model depth")
                elif grp == "QB":
                    if er == 1 and role != "QB1":
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "good", "tag": "Depth chart: starter", "txt": f"ESPN's depth chart lists him as the starting QB (healthy); the model had {role.title() or 'depth'}. Forced QB1 (ESPN chart {when})."})
                        propose(m["name"], team, grp, "QB1", f"ESPN QB1, model {role or 'depth'}")
                    elif er >= 2 and role == "QB1":
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "watch", "tag": "Depth chart: not the starter", "txt": f"ESPN's depth chart has him QB{er} ({healthy[0]['name']} first) while the model projects him as the QB1 - check the beat before trusting his legs (ESPN chart {when})."})
                else:
                    tgt = m.get("tgt"); tgt = tgt / 100 if tgt is not None and tgt > 1 else tgt
                    if grp == "WR" and tgt is not None and tgt >= 0.15 and er >= 4:
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "watch", "tag": "Depth chart: lower than our numbers", "txt": f"ESPN's depth chart has him WR{er} (healthy) while the model projects a {tgt*100:.0f}% target share - a role the box score may not have caught up to (ESPN chart {when})."})
                    elif grp == "WR" and tgt is not None and tgt < 0.08 and er <= 2:
                        notes.append({"player": m["name"], "team": team, "pos": grp, "k": "info", "tag": "Depth chart: higher than our numbers", "txt": f"ESPN's depth chart has him WR{er} while the model projects only a {tgt*100:.0f}% target share (ESPN chart {when})."})
    json.dump({"week": week, "built": now.isoformat(), "players": notes, "games": {}, "espn_mirrored": DC.get("mirrored")}, open(os.path.join(IN, "ctx_depth.json"), "w"), indent=1)
    json.dump(rows, open(os.path.join(OUT, "depth_rows.json"), "w"), indent=1)
    from collections import Counter
    print(f"depth check week {week} (ESPN chart {when}): {len(notes)} notes {dict(Counter(n['tag'] for n in notes))}, {len(rows)} proposed Forced Role rows")
    for n in notes: print(f"  [{n['tag']}] {n['player']} ({n['team']} {n['pos']}): {n['txt'][:130]}")
    if rows:
        print("PROPOSED 'AUTO - Weekly Availability' Forced Role rows (skip if he already has a forced role or an OUT this week):")
        for r in rows: print("  ", r[1], r[2], r[3], "->", r[6], "|", r[9])
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else 9)
