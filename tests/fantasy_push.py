"""Sunday inactives and the Saturday lineup check for a reader with MANY leagues (owner 11/17: "I have a ton of sleeper teams").
push/slip-alerts.ts inactives() and startsit() used to send one push per league under one tag - each replaced the last on the phone,
so a 14-league account saw one league's message. Now: one push per player (inactives) or per Saturday (lineup check) per person, naming
how many lineups; a one-league reader gets exactly the old message. This runs THAT file's functions - cut out of it, with the
database, the push service, the feeds and the projections stubbed - under node (type stripping). The owner deploys the function.
Skipped when node cannot strip types (needs node 22.6+)."""
import json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
src = open(os.environ.get("ALERTS_TS") or os.path.join(HERE, "push", "slip-alerts.ts"), encoding="utf-8").read()
def cut(sig):
    m = re.search(re.escape(sig) + r".*?\n}\n", src, re.S); return m.group(0) if m else None
parts = {k: cut(k) for k in ("export function norm(", "async function pushAll(", "async function projections(", "export async function inactives(", "export async function startsit(")}
check(all(parts.values()), "push/slip-alerts.ts has norm, pushAll, projections, inactives and startsit")
ctd = re.search(r"^const CT_DATE = .*$", src, re.M)
check(bool(ctd), "and CT_DATE")
if not all(parts.values()) or not ctd: print(f"\n{ok} passed, {bad} failed"); sys.exit(1)
HARNESS = r"""
type Sub = { endpoint: string; user_id: string; p256dh?: string; auth?: string; live?: boolean; weekly?: boolean };
const SITE = "https://example.test", FEEDS = "https://feeds.test";
let ROSTERS: any[] = []; let SUBS: any[] = []; let SENT: any[] = []; let INA: any = { games: {} }; let PROJ: any = { week: 11, players: [] };
const pushes: any[] = []; const marks: any[] = [];
(globalThis as any).fetch = async (u: string) => ({ json: async () => (String(u).indexOf("inactives.json") >= 0 ? INA : PROJ) });
async function rest(path: string, _init?: any): Promise<any> {
  if (path.startsWith("fantasy_rosters?")) return ROSTERS; if (path.startsWith("push_subs?")) return SUBS;
  if (path.startsWith("push_sent?")) { const st = (path.match(/status=eq\.(\w+)/) || [])[1]; return SENT.filter((x) => x.status === st); } return []; }
async function sendPush(s: Sub, msg: any): Promise<number> { pushes.push({ to: s.endpoint, uid: s.user_id, msg }); return 201; }
async function mark(uid: string, W: number, player: string, status: string) { marks.push({ uid, W, player, status }); SENT.push({ user_id: uid, player, status }); }
async function dropGone(_g: string[]) {}
__FNS__
const pl = (n: string, p: string, t = "HOU") => ({ name: n, pos: p, team: t });
const P = (n: string, p: string, fp: number, av = "", o = "IND") => ({ n, p, t: "HOU", o, fp, av });
PROJ = { week: 11, players: [P("Joe Mixon", "RB", 14.2, "OUT"), P("Tee Higgins", "WR", 13.0), P("Nick Chubb", "RB", 9.4), P("Dameon Pierce", "RB", 6.1), P("Woody Marks", "RB", 11.8), P("Nico Collins", "WR", 16.5), P("Tank Dell", "WR", 12.2),
  P("Xavier Hutchinson", "WR", 7.0), P("Jayden Higgins", "WR", 10.9), P("Dalton Schultz", "TE", 8.8), P("Cade Stover", "TE", 4.1)] };
INA = { games: { g1: { out: [{ name: "Joe Mixon", team: "HOU" }, { name: "Tee Higgins", team: "CIN" }] } } };
const lg = (uid: string, id: string, name: string, starters: any[], bench: any[]) => ({ user_id: uid, league_id: id, league: name, starters, bench });
ROSTERS = [
  lg("A", "L1", "Nashville Dynasty", [pl("Joe Mixon", "RB"), pl("Nico Collins", "WR")], [pl("Nick Chubb", "RB"), pl("Dameon Pierce", "RB")]),
  lg("A", "L2", "Work League", [pl("Joe Mixon", "RB"), pl("Tank Dell", "WR")], [pl("Woody Marks", "RB")]),
  lg("A", "L3", "Family League", [pl("Joe Mixon", "RB")], [pl("Xavier Hutchinson", "WR")]),
  lg("A", "L4", "Titans Up", [pl("Tee Higgins", "WR"), pl("Dalton Schultz", "TE")], [pl("Jayden Higgins", "WR")]),
  lg("A", "L5", "High Stakes 12", [pl("Nico Collins", "WR"), pl("Dalton Schultz", "TE")], [pl("Cade Stover", "TE")]),
  lg("B", "M1", "Home League", [pl("Joe Mixon", "RB")], [pl("Nick Chubb", "RB")]),
  lg("C", "N1", "No Push League", [pl("Joe Mixon", "RB")], [pl("Nick Chubb", "RB")]),
];
SUBS = [{ endpoint: "a1", user_id: "A" }, { endpoint: "a2", user_id: "A" }, { endpoint: "b1", user_id: "B" }, { endpoint: "d1", user_id: "D" }];
const out: any = {};
const snap = () => ({ pushes: pushes.map((p) => ({ to: p.to, title: p.msg.title, body: p.msg.body, url: p.msg.url, tag: p.msg.tag })), marks: marks.map((m) => m.uid + "|" + m.player + "|" + m.status) });
const run = async (name: string, f: () => Promise<any>) => { pushes.length = 0; marks.length = 0; let r: any; try { r = await f(); } catch (e) { r = "threw: " + String(e); } out[name] = { r, ...snap() }; };
const NOW = Date.UTC(2026, 10, 22, 17, 35, 0);
await run("ina", () => inactives(NOW));
await run("ina_again", () => inactives(NOW));
ROSTERS.push(lg("A", "L6", "College Buddies", [pl("Joe Mixon", "RB")], []));
await run("ina_late", () => inactives(NOW));
INA = { games: {} }; await run("ina_none", () => inactives(NOW));
// Saturday: Mixon is out in the projections, and Tank Dell (12.2) sits behind Xavier Hutchinson (7.0) in one league
ROSTERS = [
  lg("A", "L1", "Nashville Dynasty", [pl("Joe Mixon", "RB"), pl("Xavier Hutchinson", "WR")], [pl("Nick Chubb", "RB"), pl("Tank Dell", "WR")]),
  lg("A", "L2", "Work League", [pl("Joe Mixon", "RB")], [pl("Woody Marks", "RB")]),
  lg("A", "L3", "Family League", [pl("Nico Collins", "WR")], [pl("Xavier Hutchinson", "WR")]),
  lg("A", "L4", "Titans Up", [pl("Cade Stover", "TE")], [pl("Dalton Schultz", "TE")]),
  lg("A", "L5", "High Stakes 12", [pl("Dameon Pierce", "RB")], [pl("Woody Marks", "RB")]),
  lg("B", "M1", "Home League", [pl("Cade Stover", "TE")], [pl("Dalton Schultz", "TE")]),
  lg("E", "Q1", "Quiet League", [pl("Cade Stover", "TE")], [pl("Dalton Schultz", "TE")]),
];
SUBS = [{ endpoint: "a1", user_id: "A" }, { endpoint: "b1", user_id: "B" }, { endpoint: "e1", user_id: "E", weekly: false }];
await run("ss", () => startsit(NOW));
await run("ss_again", () => startsit(NOW));
console.log(JSON.stringify(out));
"""
fns = "\n".join([ctd.group(0)] + [parts[k].replace("export async function", "async function").replace("export function", "function") for k in parts])
with tempfile.TemporaryDirectory() as td:
    f = os.path.join(td, "harness.mts"); open(f, "w", encoding="utf-8").write(HARNESS.replace("__FNS__", fns))
    r = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", f], capture_output=True, text=True, timeout=120)
