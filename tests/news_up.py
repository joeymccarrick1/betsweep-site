"""Big-name news push (owner 11/20: "push notifications about prominent players being out or released. Ken Walker will be inactive
this weekend. Daniel Jones got released today."). The function is push/slip-alerts.ts newsFinds / newsUp; the owner deploys it. This
runs newsFinds - cut out of the file - under node (type stripping) against made-up rows and, when they are on disk, the real mirror
and feed (/home/claude/work/sm/in/avail.json, /tmp/news_feed.json).   python3 tests/news_up.py"""
import json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
src = open(os.path.join(HERE, "push", "slip-alerts.ts"), encoding="utf-8").read()
m = re.search(r"export function newsFinds\(.*?\n}\n", src, re.S)
check(bool(m) and "export async function newsUp(" in src, "push/slip-alerts.ts has newsFinds and newsUp")
check("try { nnews = await newsUp(W, now, gone, D.games || []); } catch" in src and "news: nnews" in src, "the run calls it inside its own try and reports the count (a missing column cannot cost the other alerts)")
check("push_subs?select=endpoint,user_id,p256dh,auth&news=is.true" in src and 'mark(uid, W, f.key, "NEWS")' in src, "only devices with the switch on are asked, and each push is marked once per player and event")
sql = open(os.path.join(HERE, "sql", "push_news.sql"), encoding="utf-8").read()
check("add column if not exists news boolean not null default false" in sql and "__" not in sql, "sql/push_news.sql adds the switch, off by default, with no secret or placeholder in it")
acct = open(os.path.join(HERE, "account.py"), encoding="utf-8").read(); mflag = re.search(r"^NEWS_ALERTS = (True|False)\b", acct, re.M)
check(mflag is not None and "{NEWS_CB}" in acct and "update({news: pn.checked})" in acct, "the account page has the switch behind NEWS_ALERTS and saves push_subs.news on its own")
mep = os.path.join(os.environ.get("SITE") or os.path.join(HERE, "site"), "me", "index.html")
if mflag and os.path.exists(mep):
    on = mflag.group(1) == "True"; me = open(mep, encoding="utf-8").read()
    check(('id="ppnewslab" hidden' in me) == on, f"My BetSweep {'shows' if on else 'does not show'} the switch (NEWS_ALERTS = {on})")
sys.path.insert(0, HERE); import prominent
v = [["Week", "Player", "Team", "Pos", "Opponent", "Pass Att", "Fantasy Pts"]] + [[str(w), "Star Back", "AAA", "RB", "X", "0", "20"] for w in range(1, 6)] + [[str(w), "Depth Guy", "AAA", "RB", "X", "0", "1"] for w in range(1, 3)] + [[str(w), "The QB", "BBB", "QB", "X", "30", "18"] for w in range(1, 6)]
L = prominent.build(v); check({p["n"] for p in L} == {"Star Back", "The QB"}, f"prominent.build keeps the starter and the lead back and drops a two-game depth player ({[p['n'] for p in L]})")
if not m: print(f"\n{ok} passed, {bad} failed"); sys.exit(1)
NOW = 1795222800000   # 2026-11-20 19:00 CT
PROM = [{"n": "Star Back", "tm": "AAA", "pos": "RB"}, {"n": "The QB", "tm": "BBB", "pos": "QB"}, {"n": "Cut Smith", "tm": "CCC", "pos": "WR"}]
H = ["Projection Week", "Player", "Team", "Pos", "Availability", "", "", "", "", "Reason / Injury", "Source", "Last Updated"]
row = lambda wk, n, tm, st, why, d: [str(wk), n, tm, "RB", st, "", "", "", "", why, "", d]
AV = [H, row(11, "Star Back", "AAA", "OUT", "AUTO HOURLY: Star Back: Out (Groin) - ruled out for Sunday. | was: QUESTIONABLE - x", "2026-11-20"),
      row(11, "The QB", "BBB", "QUESTIONABLE", "NEWS DESK: limited", "2026-11-20"), row(11, "Nobody Special", "AAA", "OUT", "x", "2026-11-20"), row(10, "Cut Smith", "CCC", "OUT", "old week", "2026-11-13")]
