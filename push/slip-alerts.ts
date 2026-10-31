// BetSweep slip alerts - Supabase Edge Function "slip-alerts" (owner 10/30: alerts when a player on a saved slip is ruled out).
//
// Every 10 minutes (pg_cron -> this URL with the x-cron-secret header) it:
//   1. reads this week's legs + kickoffs from the live Parlay Builder data file on betsweep.co (the same file the site uses)
//   2. reads injury statuses from ESPN's NFL injuries feed (Out / Injured Reserve / Suspension -> OUT, Doubtful -> DOUBTFUL)
//   3. reads every signed-in user's saved slips + open betslip for this week (user_state keys bs_slips_w<W>, bs_slipk_w<W>)
//   4. for each player on a slip whose game has not kicked off and who is OUT or DOUBTFUL, sends ONE web push per user per player per
//      status (push_sent remembers), naming the slips he is on and a swap idea from the same game (best model edge, player healthy,
//      not already on the slip)
// POST {"test": true} with a signed-in user's Bearer token sends that user a test alert (the "Send a test alert" button on /me/).
// No npm packages: web push (RFC 8291 aes128gcm + RFC 8292 VAPID) is done with WebCrypto below.
//
// Secrets (Edge Functions > Secrets): VAPID_PUBLIC, VAPID_PRIVATE, CRON_SECRET. SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are built in.
// Deploy with "Verify JWT" OFF (the cron call carries the secret, the test call is checked against Supabase auth here).

const SB = Deno.env.get("SUPABASE_URL") ?? "";
const SRK = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const VPUB = Deno.env.get("VAPID_PUBLIC") ?? "";
const VPRIV = Deno.env.get("VAPID_PRIVATE") ?? "";
const CRON = Deno.env.get("CRON_SECRET") ?? "";
const SITE = Deno.env.get("SITE_URL") ?? "https://betsweep.co";
const ESPN = Deno.env.get("ESPN_INJURIES_URL") ?? "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries";
const SUBJECT = "mailto:support@betsweep.co";
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, content-type, apikey, x-client-info", "Access-Control-Allow-Methods": "POST, OPTIONS" };

// ---------------- base64url ----------------
export function b64u(buf: ArrayBuffer | Uint8Array): string {
  const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = ""; for (const c of b) s += String.fromCharCode(c);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
export function unb64u(s: string): Uint8Array {
  s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "=";
  const bin = atob(s); const out = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i); return out;
}
const te = new TextEncoder();
function cat(...a: Uint8Array[]): Uint8Array { const n = a.reduce((s, x) => s + x.length, 0); const o = new Uint8Array(n); let i = 0; for (const x of a) { o.set(x, i); i += x.length; } return o; }
async function hmac(key: Uint8Array, data: Uint8Array): Promise<Uint8Array> {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data));
}

// ---------------- VAPID (RFC 8292) ----------------
let _vkey: CryptoKey | null = null;
async function vapidKey(): Promise<CryptoKey> {
  if (_vkey) return _vkey;
  const pub = unb64u(VPUB);
  _vkey = await crypto.subtle.importKey("jwk", { kty: "EC", crv: "P-256", x: b64u(pub.slice(1, 33)), y: b64u(pub.slice(33, 65)), d: VPRIV, ext: true },
    { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  return _vkey;
}
export async function vapidHeader(endpoint: string): Promise<string> {
  const aud = new URL(endpoint).origin;
  const h = b64u(te.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const p = b64u(te.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: SUBJECT })));
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, await vapidKey(), te.encode(h + "." + p));
  return `vapid t=${h}.${p}.${b64u(sig)}, k=${VPUB}`;
}

