"""reprice.live_data reads the builder data file the published page LINKS (11/17).

Since 11/15 a publish keeps the previous build's data-<hash>.js in /build/ for pages cached a few minutes. live_data took "the last
file by name", which was the previous build's as often as not; on the first morning after a week roll it was last week's, so every
scheduled rebuild would have stopped with "rolling the week is a session's job".
  python3 tests/reprice_live.py"""
import json, os, sys, tempfile, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import reprice
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def clone(files, linked, mtimes=None):
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "build"))
    for name, week in files.items():
        p = os.path.join(d, "build", name); open(p, "w").write("window.__BS = " + json.dumps({"week": week, "built": "x", "legs": []}) + ";")
        if mtimes and name in mtimes: os.utime(p, (mtimes[name], mtimes[name]))
    if linked is not None: open(os.path.join(d, "build", "index.html"), "w").write(f'<html><script src="/build/{linked}"></script></html>')
    return d
now = time.time()
# the old week's file sorts LAST by name - the case that happened on 11/17 (data-4ed8... week 10 beside data-02f3... week 11)
c = clone({"data-02f30c0e92f3.js": 11, "data-4ed8b65dfdb7.js": 10}, "data-02f30c0e92f3.js")
check((reprice.live_data(c) or {}).get("week") == 11, "the linked file wins when the previous build's file sorts after it")
c = clone({"data-ffff0c0e92f3.js": 11, "data-0aaab65dfdb7.js": 10}, "data-ffff0c0e92f3.js")
check((reprice.live_data(c) or {}).get("week") == 11, "and when it sorts before it")
c = clone({"data-02f30c0e92f3.js": 11, "data-4ed8b65dfdb7.js": 10}, None, {"data-02f30c0e92f3.js": now, "data-4ed8b65dfdb7.js": now - 9000})
check((reprice.live_data(c) or {}).get("week") == 11, "no page to read: the newest file by time, not by name")
c = clone({"data-4ed8b65dfdb7.js": 10}, "data-02f30c0e92f3.js")
check((reprice.live_data(c) or {}).get("week") == 10, "the page links a file that is not there: the file that is")
c = clone({}, None)
check(reprice.live_data(c) is None, "no data file at all: None")
# ---- 11/17: the Sweep says lines - a session's rewrite committed to the bundle (voice/voice-w<W>.json) wins only while it is the newest ----
import shutil
def voice_case(out_built, pub_built, bun_built, W=77):
    out = tempfile.mkdtemp(); c = tempfile.mkdtemp(); os.makedirs(os.path.join(c, "b")); here = tempfile.mkdtemp(); os.makedirs(os.path.join(here, "voice"))
    mk = lambda who, built: {"week": W, "built": built, "games": {"AAA-BBB": who}}
    if out_built: json.dump(mk("out", out_built), open(os.path.join(out, "voice.json"), "w"))
    if pub_built: json.dump(mk("pub", pub_built), open(os.path.join(c, "b", "voice.json"), "w"))
    if bun_built: json.dump(mk("bundle", bun_built), open(os.path.join(here, "voice", f"voice-w{W}.json"), "w"))
    keep = (reprice.OUT, reprice.HERE); reprice.OUT, reprice.HERE = out, here
    try:
        msg = reprice.ensure_voice(c, W); got = json.load(open(os.path.join(out, "voice.json")))["games"]["AAA-BBB"]
    finally: reprice.OUT, reprice.HERE = keep
    for d in (out, c, here): shutil.rmtree(d, ignore_errors=True)
    return got, msg
check(voice_case(None, "2026-11-17T14:00:00Z", "2026-11-17T17:00:00Z")[0] == "bundle", "Sweep says: the bundle's lines win over an older published copy")
check(voice_case(None, "2026-11-17T21:00:00Z", "2026-11-17T17:00:00Z")[0] == "pub", "Sweep says: a later published copy wins over the bundle's lines")
check(voice_case("2026-11-17T22:00:00Z", "2026-11-17T21:00:00Z", "2026-11-17T17:00:00Z")[0] == "out", "Sweep says: a session's own newer file stays")
check(voice_case("2026-11-17T14:00:00Z", None, "2026-11-17T17:00:00Z")[0] == "bundle", "Sweep says: the bundle's lines replace an older local file")
check(voice_case(None, "2026-11-17T14:00:00Z", None)[0] == "pub", "Sweep says: no bundle file - the published copy, as before")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
