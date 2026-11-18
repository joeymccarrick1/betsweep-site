"""\"The Daily Sweep is up\": one push per posted slip to the devices that asked (owner 11/17, "I want all four").
The function is push/slip-alerts.ts promoUp; the owner deploys it. This runs THAT function's text - cut out of the file, with the
database, the push service and the promo file stubbed - under node (type stripping), so what is checked is what gets deployed.
Skipped when node cannot strip types (needs node 22.6+)."""
import json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
src = open(os.path.join(HERE, "push", "slip-alerts.ts"), encoding="utf-8").read()
m = re.search(r"export async function promoUp\(.*?\n}\n", src, re.S)
check(bool(m), "push/slip-alerts.ts has promoUp")
check("try { npost = await promoUp(W, now, gone); } catch" in src and "posted: npost" in src, "the run calls it inside its own try and reports the count (a missing column cannot cost the other alerts)")
sql = open(os.path.join(HERE, "sql", "push_promo.sql"), encoding="utf-8").read()
check("add column if not exists promo boolean not null default false" in sql and "__" not in sql, "sql/push_promo.sql adds the switch, off by default, with no secret or placeholder in it")
import importlib.util
acct = open(os.path.join(HERE, "account.py"), encoding="utf-8").read()
mflag = re.search(r"^PROMO_ALERTS = (True|False)\b", acct, re.M)
check(mflag is not None and "{PROMO_CB}" in acct and "update({promo: pp.checked})" in acct, "the account page has the switch behind PROMO_ALERTS and saves push_subs.promo on its own")
mep = os.path.join(os.environ.get("SITE") or os.path.join(HERE, "site"), "me", "index.html")
if mflag and os.path.exists(mep):
    me = open(mep, encoding="utf-8").read(); on = mflag.group(1) == "True"; has = 'id="pppromo"' in me and "When BetSweep posts a slip" in me
    check(has == on and ('id="pppromolab" hidden' in me) == on, f"My BetSweep {'shows' if on else 'does not show'} the switch (PROMO_ALERTS = {on}); it starts hidden until the device's own setting is read")
if not m: print(f"\n{ok} passed, {bad} failed"); sys.exit(1)
HARNESS = r"""
type Sub = { endpoint: string; user_id: string; p256dh?: string; auth?: string };
const SITE = "https://example.test";
let PROMOS: any[] = []; let SUBS: any[] = []; let SENT: any[] = []; let NOCOL = false; let CODES: Record<string, number> = {};
const pushes: any[] = []; const marks: any[] = []; const asked: string[] = [];
(globalThis as any).fetch = async (u: string) => ({ json: async () => PROMOS });
async function rest(path: string, _init?: any): Promise<any> { asked.push(path);
  if (path.startsWith("push_subs?")) { if (NOCOL) throw new Error("column push_subs.promo does not exist"); return SUBS.filter((s) => s.promo === true).map(({ promo, ...r }) => r); }
  if (path.startsWith("push_sent?")) return SENT; return []; }
async function sendPush(s: Sub, msg: any): Promise<number> { const c = CODES[s.endpoint] || 201; pushes.push({ to: s.endpoint, msg, c }); return c; }
async function mark(uid: string, W: number, player: string, status: string) { marks.push({ uid, W, player, status }); SENT.push({ user_id: uid, player }); }
__FN__
const NOW = Date.UTC(2026, 10, 19, 20, 0, 0);          // Thu 11/19 2:00 PM Central
const ko = NOW + 5 * 3600e3;
const sweep = { week: 11, slot: 2, title: "Daily Sweep: Thursday", status: "LIVE", sweep: true, fd: 320, first_ko: ko, result: "", posted: "2026-11-19",
  legs: [{ who: "C.J. Stroud", disp: "C.J. Stroud 200+ pass yds" }, { who: "Nico Collins", disp: "Nico Collins 5+ rec" }, { who: "Over 44.5", disp: "Over 44.5" }, { who: "Tank Dell", disp: "Tank Dell 40+ rec yds" }, { who: "Texans ML", disp: "Texans ML" }] };
const old = { ...sweep, slot: 1, title: "Tuesday long shot", sweep: false, posted: "2026-11-16" };
const out: any = {};
const run = async (name: string) => { pushes.length = 0; marks.length = 0; const gone: string[] = []; let n: any; try { n = await promoUp(11, NOW, gone); } catch (e) { n = "threw: " + String(e); } out[name] = { n, pushes: pushes.map((p) => ({ to: p.to, title: p.msg.title, body: p.msg.body, url: p.msg.url, tag: p.msg.tag })), marks: marks.map((m) => `${m.uid}|${m.player}|${m.status}`), gone }; };
SUBS = [{ endpoint: "a1", user_id: "A", promo: true }, { endpoint: "a2", user_id: "A", promo: true }, { endpoint: "b1", user_id: "B", promo: true }, { endpoint: "c1", user_id: "C", promo: false }];
PROMOS = [old, sweep]; await run("first");
await run("again");
SENT = []; PROMOS = [{ ...sweep, result: "WON" }, { ...sweep, slot: 3, first_ko: NOW - 60e3 }, { ...sweep, slot: 4, status: "HIDDEN" }, { ...sweep, slot: 5, week: 10 }]; await run("closed");
SENT = []; PROMOS = [{ ...sweep, slot: 6, title: "Piss Missile Thursday", sweep: false, fd: 4174, posted: "2026-11-18" }]; await run("yesterday");
SENT = []; PROMOS = [sweep]; CODES = { a1: 410, a2: 410 }; await run("dead");
CODES = {}; SENT = []; NOCOL = true; await run("nocolumn"); NOCOL = false;
SENT = []; SUBS = SUBS.map((s) => ({ ...s, promo: false })); await run("nobody");
out.asked = asked.filter((p) => p.startsWith("push_subs?"))[0];
console.log(JSON.stringify(out));
"""
with tempfile.TemporaryDirectory() as td:
    f = os.path.join(td, "harness.mts"); open(f, "w", encoding="utf-8").write(HARNESS.replace("__FN__", m.group(0).replace("export async function", "async function")))
    r = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", f], capture_output=True, text=True, timeout=120)