// ---------------- payload encryption (RFC 8291, aes128gcm) ----------------
export async function encrypt(p256dh: string, auth: string, payload: Uint8Array): Promise<Uint8Array> {
  const uaPub = unb64u(p256dh), authSecret = unb64u(auth);
  const eph = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]) as CryptoKeyPair;
  const asPub = new Uint8Array(await crypto.subtle.exportKey("raw", eph.publicKey));
  const uaKey = await crypto.subtle.importKey("raw", uaPub, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaKey }, eph.privateKey, 256));
  const prkKey = await hmac(authSecret, shared);
  const ikm = (await hmac(prkKey, cat(te.encode("WebPush: info\0"), uaPub, asPub, new Uint8Array([1])))).slice(0, 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, cat(te.encode("Content-Encoding: aes128gcm\0"), new Uint8Array([1])))).slice(0, 16);
  const nonce = (await hmac(prk, cat(te.encode("Content-Encoding: nonce\0"), new Uint8Array([1])))).slice(0, 12);
  const k = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, k, cat(payload, new Uint8Array([2]))));
  const rs = new Uint8Array([0, 0, 16, 0]);   // record size 4096
  return cat(salt, rs, new Uint8Array([asPub.length]), asPub, ct);
}

type Sub = { endpoint: string; user_id: string; p256dh: string; auth: string };
export let lastReason = "";
export async function sendPush(s: Sub, msg: Record<string, unknown>): Promise<number> {
  const body = await encrypt(s.p256dh, s.auth, te.encode(JSON.stringify(msg)));
  const r = await fetch(s.endpoint, { method: "POST", headers: { "Authorization": await vapidHeader(s.endpoint), "Content-Encoding": "aes128gcm",
    "Content-Type": "application/octet-stream", "TTL": "21600", "Urgency": "high" }, body });
  lastReason = r.ok ? "" : (await r.text()).slice(0, 200);
  if (!r.ok) console.warn("push", new URL(s.endpoint).host, r.status, lastReason);
  return r.status;
}

// ---------------- Supabase REST (service role) ----------------
async function rest(path: string, init: RequestInit = {}): Promise<any> {
  const auth: Record<string, string> = SRK.startsWith("eyJ") ? { Authorization: `Bearer ${SRK}` } : {};   // legacy JWT key; new sb_secret_ keys go in apikey only
  const r = await fetch(`${SB}/rest/v1/${path}`, { ...init, headers: { apikey: SRK, ...auth, "Content-Type": "application/json", ...(init.headers || {}) } });
  if (!r.ok) throw new Error(`${path.split("?")[0]}: ${r.status} ${await r.text()}`);
  const t = await r.text(); return t ? JSON.parse(t) : null;
}

// ---------------- data ----------------
export function norm(s: string): string {
  return String(s || "").replace(/\./g, "").trim().replace(/\s+(jr|sr|ii|iii|iv|v)$/i, "").replace(/\s+/g, " ").toLowerCase();
}
async function builderData(): Promise<any> {
  const html = await (await fetch(`${SITE}/build/`, { headers: { "cache-control": "no-cache" } })).text();
  const m = html.match(/src="(\/build\/data-[0-9a-f]+\.js)"/);
  const js = m ? await (await fetch(SITE + m[1])).text() : html;
  const i = js.indexOf("window.__BS = "); if (i < 0) throw new Error("builder data not found");
  return JSON.parse(objectAt(js, js.indexOf("{", i)));
}
export function objectAt(s: string, start: number): string {   // the balanced {...} starting at start, skipping braces inside strings
  let depth = 0, inStr = false, esc = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (inStr) { if (esc) esc = false; else if (c === "\\") esc = true; else if (c === '"') inStr = false; continue; }
    if (c === '"') inStr = true; else if (c === "{") depth++; else if (c === "}") { depth--; if (depth === 0) return s.slice(start, i + 1); }
  }
  throw new Error("unbalanced data file");
}
export function statusOf(st: string): "OUT" | "DOUBTFUL" | null {
  const x = String(st || "").toLowerCase();
  if (x === "out" || x.includes("injured reserve") || x.includes("suspension") || x.includes("physically unable") || x === "ir") return "OUT";
  if (x === "doubtful") return "DOUBTFUL";
  return null;
}
async function espnStatuses(): Promise<Map<string, { st: "OUT" | "DOUBTFUL"; why: string }>> {
  const j = await (await fetch(ESPN)).json(); const out = new Map();
  for (const t of (j.injuries || [])) for (const x of (t.injuries || [])) {
    const nm = x?.athlete?.displayName; const st = statusOf(x?.status || x?.type?.description);
    if (nm && st) out.set(norm(nm), { st, why: String(x?.details?.type || x?.type?.description || x?.shortComment || "").slice(0, 60) });
  }
  return out;
}
const PROPS = new Set(["Receiving Yards", "Receptions", "Rushing Yards", "Passing Yards", "Rush + Rec Yards", "Anytime TD"]);
function am(o: number): string { return (o > 0 ? "+" : "−") + Math.abs(Math.round(o)); }
function legLabel(l: any): string {
  return l.m === "Anytime TD" ? `${l.pl} anytime TD` : `${l.pl} ${Number.isInteger(l.ln) ? l.ln : l.ln}+ ${String(l.ms || l.m).toLowerCase()}`;
}

