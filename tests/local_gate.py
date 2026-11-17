#!/usr/bin/env python3
"""local_gate.py [regex] - the crawl and the yes / no the publish workflow runs, against ./site, with a server of its own.

The workflow crawls the site clone after the build has been copied into it. Here the build is ./site, which lacks the one file the
price job writes straight to the live site (/data/price-moves.json) - it is borrowed from the clone (or an empty one is written) so
its absence is not reported on every page.  Exit code = the gate's (0 ok to publish, 1 hold), 2 when the crawl could not run.
  python3 tests/local_gate.py            every page
  python3 tests/local_gate.py '^/live/'  some pages
"""
import functools, http.server, json, os, shutil, socket, subprocess, sys, threading
HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.environ.get("SITE") or os.path.join(HERE, "..", "site"); CLONE = os.environ.get("CLONE", "/home/claude/betsweep-site")
pm = os.path.join(SITE, "data", "price-moves.json"); made = False
if not os.path.exists(pm):
    os.makedirs(os.path.dirname(pm), exist_ok=True); src = os.path.join(CLONE, "data", "price-moves.json")
    if os.path.exists(src): shutil.copy(src, pm)
    else: open(pm, "w").write("{}")
    made = True
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=SITE)); threading.Thread(target=srv.serve_forever, daemon=True).start()
env = dict(os.environ, SITE=os.path.abspath(SITE), BASE=f"http://127.0.0.1:{port}")
try:
    r = subprocess.run([sys.executable, os.path.join(HERE, "site_crawl.py")] + sys.argv[1:], env=env, capture_output=True, text=True)
    if r.returncode != 0: print((r.stdout + r.stderr)[-600:]); sys.exit(2)
    d = json.load(open("/tmp/site_crawl.json")); nav = sum(1 for x in d if any("NAV:" in str(e) for e in (x.get("errors") or [])))
    if not d or nav == len(d): print(f"local_gate: the crawl loaded nothing ({len(d)} pages, {nav} could not be opened)"); sys.exit(2)
    g = subprocess.run([sys.executable, os.path.join(HERE, "gate.py")], capture_output=True, text=True)
    print(g.stdout.strip()[-1500:]); sys.exit(g.returncode)
finally:
    srv.shutdown()
    if made:
        try: os.remove(pm)
        except Exception: pass
