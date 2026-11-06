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
const ESPN_BASE = Deno.env.get("ESPN_BASE") ?? "https://site.api.espn.com";
// owner 11/1: ESPN answers Supabase's servers with a block page on some runs, which left the risk list empty. A GitHub Action on the site
// repo mirrors ESPN every ~10 minutes to the `feeds` branch (.github/feeds.py); every ESPN read falls back to that mirror.
const FEEDS = Deno.env.get("FEEDS_URL") ?? "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds";
const DISCORD = Deno.env.get("DISCORD_WEBHOOK") ?? "";   // owner 11/5: optional - a channel webhook URL; the brief, weather turns, kickoff reminders and promo alerts post there too
export async function discord(title: string, body: string, url = ""): Promise<boolean> {
  if (!DISCORD) return false;
  try {
    const r = await fetch(DISCORD, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "BetSweep", embeds: [{ title: title.slice(0, 250), description: body.slice(0, 1900), url: url ? (url.startsWith("http") ? url : SITE + url) : undefined, color: 0xd7332a }] }) });
    return r.ok;
  } catch (e) { console.warn("discord", String(e).slice(0, 80)); return false; }
}
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

type Sub = { endpoint: string; user_id: string; p256dh: string; auth: string; live?: boolean | null; weekly?: boolean | null };
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
async function getJson(urls: string[], pick: (j: any) => any = (j) => j): Promise<any> {   // first route that answers JSON wins (ESPN's site.api answers some servers with an HTML block page)
  for (const u of urls) {
    try { const r = await fetch(u, { headers: { "Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; BetSweep/1.0; +https://betsweep.co)" } });
      const t = await r.text(); if (!r.ok || t.trimStart().startsWith("<")) { console.warn("route", new URL(u).host, r.status); continue; }
      const v = pick(JSON.parse(t)); if (v) return v; } catch (e) { console.warn("route", u.slice(0, 60), String(e).slice(0, 80)); }
  }
  return null;
}
// ---- game-day inactives (owner 11/1): each game's summary lists the inactives as "Out" about 90 minutes before kickoff - hours after the
// league injury report the morning boards read. Games kicking off within 3 hours (or started in the last 20 minutes) are checked every run;
// a player listed Out there joins ST as OUT ("Inactive"), so slip pushes, the risk list and the promo watch all pick him up.
export const INACT = new Set<string>();
async function gameDayOuts(D: any, now: number, ST: Map<string, any>): Promise<number> {
  INACT.clear(); let n = 0;
  const near = (D.games || []).filter((g: any) => g.ko && g.ko - now <= 3 * 3600e3 && now - g.ko <= 20 * 60e3);
  if (!near.length) return 0;
  const add = (nm: string, why: string) => { const k = norm(nm); INACT.add(k); if (!ST.has(k) || ST.get(k).st !== "OUT") { ST.set(k, { st: "OUT", why }); n++; } };
  const mir = await getJson([`${FEEDS}/inactives.json`], (j) => j.games ? j : null);
  const sb = await getJson([`${ESPN_BASE}/apis/site/v2/sports/football/nfl/scoreboard`, `https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`, `${FEEDS}/scoreboard.json`], (j) => j.events ? j : null);
  for (const g of near) {
    const ev = (sb?.events || []).find((e: any) => { const abs = ((e.competitions || [])[0]?.competitors || []).map((x: any) => EAB[x?.team?.abbreviation] || x?.team?.abbreviation); return abs.includes(g.a) && abs.includes(g.b); });
    let outs: any[] | null = null;
    if (ev) {
      const sm = await getJson([`${ESPN_BASE}/apis/site/v2/sports/football/nfl/summary?event=${ev.id}`, `https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${ev.id}`], (j) => j.injuries ? j : null);
      if (sm) outs = (sm.injuries || []).flatMap((t: any) => (t.injuries || []).filter((x: any) => /^(out|inactive)$/i.test(String(x?.status || ""))).map((x: any) => ({ name: x?.athlete?.displayName, date: x?.date })));
      else if (mir?.games?.[ev.id]) outs = mir.games[ev.id].out || [];
    }
    for (const o of (outs || [])) if (o.name && (!o.date || Date.parse(o.date) >= g.ko - 12 * 3600e3)) add(o.name, "Inactive");   // game-day designations only
  }
  return n;
}
export const QST = new Map<string, string>();   // owner 11/1: questionable players too, for the live risk list (not pushed)
async function espnStatuses(): Promise<Map<string, { st: "OUT" | "DOUBTFUL"; why: string }>> {
  const out = new Map(); QST.clear();
  const j = await getJson([ESPN, "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/injuries", "https://cdn.espn.com/core/nfl/injuries?xhr=1", `${FEEDS}/injuries.json`],
    (j) => j.injuries ? j : (j.content && j.content.injuries ? { injuries: j.content.injuries } : null));
  if (!j) { console.warn("no injury feed reachable this run"); return out; }
  for (const t of (j.injuries || [])) for (const x of (t.injuries || [])) {
    const nm = x?.athlete?.displayName; const st = statusOf(x?.status || x?.type?.description);
    if (nm && st) out.set(norm(nm), { st, why: String(x?.details?.type || x?.type?.description || x?.shortComment || "").slice(0, 60) });
    else if (nm && /questionable/i.test(String(x?.status || x?.type?.description || ""))) QST.set(norm(nm), String(x?.details?.type || "").slice(0, 60));
  }
  return out;
}
const PROPS = new Set(["Receiving Yards", "Receptions", "Rushing Yards", "Passing Yards", "Rush + Rec Yards", "Anytime TD"]);
function am(o: number): string { return (o > 0 ? "+" : "−") + Math.abs(Math.round(o)); }
function legLabel(l: any): string {
  return l.m === "Anytime TD" ? `${l.pl} anytime TD` : `${l.pl} ${Number.isInteger(l.ln) ? l.ln : l.ln}+ ${String(l.ms || l.m).toLowerCase()}`;
}


// ---- weather turns (owner 11/1: "We should've had the weather update for the Bucs Falcons game ... Push notification for something like that
// would be helpful"). The boards read the sheet's kickoff forecast at build time; a forecast that turns after the last rebuild never reached
// anyone. Every 10-minute run now checks the open-air stadiums for games kicking off in the next 6 hours (Open-Meteo, no key) and pushes
// once per user per game when wind or rain reaches the same bar flags.py uses (wind 15+ mph or gusts 28+, or rain 60%+ with real rainfall),
// naming the passing / receiving legs on that user's slips.
const WXAPI = Deno.env.get("OPEN_METEO") ?? "https://api.open-meteo.com/v1/forecast";
// home team -> [lat, lon, "open" | "roof"]; roofs (domes, retractables, SoFi's canopy) are skipped
export const STADIUM: Record<string, [number, number, string]> = {
  ARI: [33.5276, -112.2626, "roof"], ATL: [33.7554, -84.4008, "roof"], BAL: [39.2780, -76.6227, "open"], BUF: [42.7738, -78.7870, "open"],
  CAR: [35.2258, -80.8528, "open"], CHI: [41.8623, -87.6167, "open"], CIN: [39.0955, -84.5161, "open"], CLE: [41.5061, -81.6995, "open"],
  DAL: [32.7473, -97.0945, "roof"], DEN: [39.7439, -105.0201, "open"], DET: [42.3400, -83.0456, "roof"], GB: [44.5013, -88.0622, "open"],
  HOU: [29.6847, -95.4107, "roof"], IND: [39.7601, -86.1639, "roof"], JAX: [30.3239, -81.6373, "open"], KC: [39.0489, -94.4839, "open"],
  LV: [36.0909, -115.1833, "roof"], LAC: [33.9535, -118.3392, "roof"], LA: [33.9535, -118.3392, "roof"], MIA: [25.9580, -80.2389, "open"],
  MIN: [44.9738, -93.2577, "roof"], NE: [42.0909, -71.2643, "open"], NO: [29.9511, -90.0812, "roof"], NYG: [40.8135, -74.0745, "open"],
  NYJ: [40.8135, -74.0745, "open"], PHI: [39.9008, -75.1675, "open"], PIT: [40.4468, -80.0158, "open"], SF: [37.4033, -121.9694, "open"],
  SEA: [47.5952, -122.3316, "open"], TB: [27.9759, -82.5033, "open"], TEN: [36.1665, -86.7713, "open"], WAS: [38.9078, -76.8645, "open"],
};
export type Wx = { wind: number; gust: number; pop: number; rain: number };
export function wxBad(w: Wx): string[] {   // same bar as flags.py's Wind flag, plus real rain
  const out: string[] = [];
  if (w.wind >= 15 || w.gust >= 28) out.push(`wind ${Math.round(w.wind)} mph` + (w.gust >= 20 ? `, gusts ${Math.round(w.gust)}` : ""));
  if (w.pop >= 60 && w.rain >= 0.04) out.push(`${w.rain >= 0.15 ? "heavy rain" : "rain"} ${Math.round(w.pop)}%`);
  else if (w.pop >= 40) out.push(`rain possible (${Math.round(w.pop)}% chance)`);   // owner 11/5 TNF: "WHERE WAS THE UPDATE THAT IT COULD BE RAINING?"
  return out;
}
export function wxSummary(w: Wx): string {   // the plain kickoff report every outdoor game gets, good weather or not
  const rain = w.pop >= 60 ? `rain likely (${Math.round(w.pop)}%)` : w.pop >= 20 ? `${Math.round(w.pop)}% chance of rain` : "dry";
  return `wind ${Math.round(w.wind)} mph${w.gust >= 20 ? ` (gusts ${Math.round(w.gust)})` : ""}, ${rain}`;
}
export const WXLEG = (m: string) => /^(Passing Yards|Receiving Yards|Receptions|Longest Reception|Rush \+ Rec Yards)$/.test(m);   // overs that wind / rain hurt
export function wxWindow(j: any, ko: number): Wx | null {   // kickoff hour through the next 3 hours, worst value of each
  const h = j?.hourly; if (!h || !Array.isArray(h.time)) return null;
  const w: Wx = { wind: 0, gust: 0, pop: 0, rain: 0 }; let n = 0;
  for (let i = 0; i < h.time.length; i++) {
    const t = Date.parse(h.time[i] + (/Z$|[+-]\d\d:?\d\d$/.test(h.time[i]) ? "" : "Z"));
    if (t < ko - 3600e3 || t > ko + 3 * 3600e3) continue; n++;
    w.wind = Math.max(w.wind, +h.wind_speed_10m?.[i] || 0); w.gust = Math.max(w.gust, +h.wind_gusts_10m?.[i] || 0);
    w.pop = Math.max(w.pop, +h.precipitation_probability?.[i] || 0); w.rain = Math.max(w.rain, +h.precipitation?.[i] || 0);
  }
  return n ? w : null;
}
async function wxAt(lat: number, lon: number, ko: number): Promise<Wx | null> {
  try {
    const r = await fetch(`${WXAPI}?latitude=${lat}&longitude=${lon}&hourly=wind_speed_10m,wind_gusts_10m,precipitation_probability,precipitation&wind_speed_unit=mph&precipitation_unit=inch&timezone=GMT&forecast_days=3`);
    if (!r.ok) { console.warn("weather", r.status); return null; }
    return wxWindow(await r.json(), ko);
  } catch (e) { console.warn("weather", String(e).slice(0, 80)); return null; }
}
async function homesOf(games: any[]): Promise<Map<string, { home: string; away: string; indoor: boolean }>> {   // ESPN scoreboard: who is at home, and the indoor flag
  const out = new Map(); const kos = games.map((g) => g.ko);
  const dr = `${ymd(Math.min(...kos) - 864e5)}-${ymd(Math.max(...kos) + 864e5)}`;
  const sb = await getJson([`${ESPN_BASE}/apis/site/v2/sports/football/nfl/scoreboard?dates=${dr}`, `https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=${dr}`, `https://cdn.espn.com/core/nfl/scoreboard?xhr=1&dates=${dr}`, `${FEEDS}/scoreboard.json`],
    (j) => j.events ? j : (j.content && j.content.sbData && j.content.sbData.events ? j.content.sbData : null));
  if (!sb) { console.warn("weather: no scoreboard"); return out; }
  for (const ev of (sb.events || [])) {
    const c = (ev.competitions || [])[0]; if (!c) continue;
    const ab = (x: any) => EAB[x?.team?.abbreviation] || x?.team?.abbreviation;
    const h = (c.competitors || []).find((x: any) => x.homeAway === "home"), a = (c.competitors || []).find((x: any) => x.homeAway === "away"); if (!h || !a) continue;
    for (const g of games) if ([g.a, g.b].includes(ab(h)) && [g.a, g.b].includes(ab(a))) out.set(g.gid, { home: ab(h), away: ab(a), indoor: !!c.venue?.indoor, neutral: !!c.neutralSite });
  }
  return out;
}

