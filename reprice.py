#!/usr/bin/env python3
"""reprice.py - the rebuild's script chain with no Claude session (owner 11/10: "Hourly auto-reprice with no Claude session, which
also ends blocked manual rebuilds").

Between rebuild sessions the site's prices stood still (Tuesday 3:56 PM to Thursday 3:40 PM) while the sheet mirror refreshed every
30 minutes.  This runs every generator the RUNBOOK lists, in the RUNBOOK's order, on the newest mirror, and stops short of the three
things only a session does: it never writes to the Google Sheet (no archive rows, no availability rows, no snap-trend refresh), it
never writes a Sweep says line (it re-uses the lines the last session published at /b/voice.json), and it never runs the Tuesday
grading.  Everything else - weather, the context desk's flags, boards, builder, every page - is rebuilt from the same code.

  python3 reprice.py --mirror <sheet-mirror clone>/in --clone <site clone on main> [--publish all|changed|none] [options]

  --publish none      build ./site and check it, touch nothing in the clone (default)
  --publish all       copy the whole build into the clone (what RUNBOOK Step 6c does by hand)
  --publish changed   the hourly mode: the same copy, but only when a FanDuel price or the list of legs differs from what
                      the clone is serving; otherwise it leaves the clone alone and exits 0 with "nothing moved"
  --max-age N         refuse a mirror older than N minutes (default 180: the mirror job itself is sometimes an hour late; 0 = any age)
  --allow-week-change build even when the mirror's week is not the week the clone is serving (a session rolls the week, not this)
  --keep-in           do not copy the mirror into in/ (use in/ as it is)
  --skip-desk         skip weather / owner notes / the context desk (flags come from whatever in/ctx_*.json already holds)

Exit codes: 0 built (and copied, if asked) - 2 mirror too old - 3 week differs - 4 a required step failed - 5 a check on the built
site failed - 6 a flag step failed, so the build is not copied.  The caller commits and pushes the clone; this script never runs git
except `git fetch origin feeds` inside the generators that need the feeds branch.  It prints one JSON summary line last.
"""
import argparse, datetime, glob, html, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); SITE = os.path.join(HERE, "site")

# (label, script + args, level).  hard = the build stops.  flag = the build finishes but is not copied (the page flags would be wrong).
# soft = noted; that page keeps whatever the clone already serves.
DESK = [
    ("weather feed", "weather_feed.py {clone} {W}", "flag"),
    ("owner notes", "risk_notes.py {clone}/data/risk-notes.json {W}", "soft"),
    ("news desk", "news_desk.py {W}", "flag"),
    ("depth charts", "depth_check.py {W}", "flag"),
    ("defensive injuries", "def_inj.py {W}", "flag"),
    ("stakes", "stakes.py {W}", "soft"),
    ("role rising", "role_rising.py {W}", "flag"),
    ("consensus", "consensus.py {W}", "flag"),
    ("availability reach", "avail_check.py", "soft"),
    ("snap trends", "build_snaps.py", "soft"),
    ("strength of schedule", "build_sos.py", "soft"),
]
BUILD = [
    ("first TD", "build_firsttd.py", "hard"),
    ("VOICE", "", "hard"),
    ("boards", "build_boards.py", "hard"),
    ("calls", "build_calls.py", "soft"),
    ("red-zone TD model", "rztd.py {W}", "soft"),
    ("builder", "build_builder.py", "hard"),
    ("players (first pass: lets the team, dossier and home pages link them)", "build_players.py", "soft"),
    ("live", "build_live.py", "hard"),
    ("today", "build_today.py", "hard"),
    ("teasers", "build_teasers.py", "soft"),
    ("survivor", "build_survivor.py", "soft"),
    ("sweep my slip", "build_slipcheck.py", "soft"),
    ("pairs", "build_pairs.py", "soft"),
    ("boost finder", "build_boost.py", "soft"),
    ("line shop", "build_shop.py", "soft"),
    ("beat the model", "build_beat.py", "soft"),
    ("missed by one", "badbeats.py {Wprev}", "soft"),
    ("fantasy", "build_team.py", "soft"),
    ("dfs", "build_dfs.py", "soft"),
    ("my data", "build_mydata.py", "soft"),
    ("trade", "build_trade.py", "soft"),
    ("dossier", "build_dossier.py", "soft"),
    ("teams", "build_teams.py", "soft"),
    ("targets", "build_targets.py", "soft"),
    ("today (with targets)", "build_today.py", "hard"),
    ("players", "build_players.py", "soft"),
    ("usage", "build_usage.py", "soft"),
    ("guide", "build_guide.py", "soft"),
    ("legal", "build_legal.py", "soft"),
    ("shadow slips", "shadow_slips.py", "soft"),
    ("promos", "build_promo.py {clone}/promo-slips", "hard"),
    ("site", "build_site.py betsweep.co {clone}/posts", "hard"),
]

