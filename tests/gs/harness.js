// tests/gs/harness.js - runs FanDuelOdds.gs (any version) in Node against a fake sheet and a fake Odds API.
//   node tests/gs/harness.js   -> the checks for the current FanDuelOdds.gs (exit 1 on a failure)
// Why it exists (11/10): the sheet script cannot be run from a session, and the 11/5 version - edited on an older copy - silently dropped
// the unders pull, the 2+/3+ TD prices and the rule that keeps the DK / HR game lines. Nothing noticed for five days. RUN THIS BEFORE
// HANDING THE OWNER A NEW FanDuelOdds.gs: it compares a full refresh against the last two installed versions tab by tab
// (tests/gs/FanDuelOdds-<date>.gs.txt - add the file the owner is replacing when the script changes again).
// Fakes: SpreadsheetApp (sheets as sparse grids), UrlFetchApp (events + per-event odds, credit accounting the way The Odds API bills:
// one credit per market returned per region), PropertiesService, Utilities.formatDate, ScriptApp, Logger, and a clock.
const vm = require('vm'), fs = require('fs'), path = require('path');
const DIR = __dirname;

// ---------- fake spreadsheet ----------
function colNum(s) { let n = 0; for (const ch of s) n = n * 26 + (ch.charCodeAt(0) - 64); return n; }
function makeSheet(name) {
  const cells = [];   // cells[r][c], 1-based
  const get = (r, c) => (cells[r] && cells[r][c] !== undefined) ? cells[r][c] : '';
  const set = (r, c, v) => { (cells[r] = cells[r] || [])[c] = v; };
  let maxRows = 1000, maxCols = 26;
  const sh = {
    name, _cells: cells,
    getLastRow() { let last = 0; for (let r = cells.length - 1; r >= 1; r--) { if (cells[r] && cells[r].some(v => v !== '' && v !== undefined && v !== null)) { last = r; break; } } return last; },
    getMaxRows() { return maxRows; }, getMaxColumns() { return maxCols; },
    insertRowsAfter(_a, n) { maxRows += n; }, insertColumnsAfter(_a, n) { maxCols += n; },
    setFrozenRows() {}, clearContents() { cells.length = 0; },
    getRange(a, b, c, d) {
      let r0, c0, nr, nc;
      if (typeof a === 'string') { const m = a.match(/^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$/); if (!m) throw new Error('bad range ' + a);
        r0 = +m[2]; c0 = colNum(m[1]); nr = m[4] ? +m[4] - r0 + 1 : 1; nc = m[3] ? colNum(m[3]) - c0 + 1 : 1; }
      else { r0 = a; c0 = b; nr = c === undefined ? 1 : c; nc = d === undefined ? 1 : d; }
      if (nr < 1 || nc < 1) throw new Error('range with ' + nr + ' rows, ' + nc + ' columns on ' + name);
      if (r0 + nr - 1 > maxRows) throw new Error('range past the last row on ' + name + ': ' + (r0 + nr - 1) + ' > ' + maxRows);
      const rg = {
        getValues() { const out = []; for (let r = 0; r < nr; r++) { const row = []; for (let c2 = 0; c2 < nc; c2++) row.push(get(r0 + r, c0 + c2)); out.push(row); } return out; },
        setValues(v) { if (v.length !== nr || v.some(row => row.length !== nc)) throw new Error('setValues shape ' + v.length + 'x' + (v[0] || []).length + ' into ' + nr + 'x' + nc + ' on ' + name);
          for (let r = 0; r < nr; r++) for (let c2 = 0; c2 < nc; c2++) set(r0 + r, c0 + c2, v[r][c2]); return rg; },
        clearContent() { for (let r = 0; r < nr; r++) for (let c2 = 0; c2 < nc; c2++) if (cells[r0 + r]) cells[r0 + r][c0 + c2] = ''; return rg; },
        setNumberFormat() { return rg; }, setFontWeight() { return rg; },
      };
      return rg;
    },
    rows(ncols) { const last = sh.getLastRow(); return last > 1 ? sh.getRange(2, 1, last - 1, ncols).getValues().filter(r => r[0] !== '' && r[0] !== undefined) : []; },
  };
  return sh;
}

// ---------- fake Odds API ----------
const TEAMS = ['Washington Commanders', 'New York Giants', 'New England Patriots', 'Detroit Lions', 'Kansas City Chiefs', 'Atlanta Falcons', 'Buffalo Bills', 'New York Jets',
  'Carolina Panthers', 'New Orleans Saints', 'Houston Texans', 'Cleveland Browns', 'Minnesota Vikings', 'Green Bay Packers', 'Miami Dolphins', 'Indianapolis Colts',
  'Jacksonville Jaguars', 'Tennessee Titans', 'Los Angeles Rams', 'Arizona Cardinals', 'Seattle Seahawks', 'Las Vegas Raiders', 'San Francisco 49ers', 'Dallas Cowboys',
  'Pittsburgh Steelers', 'Cincinnati Bengals', 'Los Angeles Chargers', 'Baltimore Ravens'];
// kickoffs (UTC): Thu 11/12 7:15 PM CT, Sun 11/15 8:30 AM / noon x7 / 3:05 x2 / 3:25 / 7:20 PM CT, Mon 11/16 7:15 PM CT
const KO = ['2026-11-13T01:15:00Z', '2026-11-15T14:30:00Z', '2026-11-15T18:00:00Z', '2026-11-15T18:00:00Z', '2026-11-15T18:00:00Z', '2026-11-15T18:00:00Z', '2026-11-15T18:00:00Z',
  '2026-11-15T18:00:00Z', '2026-11-15T18:00:00Z', '2026-11-15T21:05:00Z', '2026-11-15T21:05:00Z', '2026-11-15T21:25:00Z', '2026-11-16T01:20:00Z', '2026-11-17T01:15:00Z'];