if r.returncode != 0 and ("strip-types" in r.stderr or "bad option" in r.stderr or "Unknown file extension" in r.stderr):
    print("SKIP the run (this node cannot strip types):", r.stderr.strip().splitlines()[-1][:120]); print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
check(r.returncode == 0, "the two functions run under node" + ("" if r.returncode == 0 else ": " + r.stderr.strip()[-300:]))
if r.returncode != 0: print(f"\n{ok} passed, {bad} failed"); sys.exit(1)
o = json.loads(r.stdout.strip().splitlines()[-1])
ina = o["ina"]; A = [p for p in ina["pushes"] if p["to"] == "a1"]; B = [p for p in ina["pushes"] if p["to"] == "b1"]
mix = next((p for p in A if p["title"].startswith("Joe Mixon")), {"title": "", "body": ""}); tee = next((p for p in A if p["title"].startswith("Tee Higgins")), {"title": "", "body": ""})
check(len(A) == 2 and mix["title"] == "Joe Mixon is INACTIVE in 3 of your lineups", f"a starter who is inactive in three of one reader's lineups is ONE push ({mix['title']})")
check(mix["body"] == "Official inactives. Best bench play by the model: Nashville Dynasty: Nick Chubb (9.4); Work League: Woody Marks (11.8); Family League: no RB on the bench. Swap before kickoff." and mix["url"] == "/team/",
      f"it names each league's best bench play, and says so when there is none ({mix['body']})")