# What the clone keeps no matter what the build holds (RUNBOOK 6c): the owner's uploads, the workflows, the concept lab.
PROTECTED = {".git", ".github", ".gitignore", "posts", "promo-slips", "lab", "CNAME"}
# Folders that are added to, never emptied first: old short links keep working, the workflows' own files in data/ stay, older receipts
# stay, the app-store wrapper project in app/ stays.
MERGE = {"b", "data", "receipts", "app", "season"}


def log(*a): print(*a, flush=True)


def vals(name):
    d = json.load(open(os.path.join(IN, name))); return d.get("values", d) if isinstance(d, dict) else d


def week_of_inputs():
    return int(float(next(r[1] for r in vals("settings.json") if r and str(r[0]).strip().lower() == "projection week")))


def live_data(clone):
    """The builder data the clone is serving: {"week", "built", "legs": {key: (odds, status)}}, or None."""
    fs = sorted(glob.glob(os.path.join(clone, "build", "data-*.js")))
    if not fs: return None
    s = open(fs[-1], encoding="utf-8").read(); m = re.search(r"window\.__BS\s*=\s*", s)
    if not m: return None
    return json.JSONDecoder().raw_decode(s, m.end())[0]


def leg_prices(bd):
    out = {}
    for l in (bd or {}).get("legs") or []:
        out[f'{l.get("g")}|{l.get("pl")}|{l.get("m")}|{l.get("ln")}'] = l.get("o")
    return out


def ensure_voice(clone, W):
    """out/voice.json for week W: keep a session's own file, else the copy the last build published, else the lines on the home page."""
    p = os.path.join(OUT, "voice.json")
    try:
        v = json.load(open(p))
        if int(v.get("week") or 0) == W and v.get("games"): return f"out/voice.json as it is ({len(v['games'])} game lines)"
    except Exception: pass
    try:
        v = json.load(open(os.path.join(clone, "b", "voice.json")))
        if int(v.get("week") or 0) == W and v.get("games"):
            json.dump(v, open(p, "w"), ensure_ascii=False); return f"the published /b/voice.json ({len(v['games'])} game lines, written {v.get('built')})"
    except Exception: pass
    # last resort: read the lines back off the home page the clone serves (same week only)
    try:
        bd = live_data(clone); page = open(os.path.join(clone, "index.html"), encoding="utf-8").read()
        if not bd or int(bd.get("week") or 0) != W: raise ValueError("the clone serves another week")
        games, picks = {}, {}
        for card in re.split(r'(?=<article class="tdgame")', page)[1:]:
            g = re.search(r'data-gid="([^"]+)"', card); s = re.search(r'<p class="sweepsays"><i>Sweep says</i>(.*?)</p>', card, re.S)
            if g and s: games[g.group(1)] = html.unescape(re.sub(r"<[^>]+>", "", s.group(1))).strip()
        if not games: raise ValueError("no Sweep says lines on the home page")
        json.dump({"week": W, "built": "read back from the home page", "games": games, "picks": picks}, open(p, "w"), ensure_ascii=False)
        return f"read back from the home page ({len(games)} game lines; picks and leans are not recoverable this way)"
    except Exception as e:
        if os.path.exists(p): os.remove(p)
        return f"NONE ({e}) - the cards carry no Sweep says line until a session writes one"


def run(label, cmd, level, env):
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable] + cmd.split(), cwd=HERE, capture_output=True, text=True, timeout=900, env=env)
        ok = r.returncode == 0; lines = [x for x in (r.stdout or "").strip().splitlines() if x.strip()]
        tail = lines[-1] if lines else ""; err = (r.stderr or "").strip().splitlines()[-3:]
    except subprocess.TimeoutExpired:
        ok, tail, err, lines = False, "timed out after 15 minutes", [], []
    log(f"[{'ok' if ok else 'FAILED'} {time.time() - t0:5.1f}s] {label}: {tail[:300]}")
    warn = [x for x in lines if x.lstrip().upper().startswith(("WARNING", "WARN:", "PICK REFUSED", "IGNORED BY THE SHEET"))]
    for x in warn[:6]: log("        " + x[:300])
    if not ok:
        for x in err: log("        ! " + x[:300])
    return ok, tail, warn