// ---------------- the run ----------------
// 11/5 Beat the model: the model's five for the week are frozen the first time the hourly run sees a week without a beat_model row -
// the Thursday-morning build's picks are the model's picks for the week, however the lines and the build move afterwards.
async function freezeBeat(W: number) {
  try {
    const have: any[] = await rest(`beat_model?select=week&week=eq.${W}`);
    if (have.length) return false;
    const b = await (await fetch(`${SITE}/b/beat.json`, { headers: { "cache-control": "no-cache" } })).json();
    if (!b || b.week !== W || !Array.isArray(b.model) || b.model.length !== 5) return false;
    await rest("beat_model", { method: "POST", headers: { Prefer: "resolution=ignore-duplicates" }, body: JSON.stringify({ week: W, keys: b.model }) });
    return true;
  } catch (e) { console.log("freezeBeat skipped:", String(e).slice(0, 120)); return false; }
}

export async function run(now = Date.now()) {
  const D = await builderData(); const W = D.week;
  const frozeBeat = await freezeBeat(W);
  const ko = new Map<string, number>(); for (const g of (D.games || [])) ko.set(g.gid, g.ko || 0);
  const gameOf = new Map<string, string>(); for (const l of (D.legs || [])) if (l.pos && !gameOf.has(norm(l.pl))) gameOf.set(norm(l.pl), l.g);
  const subs: Sub[] = await rest("push_subs?select=endpoint,user_id,p256dh,auth,live,weekly");
  if (!subs.length) return { week: W, subs: 0, sent: 0, frozeBeat };
  const users = [...new Set(subs.map((s) => s.user_id))];
  const states: any[] = await rest(`user_state?select=user_id,key,value&key=in.(bs_slips_w${W},bs_slipk_w${W})&user_id=in.(${users.join(",")})`);
  const sent: any[] = await rest(`push_sent?select=user_id,player,status&week=eq.${W}`);
  const done = new Set(sent.map((x) => `${x.user_id}|${x.player}|${x.status}`));
  const ST = await espnStatuses();
  let ninact = 0; try { ninact = await gameDayOuts(D, now, ST); } catch (e) { console.warn("inactives", String(e)); }
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
      const msg = { title: h.why === "Inactive" ? `${h.name} is INACTIVE tonight` : `${h.name} is ${h.st === "OUT" ? "OUT" : "DOUBTFUL"}${h.why ? " (" + h.why + ")" : ""}`,
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
  // ---- kickoff reminders (owner 11/4, "the app on the phone during football season"): 20-40 minutes before a game, one push per user per
  // game naming how many of their slip legs are in it; the run is every 10 minutes so the window catches each kickoff once (push_sent __ko__<gid>).
  let nko = 0;
  try {
    const LEGG = new Map<string, string>(); for (const l of (D.legs || [])) { LEGG.set(`${l.pl}|${l.m}|${Math.floor(Number(l.ln || 1) + 0.5)}`, l.g); if (!l.gl) LEGG.set(`${l.pl}|${l.m}|${l.ln}`, l.g); }
    const soonKo = (D.games || []).filter((g: any) => g.ko && g.ko - now > 20 * 60e3 && g.ko - now <= 40 * 60e3);
    if (soonKo.length) for (const uid of users) {
      const keys: string[] = [];
      for (const r of states.filter((x) => x.user_id === uid)) { let v: any = null; try { v = JSON.parse(r.value?.v ?? "null"); } catch { v = null; }
        if (r.key.startsWith("bs_slips_w") && Array.isArray(v)) for (const sl of v) if (sl && Array.isArray(sl.keys)) keys.push(...sl.keys.map(String));
        if (r.key.startsWith("bs_slipk_w") && Array.isArray(v)) keys.push(...v.map(String)); }
      if (!keys.length) continue;
      const us = subs.filter((s) => s.user_id === uid && s.live !== false);
      for (const g of soonKo) {
        const key = `__ko__${g.gid}`; if (done.has(`${uid}|${key}|SENT`)) continue;
        const n = new Set(keys.filter((k) => (LEGG.get(k) || gameOf.get(norm(k.split("|")[0]))) === g.gid)).size; if (!n) continue;
        const mins = Math.round((g.ko - now) / 60e3);
        if (DISCORD && !(await keysDone(`dc|ko|${W}|${g.gid}`)).size) { if (await discord(`${g.a} @ ${g.b} kicks off in ${mins} min`, `Live page tracks every leg against the box score with the model's chance from here.`, `/live/#lv-${g.gid}`)) await markKey(`dc|ko|${W}|${g.gid}`); }
        const msg = { title: `${g.a} @ ${g.b} kicks off in ${mins} min`, body: `${n} of your legs ${n === 1 ? "is" : "are"} in this one. Live page tracks them against the box score with the model's chance from here.`, url: `/live/#g-${g.gid}`, tag: `bs-ko-${g.gid}` };
        for (const s of us) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) nko++; } catch (e) { console.warn("push", String(e)); } }
        await mark(uid, W, key, "SENT"); done.add(`${uid}|${key}|SENT`);
      }
    }
  } catch (e) { console.warn("kickoff reminders", String(e).slice(0, 200)); }
  // ---- weather turns (owner 11/1) ----
  let nwx = 0; const wxGames: string[] = [];
  const LEG = new Map<string, any>(); for (const l of (D.legs || [])) { const k = `${l.pl}|${l.m}|${Math.floor(Number(l.ln || 1) + 0.5)}`; if (!LEG.has(k)) LEG.set(k, l); }
  const soon = (D.games || []).filter((g: any) => g.ko && g.ko > now && g.ko - now <= 6 * 3600e3);
  if (soon.length) {
    const HOME = await homesOf(soon); const WX = new Map<string, { bad: string[]; title: string }>(); const REPORT = new Map<string, { txt: string; title: string }>();
    for (const g of soon) {
      const h = HOME.get(g.gid) as any; if (!h || h.indoor || h.neutral) continue;
      const st = STADIUM[h.home]; if (!st || st[2] !== "open") continue;
      const w = await wxAt(st[0], st[1], g.ko); if (!w) continue;
      const bad = wxBad(w); if (bad.length) { WX.set(g.gid, { bad, title: `${h.away} @ ${h.home}` }); wxGames.push(`${h.away}@${h.home}: ${bad.join(", ")}`); }
      else REPORT.set(g.gid, { txt: wxSummary(w), title: `${h.away} @ ${h.home}` });
    }
    // owner 11/5 TNF: every outdoor game gets a kickoff weather report once (within 6 hours of kickoff), even when it is fine - a later
    // turn for the worse still pushes the bad-weather alert below (its own tag), so nobody is left guessing.
    for (const [gid, x] of REPORT) {
      for (const uid of users) {
        if (done.has(`${uid}|wxr|${gid}|WXR`)) continue;
        const msg = { title: `🌤 Weather: ${x.title}`.slice(0, 90), body: `Kickoff forecast: ${x.txt}. No weather flag on this game's legs.`, url: `/boards/#${gid}`, tag: `bs-wxr-${W}-${gid}` };
        for (const s of subs.filter((s) => s.user_id === uid)) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) nwx++; } catch (e) { console.warn("push", String(e)); } }
        done.add(`${uid}|wxr|${gid}|WXR`); await mark(uid, W, `wxr|${gid}`, "WXR");
      }
    }
    // owner 11/5 ("always push weather updates"): every subscriber hears about every bad-weather kickoff once, legs or no legs; the legs
    // on their slips are named when there are any. Discord gets one message per game.
    if (WX.size && DISCORD) { const dc = await keysDone(`dc|wx|${W}|`);
      for (const [gid, x] of WX) { if (dc.has(`dc|wx|${W}|${gid}`)) continue; if (await discord(`Weather: ${x.title}`, `Kickoff forecast: ${x.bad.join(", ")}. Wind and rain cut passing and deep throws - runs and unders gain.`, `/boards/#${gid}`)) await markKey(`dc|wx|${W}|${gid}`); } }
    if (WX.size) for (const uid of users) {
      const per = new Map<string, Set<string>>();
      for (const r of states.filter((x) => x.user_id === uid)) {
        let v: any = null; try { v = JSON.parse(r.value?.v ?? "null"); } catch { v = null; }
        const keys: string[] = r.key.startsWith("bs_slipk_w") ? (Array.isArray(v) ? v : []) : (Array.isArray(v) ? v.flatMap((s: any) => (s && Array.isArray(s.keys)) ? s.keys : []) : []);
        for (const k of keys) { const l = LEG.get(k); if (!l || !l.g || !WX.has(l.g) || !WXLEG(String(l.m))) continue;
          const set = per.get(l.g) || new Set(); set.add(legText(l, k)); per.set(l.g, set); }
      }
      for (const [gid, x] of WX) {
        if (done.has(`${uid}|wx|${gid}|WX`)) continue;
        const L = [...(per.get(gid) || [])];
        const mine = L.length ? ` On your slips: ${L.slice(0, 3).join("; ")}${L.length > 3 ? ` +${L.length - 3} more` : ""}.` : " Nothing of yours is in it.";
        const msg = { title: `⛈ Weather: ${x.title}`.slice(0, 90),
          body: `Kickoff forecast: ${x.bad.join(", ")}.${mine} Wind and rain cut passing and deep throws - runs and unders gain.`,
          url: L.length ? "/me/" : `/boards/#${gid}`, tag: `bs-wx-${W}-${gid}` };
        for (const s of subs.filter((s) => s.user_id === uid)) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) nwx++; } catch (e) { console.warn("push", String(e)); } }
        done.add(`${uid}|wx|${gid}|WX`); await mark(uid, W, `wx|${gid}`, "WX");
      }
    }
  }
  // ---- line moves on YOUR legs (owner 11/5): data/price-moves.json (hourly, every board leg) x each subscriber's slip keys ----
  // one push per leg per direction (push_sent __mv__<key>|<dir>), 3+ implied points (about 10 cents) or more, game not yet kicked off.
  let nmv = 0;
  try {
    const pmj: any = await (await fetch(`${SITE}/data/price-moves.json`, { headers: { "cache-control": "no-cache" } })).json().catch(() => null);
    const MV = new Map<string, any>(); for (const m of (pmj?.moves || [])) if (m && m.key && Math.abs(+m.pts || 0) >= 3 && (!m.ko || m.ko > now)) MV.set(String(m.key), m);
    const imp = (o: number) => o > 0 ? 100 / (o + 100) : -o / (-o + 100);
    if (MV.size) for (const uid of users) {
      const keys = new Set<string>();
      for (const r of states.filter((x) => x.user_id === uid)) { let v: any = null; try { v = JSON.parse(r.value?.v ?? "null"); } catch { v = null; }
        if (r.key.startsWith("bs_slips_w") && Array.isArray(v)) for (const sl of v) if (sl && Array.isArray(sl.keys)) for (const k of sl.keys) keys.add(String(k));
        if (r.key.startsWith("bs_slipk_w") && Array.isArray(v)) for (const k of v) keys.add(String(k)); }
      if (!keys.size) continue;
      const us = subs.filter((s) => s.user_id === uid && s.live !== false); if (!us.length) continue;
      for (const k of keys) {
        const m = MV.get(k); if (!m) continue;
        const mk = `__mv__${k}|${m.dir}`.slice(0, 300); if (done.has(`${uid}|${mk}|SENT`)) continue;
        const l = LEG.get(k); const edge = l && typeof l.p === "number" ? Math.round((l.p - imp(+m.now)) * 100) : null;
        const up = m.dir === "SHORTENED";
        const msg = { title: `${up ? "📈" : "📉"} ${m.pl}: ${am(+m.built)} → ${am(+m.now)}`.slice(0, 90),
          body: `${String(m.detail || "").replace(/^[^:]*: /, "")}${edge === null ? "" : up ? (edge > 0 ? ` Still +${edge} edge at the new price.` : ` The edge is gone at the new price (${edge}).`) : ` Model edge at the new price: ${edge > 0 ? "+" : ""}${edge}.`}`.slice(0, 300),
          url: "/me/", tag: `bs-mv-${W}-${k}`.slice(0, 60) };
        for (const s of us) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) nmv++; } catch (e) { console.warn("push", String(e)); } }
        await mark(uid, W, mk, "SENT"); done.add(`${uid}|${mk}|SENT`);
      }
    }
  } catch (e) { console.warn("line moves", String(e).slice(0, 200)); }
  // ---- live risk list + promo watch (owner 11/1) ----
  let nrisk = 0, npromo = 0;
  try {
    const nowIso = new Date(now).toISOString(); const rows: any[] = [];
    const legOfName = new Map<string, any>(); for (const l of (D.legs || [])) if (l.pos && !legOfName.has(norm(l.pl))) legOfName.set(norm(l.pl), l);
    const injRow = (n: string, st: string, why: string) => { const l = legOfName.get(n); if (!l || (ko.get(l.g) || 0) <= now) return;
      rows.push({ id: `inj|${n}`, kind: "injury", week: W, player: l.pl, team: l.tm, gid: l.g, status: st, level: st === "OUT" ? "block" : "warn", detail: why || null, by_owner: false, updated_at: nowIso }); };
    for (const [n, v] of ST) injRow(n, v.st, v.why);
    for (const [n, why] of QST) if (!ST.has(n)) injRow(n, "QUESTIONABLE", why);
    const day = (D.games || []).filter((g: any) => g.ko && g.ko > now && g.ko - now <= 24 * 3600e3);
    const WX24 = new Map<string, string[]>();
    if (day.length) { const HOME = await homesOf(day);
      for (const g of day) { const h = HOME.get(g.gid) as any; if (!h || h.indoor || h.neutral) continue; const stad = STADIUM[h.home]; if (!stad || stad[2] !== "open") continue;
        const w = await wxAt(stad[0], stad[1], g.ko); if (!w) continue; const bad = wxBad(w); if (!bad.length) continue; WX24.set(g.gid, bad);
        const who = [...new Set((D.legs || []).filter((l: any) => l.g === g.gid && WXLEG(String(l.m)) && ["QB", "WR", "TE"].includes(l.pos)).map((l: any) => l.pl))];
        rows.push({ id: `wx|${g.gid}`, kind: "weather", week: W, player: null, team: null, gid: g.gid, status: "WEATHER", level: "warn", detail: `${h.away} @ ${h.home} kickoff forecast: ${bad.join(", ")}`, players: who, by_owner: false, updated_at: nowIso }); } }
    for (let i = 0; i < rows.length; i += 200) await rest("risk_feed?on_conflict=id", { method: "POST", headers: { Prefer: "resolution=merge-duplicates" }, body: JSON.stringify(rows.slice(i, i + 200)) });
    await rest(`risk_feed?kind=in.(injury,weather)&updated_at=lt.${encodeURIComponent(new Date(now - 25 * 60e3).toISOString())}`, { method: "DELETE" });
    nrisk = rows.length;
    // promo watch: any LIVE promo leg not yet kicked off that an injury, a weather turn or an owner note now touches -> one push to the owner
    const notes: any[] = await rest("risk_feed?kind=eq.note&select=player,status,detail");
    const promos: any[] = await (await fetch(`${SITE}/b/promos.json`, { headers: { "cache-control": "no-cache" } })).json().catch(() => []);
    const owner = await rest("rpc/bs_owner_id", { method: "POST", body: "{}" }).catch(() => null);
    const osubs = owner ? subs.filter((s) => s.user_id === owner) : [];
    const riskOf = (n: string, m: string, gid: string) => ST.has(n) || QST.has(n) || notes.some((x) => norm(x.player) === n && ["OUT", "HURT", "LIMITED"].includes(x.status)) || (WX24.has(gid) && WXLEG(m));
    const swapFor = (lg: any, pr: any) => {
      const mk = String(lg.market || String(lg.key || "").split("|")[1] || ""); if (!mk || /either/i.test(mk)) return null;
      const inPromo = new Set((pr.legs || []).flatMap((x: any) => String(x.who || "").split(/\s+or\s+/i).map(norm)));
      const orig = (D.legs || []).find((l: any) => `${l.pl}|${l.m}|${Math.round(l.ln || 1)}` === lg.key);
      const pool = (D.legs || []).filter((l: any) => l.g === lg.gid && l.m === mk && l.pos && !l.w && !inPromo.has(norm(l.pl)) && !riskOf(norm(l.pl), l.m, l.g)
        && (!orig || (Math.abs(l.ln - orig.ln) <= Math.max(10, orig.ln * 0.35) && l.p >= orig.p - 0.08)));
      pool.sort((a: any, b: any) => (b.e - a.e) || (b.p - a.p)); return pool[0] || null; };
    if (owner && Array.isArray(promos)) for (const pr of promos) {
      if (String(pr.status || "LIVE").toUpperCase() !== "LIVE" || pr.week !== W) continue; const code = `w${pr.week}-${pr.slot}`;
      for (const lg of (pr.legs || [])) {
        if (!lg.ko || lg.ko <= now) continue;
        for (const who of String(lg.who || "").split(/\s+or\s+/i)) {
          const n = norm(who); let why = "", tag = "";
          const inj = ST.get(n); if (inj) { why = `${inj.st}${inj.why ? " (" + inj.why + ")" : ""} on the injury report`; tag = inj.st; }
          else if (QST.has(n)) { why = `Questionable${QST.get(n) ? " (" + QST.get(n) + ")" : ""}`; tag = "Q"; }
          const nt = notes.find((x) => norm(x.player) === n && ["OUT", "HURT", "LIMITED"].includes(x.status)); if (!why && nt) { why = `your note: ${String(nt.status).toLowerCase()}${nt.detail ? " - " + nt.detail : ""}`; tag = "N" + nt.status; }
          if (!why && WX24.has(lg.gid) && WXLEG(String(lg.market))) { why = `weather - ${WX24.get(lg.gid)!.join(", ")}`; tag = "WX"; }
          if (!why) continue;
          const key = `promo|${code}|${n}|${tag}`; if (done.has(`${owner}|${key}|PROMO`)) continue;
          // owner 11/1: name the model's best clean replacement from the same game and market, and open the builder with the swapped slip
          const sw = swapFor(lg, pr); let body = `${who}: ${why}. Leg: ${lg.disp || lg.key}.`, url = `/b/${code}/`;
          if (sw) { body += ` Swap: ${legLabel(sw)} (${am(sw.o)}, model ${Math.round(sw.p * 100)}%). Tap to load the swapped slip.`;
            const ks = (pr.legs || []).map((x: any) => x === lg ? `${sw.pl}|${sw.m}|${Math.round(sw.ln || 1)}` : x.key).filter(Boolean);
            url = `/build/?new=1&${ks.map((k: string) => "add=" + encodeURIComponent(k)).join("&")}#slip`; }
          else body += " No clean same-game swap on the board - pull it before kickoff.";
          const msg = { title: `⚠ Promo at risk: ${pr.title}`.slice(0, 90), body: body.slice(0, 300), url, tag: `bs-promo-${code}` };
          for (const s of osubs) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) npromo++; } catch (e) { console.warn("push", String(e)); } }
          done.add(`${owner}|${key}|PROMO`); await mark(String(owner), W, key, "PROMO");
        }
      }
    }
    // price moves (owner 11/4): the price-moves workflow writes data/price-moves.json (Model's Best plus / TD legs whose FanDuel price moved 3+
    // implied points since the build). A move TOWARD the model is the market agreeing and the leg going away - push the owner once per key.
    try {
      const pm: any = await (await fetch(`${SITE}/data/price-moves.json`, { headers: { "cache-control": "no-cache" } })).json().catch(() => null);
      if (owner && pm && pm.week === W && Array.isArray(pm.moves)) for (const mv of pm.moves) {
        if (mv.dir !== "SHORTENED" || !mv.ko || mv.ko <= now || Math.abs(mv.pts || 0) < 3) continue;
        const key = `price|${mv.key}`; if (done.has(`${owner}|${key}|PRICE`)) continue;
        const msg = { title: `📈 Market moving our way: ${mv.pl}`.slice(0, 90), body: `${mv.detail}. Still on the board - the price is going.`.slice(0, 300), url: `/build/?new=1&add=${encodeURIComponent(mv.key)}#slip`, tag: `bs-price-${String(mv.key).replace(/[^a-z0-9]/gi, "").slice(0, 40)}` };
        for (const s of osubs) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) npromo++; } catch (e) { console.warn("push", String(e)); } }
        done.add(`${owner}|${key}|PRICE`); await mark(String(owner), W, key, "PRICE");
      }
    } catch (e) { console.warn("price moves", String(e).slice(0, 200)); }
  } catch (e) { console.warn("risk", String(e).slice(0, 200)); }
  // ---- live slip updates (owner 10/30): during games, a note when a leg on a saved slip hits or busts, and when a slip cashes ----
  let nlive = 0;
  const liveSubs = subs.filter((s) => s.live !== false);
  const recent = (D.games || []).filter((g: any) => g.ko && now >= g.ko && now <= g.ko + 5 * 3600e3);
  if (liveSubs.length && recent.length) {
    const BOX = await liveBox(recent);
    for (const uid of [...new Set(liveSubs.map((s) => s.user_id))]) {
      const events: string[] = []; const evSid: string[] = [];   // owner 11/1: a tap opens that slip on the Live page
      for (const r of states.filter((x) => x.user_id === uid && (x.key.startsWith("bs_slips_w") || x.key.startsWith("bs_slipk_w")))) {
        let v: any = null; try { v = JSON.parse(r.value?.v ?? "null"); } catch { v = null; }
        // owner 11/5 ("how come I'm not getting live notifications about legs hitting?"): the working Builder slip counts too, not only saved slips
        if (r.key.startsWith("bs_slipk_w")) v = (Array.isArray(v) && v.length) ? [{ id: "builder", name: "Builder slip", keys: v }] : [];
        for (const sl of (Array.isArray(v) ? v : [])) {
          if (!sl || !Array.isArray(sl.keys) || !sl.keys.length) continue;
          const name = String(sl.name || "Saved slip"), sid = String(sl.id || name);
          // owner 11/1: legs FanDuel stopped pricing at kickoff are gone from the builder data - rebuild them from the key and the box score's game
          const legOf = (k: string) => { const l = LEG.get(k); if (l) return l; const [pl, m, ln] = String(k).split("|"); const r = BOX.players.get(norm(pl || ""));
            return r && m ? { pl, m, ln: Number(ln), g: r.g } : undefined; };
          const st = sl.keys.map((k: string) => { const l = legOf(k); return { k, l, s: gradeLeg(l, k, BOX) }; });
          if (!st.some((x: any) => x.s !== "open" && x.s !== "na")) continue;
          const busted = st.find((x: any) => x.s === "miss"), hits = st.filter((x: any) => x.s === "hit").length;
          const tag = (what: string) => `${sid}|${what}`;
          if (busted) {
            if (!done.has(`${uid}|${tag("BUST")}|BUST`)) { events.push(`\u2717 "${name}" busted: ${legText(busted.l, busted.k)}`); evSid.push(sid); done.add(`${uid}|${tag("BUST")}|BUST`); await mark(uid, W, tag("BUST"), "BUST"); }
            continue;
          }
          if (hits === st.length) {
            if (!done.has(`${uid}|${tag("CASH")}|CASH`)) { events.push(`\u2705 "${name}" cashed - all ${st.length} legs hit`); evSid.push(sid); done.add(`${uid}|${tag("CASH")}|CASH`); await mark(uid, W, tag("CASH"), "CASH"); }
            continue;
          }
          for (const x of st.filter((x: any) => x.s === "hit")) {
            const key = tag(x.k);
            if (done.has(`${uid}|${key}|HIT`)) continue;
            events.push(`\u2713 ${legText(x.l, x.k)} - "${name}" ${hits}/${st.length}, ${st.length - hits} to go`); evSid.push(sid); done.add(`${uid}|${key}|HIT`); await mark(uid, W, key, "HIT");
          }
        }
      }
      if (!events.length) continue;
      const one = [...new Set(evSid)].length === 1 ? evSid[0] : ""; const lurl = one ? `/live/?slip=${encodeURIComponent(one)}` : "/live/?slip=all";
      const msg = events.length === 1 ? { title: events[0].slice(0, 90), body: events[0].length > 90 ? events[0] : "Tap to see this slip live.", url: lurl, tag: `bs-live-${W}` }
        : { title: `${events.length} slip updates`, body: events.join(" \u00b7 ").slice(0, 300), url: lurl, tag: `bs-live-${W}` };
      for (const s of liveSubs.filter((s) => s.user_id === uid)) {
        try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) nlive++; } catch (e) { console.warn("push", String(e)); }
      }
    }
  }
  for (const ep of [...new Set(gone)]) await rest(`push_subs?endpoint=eq.${encodeURIComponent(ep)}`, { method: "DELETE" });
  return { week: W, subs: subs.length, users: users.length, alerts: nalerts, sent: nsent, kickoff: nko, live: nlive, weather: wxGames, wxSent: nwx, moves: nmv, risk: nrisk, promoAlerts: npromo, inactives: ninact, removed: gone.length, statuses: ST.size, frozeBeat };
}