check(tee["title"] == "Tee Higgins is INACTIVE (Titans Up)" and tee["body"] == "Official inactives. Your best bench WR by the model: Jayden Higgins (10.9 pts vs IND). Swap before kickoff.", f"a starter in one lineup reads exactly as before ({tee['title']} / {tee['body']})")
check(len(B) == 1 and B[0]["title"] == "Joe Mixon is INACTIVE (Home League)" and B[0]["body"] == "Official inactives. Your best bench RB by the model: Nick Chubb (9.4 pts vs IND). Swap before kickoff.", "a one-league reader gets the same message he always did")
check(sorted(set(p["to"] for p in ina["pushes"])) == ["a1", "a2", "b1"] and len(ina["pushes"]) == 5 and ina["r"]["sent"] == 5, f"both of a reader's devices get it; a reader with no device, and a device with no roster, get nothing ({len(ina['pushes'])} pushes)")
check(sorted(re.sub(r"\|[a-z ]+\|", "|", m) for m in ina["marks"]) == ["A|__ina__L1|INACTIVE", "A|__ina__L2|INACTIVE", "A|__ina__L3|INACTIVE", "A|__ina__L4|INACTIVE", "B|__ina__M1|INACTIVE"], f"every league it covered is marked sent, under the key the old loop used ({ina['marks'][0] if ina['marks'] else None})")
check(not o["ina_again"]["pushes"] and not o["ina_again"]["marks"], "the next run of the same window sends nothing")
late = o["ina_late"]["pushes"]; check(len(late) == 2 and late[0]["title"] == "Joe Mixon is INACTIVE (College Buddies)" and "No RB on your bench with a projection" in late[0]["body"], f"a lineup saved after the first run still gets its own push ({late[0]['title'] if late else None})")
check(o["ina_none"]["r"].get("reason") == "no inactives in the window" and not o["ina_none"]["pushes"], "no inactives, no push")
ss = o["ss"]; SA = [p for p in ss["pushes"] if p["to"] == "a1"]; SB = [p for p in ss["pushes"] if p["to"] == "b1"]
check(len(SA) == 1 and SA[0]["title"] == "Lineup check: 4 of your lineups", f"Saturday night is ONE push for a reader with calls in four leagues ({SA[0]['title'] if SA else None})")
check(bool(SA) and SA[0]["body"] == "Nashville Dynasty: Joe Mixon is out +1 more. Work League: Joe Mixon is out. Titans Up: Dalton Schultz over Cade Stover (+4.7). 1 more league. Every lineup that needs you is on the Fantasy page." and len(SA[0]["body"]) <= 300,
      f"it gives the first call from three leagues and counts the rest ({SA[0]['body'] if SA else None})")
check(len(SB) == 1 and SB[0]["title"] == "Lineup check: Home League" and SB[0]["body"] == "The model would start Dalton Schultz over Cade Stover (+4.7). Full lineup and the reasons on the Fantasy page.", f"one league with a call reads exactly as before ({SB[0]['body'] if SB else None})")
check(not any(p["to"] == "e1" for p in ss["pushes"]) and len(ss["marks"]) == 5 and not any("L3" in m for m in ss["marks"]), f"a device with weekly alerts off gets nothing; a league with no call is not marked ({len(ss['marks'])} marks)")
check(not o["ss_again"]["pushes"], "the lineup check is sent once")
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