def check_site(W, live):
    """Cheap, browser-free checks on ./site before anything is copied.  Returns a list of problems (empty = good)."""
    bad = []
    def need(path, min_kb):
        p = os.path.join(SITE, path)
        if not os.path.exists(p): bad.append(f"{path} is missing")
        elif os.path.getsize(p) < min_kb * 1024: bad.append(f"{path} is only {os.path.getsize(p) // 1024} KB")
    for path, kb in (("index.html", 60), ("boards/index.html", 300), ("build/index.html", 100), ("live/index.html", 100), ("short/index.html", 8),
                     ("sw.js", 1), ("manifest.webmanifest", 0), ("404.html", 1), ("s", 0), ("b/index.html", 1)):
        need(path, kb)
    try: bd = json.load(open(os.path.join(OUT, "builder_data.json")))
    except Exception as e: return bad + [f"out/builder_data.json unreadable: {e}"]
    if int(bd.get("week") or 0) != W: bad.append(f"builder data is week {bd.get('week')}, inputs are week {W}")
    n_new, n_live = len(bd.get("legs") or []), len((live or {}).get("legs") or [])
    if n_live and n_new < 0.6 * n_live: bad.append(f"the board shrank: {n_new} legs against {n_live} live")
    if not n_live and n_new < 200: bad.append(f"only {n_new} legs priced")
    g_new, g_live = len(bd.get("games") or []), len((live or {}).get("games") or [])
    if g_live and g_new < g_live - 1 and int((live or {}).get("week") or 0) == W: bad.append(f"games fell from {g_live} to {g_new}")
    try:
        b = open(os.path.join(SITE, "boards", "index.html"), encoding="utf-8").read()
        if f"Week {W}" not in b: bad.append(f"boards page does not say Week {W}")
        for path in ("index.html", "short/index.html"):
            t = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<[^>]+>", " ", open(os.path.join(SITE, path), encoding="utf-8").read(), flags=re.S)
            for w in ("undefined", "NaN%", "Traceback"):
                if re.search(r"\b" + re.escape(w), t): bad.append(f"{path} shows '{w}' in its text")
    except Exception as e: bad.append(f"could not read a built page: {e}")
    return bad