// owner 11/5: marks that are not per user (Discord posts, model-wide sends) live in bs_marks (key text primary key; owner/betsweep-11-5.sql)
export async function keysDone(prefix: string): Promise<Set<string>> {
  try { const rows: any[] = await rest(`bs_marks?select=key&key=like.${encodeURIComponent(prefix + "%")}`); return new Set(rows.map((r) => r.key)); } catch { return new Set(); }
}
export async function markKey(key: string) {
  try { await rest("bs_marks", { method: "POST", headers: { Prefer: "resolution=ignore-duplicates" }, body: JSON.stringify([{ key: key.slice(0, 300) }]) }); } catch (e) { console.warn("markKey", String(e).slice(0, 80)); }
}
async function mark(uid: string, W: number, player: string, status: string) {
  await rest("push_sent", { method: "POST", headers: { Prefer: "resolution=ignore-duplicates" }, body: JSON.stringify([{ user_id: uid, week: W, player: player.slice(0, 300), status }]) });
}

// ESPN box scores for games under way / just finished: {players: norm(name) -> {pass,rush,rec,recy,long,td}, first: gid -> norm(name), state: gid -> pre|in|post}
type Box = { players: Map<string, any>; first: Map<string, string>; state: Map<string, string> };
const EAB: Record<string, string> = { WSH: "WAS", LAR: "LA" };
function ymd(t: number) { const d = new Date(t); return `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, "0")}${String(d.getUTCDate()).padStart(2, "0")}`; }
export function parseSummary(js: any, gid: string, B: Box) {
  const num = (v: any) => { const m = String(v ?? "").match(/-?\d+(\.\d+)?/); return m ? +m[0] : 0; };
  for (const tm of (js?.boxscore?.players || [])) for (const cat of (tm.statistics || [])) {
    const keys = cat.keys || cat.labels || [];
    for (const a of (cat.athletes || [])) {
      const n = norm(a?.athlete?.displayName || a?.athlete?.shortName || ""); if (!n) continue;
      const r = B.players.get(n) || { pass: 0, rush: 0, rec: 0, recy: 0, long: 0, td: 0, g: gid }; B.players.set(n, r);
      const S: Record<string, any> = {}; keys.forEach((k: string, i: number) => { S[k] = (a.stats || [])[i]; });
      if (cat.name === "passing") r.pass = num(S.passingYards ?? S.YDS);
      if (cat.name === "rushing") { r.rush = num(S.rushingYards ?? S.YDS); r.td += num(S.rushingTouchdowns ?? S.TD); }
      if (cat.name === "receiving") { r.rec = num(S.receptions ?? S.REC); r.recy = num(S.receivingYards ?? S.YDS); r.long = Math.max(r.long, num(S.longReception ?? S.LONG)); r.td += num(S.receivingTouchdowns ?? S.TD); }
    }
  }
  const sp = (js?.scoringPlays || []).filter((p: any) => (p.type && /touchdown/i.test(p.type.text || "")) || /\bTD\b|touchdown/i.test(p.text || ""));
  if (sp.length) { const m = String(sp[0].text || "").match(/^([A-Z][\w.'-]+(?:\s[A-Z][\w.'-]+){0,3}?)\s+\d+\s+(?:Yd|Yard)/i); B.first.set(gid, m ? norm(m[1]) : "?"); }
}
async function liveBox(games: any[]): Promise<Box> {
  const B: Box = { players: new Map(), first: new Map(), state: new Map() };
  const kos = games.map((g) => g.ko);
  const dr = `${ymd(Math.min(...kos) - 864e5)}-${ymd(Math.max(...kos) + 864e5)}`;
  const sb = await getJson([`${ESPN_BASE}/apis/site/v2/sports/football/nfl/scoreboard?dates=${dr}`, `https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=${dr}`, `https://cdn.espn.com/core/nfl/scoreboard?xhr=1&dates=${dr}`, `${FEEDS}/scoreboard.json`],
    (j) => j.events ? j : (j.content && j.content.sbData && j.content.sbData.events ? j.content.sbData : null));
  if (!sb) { console.warn("no scoreboard reachable this run"); return B; }
  for (const ev of (sb.events || [])) {
    const c = (ev.competitions || [])[0]; if (!c) continue;
    const abs = (c.competitors || []).map((x: any) => EAB[x?.team?.abbreviation] || x?.team?.abbreviation);
    for (const g of games) {
      if (!abs.includes(g.a) || !abs.includes(g.b)) continue;
      const st = ((ev.status || c.status || {}).type || {}).state || "pre"; B.state.set(g.gid, st);
      if (st === "pre") continue;
      const sm = await getJson([`${ESPN_BASE}/apis/site/v2/sports/football/nfl/summary?event=${ev.id}`, `https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${ev.id}`, `https://cdn.espn.com/core/nfl/boxscore?xhr=1&gameId=${ev.id}`, `${FEEDS}/box/${ev.id}.json`],
        (j) => j.boxscore ? j : (j.gamepackageJSON && j.gamepackageJSON.boxscore ? j.gamepackageJSON : null));
      if (sm) { try { parseSummary(sm, g.gid, B); } catch (e) { console.warn("summary", g.gid, String(e)); } }
    }
  }
  return B;
}
// hit / miss / open for one slip leg; game lines and unknown markets stay "na" (no live note)
export function gradeLeg(l: any, key: string, B: Box): "hit" | "miss" | "open" | "na" {
  if (!l || l.gl || !l.g) return "na";
  const st = B.state.get(l.g); if (!st || st === "pre") return "open";
  const fin = st === "post", r = B.players.get(norm(l.pl)), m = String(l.m || "");
  if (m === "First TD") { const f = B.first.get(l.g); if (!f) return fin && r ? "miss" : "open"; return f === norm(l.pl) ? "hit" : "miss"; }
  if (!r) return "open";   // no box line (inactive = FanDuel voids) - never called a miss
  const need = m === "2+ TD" ? 2 : m === "3+ TD" ? 3 : m === "Anytime TD" ? 1 : Number(l.ln);
  const base = m.replace(/^Under /, "");
  const v = /TD$/.test(m) ? r.td : base === "Passing Yards" ? r.pass : base === "Rushing Yards" ? r.rush : base === "Receiving Yards" ? r.recy : base === "Receptions" ? r.rec
    : base === "Longest Reception" ? r.long : base === "Rush + Rec Yards" ? r.rush + r.recy : null;
  if (v == null || !isFinite(need)) return "na";
  if (m.startsWith("Under ")) return v > need ? "miss" : (fin ? "hit" : "open");
  return v >= need ? "hit" : (fin ? "miss" : "open");
}
function legText(l: any, key: string): string {
  if (!l) return String(key).split("|").slice(0, 2).join(" ");
  const m = String(l.m || "");
  if (/TD$/.test(m)) return `${l.pl} ${m === "Anytime TD" ? "anytime TD" : m}`;
  if (m.startsWith("Under ")) return `${l.pl} under ${l.ln} ${String(l.ms || m.slice(6)).toLowerCase()}`;
  return `${l.pl} ${l.ln}+ ${String(l.ms || m).toLowerCase()}`;
}