if r.returncode != 0 and ("strip-types" in r.stderr or "bad option" in r.stderr or "Unknown file extension" in r.stderr):
    print("SKIP the run (this node cannot strip types):", r.stderr.strip().splitlines()[-1][:120]); print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
check(r.returncode == 0, f"the function runs under node ({(r.stderr or '').strip()[:200]})")
if r.returncode == 0:
    o = json.loads(r.stdout.strip().splitlines()[-1]); a = o["first"]
    check(a["n"] == 3 and sorted(p["to"] for p in a["pushes"]) == ["a1", "a2", "b1"], f"a slip posted today goes to every device that asked - three devices, two people - and not to the one that did not ({a['n']} sent)")
    p0 = a["pushes"][0]; check(p0["title"] == "The Daily Sweep is up (+320)" and p0["url"] == "/b/w11-2" and p0["tag"] == "bs-promoup-w11-2", f"the Daily Sweep is named, priced and linked ({p0['title']} -> {p0['url']})")
    check(p0["body"] == "C.J. Stroud 200+ pass yds · Nico Collins 5+ rec · Over 44.5 · Tank Dell 40+ rec yds +1 more", f"the body is the first four legs and a count ({p0['body']})")
    check(sorted(a["marks"]) == ["A|__promoup__w11-2|POSTED", "B|__promoup__w11-2|POSTED"] and all("w11-1" not in p["url"] for p in a["pushes"]), "each person is marked once; a slip posted three days ago is not replayed")
    check(o["again"]["n"] == 0 and not o["again"]["pushes"], "the next run sends nothing more")
    check(o["closed"]["n"] == 0 and not o["closed"]["pushes"], "graded, kicked off, archived or another week's: nothing")
    y = o["yesterday"]; check(y["n"] == 3 and y["pushes"][0]["title"] == "New slip: Piss Missile Thursday (+4174)", f"a slip posted last night still goes out; one that is not the Sweep is named ({y['pushes'][0]['title'] if y['pushes'] else y})")
    d = o["dead"]; check(d["n"] == 1 and sorted(d["gone"]) == ["a1", "a2"] and d["marks"] == ["B|__promoup__w11-2|POSTED"], f"dead devices are handed back for removal and their owner is not marked as told ({d['gone']}, {d['marks']})")
    check(str(o["nocolumn"]["n"]).startswith("threw") and not o["nocolumn"]["pushes"], "before the column exists the function throws (the run's try catches it) and sends nothing")
    check(o["nobody"]["n"] == 0, "nobody opted in: nothing sent")
    check("promo=is.true" in (o.get("asked") or ""), f"only devices with the switch on are read ({o.get('asked')})")
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