def copy_into_clone(clone):
    """RUNBOOK Step 6c as code.  Every top-level thing the build made replaces the clone's copy, except the MERGE folders (added to)
    and the PROTECTED names (never touched).  A folder the build did not make this run (season/, an older receipt) stays as it is."""
    done = []
    for name in sorted(os.listdir(SITE)):
        if name in PROTECTED: continue
        src, dst = os.path.join(SITE, name), os.path.join(clone, name)
        if os.path.isdir(src):
            if name == "app":
                os.makedirs(dst, exist_ok=True)
                for f in glob.glob(os.path.join(src, "*.png")): shutil.copy2(f, dst)
            elif name in MERGE: shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                if os.path.isdir(dst): shutil.rmtree(dst)
                shutil.copytree(src, dst)
        else: shutil.copy2(src, dst)
        done.append(name)
    if "promo" not in done and os.path.isdir(os.path.join(clone, "promo")): shutil.rmtree(os.path.join(clone, "promo"))   # last week's posters
    mk = os.path.join(clone, "lab", "merged", "make.py")
    if os.path.exists(mk):
        r = subprocess.run([sys.executable, "lab/merged/make.py"], cwd=clone, capture_output=True, text=True)
        log("lab/merged:", ((r.stdout or r.stderr).strip().splitlines() or ["(no output)"])[-1][:200])
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mirror"); ap.add_argument("--clone", required=True); ap.add_argument("--publish", choices=("none", "all", "changed"), default="none")
    ap.add_argument("--max-age", type=int, default=180); ap.add_argument("--allow-week-change", action="store_true")
    ap.add_argument("--keep-in", action="store_true"); ap.add_argument("--skip-desk", action="store_true")
    a = ap.parse_args(); clone = os.path.abspath(a.clone); S = {"started": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "publish": a.publish}
    def finish(code, why):
        S["exit"] = code; S["result"] = why; log("REPRICE " + json.dumps(S, separators=(",", ":"))); sys.exit(code)
    os.makedirs(IN, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    if not a.keep_in:
        if not a.mirror: raise SystemExit("--mirror <sheet-mirror clone>/in is required unless --keep-in")
        stamp = json.load(open(os.path.join(a.mirror, "MIRROR.json"))).get("pulled", "")
        age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)).total_seconds() / 60
        S["mirror"] = stamp; S["mirror_age_min"] = round(age)
        if a.max_age and age > a.max_age: finish(2, f"mirror is {age:.0f} minutes old (limit {a.max_age})")
        n = 0
        for f in glob.glob(os.path.join(a.mirror, "*.json")) + glob.glob(os.path.join(a.mirror, "games.csv")):
            shutil.copy2(f, IN); n += 1
        log(f"inputs from sheet-mirror {stamp} ({age:.0f} min old, {n} files)")
    W = week_of_inputs(); S["week"] = W
    live = live_data(clone); S["live_week"] = (live or {}).get("week"); S["live_built"] = (live or {}).get("built")
    if live and int(live.get("week") or 0) != W and not a.allow_week_change:
        finish(3, f"the mirror is week {W}, the site serves week {live.get('week')}: rolling the week is a session's job")
    env = dict(os.environ); env.setdefault("BS_SITE", clone); env["PYTHONUNBUFFERED"] = "1"
    sub = lambda c: c.format(clone=clone, W=W, Wprev=W - 1)
    failed = {"hard": [], "flag": [], "soft": []}; warns = []
    steps = ([] if a.skip_desk else DESK) + BUILD
    if not a.skip_desk:      # the desk reads the public feeds branch; raw.githubusercontent.com first, this fetch is the fall-back they use
        r = subprocess.run(["git", "-C", clone, "fetch", "-q", "--depth", "1", "origin", "+feeds:refs/remotes/origin/feeds"], capture_output=True, text=True)
        log("[feeds] " + ("fetched origin/feeds" if r.returncode == 0 else "fetch failed: " + (r.stderr or "").strip()[:160]))
    for label, cmd, level in steps:
        if label == "VOICE":
            S["voice"] = ensure_voice(clone, W); log("[voice] " + S["voice"]); continue
        if not os.path.exists(os.path.join(HERE, cmd.split()[0])):
            log(f"[skip] {label}: {cmd.split()[0]} is not in this bundle"); continue
        if label == "site":      # the builder's preview image is rendered by a session (Step 4); keep the one the clone serves
            img = os.path.join(OUT, "img-build")
            if not os.path.exists(os.path.join(img, "preview.png")) and os.path.isdir(os.path.join(clone, "build", "img")):
                shutil.copytree(os.path.join(clone, "build", "img"), img, dirs_exist_ok=True)
        ok, tail, w = run(label, sub(cmd), level, env); warns += [f"{label}: {x}" for x in w]
        if not ok:
            failed[level].append(label)
            if level == "hard": S["failed"] = failed; finish(4, f"required step failed: {label}")
    S["failed"] = {k: v for k, v in failed.items() if v}; S["warnings"] = len(warns)
    bad = check_site(W, live); S["checks"] = bad or "ok"
    for b in bad: log("CHECK FAILED: " + b)
    if bad: finish(5, "the built site failed its checks; nothing copied")
    try: new = json.load(open(os.path.join(OUT, "builder_data.json")))
    except Exception: new = {}
    pn, pl = leg_prices(new), leg_prices(live)
    moved = sum(1 for k, v in pn.items() if k in pl and v != pl[k]); added = len(set(pn) - set(pl)); gone = len(set(pl) - set(pn))
    S["legs"] = len(pn); S["prices_moved"] = moved; S["legs_added"] = added; S["legs_gone"] = gone
    log(f"against the live site: {moved} legs with a new price, {added} new legs, {gone} legs gone ({len(pn)} legs now)")
    if a.publish == "none": finish(0, "built and checked; nothing copied (--publish none)")
    if failed["flag"]: finish(6, "a flag step failed (" + ", ".join(failed["flag"]) + "); not copied, the live flags stay")
    if a.publish == "changed" and not (moved or added or gone): finish(0, "nothing moved; the clone is left alone")
    S["copied"] = len(copy_into_clone(clone)); finish(0, "built, checked and copied into the clone")


if __name__ == "__main__":
    main()