// ---- DraftKings salaries (owner 10/30: "let's do draft kings"): every 3 hours (pg_cron, body {"mode":"dk"}) find the main classic NFL slate in
// DraftKings' public lobby and store its player list in public.dfs_salaries (site 'dk', this week) as DraftKings' own CSV, which the DFS page
// loads for everyone. Same rules as the old sheet script DKSalaries.gs (Featured classic slate first, then the most games, then the soonest).
const DKH = { "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.draftkings.com/lobby", "Origin": "https://www.draftkings.com",
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36" };
const DKW = Deno.env.get("DK_WWW") ?? "https://www.draftkings.com", DKA = Deno.env.get("DK_API") ?? "https://api.draftkings.com";
export function parseCsv(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) { const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c; }
    else if (c === '"') q = true; else if (c === ",") { row.push(cur); cur = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cur); rows.push(row); row = []; cur = ""; } else cur += c; }
  if (cur.length || row.length) { row.push(cur); rows.push(row); }
  return rows;
}
function csvq(c: unknown) { const x = String(c ?? ""); return /[",\n]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x; }
export async function dkSalaries() {
  const D = await builderData(); const W = D.week;
  const lob = await fetch(`${DKW}/lobby/getcontests?sport=NFL`, { headers: DKH });
  if (!lob.ok) return { error: `DraftKings lobby answered ${lob.status}` };
  const L = await lob.json();
  const groups = (L.DraftGroups || L.draftGroups || []).filter((g: any) => ((g.GameTypeId === 1) || (g.GameTypeId == null && g.ContestTypeId === 21)) && !g.ContestStartTimeSuffix && (g.Sport == null || g.Sport === "NFL"));
  if (!groups.length) return { error: `no classic NFL draft group in the lobby (${(L.DraftGroups || []).length} groups)` };
  groups.sort((a: any, b: any) => ((b.DraftGroupTag === "Featured" ? 1 : 0) - (a.DraftGroupTag === "Featured" ? 1 : 0)) || ((b.GameCount || 0) - (a.GameCount || 0)) || String(a.StartDateEst || "").localeCompare(String(b.StartDateEst || "")));
  const g = groups[0], id = g.DraftGroupId;
  let rows: string[][] = [], how = "csv", why = "";
  // a) the player-list CSV (DraftKings' own "Export to CSV" file) from www.draftkings.com
  try {
    const c = await fetch(`${DKW}/lineup/getavailableplayerscsv?contestTypeId=${g.ContestTypeId || 21}&draftGroupId=${id}`, { headers: { ...DKH, "Accept": "text/csv, */*" } });
    const t = await c.text();
    if (c.ok && /Salary/.test(t.slice(0, 600))) {
      const all = parseCsv(t); const hi = all.findIndex((x) => x.includes("Salary") && x.includes("Position"));
      if (hi >= 0) { const c0 = all[hi].indexOf("Position"); rows = all.slice(hi).map((x) => x.slice(c0, c0 + 9)).filter((x) => x[0]); }
    } else why = `csv ${c.status}`;
  } catch (e) { why = "csv " + String(e).slice(0, 60); }
  if (rows.length < 21) {
    how = "draftables"; rows = [["Position", "Name + ID", "Name", "ID", "Roster Position", "Salary", "Game Info", "TeamAbbrev", "AvgPointsPerGame"]];
    const r = await fetch(`${DKA}/draftgroups/v1/draftgroups/${id}/draftables`, { headers: DKH });
    if (!r.ok) return { error: `DraftKings player list blocked (${why}; draftables ${r.status}) for draft group ${id}` };
  const dj = await r.json(); const seen = new Set<number>();
  for (const p of (dj.draftables || [])) {
    if (seen.has(p.draftableId)) continue; seen.add(p.draftableId);
    const comp = p.competition || {}, pos = p.position || "";
    rows.push([pos, `${p.displayName} (${p.draftableId})`, p.displayName, String(p.draftableId), pos === "QB" ? "QB" : pos === "DST" ? "DST" : `${pos}/FLEX`, String(p.salary),
      String(comp.name || "").replace(/\s/g, ""), p.teamAbbreviation || "", ""]);
  }
  }
  if (rows.length < 21) return { error: `draftables returned only ${rows.length - 1} players (draft group ${id})` };
  const csv = rows.map((x) => x.map(csvq).join(",")).join("\n");
  await rest("dfs_salaries?on_conflict=site,week", { method: "POST", headers: { Prefer: "resolution=merge-duplicates" },
    body: JSON.stringify([{ site: "dk", week: W, slate: `main slate (${g.GameCount || "?"} games)`, csv, players: rows.length - 1, updated_at: new Date().toISOString() }]) });
  return { week: W, draftGroup: id, games: g.GameCount, players: rows.length - 1, via: how };
}

// ---- weekly Model's Best note (owner 10/30): one push per user per week, Thursday morning (pg_cron, body {"mode":"weekly"}) ----
export async function weekly(now = Date.now()) {
  const D = await builderData(); const W = D.week;
  const ko = new Map<string, number>(); for (const g of (D.games || [])) ko.set(g.gid, g.ko || 0);
  const best = (D.legs || []).filter((l: any) => l.tier && (ko.get(l.g) || 0) > now);
  if (!best.length) return { week: W, best: 0, sent: 0 };
  const subs: Sub[] = (await rest("push_subs?select=endpoint,user_id,p256dh,auth,live,weekly")).filter((s: Sub) => s.weekly !== false);
  const sent: any[] = await rest(`push_sent?select=user_id&week=eq.${W}&player=eq.__weekly__`);
  const done = new Set(sent.map((x) => x.user_id));
  const top = best.filter((l: any) => l.tier !== "td").sort((a: any, b: any) => b.p - a.p).slice(0, 3);
  const msg = { title: `Week ${W} Model's Best is up: ${best.length} picks`,
    body: "Top: " + top.map((l: any) => `${legText(l, "")} (${am(l.o)}, ${Math.round(l.p * 100)}%)`).join(" \u00b7 "), url: "/build/?best=1", tag: `bs-weekly-${W}` };
  let n = 0; const gone: string[] = [];
  for (const uid of [...new Set(subs.map((s) => s.user_id))]) {
    if (done.has(uid)) continue;
    for (const s of subs.filter((s) => s.user_id === uid)) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) n++; } catch (e) { console.warn("push", String(e)); } }
    await mark(uid, W, "__weekly__", "SENT");
  }
  for (const ep of gone) await rest(`push_subs?endpoint=eq.${encodeURIComponent(ep)}`, { method: "DELETE" });
  return { week: W, best: best.length, sent: n };
}

