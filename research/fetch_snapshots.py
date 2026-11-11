#!/usr/bin/env python3
"""fetch_snapshots.py - the boards the site published before each game day's first kickoff, for research/risk_grade.py
(owner 11/10 deep dive: "a Tuesday report card grading every flag").

  python3 research/fetch_snapshots.py WEEK [WEEK ...]      (needs in/games.csv - the nflverse schedule the rebuild already reads)

For every kickoff time of the week it finds the last commit on main that touched build/ before that kickoff, downloads the builder data that commit served (build/data-<hash>.js, or the older build/index.html with the
data inline) into research/snapshots/, and prints the arguments to hand to risk_grade.py:

  python3 research/risk_grade.py 9=research/snapshots/w9-2026-11-05-1915.js@2026-11-06T01:01:12Z 9=research/snapshots/w9-2026-11-08-1200.js@2026-11-08T16:08:16Z ...

Reads through the GitHub API (`gh api`, or plain HTTPS when gh is not there - the repo is public). Nothing is written anywhere
but research/snapshots/ (not committed: .gitignore). Files already there are kept.
"""
import csv, datetime, json, os, subprocess, sys, urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.dirname(HERE); SNAP = os.path.join(HERE, "snapshots")
REPO = "joeymccarrick1/betsweep-site"; ET = ZoneInfo("America/New_York"); CT = ZoneInfo("America/Chicago")


def api(path, raw=False):
    try:
        cmd = ["gh", "api"] + (["-H", "Accept: application/vnd.github.raw"] if raw else []) + [path]
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if r.returncode == 0 and r.stdout: return r.stdout if raw else json.loads(r.stdout)
    except Exception: pass
    req = urllib.request.Request("https://api.github.com/" + path, headers={"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json", "User-Agent": "betsweep-research"})
    b = urllib.request.urlopen(req, timeout=120).read()
    return b if raw else json.loads(b)


def game_days(week, season=2026):
    days = {}
    for r in csv.DictReader(open(os.path.join(GP, "in", "games.csv"))):
        try:
            if int(r["season"]) != season or int(r["week"]) != int(week) or r.get("game_type", "REG") != "REG": continue
            ko = datetime.datetime.strptime(r["gameday"] + " " + (r.get("gametime") or "13:00"), "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        except Exception: continue
        days[ko.astimezone(CT).strftime("%Y-%m-%d-%H%M")] = ko      # one board per kickoff time: Sunday's noon games get Sunday morning's flags
    return sorted(days.items())


def main(weeks):
    os.makedirs(SNAP, exist_ok=True); args = []; have = {}      # commit -> file: several kickoff times often share one board
    for wk in weeks:
        for d, ko in game_days(wk):
            until = ko.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cs = api(f"repos/{REPO}/commits?sha=main&path=build&until={until}&per_page=1")
            if not cs: print(f"week {wk} {d}: no build/ commit before {until}"); continue
            sha = cs[0]["sha"]; when = cs[0]["commit"]["committer"]["date"]
            ls = api(f"repos/{REPO}/contents/build?ref={sha}"); name = next((x["name"] for x in ls if x["name"].startswith("data-") and x["name"].endswith(".js")), "index.html")
            if sha in have: continue
            out = os.path.join(SNAP, f"w{wk}-{d}" + (".js" if name != "index.html" else ".html")); have[sha] = out
            if not os.path.exists(out) or os.path.getsize(out) < 1000:
                open(out, "wb").write(api(f"repos/{REPO}/contents/build/{name}?ref={sha}", raw=True))
            print(f"week {wk} {d}: board of {when} (commit {sha[:8]}, {name}, {os.path.getsize(out) // 1024} KB), first kickoff {until}")
            args.append(f"{wk}={os.path.relpath(out, GP)}@{when}")
    print("\npython3 research/risk_grade.py " + " ".join(args))


if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    main(sys.argv[1:])