it = lambda src, ts, title, text="": {"src": src, "ts": ts, "title": title, "text": text}
ITEMS = [it("espn", "2026-11-20T18:19:03Z", "Lions release QB The QB, turn to rookie"), it("yahoo", "Fri, 20 Nov 2026 18:12:19 +0000", "Cut Smith released by Bears"),
         it("yahoo", "Tue, 17 Nov 2026 01:37:14 +0000", "Team required to release an injury report on Star Back"), it("rotowire", "Fri, 20 Nov 2026 10:16:00 AM PST", "Somebody Else: New starter", "after the team waived The QB.")]
real = {}
try:
    real["av"] = json.load(open("/home/claude/work/sm/in/avail.json"))["values"]; real["items"] = json.load(open("/tmp/news_feed.json"))["items"]
    real["prom"] = prominent.build(json.load(open("/home/claude/work/sm/in/gamelog.json"))["values"])
except Exception: real = {}
HARNESS = "__FN__\n" + r"""
const A = JSON.parse(process.argv[2]);
const out: any = {};
out.base = newsFinds(A.PROM, A.AV, A.ITEMS, 11, A.NOW, { AAA: A.NOW + 40 * 3600e3, BBB: A.NOW + 40 * 3600e3 });
out.started = newsFinds(A.PROM, A.AV, [], 11, A.NOW, { AAA: A.NOW - 3600e3 });
out.stale = newsFinds(A.PROM, A.AV, A.ITEMS, 11, A.NOW + 3 * 24 * 3600e3, { AAA: A.NOW + 4 * 24 * 3600e3 });
out.one = newsFinds(A.PROM, [], A.ITEMS.slice(1, 2), 11, A.NOW, {});
if (A.real.av) out.real = newsFinds(A.real.prom, A.real.av, A.real.items, 11, A.NOW, { KC: A.NOW + 40 * 3600e3, IND: A.NOW - 24 * 3600e3 });
console.log(JSON.stringify(out));
"""
with tempfile.TemporaryDirectory() as td:
    f = os.path.join(td, "harness.mts"); open(f, "w", encoding="utf-8").write(HARNESS.replace("__FN__", m.group(0).replace("export function", "function")))
    arg = os.path.join(td, "a.json"); json.dump({"PROM": PROM, "AV": AV, "ITEMS": ITEMS, "NOW": NOW, "real": real}, open(arg, "w"))
    open(f, "a").write(""); src2 = open(f).read().replace("JSON.parse(process.argv[2])", "JSON.parse((await import('node:fs')).readFileSync(process.argv[2], 'utf8'))"); open(f, "w").write(src2)
    r = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", f, arg], capture_output=True, text=True, timeout=120)
if r.returncode != 0 and ("strip-types" in r.stderr or "bad option" in r.stderr or "Unknown file extension" in r.stderr):
    print("SKIP the run (this node cannot strip types):", r.stderr.strip().splitlines()[-1][:120]); print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
if r.returncode != 0: print(r.stderr[-800:]); check(False, "the function runs under node"); print(f"\n{ok} passed, {bad} failed"); sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1]); k = lambda x: sorted(f["key"] for f in x)
check(k(o["base"]) == ["__news__out|Star Back|11", "__news__rel|The QB"], f"a prominent player ruled out today and a quarterback ESPN says was released are found; a Questionable tag, a depth player, last week's row and a single non-ESPN headline are not ({k(o['base'])})")
b = {f["key"]: f for f in o["base"]}
check(b["__news__out|Star Back|11"]["title"] == "Star Back is out this week" and b["__news__out|Star Back|11"]["body"].startswith("Out (Groin) - ruled out for Sunday.") and "was:" not in b["__news__out|Star Back|11"]["body"], f"the Out push reads cleanly ({b['__news__out|Star Back|11']['body']})")
check(b["__news__rel|The QB"]["title"] == "The QB has been released" and "Lions release" in b["__news__rel|The QB"]["body"], "the release push carries the ESPN headline")
check(o["started"] == [], "no Out push once his team has kicked off")
check(o["stale"] == [], "three days later nothing is replayed (the row is old, the headlines are past 36 hours)")
check(o["one"] == [], "one headline from a non-ESPN, non-RotoWire source is not enough for a release push")
if "real" in o:
    rk = k(o["real"]); print("   real data finds:", [(f["title"], f["body"][:90]) for f in o["real"]])
    check("__news__out|Kenneth Walker III|11" in rk and "__news__rel|Daniel Jones" in rk, f"on tonight's real mirror and feed: Kenneth Walker III out and Daniel Jones released are both found ({rk})")
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