// owner 11/4 ("one of the few apps on the phone during football season"): the morning brief. pg_cron calls {"mode":"brief"} every day at
// 9:05 am Central; build_today.py leaves /b/today.json with a ready title/body per GAME DAY (Central date). No game today -> nothing is sent.
// One push per subscriber per game day (push_sent player = __brief__<date>); honours the same "weekly" preference as the Thursday push.
export async function brief(now = Date.now()) {
  const tj: any = await (await fetch(`${SITE}/b/today.json`, { headers: { "cache-control": "no-cache" } })).json().catch(() => null);
  if (!tj || !tj.briefs) return { sent: 0, reason: "no today.json" };
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(now));
  const o: Record<string, string> = {}; for (const x of p) o[x.type] = x.value; const date = `${o.year}-${o.month}-${o.day}`;
  const b = tj.briefs[date]; if (!b) return { sent: 0, date, reason: "no games today" };
  const W = tj.week; const key = `__brief__${date}`;
  const subs: Sub[] = (await rest("push_subs?select=endpoint,user_id,p256dh,auth,live,weekly")).filter((s: Sub) => s.weekly !== false);
  const sent: any[] = await rest(`push_sent?select=user_id&week=eq.${W}&player=eq.${key}`);
  const done = new Set(sent.map((x) => x.user_id));
  const msg = { title: `☀️ ${b.title}`.slice(0, 90), body: String(b.body || "").slice(0, 300), url: b.url || "/today/", tag: `bs-brief-${date}` };
  if (DISCORD && !(await keysDone(`dc|brief|${date}`)).size) { if (await discord(b.title, String(b.body || ""), b.url || "/today/")) await markKey(`dc|brief|${date}`); }
  let n = 0; const gone: string[] = [];
  for (const uid of [...new Set(subs.map((s) => s.user_id))]) {
    if (done.has(uid)) continue;
    for (const s of subs.filter((s) => s.user_id === uid)) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) n++; } catch (e) { console.warn("push", String(e)); } }
    await mark(uid, W, key, "SENT");
  }
  for (const ep of gone) await rest(`push_subs?endpoint=eq.${encodeURIComponent(ep)}`, { method: "DELETE" });
  return { week: W, date, sent: n, title: msg.title };
}