const EVENTS = KO.map((k, i) => ({id: 'ev' + i, commence_time: k, away_team: TEAMS[2 * i], home_team: TEAMS[2 * i + 1]}));
function hash(s) { let h = 2166136261; for (const ch of s) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0); }
function american(seed, lo, hi) { const span = hi - lo; let v = lo + (hash(seed) % span); if (v > -100 && v < 100) v = v < 0 ? -110 : 110; return v; }
function makeApi() {
  const api = {version: {}, fail: {}, noFanDuel: {}, remaining: 20000, paidCalls: 0, credits: 0, log: [], freeCalls: 0, fdExtra: false, badKeys: {}, last: 0, urls: []};
  // 11/19: through this feed FanDuel has never returned interceptions, completions or rush attempts (DraftKings and Hard Rock do). api.fdExtra = true
  // makes the fake FanDuel post them, plus kicking points and pass attempts, for the tests of the extra-markets request.
  const FD_ONLY_IF_EXTRA = {player_pass_interceptions: 1, player_pass_interceptions_alternate: 1, player_pass_completions: 1, player_pass_completions_alternate: 1, player_rush_attempts: 1, player_rush_attempts_alternate: 1, player_kicking_points: 1, player_pass_attempts: 1, team_totals: 1};
  const players = i => ['QB', 'RB', 'WR', 'TE'].map(p => `P${i} ${p}. Jr.`);
  function eventOdds(e, marketsAsked, books) {
    const i = +e.id.slice(2), v = api.version[e.id] || 0, P = players(i), out = [];
    for (const bk of books) {
      if (bk === 'fanduel' && api.noFanDuel[e.id]) continue;
      const markets = [];
      const add = (key, outcomes) => { if (bk === 'fanduel' && FD_ONLY_IF_EXTRA[key] && !api.fdExtra) return; if (marketsAsked.includes(key) && outcomes.length) markets.push({key, last_update: '2026-11-10T12:00:00Z', sid: `m.${e.id}.${key}`, outcomes}); };
      const link = (key, pl, pt, side) => bk === 'fanduel' ? `https://sportsbook.fanduel.com/addToBetslip?marketId=42.${hash(e.id + key + pl) % 900000000}&selectionId=${hash(e.id + key + pl + pt + side) % 90000000}` : `https://${bk}.example/${e.id}/${key}`;
      const oc = (key, pl, name, pt, lo, hi) => ({name, description: pl, point: pt, price: american([bk, e.id, key, pl, name, pt, v].join('|'), lo, hi), link: link(key, pl, pt, name), sid: 's' + (hash(bk + e.id + key + pl + name + pt) % 1e8)});
      // main lines: Over + Under
      const mains = [['player_pass_yds', P[0], 224.5], ['player_rush_yds', P[1], 58.5], ['player_reception_yds', P[2], 61.5], ['player_reception_yds', P[3], 33.5], ['player_receptions', P[2], 4.5], ['player_receptions', P[1], 2.5]];
      const byKey = {}; mains.forEach(([k, pl, pt]) => { (byKey[k] = byKey[k] || []).push(oc(k, pl, 'Over', pt, -130, -100), oc(k, pl, 'Under', pt, -130, -100)); });
      Object.keys(byKey).forEach(k => add(k, byKey[k]));
      add('player_reception_longest', [oc('player_reception_longest', P[2], 'Over', 20.5, -125, -105), oc('player_reception_longest', P[2], 'Under', 20.5, -125, -105)]);
      // alternates: Over ladders
      const ladders = [['player_pass_yds_alternate', P[0], [174.5, 199.5, 224.5, 249.5, 274.5]], ['player_rush_yds_alternate', P[1], [24.5, 39.5, 49.5, 59.5, 69.5, 79.5]],
        ['player_reception_yds_alternate', P[2], [24.5, 39.5, 49.5, 59.5, 69.5, 79.5, 99.5]], ['player_reception_yds_alternate', P[3], [14.5, 24.5, 39.5]],
        ['player_receptions_alternate', P[2], [2.5, 3.5, 4.5, 5.5, 6.5]], ['player_reception_longest_alternate', P[2], [14.5, 19.5, 24.5, 29.5]], ['player_rush_reception_yds_alternate', P[1], [49.5, 69.5, 89.5]],
        ['player_pass_completions_alternate', P[0], [17.5, 19.5, 21.5]]];
      const lk = {}; ladders.forEach(([k, pl, pts]) => pts.forEach((pt, j) => (lk[k] = lk[k] || []).push(oc(k, pl, 'Over', pt, -700 + j * 180, -500 + j * 180))));
      Object.keys(lk).forEach(k => add(k, lk[k]));
      add('player_rush_reception_yds', [oc('player_rush_reception_yds', P[1], 'Over', 79.5, -120, -100), oc('player_rush_reception_yds', P[1], 'Under', 79.5, -120, -100)]);
      add('player_anytime_td', P.slice(1).flatMap(pl => [oc('player_anytime_td', pl, 'Yes', undefined, 110, 420), oc('player_anytime_td', pl, 'No', undefined, -500, -150)]));
      add('player_1st_td', P.slice(1).map(pl => oc('player_1st_td', pl, 'Yes', undefined, 500, 1800)));
      add('player_pass_tds', [oc('player_pass_tds', P[0], 'Over', 1.5, -140, 140), oc('player_pass_tds', P[0], 'Under', 1.5, -140, 140)]);
      add('player_pass_tds_alternate', [0.5, 1.5, 2.5, 3.5].map((pt, j) => oc('player_pass_tds_alternate', P[0], 'Over', pt, -500 + j * 300, -300 + j * 300)));
      add('player_pass_interceptions_alternate', [oc('player_pass_interceptions_alternate', P[0], 'Over', 1.5, 300, 500)]);
      add('player_rush_attempts_alternate', [11.5, 17.5].map((pt, j) => oc('player_rush_attempts_alternate', P[1], 'Over', pt, -400 + j * 500, -200 + j * 500)));
      add('player_kicking_points', [oc('player_kicking_points', `P${i} K`, 'Over', 7.5, -125, -105), oc('player_kicking_points', `P${i} K`, 'Under', 7.5, -125, -105)]);
      add('player_pass_attempts', [oc('player_pass_attempts', P[0], 'Over', 33.5, -125, -105), oc('player_pass_attempts', P[0], 'Under', 33.5, -125, -105)]);
      add('team_totals', [{name: 'Over', description: e.home_team, point: 23.5, price: -110}, {name: 'Under', description: e.home_team, point: 23.5, price: -110}]);
      add('player_pass_interceptions', [oc('player_pass_interceptions', P[0], 'Over', 0.5, -140, 140), oc('player_pass_interceptions', P[0], 'Under', 0.5, -140, 140)]);
      add('player_pass_completions', [oc('player_pass_completions', P[0], 'Over', 20.5, -125, -105), oc('player_pass_completions', P[0], 'Under', 20.5, -125, -105)]);
      add('player_rush_attempts', [oc('player_rush_attempts', P[1], 'Over', 14.5, -125, -105), oc('player_rush_attempts', P[1], 'Under', 14.5, -125, -105)]);
      if (bk === 'fanduel') add('player_tds_over', [oc('player_tds_over', P[1], 'Over', 0.5, 110, 200), oc('player_tds_over', P[1], 'Over', 1.5, 500, 900), oc('player_tds_over', P[2], 'Over', 1.5, 700, 1200), oc('player_tds_over', P[1], 'Over', 2.5, 2000, 3500)]);
      // game lines for the DK/HR job
      add('h2h', [{name: e.home_team, price: -150}, {name: e.away_team, price: 130}]); add('spreads', [{name: e.home_team, point: -2.5, price: -110}, {name: e.away_team, point: 2.5, price: -110}]);
      add('totals', [{name: 'Over', point: 44.5, price: -110}, {name: 'Under', point: 44.5, price: -110}]);
      add('alternate_spreads', [{name: e.home_team, point: -3.5, price: 120}, {name: e.away_team, point: 3.5, price: -140}]); add('alternate_totals', [{name: 'Over', point: 47.5, price: 130}, {name: 'Under', point: 47.5, price: -150}]);
      if (markets.length) out.push({key: bk, title: bk, markets});
    }
    return out;
  }
  const res = (code, body) => ({getResponseCode: () => code, getContentText: () => typeof body === 'string' ? body : JSON.stringify(body), getHeaders: () => ({'x-requests-remaining': String(api.remaining), 'x-requests-last': String(api.last)})});
  api.fetch = function (url) {
    const u = new URL(url), q = u.searchParams, p = u.pathname; api.urls.push(url); api.last = 0;
    if (url.length > 2000) throw new Error('URL too long for UrlFetchApp: ' + url.length);
    if (/\/events$/.test(p)) { api.freeCalls++; return res(200, EVENTS); }
    const m = p.match(/\/events\/([^/]+)\/odds$/);
    const books = (q.get('bookmakers') || 'fanduel').split(','), markets = (q.get('markets') || '').split(',').filter(Boolean);
    if (m) {
      const e = EVENTS.find(x => x.id === m[1]); if (!e) return res(404, {message: 'no event'});
      if (api.fail[e.id]) { api.log.push({ev: e.id, fail: 1}); return res(500, 'upstream'); }
      if (markets.some(k => api.badKeys[k])) { api.log.push({ev: e.id, rejected: markets.length}); return res(422, {message: 'Invalid markets'}); }   // one bad key rejects the whole request, free of charge
      const bms = eventOdds(e, markets, books); const got = new Set(); bms.forEach(b => b.markets.forEach(mk => got.add(mk.key)));
      api.paidCalls++; api.credits += got.size; api.remaining -= got.size; api.last = got.size; api.log.push({ev: e.id, markets: got.size, books: books.join(','), asked: markets.length});
      return res(200, Object.assign({}, e, {bookmakers: bms}));
    }
    if (/\/odds$/.test(p)) {   // main game lines, all events
      const body = EVENTS.map(e => Object.assign({}, e, {bookmakers: eventOdds(e, markets, books)}));
      api.paidCalls++; api.credits += markets.length; api.remaining -= markets.length; api.log.push({all: 1, markets: markets.length});
      return res(200, body);
    }
    return res(404, {message: 'unknown ' + p});
  };
  return api;
}