// ---------------- the run ----------------
export async function run(now = Date.now()) {
  const D = await builderData(); const W = D.week;
  const ko = new Map<string, number>(); for (const g of (D.games || [])) ko.set(g.gid, g.ko || 0);
  const gameOf = new Map<string, string>(); for (const l of (D.legs || [])) if (l.pos && !gameOf.has(norm(l.pl))) gameOf.set(norm(l.pl), l.g);
  const subs: Sub[] = await rest("push_subs?select=endpoint,user_id,p256dh,auth");
  if (!subs.length) return { week: W, subs: 0, sent: 0 };
  const users = [...new Set(subs.map((s) => s.user_id))];
  const states: any[] = await rest(`user_state?select=user_id,key,value&key=in.(bs_slips_w${W},bs_slipk_w${W})&user_id=in.(${users.join(",")})`);
  const sent: any[] = await rest(`push_sent?select=user_id,player,status&week=eq.${W}`);
  const done = new Set(sent.map((x) => `${x.user_id}|${x.player}|${x.status}`));
  const ST = await espnStatuses();
  let nsent = 0, nalerts = 0; const gone: string[] = [];
  for (const uid of users) {
    // slips: name -> keys
    const slips: { name: string; keys: string[] }[] = [];
    for (const r of states.filter((x) => x.user_id === uid)) {
      let v: any = null; try { v = JSON.parse(r.value?.v ?? "null"); } catch { v = null; }
      if (r.key.startsWith("bs_slips_w") && Array.isArray(v)) for (const s of v) if (s && Array.isArray(s.keys)) slips.push({ name: String(s.name || "Saved slip"), keys: s.keys });
      if (r.key.startsWith("bs_slipk_w") && Array.isArray(v) && v.length) slips.push({ name: "your open betslip", keys: v });
    }
    const mine = new Set(slips.flatMap((s) => s.keys.map((k) => norm(String(k).split("|")[0]))));
    const hits = new Map<string, { name: string; st: string; why: string; slips: string[]; g: string }>();
    for (const s of slips) for (const k of s.keys) {
      const who = String(k).split("|")[0]; const n = norm(who); const st = ST.get(n); const g = gameOf.get(n) || "";
      if (!st || !g || (ko.get(g) || 0) <= now) continue;
      if (done.has(`${uid}|${n}|${st.st}`)) continue;
      const h = hits.get(n) || { name: who, st: st.st, why: st.why, slips: [], g }; if (!h.slips.includes(s.name)) h.slips.push(s.name); hits.set(n, h);
    }
    if (!hits.size) continue;
    const us = subs.filter((s) => s.user_id === uid);
    for (const [n, h] of hits) {
      const swap = (D.legs || []).filter((l: any) => l.g === h.g && PROPS.has(l.m) && l.e > 0 && l.p >= 0.45 && l.p <= 0.75 && !(l.pos === "QB" && l.m === "Rushing Yards")
          && (l.m === "Receptions" || l.m === "Anytime TD" || (l.ln || 0) >= 15) && !mine.has(norm(l.pl)) && !ST.get(norm(l.pl)))
        .sort((a: any, b: any) => b.e - a.e)[0];
      const where = h.slips.length === 1 ? (h.slips[0] === "your open betslip" ? "He's on your open betslip." : `He's on "${h.slips[0]}".`) : `He's on ${h.slips.length} of your slips (${h.slips.slice(0, 3).map((x) => x === "your open betslip" ? "open betslip" : `"${x}"`).join(", ")}).`;
      const msg = { title: `${h.name} is ${h.st === "OUT" ? "OUT" : "DOUBTFUL"}${h.why ? " (" + h.why + ")" : ""}`,
        body: where + (h.st === "OUT" ? " Check the slip before kickoff." : " Doubtful players rarely play - check the slip before kickoff.") +
          (swap ? ` Swap idea: ${legLabel(swap)} (FD ${am(swap.o)}, model ${Math.round(swap.p * 100)}%).` : ""),
        url: "/me/", tag: `bs-${W}-${n}` };
      nalerts++;
      for (const s of us) {
        try { const code = await sendPush(s, msg); if (code === 404 || code === 410) gone.push(s.endpoint); else if (code < 300) nsent++; }
        catch (e) { console.warn("push", String(e)); }
      }
      await rest("push_sent", { method: "POST", headers: { Prefer: "resolution=ignore-duplicates" }, body: JSON.stringify([{ user_id: uid, week: W, player: n, status: h.st }]) });
    }
  }
  for (const ep of gone) await rest(`push_subs?endpoint=eq.${encodeURIComponent(ep)}`, { method: "DELETE" });
  return { week: W, subs: subs.length, users: users.length, alerts: nalerts, sent: nsent, removed: gone.length, statuses: ST.size };
}