// =====================================================================================================================================
// 11/5 modes (owner: "do all of your out of the box things"). Each one is independent and does nothing without its data or secret.
// =====================================================================================================================================
const RESEND = Deno.env.get("RESEND_API_KEY") ?? "", EMAIL_FROM = Deno.env.get("EMAIL_FROM") ?? "BetSweep <brief@betsweep.co>";
const ANTHROPIC = Deno.env.get("ANTHROPIC_API_KEY") ?? "", ASK_MODEL = Deno.env.get("ASK_MODEL") ?? "claude-haiku-5-5";
function slipKeysOf(states: any[], uid: string): string[] {
  const keys: string[] = [];
  for (const r of states.filter((x) => x.user_id === uid)) { let v: any = null; try { v = JSON.parse(r.value?.v ?? "null"); } catch { v = null; }
    if (r.key.startsWith("bs_slips_w") && Array.isArray(v)) for (const sl of v) if (sl && Array.isArray(sl.keys)) keys.push(...sl.keys.map(String));
    if (r.key.startsWith("bs_slipk_w") && Array.isArray(v)) keys.push(...v.map(String)); }
  return keys;
}
async function pushAll(subs: Sub[], msg: Record<string, unknown>, gone: string[]): Promise<number> {
  let n = 0; for (const s of subs) { try { const c = await sendPush(s, msg); if (c === 404 || c === 410) gone.push(s.endpoint); else if (c < 300) n++; } catch (e) { console.warn("push", String(e)); } } return n;
}
async function dropGone(gone: string[]) { for (const ep of gone) await rest(`push_subs?endpoint=eq.${encodeURIComponent(ep)}`, { method: "DELETE" }); }
const CT_DATE = (t: number) => { const p = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Chicago", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(t)); const o: Record<string, string> = {}; for (const x of p) o[x.type] = x.value; return `${o.year}-${o.month}-${o.day}`; };

// ---- "Your Sunday" recap (11:35 PM CT on game nights): saved slips graded against the box score, the one leg away, your CLV ----
export async function recap(now = Date.now()) {
  const D = await builderData(); const W = D.week; const date = CT_DATE(now);
  const todays = (D.games || []).filter((g: any) => g.ko && CT_DATE(g.ko) === date);
  if (!todays.length) return { week: W, date, sent: 0, reason: "no games today" };
  const subs: Sub[] = (await rest("push_subs?select=endpoint,user_id,p256dh,auth,live,weekly")).filter((s: Sub) => s.weekly !== false);
  if (!subs.length) return { week: W, sent: 0 };
  const users = [...new Set(subs.map((s) => s.user_id))];
  const states: any[] = await rest(`user_state?select=user_id,key,value&key=eq.bs_slips_w${W}&user_id=in.(${users.join(",")})`);
  const sent: any[] = await rest(`push_sent?select=user_id&week=eq.${W}&player=eq.__recap__${date}`); const done = new Set(sent.map((x) => x.user_id));
  const B = await liveBox(D.games || []); const todaySet = new Set(todays.map((g: any) => g.gid));
  const LEG = new Map<string, any>(); for (const l of (D.legs || [])) { const k = `${l.pl}|${l.m}|${Math.floor(Number(l.ln || 1) + 0.5)}`; if (!LEG.has(k)) LEG.set(k, l); }
  let close: any = null; try { close = await (await fetch(`${SITE}/data/close-w${W}.json`, { headers: { "cache-control": "no-cache" } })).json(); } catch { close = null; }
  const imp = (o: number) => o > 0 ? 100 / (o + 100) : -o / (-o + 100);
  let n = 0; const gone: string[] = [];
  for (const uid of users) {
    if (done.has(uid)) continue;
    const row = states.find((x) => x.user_id === uid); let slips: any[] = []; try { slips = JSON.parse(row?.value?.v ?? "[]"); } catch { slips = []; }
    slips = (Array.isArray(slips) ? slips : []).filter((sl: any) => sl && Array.isArray(sl.keys) && sl.keys.some((k: string) => { const l = LEG.get(String(k)); return l && todaySet.has(l.g); }));
    if (!slips.length) continue;
    let cashed = 0, missed = 0, open = 0, beat = 0, clvN = 0, clvSum = 0; let oneAway = "";
    for (const sl of slips) {
      const res = sl.keys.map((k: string) => { const l = LEG.get(String(k)); return l ? gradeLeg(l, String(k), B) : "na"; });
      const misses = res.filter((r: string) => r === "miss").length, opens = res.filter((r: string) => r === "open").length;
      if (misses) { missed++; if (misses === 1 && !oneAway) { const i = res.indexOf("miss"); const l = LEG.get(String(sl.keys[i])); if (l) { const r = B.players.get(norm(l.pl)); const base = String(l.m).replace(/^Under /, "");
          const v = r ? (/TD$/.test(l.m) ? r.td : base === "Passing Yards" ? r.pass : base === "Rushing Yards" ? r.rush : base === "Receiving Yards" ? r.recy : base === "Receptions" ? r.rec : base === "Longest Reception" ? r.long : null) : null;
          oneAway = `${sl.name || "a slip"} was one leg away: ${l.pl} ${legLabel(l).replace(l.pl + " ", "")}${v != null ? ` (had ${v})` : ""}`; } } }
      else if (opens) open++; else if (res.every((r: string) => r === "hit" || r === "na")) cashed++;
      for (const k of sl.keys) { const mine = sl.px && sl.px[k] && sl.px[k].o != null ? +sl.px[k].o : (close?.build?.[k]?.o ?? null); const cl = close?.close?.[k]?.o ?? null;
        if (mine == null || cl == null) continue; const pts = (imp(+cl) - imp(+mine)) * 100; clvN++; clvSum += pts; if (pts > 0) beat++; }
    }
    const parts = [`${slips.length} slip${slips.length === 1 ? "" : "s"} today: ${cashed} cashed, ${missed} missed${open ? `, ${open} still open` : ""}.`];
    if (oneAway) parts.push(oneAway + ".");
    if (clvN) parts.push(`You beat the closing line on ${beat} of ${clvN} legs (${clvSum / clvN >= 0 ? "+" : ""}${(clvSum / clvN).toFixed(1)} pts avg).`);
    const msg = { title: cashed ? `🧾 Your ${new Date(now).toLocaleDateString("en-US", { weekday: "long", timeZone: "America/Chicago" })}: ${cashed} cashed` : `🧾 Your ${new Date(now).toLocaleDateString("en-US", { weekday: "long", timeZone: "America/Chicago" })}, graded`,
      body: parts.join(" ").slice(0, 300), url: "/me/", tag: `bs-recap-${date}` };
    n += await pushAll(subs.filter((s) => s.user_id === uid), msg, gone); await mark(uid, W, `__recap__${date}`, "SENT");
  }
  await dropGone(gone); return { week: W, date, sent: n };
}

// the Who-should-I-start data (build_startsit.py -> /team/compare/data.json): {week, players: [{n, t, p, o, fp, av, ...}]}
async function projections(): Promise<{ P: Map<string, any>; W: number }> {
  let proj: any = null; try { proj = await (await fetch(`${SITE}/team/compare/data.json`, { headers: { "cache-control": "no-cache" } })).json(); } catch { proj = null; }
  const P = new Map<string, any>(); for (const p of (proj?.players || [])) if (p && p.n) P.set(norm(p.n), { name: p.n, pos: p.p, team: p.t, opp: p.o, fp: p.fp, out: p.av === "OUT" });
  return { P, W: +(proj?.week || 0) };
}
// ---- Sleeper roster inactives (Sunday 11:35 AM / 2:35 / 6:35 PM CT, TNF / MNF 5:35 PM): the official ESPN inactive list from the feeds
// branch x the rosters the Fantasy page saved (fantasy_rosters). "X is out - the model's best bench play is Y" from /b/startsit.json.
export async function inactives(now = Date.now()) {
  const ina: any = await (await fetch(`${FEEDS}/inactives.json`, { headers: { "cache-control": "no-cache" } })).json().catch(() => null);
  const outs: { name: string; team: string }[] = []; for (const g of Object.values((ina?.games || {}) as Record<string, any>)) for (const o of (g.out || [])) if (o?.name) outs.push({ name: String(o.name), team: String(o.team || "") });
  if (!outs.length) return { sent: 0, reason: "no inactives in the window" };
  const OUT = new Map(outs.map((o) => [norm(o.name), o]));
  const rosters: any[] = await rest("fantasy_rosters?select=user_id,league_id,league,starters,bench");
  if (!rosters.length) return { sent: 0, outs: outs.length, reason: "no saved rosters" };
  const { P, W } = await projections(); const date = CT_DATE(now);
  const subs: Sub[] = await rest("push_subs?select=endpoint,user_id,p256dh,auth,live,weekly");
  const sent: any[] = await rest(`push_sent?select=user_id,player&week=eq.${W}&status=eq.INACTIVE`); const done = new Set(sent.map((x) => `${x.user_id}|${x.player}`));
  let n = 0; const gone: string[] = [];
  for (const r of rosters) {
    const us = subs.filter((s) => s.user_id === r.user_id); if (!us.length) continue;
    for (const st of (r.starters || [])) {
      const o = OUT.get(norm(st.name)); if (!o) continue; const key = `__ina__${r.league_id}|${norm(st.name)}`.slice(0, 300); if (done.has(`${r.user_id}|${key}`)) continue;
      const pos = String(st.pos || ""); const bench = (r.bench || []).filter((b: any) => b && b.pos === pos && !OUT.has(norm(b.name))).map((b: any) => ({ b, pr: P.get(norm(b.name)) })).filter((x: any) => x.pr && x.pr.fp != null).sort((a: any, b: any) => b.pr.fp - a.pr.fp)[0];
      const msg = { title: `${st.name} is INACTIVE${r.league ? ` (${r.league})` : ""}`.slice(0, 90),
        body: bench ? `Official inactives. Your best bench ${pos} by the model: ${bench.b.name} (${(+bench.pr.fp).toFixed(1)} pts${bench.pr.opp ? ` vs ${bench.pr.opp}` : ""}). Swap before kickoff.` : `Official inactives. No ${pos} on your bench with a projection - check the waiver wire.`,
        url: "/team/", tag: `bs-ina-${norm(st.name)}` };
      n += await pushAll(us, msg, gone); await mark(r.user_id, W, key, "INACTIVE"); done.add(`${r.user_id}|${key}`);
    }
  }
  await dropGone(gone); return { week: W, date, outs: outs.length, rosters: rosters.length, sent: n };
}

// ---- Saturday-night start/sit (7:05 PM CT): the model's lineup calls for each saved roster, one push per league ----
export async function startsit(now = Date.now()) {
  const { P, W } = await projections(); if (!P.size) return { sent: 0, reason: "no projections (team/compare/data.json)" };
  const rosters: any[] = await rest("fantasy_rosters?select=user_id,league_id,league,starters,bench");
  const subs: Sub[] = (await rest("push_subs?select=endpoint,user_id,p256dh,auth,live,weekly")).filter((s: Sub) => s.weekly !== false);
  const sent: any[] = await rest(`push_sent?select=user_id,player&week=eq.${W}&status=eq.STARTSIT`); const done = new Set(sent.map((x) => `${x.user_id}|${x.player}`));
  let n = 0; const gone: string[] = [];
  for (const r of rosters) {
    const us = subs.filter((s) => s.user_id === r.user_id); if (!us.length) continue; const key = `__ss__${r.league_id}`.slice(0, 300); if (done.has(`${r.user_id}|${key}`)) continue;
    const calls: string[] = [];
    for (const st of (r.starters || [])) { const sp = P.get(norm(st.name)); if (!sp || sp.fp == null || sp.out) { if (sp?.out) calls.push(`${st.name} is out`); continue; }
      const better = (r.bench || []).filter((b: any) => b && b.pos === st.pos).map((b: any) => P.get(norm(b.name))).filter((bp: any) => bp && bp.fp != null && !bp.out && bp.fp - sp.fp >= 2).sort((a: any, b: any) => b.fp - a.fp)[0];
      if (better) calls.push(`${better.name} over ${st.name} (+${(better.fp - sp.fp).toFixed(1)})`); }
    if (!calls.length) continue;
    const msg = { title: `Lineup check${r.league ? `: ${r.league}` : ""}`.slice(0, 90), body: `The model would start ${calls.slice(0, 3).join("; ")}${calls.length > 3 ? ` +${calls.length - 3} more` : ""}. Full lineup and the reasons on the Fantasy page.`.slice(0, 300), url: "/team/", tag: `bs-ss-${W}` };
    n += await pushAll(us, msg, gone); await mark(r.user_id, W, key, "STARTSIT");
  }
  await dropGone(gone); return { week: W, rosters: rosters.length, sent: n };
}

// ---- email digest (Thu + Sun 9:20 AM CT) through Resend: the morning brief, or on Thursdays the week's top looks ----
export async function email(now = Date.now()) {
  if (!RESEND) return { sent: 0, reason: "RESEND_API_KEY not set" };
  const prefs: any[] = await rest("email_prefs?select=user_id,email&digest=eq.true"); if (!prefs.length) return { sent: 0, reason: "no subscribers" };
  const tj: any = await (await fetch(`${SITE}/b/today.json`, { headers: { "cache-control": "no-cache" } })).json().catch(() => null);
  const date = CT_DATE(now); const W = tj?.week || 0; const b = tj?.briefs?.[date];
  let plus: any = null; try { plus = await (await fetch(`${SITE}/b/plus.json`)).json(); } catch { plus = null; }
  const looks = (plus?.legs || []).filter((l: any) => !l.ko || l.ko > now).sort((a: any, b: any) => (b.p - b.bk) - (a.p - a.bk)).slice(0, 5);
  const subject = b ? b.title : `Week ${W}: this week's looks`;
  const lines = [b ? b.body : `The boards are up for Week ${W}.`, "", ...looks.map((l: any) => `• ${l.pl} ${l.m === "Anytime TD" ? "anytime TD" : `${Math.round(l.ln)}+ ${String(l.m).toLowerCase()}`} (FD ${am(l.o)}, model ${Math.round(l.p * 100)}%)`),
    "", `Today: ${SITE}/today/`, `Boards: ${SITE}/boards/`, "", "Information and analysis only, not betting advice. 21+. 1-800-GAMBLER.", `Stop these emails: ${SITE}/me/`];
  const mk = `email|${date}|`; const dc = await keysDone(mk); let n = 0;
  for (const p of prefs) {
    if (dc.has(mk + p.user_id)) continue;
    const r = await fetch("https://api.resend.com/emails", { method: "POST", headers: { Authorization: `Bearer ${RESEND}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: EMAIL_FROM, to: [p.email], subject: `BetSweep · ${subject}`.slice(0, 120), text: lines.join("\n") }) });
    if (r.ok) { n++; await markKey(mk + p.user_id); } else console.warn("resend", r.status, (await r.text()).slice(0, 120));
  }
  return { week: W, date, sent: n, of: prefs.length };
}

// ---- Ask the model (signed-in users, 20 questions a day): the week's numbers as context, a short answer, nothing invented ----
export async function ask(token: string, q: string) {
  if (!ANTHROPIC) return { error: "Ask is not switched on yet." };
  const u = await fetch(`${SB}/auth/v1/user`, { headers: { apikey: SRK, Authorization: `Bearer ${token}` } }); if (!u.ok) return { error: "Sign in to ask the model." };
  const user = await u.json(); q = String(q || "").trim().slice(0, 400); if (q.length < 3) return { error: "Ask a question." };
  const today: any[] = await rest(`ask_log?select=id&user_id=eq.${user.id}&asked_at=gte.${encodeURIComponent(new Date(Date.now() - 864e5).toISOString())}`);
  if (today.length >= 20) return { error: "That's 20 questions today - back tomorrow." };
  const D = await builderData(); const W = D.week; const now = Date.now();
  const who = q.toLowerCase(); const legs = (D.legs || []).filter((l: any) => l.pl && who.includes(String(l.pl).toLowerCase().split(" ").pop() || "~~"));
  const named = [...new Set(legs.map((l: any) => l.pl))].slice(0, 4);
  let news: any = null; try { news = await (await fetch(`${SITE}/b/today.json`)).json(); } catch { news = null; }
  const ctx: string[] = [`Week ${W}. Today ${CT_DATE(now)} CT. BetSweep's model prices every FanDuel prop; "model" = our chance, "book" = the price's implied chance, edge = model minus book in points.`];
  for (const n of named) { const ls = (D.legs || []).filter((l: any) => l.pl === n && !l.gl).slice(0, 14);
    ctx.push(`${n} (${ls[0]?.pos || ""} ${ls[0]?.tm || ""} vs ${ls[0]?.opp || ""}, game ${ls[0]?.g || ""}): ` + ls.map((l: any) => `${l.m} ${l.ln}: FD ${am(l.o)}, model ${Math.round(l.p * 100)}%, book ${Math.round(l.bk * 100)}%${l.w ? `; flags: ${String(l.w).slice(0, 160)}` : ""}`).join(" | ")); }
  if (!named.length) { const top = (D.legs || []).filter((l: any) => !l.gl && l.e > 0.04).sort((a: any, b: any) => b.e - a.e).slice(0, 12);
    ctx.push("Top edges this week: " + top.map((l: any) => `${l.pl} ${l.m} ${l.ln} (FD ${am(l.o)}, model ${Math.round(l.p * 100)}%)`).join("; ")); }
  const sys = "You are BetSweep's model desk. Answer in 2-4 plain sentences from the context only; cite the model %, the FanDuel price and any flag; if the context has nothing on the player or game, say so and suggest where on the site to look (boards, builder, player page). Never invent numbers, never guarantee outcomes, keep the tone of a sharp friend. End with 'Not betting advice.' only when you recommend a side.";
  const r = await fetch("https://api.anthropic.com/v1/messages", { method: "POST", headers: { "x-api-key": ANTHROPIC, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({ model: ASK_MODEL, max_tokens: 350, system: sys, messages: [{ role: "user", content: `Context:\n${ctx.join("\n")}\n\nQuestion: ${q}` }] }) });
  if (!r.ok) { console.warn("anthropic", r.status, (await r.text()).slice(0, 200)); return { error: "The model desk is busy - try again in a minute." }; }
  const j = await r.json(); const a = (j.content || []).map((c: any) => c.text || "").join("").trim();
  await rest("ask_log", { method: "POST", body: JSON.stringify([{ user_id: user.id, q, a: a.slice(0, 2000), tokens: (j.usage?.input_tokens || 0) + (j.usage?.output_tokens || 0) }]) });
  return { a, left: 19 - today.length };
}

// ---- Beat the model: Tuesday grading (4:40 PM CT, after the receipt) from the site's graded legs; the model's five are frozen on Thursday by the first "beat" page load of the week (beat_model row) ----
export async function grade(now = Date.now()) {
  const D = await builderData(); const W = D.week - 1; if (W < 1) return { graded: 0 };
  let gj: any = null; try { gj = await (await fetch(`${SITE}/data/graded-w${W}.json`, { headers: { "cache-control": "no-cache" } })).json(); } catch { gj = null; }
  if (!gj || !gj.legs) return { week: W, graded: 0, reason: "no graded-w.json yet" };
  const G = new Map<string, string>(Object.entries(gj.legs as Record<string, string>));
  const picks: any[] = await rest(`beat_picks?select=user_id,keys&week=eq.${W}&graded_at=is.null`);
  let n = 0;
  for (const p of picks) { const hits = (p.keys || []).filter((k: string) => G.get(String(k)) === "hit").length;
    await rest(`beat_picks?user_id=eq.${p.user_id}&week=eq.${W}`, { method: "PATCH", body: JSON.stringify({ hits, graded_at: new Date(now).toISOString() }) }); n++; }
  const m: any[] = await rest(`beat_model?select=keys,hits&week=eq.${W}`);
  if (m.length && m[0].hits == null) { const hits = (m[0].keys || []).filter((k: string) => G.get(String(k)) === "hit").length; await rest(`beat_model?week=eq.${W}`, { method: "PATCH", body: JSON.stringify({ hits }) }); }
  return { week: W, graded: n };
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
    if (body && body.mode === "ask") {   // signed-in users: the Authorization header is their session token
      const tok = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
      return Response.json(await ask(tok, body.q), { headers: CORS });
    }
    if (!CRON || req.headers.get("x-cron-secret") !== CRON) return new Response("forbidden", { status: 403, headers: CORS });
    const mode = body && body.mode;
    const r = mode === "weekly" ? await weekly() : mode === "brief" ? await brief() : mode === "dk" ? await dkSalaries() : mode === "recap" ? await recap() : mode === "inactives" ? await inactives()
      : mode === "startsit" ? await startsit() : mode === "email" ? await email() : mode === "grade" ? await grade() : await run(); console.log(JSON.stringify(r));
    return Response.json(r, { headers: CORS });
  } catch (e) {
    console.error(String(e)); return Response.json({ error: String(e) }, { status: 500, headers: CORS });
  }
});