// ---------- a run of one script version ----------
function fmt(date, tz, f) {
  const parts = {}; new Intl.DateTimeFormat('en-US', {timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', weekday: 'short'}).formatToParts(date).forEach(p => parts[p.type] = p.value);
  const dow = {Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7}[parts.weekday];
  if (f === 'u') return String(dow); if (f === 'H') return String(+parts.hour);
  if (f === 'yyyy-MM-dd HH:mm') return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
  if (f === 'EEE MM/dd HH:mm') return `${parts.weekday} ${parts.month}/${parts.day} ${parts.hour}:${parts.minute}`;
  throw new Error('format not faked: ' + f);
}
function world(file, opts) {
  opts = opts || {};
  const sheets = {}, propsStore = Object.assign({ODDS_API_KEY: 'k'}, opts.props || {}), api = opts.api || makeApi(), w = {sheets, api, props: propsStore, now: new Date('2026-11-12T12:10:00Z'), toasts: [], logs: []};
  ['AUTO - FanDuel Odds', 'V2 - Leg Board'].forEach(n => sheets[n] = makeSheet(n));
  const ss = {getSheetByName: n => sheets[n] || null, insertSheet: n => (sheets[n] = makeSheet(n)), toast: t => w.toasts.push(t)};
  const RealDate = Date;
  class FakeDate extends RealDate { constructor(...a) { if (a.length === 0) super(w.now.getTime()); else super(...a); } static now() { return w.now.getTime(); } }
  const ctx = vm.createContext({
    SpreadsheetApp: {getActiveSpreadsheet: () => ss, getActive: () => ss, getUi: () => ({createMenu: () => { const m = {addItem: () => m, addSeparator: () => m, addToUi: () => {}}; return m; }})},
    UrlFetchApp: {fetch: (u, o) => api.fetch(u, o)},
    PropertiesService: {getScriptProperties: () => ({getProperty: k => (k in propsStore ? propsStore[k] : null), setProperty: (k, v) => { propsStore[k] = String(v); }, getProperties: () => Object.assign({}, propsStore)})},
    Utilities: {formatDate: fmt}, ScriptApp: {getProjectTriggers: () => [], newTrigger: () => ({timeBased: () => ({everyHours: () => ({create: () => {}})})}), deleteTrigger: () => {}},
    Logger: {log: t => w.logs.push(String(t))}, Date: FakeDate, console, URL,
  });
  vm.runInContext(fs.readFileSync(file, 'utf8'), ctx, {filename: path.basename(file)});
  w.run = (expr, at) => { if (at) w.now = new Date(at); return vm.runInContext(expr, ctx); };
  w.tab = (n, ncols) => sheets[n] ? sheets[n].rows(ncols) : [];
  w.cell = (n, a1) => sheets[n] ? sheets[n].getRange(a1).getValues()[0][0] : '';
  return w;
}
module.exports = {world, makeApi, EVENTS, DIR};

// ---------- checks ----------
if (require.main === module) {
  let fails = 0; const ok = (c, name, extra) => { console.log((c ? 'ok  ' : 'FAIL') + ' ' + name + (extra ? '  ' + extra : '')); if (!c) fails++; };
  const NEW = path.join(DIR, '..', '..', 'FanDuelOdds.gs'), OLD = path.join(DIR, 'FanDuelOdds-2026-11-10.gs.txt');   // OLD = the file the owner is replacing
  // the 11/5 file was edited on a stale copy because the repo held two copies that had drifted apart; they must stay one text
  ok(fs.readFileSync(NEW, 'utf8') === fs.readFileSync(NEW + '.txt', 'utf8'), 'FanDuelOdds.gs and FanDuelOdds.gs.txt are the same file');
  const key = r => String(r[0]); const j = rows => JSON.stringify(rows);
  const T0 = '2026-11-12T12:10:00Z';   // Thursday 6:10 AM CT
  const DEAD = ['Interceptions', 'Completions', 'Rush Attempts'];   // asked of all three books since 11/5; FanDuel has never returned them
  const LINKS = 'AUTO - FanDuel Links', BOOKS = 'AUTO - Book Odds', COV = 'AUTO - Market Coverage';
  // 1. a full refresh against the 11/10 file, with FanDuel answering as it really does
  const a = world(OLD), b = world(NEW);
  a.run('refreshFanDuelOdds()', T0); b.run('refreshFanDuelOdds()', T0);
  ok(j(a.tab('AUTO - FanDuel Odds', 9)) === j(b.tab('AUTO - FanDuel Odds', 9)) && a.tab('AUTO - FanDuel Odds', 9).length > 300, 'full refresh: the Leg Board odds tab is identical to the 11/10 file\'s', a.tab('AUTO - FanDuel Odds', 9).length + ' rows');
  const la = a.tab(LINKS, 10), lb = b.tab(LINKS, 10), extra = lb.filter(r => !la.some(x => key(x) === key(r)));
  ok(la.every(r => lb.some(x => j(x) === j(r))) && extra.length === 14 * 3 && extra.every(r => r[2] === 'Passing TDs' && [1, 3, 4].includes(r[3]) && /marketId=/.test(r[4]) && r[5] && r[6]),
    'links tab: every 11/10 row unchanged, plus three more passing-TD rungs a quarterback (1+, 3+, 4+ beside the main 2+), each with its betslip ids', la.length + ' -> ' + lb.length);
  ok(!la.some(r => DEAD.includes(r[2])) && !lb.some(r => DEAD.includes(r[2])), '  FanDuel posts no interceptions / completions / rush attempts through the feed: neither file has a links row for them');
  ok(j(a.tab('AUTO - First TD Odds', 10)) === j(b.tab('AUTO - First TD Odds', 10)) && j(a.tab('AUTO - FanDuel Unders', 12)) === j(b.tab('AUTO - FanDuel Unders', 12)) && b.tab('AUTO - FanDuel Unders', 12).length === 14 * 6, 'first TD tab and unders tab identical');
  const ba = a.tab(BOOKS, 12), bb = b.tab(BOOKS, 12), gone = ba.filter(r => !bb.some(x => j(x) === j(r))), came = bb.filter(r => !ba.some(x => j(x) === j(r)));
  ok(gone.length > 0 && gone.every(r => DEAD.includes(r[3])) && came.length === 14 * 2 * 3 && came.every(r => r[3] === 'Passing TDs') && bb.length > 500,
    'DraftKings / Hard Rock rows: only the three markets no FanDuel leg could use are gone; the passing-TD rungs are added; the rest identical', ba.length + ' -> ' + bb.length + ' (' + gone.length + ' gone, ' + came.length + ' new)');
  ok(lb.some(r => r[2] === 'Passing TDs') && !b.tab('AUTO - FanDuel Odds', 9).some(r => r[2] === 'Passing TDs' || DEAD.includes(r[2])), '  passing TDs stay off the Leg Board');
  // the safety net: a feed that rejects the new key must not cost the whole pull
  const sn = world(NEW, {props: {BS_MARKET_CHECK: '2026-11-19b done'}}); sn.api.badKeys.player_pass_tds_alternate = true; sn.run('refreshFanDuelOdds()', T0);
  ok(j(sn.tab(LINKS, 10)) === j(la) && j(sn.tab('AUTO - FanDuel Odds', 9)) === j(a.tab('AUTO - FanDuel Odds', 9)) && /the feed rejected a market key/.test(sn.cell('AUTO - FanDuel Odds', 'L5')),
    'safety net: if the feed rejected the alternate passing-TD key, the pull goes on without it - every tab as the 11/10 file wrote it - and the notes say so');
  // game-line rows survive an odds refresh (the 10/22 rule the 11/5 file lost)
  b.run('refreshBookGameLines()', T0); const glb = b.tab(BOOKS, 12).filter(r => String(r[1]).startsWith('gl|')).length;
  b.run('refreshFanDuelOdds()', T0); const glb2 = b.tab(BOOKS, 12).filter(r => String(r[1]).startsWith('gl|')).length;
  ok(glb > 0 && glb2 === glb, 'an odds refresh keeps the DK / HR game-line rows', glb + ' -> ' + glb2);
  // 2. credits: three fewer a game than the file it replaces
  const wo = world(OLD); wo.run('refreshFanDuelOdds()', T0);
  const w = world(NEW); w.run('refreshFanDuelOdds()', T0);
  const full = w.api.credits, perGame = full / 14, oldFull = wo.api.credits;
  ok(oldFull - full === 14 * 3 && Math.abs(+w.props.BS_CREDITS_LEFT - (20000 - full)) <= 1, 'a full refresh on a fully posted slate costs 3 credits a game less than the 11/10 file', `${oldFull} -> ${full} credits (${perGame.toFixed(1)} a game); credits left recorded: ${w.props.BS_CREDITS_LEFT}`);
  ok(w.api.urls.every(u => u.length < 1900), '  every request URL fits UrlFetchApp', 'longest ' + Math.max(...w.api.urls.map(u => u.length)));
  // 3. today's games: Thursday 2:05 PM - one game refreshed, thirteen carried
  const snap = n => { const m = {}; w.tab(n[0], n[1]).forEach(r => m[(n[2] ? r[0] + '|' : '') + key(n[2] ? [r[1]] : r)] = j(r)); return m; };
  const TABS = [['AUTO - FanDuel Odds', 9, 0, 5], [LINKS, 10, 0, 8], ['AUTO - First TD Odds', 10, 0, 6], [BOOKS, 12, 1, 10], ['AUTO - FanDuel Unders', 12, 0, 6]];
  w.run('refreshBookGameLines()', T0); const before = TABS.map(snap), c0 = w.api.credits;
  EVENTS.forEach(e => w.api.version[e.id] = 1);   // every price moves at the book
  const thu = EVENTS[0].away_team + ' @ ' + EVENTS[0].home_team;
  w.props.BS_MARKET_CHECK = '2026-11-19b done';   // the one-time market check has its own test below
  w.run('gameDayRefresh()', '2026-11-12T20:05:00Z');
  const after = TABS.map(snap), cost = w.api.credits - c0;
  ok(cost > 0 && cost <= 18, "Thursday 2 PM: the hourly trigger refreshes tonight's game only", `${cost} credits (a full refresh: ${full})`);
  let allGood = true, detail = [];
  TABS.forEach((t, i) => { const rowsNow = w.tab(t[0], t[1]); const gi = t[3];
    const thuRows = rowsNow.filter(r => r[gi] === thu && !String(r[1]).startsWith('gl|')), rest = rowsNow.filter(r => r[gi] !== thu);
    const stampIdx = t[1] - 1, fresh = thuRows.every(r => r[stampIdx] === '2026-11-12 14:05'), kept = rest.every(r => before[i][(t[2] ? r[0] + '|' : '') + (t[2] ? r[1] : r[0])] === j(r));
    const same = Object.keys(before[i]).length === Object.keys(after[i]).length, moved = thuRows.filter(r => before[i][(t[2] ? r[0] + '|' : '') + (t[2] ? r[1] : r[0])] !== j(r)).length;
    const dup = rowsNow.length !== new Set(rowsNow.map(r => (t[2] ? r[0] + '|' : '') + (t[2] ? r[1] : r[0]))).size;
    if (!(thuRows.length && fresh && kept && same && moved > 0 && !dup)) allGood = false;
    detail.push(`${t[0].replace('AUTO - ', '')}: ${thuRows.length} fresh / ${rest.length} kept${dup ? ' DUP' : ''}${same ? '' : ' COUNT'}${kept ? '' : ' CHANGED'}${fresh ? '' : ' STAMP'}`); });
  ok(allGood, "  in all five tabs: tonight's rows re-priced and re-stamped, every other row byte-for-byte as it was, no row lost or doubled", detail.join(' | '));
  ok(/today's games only \(1 of 14\)/.test(w.cell('AUTO - FanDuel Odds', 'L1')) && /1 of 14 refreshed/.test(w.cell('AUTO - FanDuel Odds', 'L7')), '  the status block says so', w.cell('AUTO - FanDuel Odds', 'L1') + ' // ' + w.cell('AUTO - FanDuel Odds', 'L7'));
  // 4. when it does nothing, it costs nothing
  const quiet = (at, label, re) => { const c1 = w.api.credits, s1 = j(TABS.map(snap)); w.run('gameDayRefresh()', at); ok(w.api.credits === c1 && j(TABS.map(snap)) === s1 && re.test(w.cell('AUTO - FanDuel Odds', 'L7')), label, w.cell('AUTO - FanDuel Odds', 'L7')); };
  quiet('2026-11-11T20:05:00Z', 'Wednesday 2 PM: no game within 9 hours - no pull, no credits, nothing written', /no game kicks off/);
  quiet('2026-11-15T15:05:00Z', 'Sunday 9 AM: twelve games within 9 hours - left to the fixed windows', /games kick off in the next 9 hours/);
  const c5 = w.api.credits; w.run('gameDayRefresh()', '2026-11-15T23:05:00Z');
  ok(w.api.credits - c5 > 0 && w.api.credits - c5 <= 18 && /1 of 2 refreshed/.test(w.cell('AUTO - FanDuel Odds', 'L7')), "Sunday 5 PM: the night game alone", (w.api.credits - c5) + ' credits; ' + w.cell('AUTO - FanDuel Odds', 'L7'));
  const c6 = w.api.credits; w.run('gameDayRefresh()', '2026-11-12T14:05:00Z'); const c7 = w.api.credits; w.run('gameDayRefresh()', '2026-11-13T03:05:00Z');
  ok(c7 === c6 && w.api.credits === c7, 'Thursday 8 AM and 9 PM: outside 9 AM-7 PM, nothing runs');
  // 5. fixed windows still run a full refresh
  const c8 = w.api.credits; w.run('gameDayRefresh()', '2026-11-13T00:05:00Z');   // Thursday 6:05 PM CT
  ok(w.api.credits - c8 > 200 && !/today's games only/.test(w.cell('AUTO - FanDuel Odds', 'L1')), 'Thursday 6 PM: the fixed window is a full refresh', (w.api.credits - c8) + ' credits');
  // 6. the credit guard
  const g = world(NEW, {props: {BS_MARKET_CHECK: '2026-11-19b done'}}); g.run('refreshFanDuelOdds()', T0); const gs = j(TABS.map(t => g.tab(t[0], t[1])));
  g.props.BS_CREDITS_LEFT = '9000'; const gc = g.api.credits; g.run('gameDayRefresh()', '2026-11-12T20:05:00Z');   // 18.2 days to Dec 1 need ~10,900
  ok(g.api.credits === gc && /held back/.test(g.cell('AUTO - FanDuel Odds', 'L7')) && j(TABS.map(t => g.tab(t[0], t[1]))) === gs, 'credit guard: 9,000 left with 18 days to go - the extra pull is held back', g.cell('AUTO - FanDuel Odds', 'L7'));
  const gc2 = g.api.credits; g.run('gameDayRefresh()', '2026-11-13T00:05:00Z');
  ok(g.api.credits - gc2 > 200, '  the fixed 6 PM window still runs');
  g.props.BS_CREDITS_LEFT = '9000'; const gc3 = g.api.credits; g.run('refreshTodaysGamesNow()', '2026-11-12T20:05:00Z');
  ok(g.api.credits - gc3 > 0 && g.api.credits - gc3 <= 18, "  the menu item ignores the guard (someone asked for it)");
  g.props.BS_CREDITS_LEFT = '90000'; const gc4 = g.api.credits; g.run('gameDayRefresh()', '2026-11-12T21:05:00Z');
  ok(g.api.credits - gc4 > 0, '  with credits to spare the extra pull runs');
  delete g.props.BS_CREDITS_LEFT; const gc5 = g.api.credits; g.run('gameDayRefresh()', '2026-11-12T22:05:00Z');
  ok(g.api.credits - gc5 > 0, '  an unknown balance (first run after the paste) does not block it');
  // 7. a failed game keeps its rows
  const f = world(NEW, {props: {BS_MARKET_CHECK: '2026-11-19b done'}}); f.run('refreshFanDuelOdds()', T0); const fb = j(TABS.map(t => f.tab(t[0], t[1]))); f.api.fail.ev0 = true; EVENTS.forEach(e => f.api.version[e.id] = 2);
  f.run('gameDayRefresh()', '2026-11-12T20:05:00Z');
  ok(j(TABS.map(t => f.tab(t[0], t[1]))) === fb, "tonight's game fails at the API: its rows stay as they were instead of vanishing");
  // 8. after kickoff a started game drops out, as in a full refresh
  const k = world(NEW); k.run('refreshFanDuelOdds()', T0); k.run('gameDayRefresh()', '2026-11-15T23:05:00Z');
  const goneK = TABS.every(t => !k.tab(t[0], t[1]).some(r => r[t[3]] === thu)), have = TABS.every(t => k.tab(t[0], t[1]).some(r => r[t[3]] === EVENTS[13].away_team + ' @ ' + EVENTS[13].home_team));
  ok(goneK && have, 'Sunday night: games that already kicked off are gone from every tab, Monday night\'s is still there');
  // 9. a week of the hourly trigger: what the schedule costs, old file against new
  const week = file => { const wk = world(file, {props: {BS_MARKET_CHECK: '2026-11-19b done'}}); let fullN = 0, extraN = 0, extraC = 0, fullC = 0;
    for (let t = Date.parse('2026-11-10T06:05:00Z'); t < Date.parse('2026-11-17T06:05:00Z'); t += 3600e3) { const c1 = wk.api.credits; wk.run('gameDayRefresh()', new Date(t).toISOString()); const d = wk.api.credits - c1; if (!d) continue;
      if (/today's games only/.test(wk.cell('AUTO - FanDuel Odds', 'L1')) && d <= 4 * 21) { extraN++; extraC += d; } else { fullN++; fullC += d; } }
    return {fullN, extraN, extraC, fullC, total: fullC + extraC, api: wk.api}; };
  const wkO = week(OLD), wkN = week(NEW);
  ok(wkN.fullN === 14 && wkN.extraN >= 18 && wkN.total < wkO.total - 300, 'one week of hourly ticks costs less than under the 11/10 file',
    `${wkN.fullN} full refreshes (${wkN.fullC} credits) + ${wkN.extraN} today's-games pulls (${wkN.extraC}) = ${wkN.total}; the 11/10 file: ${wkO.total}`);
  ok(wkN.api.log.filter(x => x.books === 'fanduel' && x.asked === 6).every(x => x.markets === 0), '  the extra-markets request went out for games near kickoff and, FanDuel posting none of them, cost nothing',
    wkN.api.log.filter(x => x.books === 'fanduel' && x.asked === 6).length + ' requests, 0 credits');

  // ---------- 11/19: the extra markets (FanDuel only) ----------
  const EX = ['Interceptions', 'Completions', 'Rush Attempts'], exRows = wd => wd.tab(LINKS, 10).filter(r => EX.includes(r[2]));
  const x = world(NEW, {props: {BS_MARKET_CHECK: '2026-11-19b done'}}); x.api.fdExtra = true;   // suppose FanDuel starts posting them
  x.run('refreshFanDuelOdds()', T0);   // Thursday 6:10 AM: tonight's game is 13 hours out, Sunday's are three days out
  const x0 = exRows(x), costFull = x.api.credits;
  ok(x0.length > 0 && x0.every(r => r[8] === thu) && EX.every(m => x0.some(r => r[2] === m)) && x0.some(r => r[2] === 'Interceptions' && r[3] === 2) && x0.every(r => /marketId=/.test(r[4])),
    'extra markets: asked only for the game inside 40 hours, FanDuel\'s rungs land in the links tab with their betslip ids', x0.length + ' rows, all ' + thu);
  ok(costFull === full + 6 && /extra FanDuel markets \(6 asked\): 1 games, \d+ rows, 6 credits/.test(x.cell('AUTO - FanDuel Odds', 'L5')), '  it cost the six markets FanDuel returned, for that one game, and the notes say so', (costFull - full) + ' credits; ' + (String(x.cell('AUTO - FanDuel Odds', 'L5')).match(/extra FanDuel markets[^|]*/) || [''])[0]);
  ok(!x.tab('AUTO - FanDuel Odds', 9).some(r => EX.includes(r[2])) && !x.tab(BOOKS, 12).some(r => EX.includes(r[3])), '  none of it reaches the Leg Board or the other-books tab');
  EVENTS.forEach(e => x.api.version[e.id] = 1);
  const x1c = x.api.credits; x.run('gameDayRefresh()', '2026-11-12T17:05:00Z');   // Thursday 11:05 AM: today's-games pull, extras 4.9 hours old
  const x1 = exRows(x), x1cost = x.api.credits - x1c;
  ok(j(x1) === j(x0) && x1cost === 17 && x1.every(r => r[9] === '2026-11-12 06:10') && x.tab(LINKS, 10).some(r => r[8] === thu && r[9] === '2026-11-12 11:05'),
    '  five hours later the game is refreshed but its extra rows are not asked for again: same rows, same 6:10 stamp, beside freshly stamped main rows', x1cost + ' credits');
  const x2c = x.api.credits; x.run('gameDayRefresh()', '2026-11-12T18:05:00Z');   // noon: 6 hours old on game day -> asked again
  const x2 = exRows(x);
  ok(x2.length === x0.length && x2.every(r => r[9] === '2026-11-12 12:05') && j(x2.map(r => r[7])) !== j(x0.map(r => r[7])) && x.api.credits - x2c > 17, '  six hours later they are asked for again: re-priced and re-stamped', (x.api.credits - x2c) + ' credits');
  const x3c = x.api.credits; x.run('gameDayRefresh()', '2026-11-13T00:05:00Z');   // Thursday 6:05 PM: the full refresh, extras 6 hours old -> asked again for tonight only
  ok(exRows(x).every(r => r[8] === thu && r[9] === '2026-11-12 18:05') && x.api.credits - x3c === full + 6, '  the 6 PM full refresh re-asks them for tonight\'s game only');
  const xm = x.api.credits; EVENTS.forEach(e => x.api.version[e.id] = 2); x.run('refreshFanDuelOddsNow()', '2026-11-13T00:20:00Z');   // 6:20 PM, a person taps Refresh now: 15 minutes old, asked anyway
  ok(exRows(x).every(r => r[9] === '2026-11-12 18:20') && x.api.credits - xm === full + 6, "  'Refresh now' from the menu fetches them whatever their age");
  x.api.remaining = 9000; x.props.BS_CREDITS_LEFT = '9000'; EVENTS.forEach(e => x.api.version[e.id] = 3);   // 17 days to the reset need about 10,100
  const xhc = x.api.credits; x.run('refreshFanDuelOdds()', '2026-11-14T12:10:00Z');   // Saturday 6:10 AM, credits short: Sunday's games are inside 40 hours
  ok(exRows(x).length === 0 && x.api.credits - xhc === 13 * 17 && /12 held back for credits/.test(x.cell('AUTO - FanDuel Odds', 'L5')), '  credits short: the extra request is held back, the main refresh still runs', (x.api.credits - xhc) + ' credits; ' + (String(x.cell('AUTO - FanDuel Odds', 'L5')).match(/extra FanDuel markets[^|]*/) || [''])[0]);
  x.api.remaining = 90000; x.props.BS_CREDITS_LEFT = '90000'; const xsc = x.api.credits; x.run('refreshFanDuelOdds()', '2026-11-14T13:10:00Z');
  const sat = exRows(x), satGames = new Set(sat.map(r => r[8]));
  ok(satGames.size === 12 && !satGames.has(EVENTS[13].away_team + ' @ ' + EVENTS[13].home_team) && x.api.credits - xsc === 13 * 17 + 12 * 6, '  Saturday morning with credits: Sunday\'s twelve games get them, Monday night\'s (60 hours out) does not', satGames.size + ' games, ' + (x.api.credits - xsc) + ' credits');
  x.run('gameDayRefresh()', '2026-11-15T16:05:00Z');   // Sunday 10:05 AM full refresh: extras 21 hours old -> asked again
  ok(exRows(x).filter(r => r[9] === '2026-11-15 10:05').length > 0 && exRows(x).every(r => r[9] === '2026-11-15 10:05' || r[8] === EVENTS[13].away_team + ' @ ' + EVENTS[13].home_team), '  Sunday 10 AM: refreshed before kickoff (and Monday night\'s game, now inside 40 hours, joins)');
  x.run('gameDayRefresh()', '2026-11-15T19:05:00Z');   // Sunday 1:05 PM: early games have kicked off
  ok(exRows(x).every(r => new Date(EVENTS.find(e => e.away_team + ' @ ' + e.home_team === r[8]).commence_time) > new Date('2026-11-15T19:05:00Z')), '  after kickoff a game\'s extra rows are gone with the rest of its rows');
  x.api.fail.ev13 = false; const xf = world(NEW, {props: {BS_MARKET_CHECK: '2026-11-19b done'}}); xf.api.fdExtra = true; xf.run('refreshFanDuelOdds()', T0); const xf0 = j(exRows(xf));
  xf.api.badKeys.player_rush_attempts = true; EVENTS.forEach(e => xf.api.version[e.id] = 5); xf.run('gameDayRefresh()', '2026-11-13T00:05:00Z');
  ok(j(exRows(xf)) === xf0 && /requests failed \(rows kept\)/.test(xf.cell('AUTO - FanDuel Odds', 'L5')), '  a rejected extra request keeps the rows it had and says so');

  // ---------- 11/19: the coverage tab and the one-time market check ----------
  const cvr = wd => wd.tab(COV, 9), row = (wd, k2) => cvr(wd).find(r => r[0] === k2);
  const c = world(NEW); c.api.fdExtra = true; c.run('refreshFanDuelOdds()', T0);   // 13 hours to kickoff: the tab is made, the check waits
  ok(cvr(c).length > 50 && row(c, 'player_pass_interceptions')[2] === 'Y' && row(c, 'player_kicking_points')[2] === '' && row(c, 'team_totals')[2] === 'game lines' && row(c, 'player_kicking_points')[4] === '' && !c.props.BS_MARKET_CHECK,
    'coverage tab: made on the first refresh, the six built-in markets switched on, the check not run yet (kickoff 13 hours away)', cvr(c).length + ' market keys');
  const isCheck = u => /\/events\/[^/]+\/odds/.test(u) && !/includeLinks/.test(u), nChecks = () => c.api.urls.filter(isCheck).length;
  const cc = c.api.credits; c.run('gameDayRefresh()', '2026-11-12T17:05:00Z');   // 11:05 AM: 8 hours to kickoff
  const ckCost = c.api.credits - cc, nCk = nChecks();
  ok(/^2026-11-19b /.test(c.props.BS_MARKET_CHECK || '') && row(c, 'player_kicking_points')[4] === 2 && row(c, 'player_kicking_points')[5] === 1 && /"point":7.5/.test(row(c, 'player_kicking_points')[6]) && row(c, 'player_sacks')[4] === 0 && row(c, 'team_totals')[4] === 2 && row(c, 'player_pass_interceptions')[4] === 2 && row(c, 'player_kicking_points')[8] === thu,
    'market check: runs by itself once a game is inside 12 hours and writes what FanDuel posted, market by market', `${ckCost} credits in that pull; ${c.cell(COV, 'L1')}`);
  ok(/market check \(.*\): \d+ of \d+ other markets posted at FanDuel, \d+ credits/.test(c.cell('AUTO - FanDuel Odds', 'L5')), '  the odds tab notes say so too', (String(c.cell('AUTO - FanDuel Odds', 'L5')).match(/market check[^|]*/) || [''])[0]);
  const cc2 = c.api.credits; c.run('gameDayRefresh()', '2026-11-12T18:05:00Z');
  ok(nCk > 0 && nChecks() === nCk && c.api.credits - cc2 <= 17 + 6, '  it does not run a second time', nCk + ' check requests in all; ' + (c.api.credits - cc2) + ' credits in the next pull');
  // the switch: column C
  const setPull = (wd, k2, v) => { const sh = wd.sheets[COV], rows = cvr(wd), i = rows.findIndex(r => r[0] === k2); sh.getRange(2 + i, 3).setValues([[v]]); };
  setPull(c, 'player_kicking_points', 'y'); setPull(c, 'player_pass_interceptions', ''); setPull(c, 'team_totals', 'Y');
  c.sheets[COV].getRange(2 + cvr(c).length, 1, 1, 3).setValues([['player_made_up_market', 'Nonsense', 'Y']]);   // a key the script does not know
  EVENTS.forEach(e => c.api.version[e.id] = 7); c.run('refreshTodaysGamesNow()', '2026-11-12T19:05:00Z');
  const lk = c.tab(LINKS, 10), askedX = c.api.urls.filter(u => /bookmakers=fanduel&markets=/.test(u) && /includeLinks/.test(u) && !/player_tds_over/.test(u)).pop() || '';
  ok(lk.some(r => r[2] === 'Kicking Points' && r[3] === 8 && r[8] === thu) && !/player_pass_interceptions(,|&)/.test(askedX) && /player_pass_interceptions_alternate/.test(askedX) && !/made_up|team_totals/.test(askedX),
    'the switch: Y on kicking points adds it to the request and its rows arrive; a blank takes a market out; a game-line key or an unknown key is never sent');
  ok(!lk.some(r => r[2] === 'Interceptions' && r[3] === 1) && lk.some(r => r[2] === 'Interceptions' && r[3] === 2), '  the market switched off loses its rows; its alternate, still on, keeps them');
  c.run('checkFanDuelMarketsNow()', '2026-11-12T19:30:00Z');
  ok(row(c, 'player_kicking_points')[2] === 'y' && row(c, 'player_pass_interceptions')[2] === '' && row(c, 'player_kicking_points')[7] === '2026-11-12 13:30' && c.toasts.some(t => /other markets posted at FanDuel/.test(t)), '  running the check again from the menu keeps the switch column as it was set');
  // a key the API rejects must not hide the others
  const r2 = world(NEW); r2.api.fdExtra = true; r2.api.badKeys.player_pass_yds_q1 = true; r2.api.badKeys.totals_q1 = true; r2.run('checkFanDuelMarketsNow()', '2026-11-12T19:30:00Z');
  ok(row(r2, 'player_pass_yds_q1')[4] === 'error 422' && row(r2, 'totals_q1')[4] === 'error 422' && row(r2, 'player_kicking_points')[4] === 2 && row(r2, 'team_totals')[4] === 2 && /2 keys the API rejected/.test(r2.cell(COV, 'L1')),
    'market check: two keys the API rejects are found and marked; every other market is still read', r2.cell(COV, 'L1'));
  setPull(r2, 'player_pass_yds_q1', 'Y'); r2.run('refreshTodaysGamesNow()', '2026-11-12T19:40:00Z');
  ok(!r2.api.urls.slice(-4).some(u => /includeLinks/.test(u) && /player_pass_yds_q1/.test(u)) && r2.tab(LINKS, 10).some(r => r[2] === 'Interceptions'), '  a rejected key switched on by mistake is left out of the request, so the other extra markets still arrive');
  console.log(fails ? fails + ' FAILED' : 'FanDuelOdds.gs v2026-11-19: all checks passed'); process.exit(fails ? 1 : 0);
}