async function test(token: string) {
  if (!VPUB || !VPRIV) return { error: "Alert keys are missing on the server (VAPID_PUBLIC / VAPID_PRIVATE secrets)." };
  const u = await fetch(`${SB}/auth/v1/user`, { headers: { apikey: SRK, Authorization: `Bearer ${token}` } });
  if (!u.ok) return { error: `Could not check your sign-in (${u.status}) - sign out and back in, then try again.` };
  const user = await u.json();
  const subs: Sub[] = await rest(`push_subs?select=endpoint,user_id,p256dh,auth&user_id=eq.${user.id}`);
  if (!subs.length) return { devices: 0, sent: 0, error: "No device is saved for your account yet - tap Turn off on this device, then Turn on alerts again." };
  let ok = 0; const fails: string[] = [];
  for (const s of subs) {
    let c = 0;
    try { c = await sendPush(s, { title: "BetSweep alerts are on", body: "You'll get a note here if a player on one of your saved slips is ruled out before kickoff.", url: "/me/", tag: "bs-test" }); }
    catch (e) { fails.push(`${new URL(s.endpoint).host}: ${String(e).slice(0, 120)}`); continue; }
    if (c < 300) ok++;
    else { fails.push(`${new URL(s.endpoint).host} answered ${c}${lastReason ? " " + lastReason : ""}`); if (c === 404 || c === 410) await rest(`push_subs?endpoint=eq.${encodeURIComponent(s.endpoint)}`, { method: "DELETE" }); }
  }
  return ok ? { devices: subs.length, sent: ok } : { devices: subs.length, sent: 0, error: "The push service refused it: " + fails.join("; ") };
}

if (import.meta.main) Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    let body: any = {}; try { body = await req.json(); } catch { body = {}; }
    if (body && body.test) {
      const tok = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
      return Response.json(await test(tok), { headers: CORS });
    }
    if (!CRON || req.headers.get("x-cron-secret") !== CRON) return new Response("forbidden", { status: 403, headers: CORS });
    const r = await run(); console.log(JSON.stringify(r));
    return Response.json(r, { headers: CORS });
  } catch (e) {
    console.error(String(e)); return Response.json({ error: String(e) }, { status: 500, headers: CORS });
  }
});
