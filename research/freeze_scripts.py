#!/usr/bin/env python3
"""freeze_scripts.py - the model's read of every past game, as its card showed it at the last build before kickoff
(owner 11/17, "I want all four": save each week's game scripts so older findings can be recounted by their own definitions).

From 11/17 on build_boards.py files this itself (data/scripts-w<week>.json, updated at every build until a game kicks off). The weeks
before that were never saved anywhere but the site's history, so this digs them out once: for every week with a Parlay Builder data
file in the history, the last commit before each game's kickoff, and that game's projected points, four endings and likeliest ending
from the file that commit published.

    python3 research/freeze_scripts.py [--hist /tmp/fg/hist] [--write]      -> research/scripts_history.json

{week: {gid: {a, b, pa, pb, probs: [a by 10+, close and low, shootout, b by 10+], most, ko, commit, at}}}. Blobs are fetched from
GitHub as needed (about 2.5 MB a file, one per kickoff slot)."""
import argparse, bisect, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "research" else os.path.dirname(os.path.abspath(__file__))
def git(hist, *a): return subprocess.run(["git", "-C", hist] + list(a), capture_output=True, text=True, check=True).stdout

def data_at(hist, commit, cache={}):
    """the builder data that commit published (None when that commit had no data file)"""
    if commit in cache: return cache[commit]
    try:
        page = git(hist, "show", f"{commit}:build/index.html"); m = re.search(r"build/(data-[a-f0-9]+\.js)", page)
        if not m: cache[commit] = None; return None
        src = git(hist, "show", f"{commit}:build/{m.group(1)}"); cache[commit] = json.loads(src[src.index("{"):src.rindex("}") + 1])
    except Exception as e: print("  note:", commit, str(e)[:80]); cache[commit] = None
    return cache[commit]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--hist", default="/tmp/fg/hist"); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    subprocess.run(["git", "-C", a.hist, "fetch", "-q", "origin", "main"], check=False)
    log = [ln.split(" ", 2) for ln in git(a.hist, "log", "origin/main", "--reverse", "--format=%h %ct %s", "--", "build/index.html").splitlines()]
    commits = [(int(t), h, s) for h, t, s in log]; times = [c[0] for c in commits]
    # each week's first board build names the week's games and kickoffs
    first = {}
    for t, h, s in commits:
        m = re.match(r"Week (\d+) (boards|reprice)", s)
        if m and int(m.group(1)) not in first: first[int(m.group(1))] = h
    out = {}
    for wk in sorted(first):
        D = data_at(a.hist, first[wk])
        if not D or int(D.get("week") or 0) != wk or not D.get("games"): print(f"week {wk}: no builder data at its first build ({first[wk]}) - skipped"); continue
        games = {}
        # kickoffs can move and a game can be missing from the first build: take the union over the week's builds lazily, slot by slot
        for g in D["games"]:
            ko = g.get("ko")
            if not ko: continue
            i = bisect.bisect_left(times, int(ko / 1000)) - 1
            # walk back to the last commit before kickoff that still belongs to this week and has the game
            got = None
            while i >= 0 and not got:
                t, h, s = commits[i]; i -= 1
                if not re.match(rf"Week {wk} ", s): continue
                Dk = data_at(a.hist, h)
                if not Dk: continue
                gg = next((x for x in Dk.get("games", []) if x.get("gid") == g["gid"]), None)
                if gg and gg.get("probs"): got = (gg, h, t)
            if not got: print(f"  week {wk} {g['gid']}: no pre-kickoff build found"); continue
            gg, h, t = got
            games[g["gid"]] = {"a": gg.get("a"), "b": gg.get("b"), "pa": gg.get("pa"), "pb": gg.get("pb"), "tot": gg.get("tot"), "probs": gg.get("probs"), "most": gg.get("most"), "ko": ko, "commit": h, "at": t}
        if games and max(v["ko"] for v in games.values()) > __import__("time").time() * 1000: print(f"week {wk}: still being played - left to build_boards' own file"); continue
        out[str(wk)] = games
        mins = sorted((v["ko"] / 1000 - v["at"]) / 60 for v in games.values())
        print(f"week {wk}: {len(games)} of {len(D['games'])} games; last build before kickoff was {mins[0]:.0f} to {mins[-1]:.0f} minutes ahead (median {mins[len(mins) // 2]:.0f})")
    if a.write:
        p = os.path.join(HERE, "research", "scripts_history.json"); json.dump({"note": "the model's read of each game at the last build before its kickoff (research/freeze_scripts.py, from the site's history)", "weeks": out}, open(p, "w"), indent=0); print("wrote", p, os.path.getsize(p) // 1024, "KB")
if __name__ == "__main__": main()
