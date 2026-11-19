/**
 * FanDuel odds -> 'AUTO - FanDuel Odds' tab (feeds V2 - Alt Line Checker column AI and V2 - Leg Board).
 * Works with either provider - put ONE key under Project Settings (gear) > Script properties:
 *   PARLAY_API_KEY = your Parlay API key   (https://parlay-api.com)   <- used first if present
 *   ODDS_API_KEY   = your The Odds API key (https://the-odds-api.com)
 *
 * One-time setup:
 *   1. Extensions > Apps Script, paste this file (replace any older version), Save.
 *   2. Add the key as a Script property (above).
 *   3. Reload the sheet. Use the new "FanDuel odds" menu > Refresh now (approve permissions the first time).
 *   4. Optional: menu > Turn on auto-refresh (every 6 hours).
 *
 * Also adds the custom function SGP_LINKED used by the Alt Line Checker parlay box (exact same-game parlay chance),
 * and two menu items that write legs to 'BET - My Legs Log' with the model numbers frozen at that moment:
 *   "Log slip from Slip Builder"  - legs marked Y in column A of V2 - Slip Builder
 *   "Log legs from Alt Line Checker" - legs with Use = Y in V2 - Alt Line Checker
 * (Version 2026-11-10: (a) REPAIR. The 11/5 file was built on an older copy and silently dropped four things the 10/27-10/29 files had:
 *  the FanDuel UNDERS tab (not pulled after 11/5 6:09 PM), the 2+ / 3+ TD prices, the rule that an odds refresh keeps the DraftKings /
 *  Hard Rock game-line rows, and the game-day menu item installing both jobs. All four are back, with the 11/5 markets on top.
 *  (b) TODAY'S GAMES. Besides the fixed windows (6 AM daily; Sunday 10, 11 AM, 1, 2, 6 PM; Thursday and Monday 6 PM) the hourly trigger now
 *  refreshes ONLY the games kicking off within 9 hours, every hour from 9 AM to 7 PM Central, when that is four games or fewer - Thursday
 *  and Monday afternoons, Sunday's night game, Saturdays and holidays. One game costs about 21 credits instead of about 290 for the slate,
 *  and every other game's rows stay in the tabs exactly as last pulled (each row keeps its own Updated / Pulled stamp).
 *  (c) A CREDIT GUARD. Each refresh stores the credits left (Script property BS_CREDITS_LEFT). An extra pull is skipped when the credits
 *  left, less what the fixed schedule needs until the quota resets (CORE_PER_DAY a day to RESET_DAY, plus 15%), would not cover it -
 *  so the extras can never starve the 6 AM pull. Row 7 of the status block on the odds tab says what the last extra pull did.
 *  Nothing to re-install: the two hourly triggers already call gameDayRefresh / gameDayRefreshLines. Paste, Save, done.)
 * (Version 2026-11-05: also pulls player_pass_tds, player_pass_interceptions, player_pass_completions (+ alternate) and player_rush_attempts
 *  for the site's new markets - links tab only, about 5 more credits per game per refresh.)
 * (Version 2026-10-19: (a) FanDuel RUSH + RECEIVING YARDS ladders (player_rush_reception_yds + alternate) are pulled and written to
 *  'AUTO - FanDuel Links' as market 'Rush + Rec Yards' for the betsweep.co builder, which prices them from the rush and receiving
 *  projections; they are kept OUT of the odds tab / Leg Board (the sheet has no formula for that market). (b) When the ladder has to be
 *  trimmed to fit the Leg Board, rungs now come off the DEEPEST ladders first (stars with 8-10 priced rungs) instead of simply the
 *  farthest prices, so a bench player's only two or three rungs - the Josh Cuevas 2+ receptions at +276 case - survive the trim.)
 * (Version 2026-10-27: FanDuel UNDERS on the main lines (player_pass_yds / rush_yds / reception_yds / receptions - the markets that
 *  already come back with Over and Under at no extra credits) are written to 'AUTO - FanDuel Unders': Key | Player | Market | Line |
 *  Under odds | Over odds | Game | Kickoff | Market ID | Under selection ID | Link | Pulled. Before, every Under outcome was dropped.
 *  betsweep.co prices them from the model's ladder; the Leg Board is unchanged.)
 * (Version 2026-10-22: the odds refresh (writeBookOddsTab_) now KEEPS the gl| game-line rows in 'AUTO - Book Odds' and only replaces the
 *  prop rows - before, every odds refresh wiped the game lines, so spread / total / ML legs had no DraftKings or Hard Rock link. Game
 *  lines are written first in the tab.)
 * (Version 2026-10-21b: GAME LINES for the other books run as their OWN job - refreshBookGameLines() (menu 'Refresh game lines (DK/HR) now';
 *  scheduled by setupTrigger alongside the odds refresh, in a separate execution so neither hits the 6-minute limit). One /odds call for
 *  h2h + spreads + totals (3 credits) plus alternate spreads/totals per game (2 credits per game); DraftKings' and Hard Rock's rows go to
 *  'AUTO - Book Odds' as Market 'Moneyline' / 'Spread' / 'Total', Key 'gl|<Away @ Home>|<market>|<team full name or Over/Under>|<point>', so
 *  betsweep.co can send a spread or total leg to those books (nearest point when the number differs). The prop refresh is unchanged.)
 * (Version 2026-10-20: the same per-event call now asks for fanduel,draftkings,hardrockbet and writes the other books' rungs to 'AUTO - Book Odds' - writeBookOddsTab_ - at no extra API credits.)
 * (Version 2026-10-17: the 'AUTO - FanDuel Links' write now lives in this file - writeFanDuelLinksTab_ - and runs on every
 *  refresh; before, it was called only if FanDuelLinks.gs defined writeLinksTab_, and was skipped silently when it did not.)
 * (Version 2026-10-15b: adds FanDuel FIRST TOUCHDOWN SCORER prices -> new tab 'AUTO - First TD Odds' (kept out of the
 *  Leg Board; the 'V2 - First TD Board' tab and betsweep.co/firsttd/ read it) and their betslip IDs in the links tab.)
 * (Version 2026-10-15: The Odds API is the primary source when ODDS_API_KEY is set - full FanDuel alt ladders
 *  (main lines + alternates + anytime TD) and the betslip IDs the betsweep.co builder uses, in one pass per refresh,
 *  about 11 credits per game. Parlay API is the fallback. Pair with FanDuelLinks.gs and GameWeather.gs.)
 *
 * Parlay API: one /props call for all NFL FanDuel props (3 credits). If that call returns only one line per player
 * (no alt ladders), it also pulls FanDuel alternate ladders game by game (about 5 credits per game).
 * The Odds API: alternate ladders game by game (about 6 credits per game).
 * K1:L8 on the odds tab shows what came back (rows, alt lines found, credits left, a sample of the raw fields).
 */
const SHEET_NAME = 'AUTO - FanDuel Odds';
const SPORT = 'americanfootball_nfl';
const MARKETS = {
  player_pass_yds_alternate: 'Passing Yards',
  player_rush_yds_alternate: 'Rushing Yards',
  player_reception_yds_alternate: 'Receiving Yards',
  player_receptions_alternate: 'Receptions',
  player_reception_longest_alternate: 'Longest Reception',
  player_rush_reception_yds_alternate: 'Rush + Rec Yards',
  player_anytime_td: 'Anytime TD'
};
const LINKS_ONLY = {'Rush + Rec Yards': true, 'Passing TDs': true, 'Interceptions': true, 'Completions': true, 'Rush Attempts': true};   // markets written to the links tab for the site, never to the odds tab / Leg Board
const DAYS_AHEAD = 7;   // only games kicking off in the next 7 days and not yet started
const MIN_ODDS = -1000; // skip near-locks shorter than this (they add nothing to a parlay)
const MAX_ODDS = 500;   // skip long shots longer than this
const BOARD_ROWS = 1600; // rows the 'V2 - Leg Board' tab scores
// Ladder window when The Odds API feeds the board (keeps the full slate under BOARD_ROWS): yardage / receptions rungs
// priced between ALT_MIN and ALT_MAX, anytime TDs between MIN_ODDS and MAX_ODDS.
const ALT_MIN = -350, ALT_MAX = 350;
const FIRST_TD_MARKET = 'player_1st_td';          // The Odds API key for first touchdown scorer
const TD_OVER_MARKET = 'player_tds_over';         // v2026-10-28: Over 1.5 / 2.5 touchdowns = FanDuel's 2+ / 3+ TD scorer markets (links tab only; the site prices them)
const FIRST_TD_SHEET = 'AUTO - First TD Odds';     // written on every refresh (not part of the Leg Board)
const ODDS_MARKETS = {
  player_pass_yds: 'Passing Yards', player_rush_yds: 'Rushing Yards', player_reception_yds: 'Receiving Yards',
  player_receptions: 'Receptions', player_reception_longest: 'Longest Reception',
  player_pass_yds_alternate: 'Passing Yards', player_rush_yds_alternate: 'Rushing Yards', player_reception_yds_alternate: 'Receiving Yards',
  player_receptions_alternate: 'Receptions', player_reception_longest_alternate: 'Longest Reception', player_anytime_td: 'Anytime TD',
  player_rush_reception_yds: 'Rush + Rec Yards', player_rush_reception_yds_alternate: 'Rush + Rec Yards',
  // 2026-11-05 (owner: more prop markets): QB passing TDs / interceptions / completions and rush attempts - links tab only, priced on the site
  player_pass_tds: 'Passing TDs', player_pass_interceptions: 'Interceptions', player_pass_completions: 'Completions', player_pass_completions_alternate: 'Completions',
  player_rush_attempts: 'Rush Attempts'
};
// ---------- v2026-11-10: today's-games pulls and the credit guard ----------
const TODAY_HOURS = 9;          // a today's-games pull covers the games kicking off within this many hours
const TODAY_MAX_GAMES = 4;      // more than this (Sunday morning) costs about what a full refresh does - the fixed windows cover it
const EXTRA_FROM = 9, EXTRA_TO = 19;   // extra pulls only between these Central hours
const CREDITS_PER_GAME = 21;    // one game, every market posted: 18 prop markets + first TD + the 2+/3+ TD call, with a little room
const CORE_PER_DAY = 580;       // credits a day the fixed windows and the two game-line jobs use (11/1-11/10: 5,194 in 9.3 days, plus the restored TD call)
const RESET_DAY = 1;            // day of the month (UTC) the Odds API quota starts over
const CREDITS_PROP = 'BS_CREDITS_LEFT';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('FanDuel odds')
    .addItem('Refresh now', 'refreshFanDuelOddsNow')
    .addItem("Refresh today's games only (about 21 credits a game)", 'refreshTodaysGamesNow')
    .addItem('Refresh game lines (DK/HR) now', 'refreshBookGameLines')
    .addItem("Turn on scheduled refresh (daily 6 AM + game windows + hourly on game days)", 'setupTrigger')
    .addItem('Turn off auto-refresh', 'removeTriggers')
    .addItem('Turn on game-day refresh (Sun/Thu/Mon pre-kickoff)', 'setupGameDayTrigger')
    .addItem('Refresh game weather now', 'refreshGameWeather')
    .addSeparator()
    .addItem('Log slip from Slip Builder (legs marked Y)', 'logSlipFromBuilder')
    .addItem('Log legs from Alt Line Checker (Use = Y)', 'logLegsFromChecker')
    .addToUi();
}

// ---------- Log legs to 'BET - My Legs Log' ----------
// Both menu items append one row per leg: Week, Slip label, Player, Market, Line, FanDuel odds, Book implied %,
// Model % (raw, frozen now), History-adjusted %, Edge, Rule (KEEP if edge >= -2%), Past clear rate, Past games,
// Result = PENDING, Notes. The log's "Auto grade" column fills the result after the Tuesday load.
function legBoardIndex_() {
  const sh = SpreadsheetApp.getActive().getSheetByName('V2 - Leg Board');
  const v = sh.getRange(5, 1, BOARD_ROWS, 34).getValues(); // A..AH
  const m = {};
  v.forEach(function (r) { if (r[0]) m[r[0] + '|' + r[1] + '|' + r[2]] = {raw: r[29], games: r[31], clear: r[33], proj: r[7]}; });
  return m;
}
function logRows_(rows, label) {
  const log = SpreadsheetApp.getActive().getSheetByName('BET - My Legs Log');
  const colA = log.getRange('A1:A2000').getValues();
  let last = 1; for (let i = 0; i < colA.length; i++) if (colA[i][0] !== '' && colA[i][0] !== null) last = i + 1;
  log.getRange(last + 1, 1, rows.length, 15).setValues(rows);
  SpreadsheetApp.getUi().alert('Logged ' + rows.length + ' legs as "' + label + '" (rows ' + (last + 1) + '-' + (last + rows.length) + ').');
}
function impliedPct_(odds) { odds = Number(odds); if (!isFinite(odds) || odds === 0) return ''; return odds > 0 ? 100 / (odds + 100) : -odds / (-odds + 100); }
function pct_(x) { return (typeof x === 'number') ? Math.round(x * 1000) / 10 + '%' : String(x); }

function logSlipFromBuilder() {
  const ss = SpreadsheetApp.getActive(), ui = SpreadsheetApp.getUi();
  const sb = ss.getSheetByName('V2 - Slip Builder');
  const week = ss.getSheetByName('AUTO - Settings').getRange('B2').getValue();
  const picks = sb.getRange('A12:O71').getValues().filter(function (r) { return String(r[0]).trim().toUpperCase() === 'Y' && r[1]; });
  if (!picks.length) { ui.alert('No legs marked Y in column A of the Slip Builder.'); return; }
  const team = sb.getRange('B2').getValue(), script = sb.getRange('B4').getValue(), chance = sb.getRange('E4').getValue();
  const fairBase = sb.getRange('F6').getValue(), fairScript = sb.getRange('F7').getValue(), fdOdds = sb.getRange('B7').getValue();
  const dflt = team + ' ' + script + ' ' + picks.length + '-leg' + (fdOdds ? ' ' + (fdOdds > 0 ? '+' : '') + fdOdds : '');
  const resp = ui.prompt('Slip label', 'Name for this slip (edit if you like):', ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  const label = resp.getResponseText().trim() || dflt;
  const idx = legBoardIndex_();
  const rows = picks.map(function (r) {
    const player = r[1], market = r[3], line = r[4], odds = r[5], hist = r[6], mult = r[7], adj = r[8], book = r[9], warn = r[11];
    const lb = idx[player + '|' + market + '|' + line] || {};
    const edge = (typeof hist === 'number' && typeof book === 'number') ? Math.round((hist - book) * 10000) / 10000 : '';
    const rule = edge === '' ? 'no price' : (edge >= -0.02 ? 'KEEP' : 'CUT');
    const note = 'Slip Builder | ' + team + ' ' + script + ' (' + pct_(chance) + ' chance) | script fit ' + mult + 'x -> ' + pct_(adj) +
      ' | slip fair ' + fairBase + (fairScript ? ' (if script ' + fairScript + ')' : '') + (fdOdds ? ' | FanDuel SGP ' + fdOdds : '') + (warn ? ' | ' + warn : '');
    return [week, label, player, market, line, odds, book, lb.raw === undefined ? '' : lb.raw, hist, edge, rule, lb.clear === undefined ? '' : lb.clear, lb.games === undefined ? '' : lb.games, 'PENDING', note];
  });
  logRows_(rows, label);
}

function logLegsFromChecker() {
  const ss = SpreadsheetApp.getActive(), ui = SpreadsheetApp.getUi();
  const ck = ss.getSheetByName('V2 - Alt Line Checker');
  const week = ss.getSheetByName('AUTO - Settings').getRange('B2').getValue();
  const v = ck.getRange('A5:AH34').getValues();
  const legs = v.filter(function (r) { return String(r[16]).trim().toUpperCase() === 'Y' && r[0]; }); // Q = Use
  if (!legs.length) { ui.alert('No legs with Use = Y in the Alt Line Checker (rows 5-34).'); return; }
  const fair = ck.getRange('T15').getValue(), bookSgp = ck.getRange('T8').getValue();
  const dflt = legs.length + '-leg SGP' + (fair ? ' fair ' + fair : '');
  const resp = ui.prompt('Slip label', 'Name for this slip (edit if you like):', ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  const label = resp.getResponseText().trim() || dflt;
  const rows = legs.map(function (r) {
    const player = r[0], market = r[1], line = r[2], odds = r[3], hist = r[10], book = r[12], edge = r[13], warn = r[15], raw = r[29], games = r[31], clear = r[33];
    const rule = (typeof edge === 'number') ? (edge >= -0.02 ? 'KEEP' : 'CUT') : 'no price';
    const note = 'Alt Line Checker | slip fair (links) ' + fair + (bookSgp ? ' | book SGP ' + bookSgp : '') + (warn ? ' | ' + warn : '');
    return [week, label, player, market, line, odds === '' ? '' : odds, book === '' ? '' : book, raw === '' ? '' : raw, hist, typeof edge === 'number' ? edge : '', rule, clear === '' ? '' : clear, games === '' ? '' : games, 'PENDING', note];
  });
  logRows_(rows, label);
}

// Same normalisation as the Alt Line Checker lookup: lower case, no periods, no Jr/Sr/II/III/IV/V suffix.
function normName(s) {
  return String(s).trim().replace(/\./g, '').replace(/\s+(jr|sr|ii|iii|iv|v)$/i, '')
    .replace(/\s+/g, ' ').toLowerCase().trim();
}

function refreshFanDuelOddsNow() { refreshFanDuelOdds(); }   // the menu item (a menu click passes nothing; this keeps it explicit)
function refreshTodaysGamesNow() {
  const r = refreshFanDuelOdds({todayHours: TODAY_HOURS, manual: true});
  SpreadsheetApp.getActiveSpreadsheet().toast(r || "Today's games refreshed; every other game is as last pulled.");
}
// opts.todayHours (v2026-11-10): refresh only the games kicking off within that many hours and keep every other upcoming game's rows
// as the tabs have them. opts.manual: no slate-size limit and no credit guard (someone asked for it). No opts = a full refresh.
function refreshFanDuelOdds(opts) {
  const todayHours = (opts && typeof opts.todayHours === 'number' && opts.todayHours > 0) ? opts.todayHours : 0;
  const props = PropertiesService.getScriptProperties();
  const pKey = props.getProperty('PARLAY_API_KEY'), oKey = props.getProperty('ODDS_API_KEY');
  if (!pKey && !oKey) throw new Error('Add PARLAY_API_KEY (or ODDS_API_KEY) under Project Settings > Script properties');
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) throw new Error('Missing tab: ' + SHEET_NAME);
  const now = new Date(), until = new Date(now.getTime() + DAYS_AHEAD * 864e5);
  const stamp = Utilities.formatDate(now, 'America/Chicago', 'yyyy-MM-dd HH:mm');
  const rows = [], seen = {}, notes = [];
  let remaining = '', sample = '', carry = null, nToday = 0, nAll = 0, nCarried = 0;
  const add = function (player, mk, xplus, price, game, kick, upd) {
    if (!player || !mk || !isFinite(xplus) || !isFinite(price)) return 0;
    if (LINKS_ONLY[mk]) return 0;   // Rush + Rec Yards: links tab only (the Leg Board cannot price it)
    if (!(price >= MIN_ODDS && price <= MAX_ODDS)) return 0;
    const k = normName(player) + '|' + mk + '|' + xplus;
    if (seen[k]) return 0; seen[k] = true;
    rows.push([k, player, mk, xplus, price, game || '', kick || '', upd || '', stamp]); return 1;
  };
  const fmtKick = function (t) { try { return t ? Utilities.formatDate(new Date(t), 'America/Chicago', 'EEE MM/dd HH:mm') : ''; } catch (e) { return ''; } };
  const inWindow = function (t) { if (!t) return true; const d = new Date(t); return isNaN(d) || (d > now && d < until); };

  // ---------- per-event alternate ladders (The Odds API v4 format; Parlay API accepts the same paths/params) ----------
  const eventAlts = function (base, auth, headers) {
    const opt = {muteHttpExceptions: true, headers: headers || {}};
    const evRes = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/events' + auth, opt);
    if (evRes.getResponseCode() !== 200) { notes.push('events ' + evRes.getResponseCode()); return 0; }
    let events = JSON.parse(evRes.getContentText()); if (!Array.isArray(events)) events = events.data || events.events || [];
    events = events.filter(function (e) { return inWindow(e.commence_time); });
    let added = 0, failed = 0;
    events.forEach(function (e) {
      const r = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/events/' + e.id + '/odds' + auth + (auth ? '&' : '?') +
        'bookmakers=fanduel&markets=' + Object.keys(MARKETS).join(',') + '&oddsFormat=american', opt);
      const h = r.getHeaders(); remaining = h['x-requests-remaining'] || h['X-Requests-Remaining'] || remaining;
      if (r.getResponseCode() !== 200) { failed++; return; }
      const d = JSON.parse(r.getContentText());
      const game = (d.away_team || e.away_team) + ' @ ' + (d.home_team || e.home_team), kick = fmtKick(d.commence_time || e.commence_time);
      (d.bookmakers || []).forEach(function (b) { (b.markets || []).forEach(function (m) {
        const mk = MARKETS[m.key]; if (!mk) return;
        (m.outcomes || []).forEach(function (o) {
          const isTd = mk === 'Anytime TD';
          if (isTd ? o.name === 'No' : o.name !== 'Over') return;
          added += add(o.description || o.name, mk, isTd ? 1 : Math.round(Number(o.point) + 0.5), Number(o.price), game, kick, m.last_update);
        });
      }); });
    });
    notes.push('per-game alt ladders: ' + events.length + ' games, ' + added + ' rows' + (failed ? ', ' + failed + ' failed' : ''));
    return added;
  };

  let provider = '';
  if (oKey) {
    // ---------- The Odds API: full FanDuel ladders + betslip IDs, one call per game ----------
    const got = oddsApiLadders_(oKey, add, notes, now, until, stamp, todayHours, opts || {});
    if (got.skip) { extraNote_(sh, stamp + ' CT: no pull - ' + got.skip); return got.skip; }   // nothing fetched, nothing written
    if (got.rows > 0 || (todayHours && !got.error)) { provider = 'The Odds API'; remaining = got.remaining; sample = got.sample; carry = got.carry; nToday = got.games; nAll = got.total; }
    else notes.push('The Odds API returned no rows' + (got.error ? ' (' + got.error + ')' : '') + (pKey ? ' - falling back to Parlay API' : ''));
  }
  if (todayHours && !provider) { extraNote_(sh, stamp + ' CT: no pull - ' + (oKey ? "the Odds API did not answer" : "today's-games pulls need ODDS_API_KEY")); return 'no pull'; }   // never a partial write from the fallback
  if (!provider && pKey) {
    provider = 'Parlay API';
    // ---------- Parlay API /props: all NFL FanDuel props in one call ----------
    const base = 'https://parlay-api.com/v1', hdr = {'X-API-Key': pKey};
    const r = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/props?bookmakers=fanduel&limit=10000', {muteHttpExceptions: true, headers: hdr});
    const h = r.getHeaders(); remaining = h['x-requests-remaining'] || h['X-Requests-Remaining'] || '';
    let added = 0, lines = {}, raw = [], ladders = 0, games = {};
    if (r.getResponseCode() === 200) {
      let d = JSON.parse(r.getContentText());
      raw = Array.isArray(d) ? d : (d.data || d.props || d.results || []);
      if (raw.length) sample = JSON.stringify(raw[0]).slice(0, 400);
      raw.forEach(function (row) {
        const books = row.books && row.books.length ? row.books : [row];
        books.forEach(function (bk) {
          const book = String(bk.bookmaker || row.bookmaker || '').toLowerCase();
          if (book && book.indexOf('fanduel') < 0) return;
          const mk = mapMarket_(row.market_key || bk.market_key || row.market); if (!mk) return;
          let player = String(row.player || row.player_name || row.description || '').trim();
          let line = Number(bk.line !== undefined ? bk.line : row.line);
          // FanDuel alt ladders arrive as "CeeDee Lamb 100+ Yards" with line 0.5 -> player "CeeDee Lamb", 100+
          const alt = player.match(/^(.*?)\s+(\d+)\+\s*(yards|yds|receptions|catches|rec)?\s*$/i);
          if (alt && mk !== 'Anytime TD') { player = alt[1].trim(); line = Number(alt[2]) - 0.5; ladders++; }
          const price = Number(bk.over_price !== undefined ? bk.over_price : (row.over_price !== undefined ? row.over_price : (bk.price !== undefined ? bk.price : row.price)));
          const ct = row.commence_time || row.start_time || row.event_start;
          if (!inWindow(ct)) return;
          const game = row.away_team && row.home_team ? row.away_team + ' @ ' + row.home_team : (row.event_name || row.game || '');
          const xplus = mk === 'Anytime TD' ? 1 : Math.round(line + 0.5);
          const n = add(player, mk, xplus, price, game, fmtKick(ct), row.last_update || row.updated_at || '');
          if (n && game) games[game] = 1;
          added += n; if (n) { const lk = normName(player) + '|' + mk; lines[lk] = (lines[lk] || 0) + 1; }
        });
      });
      notes.push('props call: ' + raw.length + ' raw rows, ' + added + ' FanDuel rows kept, ' + ladders + ' alt-ladder rows, ' +
        Object.keys(games).length + ' games posted so far');
    } else notes.push('props call failed ' + r.getResponseCode() + ': ' + r.getContentText().slice(0, 150));
    const lk = Object.keys(lines).filter(function (k) { return k.indexOf('Anytime TD') < 0; });
    const perPlayer = lk.length ? lk.reduce(function (s, k) { return s + lines[k]; }, 0) / lk.length : 0;
    notes.push('lines per player-market (yards/catches): ' + perPlayer.toFixed(2));
    // Per-game fallback only if the props call had no ladders at all (it failed 17/17 on Parlay's events path anyway)
    if (!ladders && perPlayer < 1.5) eventAlts(base, '?apiKey=' + pKey, hdr);
  }

  // v2026-11-10: a today's-games refresh keeps every other upcoming game's rows exactly as the tab has them (their own stamp included)
  if (todayHours && carry) {
    const lastOld = sh.getLastRow();
    if (lastOld > 1) sh.getRange(2, 1, lastOld - 1, 9).getValues().forEach(function (r) {
      const k = String(r[0] || ''); if (!k || !carry[r[5]] || seen[k]) return; seen[k] = true; rows.push(r); nCarried++; });
    notes.push("today's games only: " + nToday + ' of ' + nAll + ' games refreshed, ' + nCarried + ' rows carried from the last pull');
  }
  // Keep the board under its row limit. Rungs come off the DEEPEST ladders first (a star with ten priced rungs loses his
  // farthest ones before a bench player loses his only two), then by distance from -130. Before 2026-10-19 the sort was by
  // distance alone, which cut thin-room players' cheap rungs (Josh Cuevas 2+ receptions +276, Week 6) while keeping the
  // eighth rung of a WR1's ladder.
  if (rows.length > BOARD_ROWS - 10) {
    const depth = {};
    rows.forEach(function (r) { const k = normName(r[1]) + '|' + r[2]; depth[k] = (depth[k] || 0) + 1; });
    const keep = BOARD_ROWS - 10, cut = rows.length - keep;
    rows.sort(function (a, b) {   // most-droppable first
      const da = depth[normName(a[1]) + '|' + a[2]], db = depth[normName(b[1]) + '|' + b[2]];
      if (da !== db) return db - da;
      return Math.abs(b[4] + 130) - Math.abs(a[4] + 130);
    });
    // drop one rung at a time from whichever player-market is currently deepest (so a 10-rung ladder gives up several before a 4-rung one gives up any)
    const dropped = [];
    for (let i = 0; i < cut; i++) {
      let best = -1, bestScore = -1;
      for (let j = 0; j < rows.length; j++) {
        const k = normName(rows[j][1]) + '|' + rows[j][2];
        if (depth[k] <= 2) continue;   // never trim a player-market down past two rungs
        const score = depth[k] * 1000 + Math.abs(rows[j][4] + 130);
        if (score > bestScore) { bestScore = score; best = j; }
      }
      if (best < 0) break;
      const k = normName(rows[best][1]) + '|' + rows[best][2]; depth[k]--;
      dropped.push(rows.splice(best, 1)[0]);
    }
    notes.push('trimmed ' + dropped.length + ' rungs from the deepest ladders to fit the Leg Board' + (rows.length > keep ? ' (' + (rows.length - keep) + ' over; the tab holds them but the board scores the first ' + BOARD_ROWS + ')' : ''));
  }
  rows.sort(function (a, b) { return (a[5] + a[1] + a[2]).localeCompare(b[5] + b[1] + b[2]) || a[3] - b[3]; });
  const last = Math.max(sh.getLastRow(), 2);
  sh.getRange(2, 1, last - 1, 9).clearContent();
  if (rows.length) sh.getRange(2, 1, rows.length, 9).setValues(rows);
  sh.getRange('K1:L6').setValues([
    ['Status', 'Last refresh ' + stamp + ' CT' + (todayHours ? " · today's games only (" + nToday + ' of ' + nAll + '); the rest as last pulled' : '')],
    ['Provider', provider || 'none (no key worked)'],
    ['Odds rows', rows.length + (rows.length > BOARD_ROWS ? ' (Leg Board only scores the first ' + BOARD_ROWS + ')' : '')],
    ['API credits left', remaining],
    ['Notes', notes.join(' | ')],
    ['Sample raw row', sample]
  ]);
  saveCredits_(remaining);
  if (todayHours) { const sp = creditsSpare_(now); extraNote_(sh, stamp + " CT: today's games - " + nToday + ' of ' + nAll + ' refreshed' + (sp === null ? '' : ' · ' + sp + ' credits to spare beyond the fixed schedule')); }
  return '';
}

// ---------- v2026-11-10 helpers ----------
function saveCredits_(remaining) {
  const n = Number(remaining); if (remaining === '' || remaining === null || !isFinite(n)) return;
  try { PropertiesService.getScriptProperties().setProperty(CREDITS_PROP, String(Math.round(n))); } catch (e) {}
}
// credits left beyond what the fixed schedule needs until the quota resets; null = not known yet (the next refresh records it)
function creditsSpare_(now) {
  const raw = PropertiesService.getScriptProperties().getProperty(CREDITS_PROP), left = Number(raw);
  if (raw === null || raw === '' || !isFinite(left)) return null;
  const y = now.getUTCFullYear(), m = now.getUTCMonth(), d = now.getUTCDate();
  const reset = d < RESET_DAY ? Date.UTC(y, m, RESET_DAY) : Date.UTC(y, m + 1, RESET_DAY);
  const days = Math.max(0, (reset - now.getTime()) / 864e5);
  return Math.floor(left - days * CORE_PER_DAY * 1.15);
}
function extraNote_(sh, text) {   // rows 7-8 of the status block: what the last extra pull did, and the rule
  try { sh.getRange('K7:L8').setValues([['Extra pulls', text],
    ['Extra pulls rule', "Hourly " + EXTRA_FROM + " AM-" + (EXTRA_TO - 12) + " PM CT outside the fixed windows: only games kicking off within " + TODAY_HOURS + " hours, only when that is " + TODAY_MAX_GAMES + " or fewer, and only while the credits left cover the fixed schedule to the " + RESET_DAY + ordinal_(RESET_DAY) + " (" + CORE_PER_DAY + " a day + 15%)."]]); } catch (e) {}
}
function ordinal_(n) { return n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'; }
// rows already in a tab for the games a today's-games refresh is not touching: (sheet, first data row, columns, game column, key of a row)
function carried_(sh, ncols, gameIdx, carry, have, keyOf) {
  const out = []; if (!sh || !carry) return out; const last = sh.getLastRow(); if (last < 2) return out;
  sh.getRange(2, 1, last - 1, ncols).getValues().forEach(function (r) {
    if (!r[0] || !carry[r[gameIdx]]) return; const k = keyOf(r); if (have[k]) return; have[k] = true; out.push(r); });
  return out;
}


// ---------- The Odds API pass: odds rows for the Leg Board + betslip IDs for 'AUTO - FanDuel Links' ----------
function oddsApiLadders_(key, add, notes, now, until, stamp, todayHours, opts) {
  const base = 'https://api.the-odds-api.com/v4', auth = '?apiKey=' + key, opt = {muteHttpExceptions: true};
  const out = {rows: 0, remaining: '', sample: '', error: '', skip: '', carry: null, games: 0, total: 0};
  opts = opts || {};
  const evRes = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/events' + auth, opt);   // the events list is free
  if (evRes.getResponseCode() !== 200) { out.error = 'events ' + evRes.getResponseCode(); return out; }
  const allEvents = JSON.parse(evRes.getContentText()).filter(function (e) { const d = new Date(e.commence_time); return d > now && d < until; });
  const nameOf = function (e) { return e.away_team + ' @ ' + e.home_team; };
  let events = allEvents; out.total = allEvents.length;
  if (todayHours) {   // v2026-11-10: only the games about to kick off; everything else is carried over by the tab writers
    const lim = new Date(now.getTime() + todayHours * 36e5);
    events = allEvents.filter(function (e) { return new Date(e.commence_time) <= lim; });
    if (!events.length) { out.skip = 'no game kicks off in the next ' + todayHours + ' hours'; return out; }
    if (!opts.manual && events.length > TODAY_MAX_GAMES) { out.skip = events.length + ' games kick off in the next ' + todayHours + ' hours; the fixed windows cover a slate that size'; return out; }
    if (!opts.manual) { const spare = creditsSpare_(now), cost = events.length * CREDITS_PER_GAME;
      if (spare !== null && spare < cost) { out.skip = 'held back: ' + spare + ' credits to spare beyond the fixed schedule, this pull needs about ' + cost; return out; } }
    out.carry = {}; allEvents.forEach(function (e) { if (events.indexOf(e) < 0) out.carry[nameOf(e)] = true; });
  }
  out.games = events.length;
  const qs = function (url, name) { const m = String(url || '').match(new RegExp('[?&]' + name + '=([^&#]+)')); return m ? decodeURIComponent(m[1]) : ''; };
  const fmtKick = function (t) { try { return t ? Utilities.formatDate(new Date(t), 'America/Chicago', 'EEE MM/dd HH:mm') : ''; } catch (e) { return ''; } };
  const links = [], seenL = {}, firstTd = [], otherBooks = [], seenB = {}, unders = [], overMain = {}; let failed = 0, ladder = 0, withId = 0, tdPlus = 0, tdPlusFail = 0;
  events.forEach(function (e) {
    const r = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/events/' + e.id + '/odds' + auth +
      '&bookmakers=' + BOOKMAKERS + '&markets=' + Object.keys(ODDS_MARKETS).concat([FIRST_TD_MARKET]).join(',') + '&oddsFormat=american&includeLinks=true&includeSids=true', opt);
    const h = r.getHeaders(); out.remaining = h['x-requests-remaining'] || h['X-Requests-Remaining'] || out.remaining;
    if (r.getResponseCode() !== 200) { failed++; if (out.carry) out.carry[nameOf(e)] = true; return; }   // a failed game keeps the rows it had
    const d = JSON.parse(r.getContentText());
    const game = (d.away_team || e.away_team) + ' @ ' + (d.home_team || e.home_team), kick = fmtKick(d.commence_time || e.commence_time);
    // v2026-10-28: 2+ / 3+ TD scorer prices - a separate, guarded request so an unsupported market key can never break the main pull
    try {
      const r2 = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/events/' + e.id + '/odds' + auth + '&bookmakers=fanduel&markets=' + TD_OVER_MARKET + '&oddsFormat=american&includeLinks=true&includeSids=true', opt);
      const h2 = r2.getHeaders(); out.remaining = h2['x-requests-remaining'] || h2['X-Requests-Remaining'] || out.remaining;   // v2026-11-10: this call spends a credit too
      if (r2.getResponseCode() === 200) {
        const d2 = JSON.parse(r2.getContentText());
        (d2.bookmakers || []).forEach(function (b2) { if (b2.key !== 'fanduel') return; (b2.markets || []).forEach(function (m2) { if (m2.key !== TD_OVER_MARKET) return;
          (m2.outcomes || []).forEach(function (o2) {
            if (o2.name !== 'Over') return; const pt2 = Number(o2.point), pr2 = Number(o2.price), pl2 = o2.description || '';
            const mk2 = pt2 === 1.5 ? '2+ TD' : pt2 === 2.5 ? '3+ TD' : ''; if (!mk2 || !pl2 || !isFinite(pr2)) return;   // 0.5 = anytime, already covered
            const k2 = normName(pl2) + '|' + mk2 + '|1'; if (seenL[k2]) return; seenL[k2] = true;
            const lk2 = o2.link || '', mId2 = qs(lk2, 'marketId') || m2.sid || '', sId2 = qs(lk2, 'selectionId') || o2.sid || '';
            if (lk2 || (mId2 && sId2)) withId++; tdPlus++;
            links.push([k2, pl2, mk2, 1, lk2, mId2, sId2, pr2, game, stamp]);
          }); }); });
      } else { tdPlusFail++; }
    } catch (e2) { tdPlusFail++; }
    (d.bookmakers || []).forEach(function (b) {
      // other books (DraftKings, Hard Rock): same rungs, their price + deep link + ids -> 'AUTO - Book Odds'. Same API credits: the call is
      // charged per market, not per bookmaker. FanDuel stays the reference for the Leg Board, the links tab and the grading.
      if (b.key !== 'fanduel') {
        (b.markets || []).forEach(function (m) {
          const mk2 = m.key === FIRST_TD_MARKET ? 'First TD' : ODDS_MARKETS[m.key]; if (!mk2) return;
          (m.outcomes || []).forEach(function (o) {
            const isTd2 = (mk2 === 'Anytime TD' || mk2 === 'First TD');
            if (isTd2 ? o.name === 'No' : o.name !== 'Over') return;
            const player2 = o.description || o.name, x2 = isTd2 ? 1 : Math.round(Number(o.point) + 0.5), price2 = Number(o.price);
            if (!player2 || !isFinite(price2)) return;
            const k2 = normName(player2) + '|' + mk2 + '|' + x2, dk = b.key + '|' + k2;
            if (seenB[dk]) return; seenB[dk] = true;
            otherBooks.push([b.key, k2, player2, mk2, x2, price2, o.link || '', m.sid || '', o.sid || '', e.id || '', game, stamp]);
          });
        });
        return;
      }
      (b.markets || []).forEach(function (m) {
      if (m.key === FIRST_TD_MARKET) {
        (m.outcomes || []).forEach(function (o) {
          if (o.name === 'No') return;
          const player = o.description || o.name, price = Number(o.price), link = o.link || '';
          if (!player || !isFinite(price)) return;
          const marketId = qs(link, 'marketId') || m.sid || '', selectionId = qs(link, 'selectionId') || o.sid || '';
          const k = normName(player) + '|First TD|1';
          if (!seenL[k]) { seenL[k] = true; if (link || (marketId && selectionId)) withId++; links.push([k, player, 'First TD', 1, link, marketId, selectionId, price, game, stamp]); }
          firstTd.push([k, player, price, link, marketId, selectionId, game, kick, m.last_update || '', stamp]);
        });
        return;
      }
      const mk = ODDS_MARKETS[m.key]; if (!mk) return;
      const isMain = UNDER_MARKETS[m.key] === true;
      (m.outcomes || []).forEach(function (o) {
        const isTd = mk === 'Anytime TD';
        if (isMain && (o.name === 'Under' || o.name === 'Over')) {   // v2026-10-27: main-line pairs (the Under used to be dropped)
          const pl = o.description || o.name, pt = Number(o.point), pr = Number(o.price), lk = o.link || '';
          if (pl && isFinite(pt) && isFinite(pr)) {
            const uk = normName(pl) + '|' + mk + '|' + pt;
            if (o.name === 'Over') overMain[uk] = pr;
            else unders.push([uk, pl, mk, pt, pr, '', game, kick, qs(lk, 'marketId') || m.sid || '', qs(lk, 'selectionId') || o.sid || '', lk, stamp]);
          }
        }
        if (isTd ? o.name === 'No' : o.name !== 'Over') return;
        const player = o.description || o.name, xplus = isTd ? 1 : Math.round(Number(o.point) + 0.5), price = Number(o.price);
        if (!out.sample) out.sample = JSON.stringify(o).slice(0, 400);
        // betslip IDs: every rung, no price window
        const k = normName(player) + '|' + mk + '|' + xplus;
        if (!seenL[k]) {
          seenL[k] = true; const link = o.link || '';
          const marketId = qs(link, 'marketId') || m.sid || '', selectionId = qs(link, 'selectionId') || o.sid || '';
          if (link || (marketId && selectionId)) withId++;
          links.push([k, player, mk, xplus, link, marketId, selectionId, price, game, stamp]);
        }
        // odds rows for the board: window the ladder so the slate fits (Rush + Rec Yards stays links-only)
        if (LINKS_ONLY[mk]) return;
        if (!isTd && (price < ALT_MIN || price > ALT_MAX)) return;
        ladder += add(player, mk, xplus, price, game, kick, m.last_update);
      });
    }); });
  });
  out.rows = ladder;
  notes.push('2+/3+ TD prices: ' + tdPlus + (tdPlusFail ? ' (' + tdPlusFail + ' games failed - market not available?)' : ''));
  notes.push('The Odds API: ' + events.length + ' games' + (failed ? ' (' + failed + ' failed)' : '') + ', ' + ladder + ' rungs in window [' + ALT_MIN + ', ' + ALT_MAX + '] (TDs to ' + MAX_ODDS + ')');
  // Betslip IDs -> 'AUTO - FanDuel Links'. Written from THIS file on every refresh (it used to live in FanDuelLinks.gs and was
  // skipped silently when that file was missing); the notes cell always says what happened.
  const cy = out.carry, gamesTxt = cy ? events.length + ' of ' + allEvents.length + " (today's games only)" : events.length;
  try { notes.push('links tab: ' + writeFanDuelLinksTab_(links, gamesTxt, failed, out.remaining, withId, stamp, cy) + ' rows'); }
  catch (e) { notes.push('links tab FAILED: ' + e); }
  try { notes.push('first TD prices: ' + writeFirstTdTab_(firstTd, gamesTxt, failed, stamp, cy)); } catch (e) { notes.push('first TD tab: ' + e); }
  try { notes.push('book odds: ' + writeBookOddsTab_(otherBooks, gamesTxt, failed, stamp, cy) + ' rows'); } catch (e) { notes.push('book odds tab FAILED: ' + e); }
  try { unders.forEach(function (u) { if (u[0] in overMain) u[5] = overMain[u[0]]; }); notes.push('unders: ' + writeUndersTab_(unders, stamp, cy) + ' rows'); } catch (e) { notes.push('unders tab FAILED: ' + e); }
  return out;
}

// ---------- v2026-10-27: FanDuel main-line unders -> 'AUTO - FanDuel Unders' (betsweep.co prices them; the Leg Board does not read this tab) ----------
const UNDER_MARKETS = {player_pass_yds: true, player_rush_yds: true, player_reception_yds: true, player_receptions: true};
const UNDERS_SHEET = 'AUTO - FanDuel Unders';
function writeUndersTab_(rows, stamp, carry) {
  const ss = SpreadsheetApp.getActive(); let sh = ss.getSheetByName(UNDERS_SHEET);
  if (!sh) sh = ss.insertSheet(UNDERS_SHEET);
  const hdr = ['Key', 'Player', 'Market', 'Line', 'Under odds', 'Over odds', 'Game', 'Kickoff (CT)', 'Market ID', 'Under selection ID', 'Link', 'Pulled (CT)'];
  if (carry) { const have = {}; rows.forEach(function (r) { have[r[0]] = true; }); rows = rows.concat(carried_(sh, hdr.length, 6, carry, have, function (r) { return String(r[0]); })); }
  sh.clearContents();
  const all = [hdr].concat(rows);
  if (sh.getMaxRows() < all.length + 5) sh.insertRowsAfter(sh.getMaxRows(), all.length + 5 - sh.getMaxRows());
  if (sh.getMaxColumns() < hdr.length) sh.insertColumnsAfter(sh.getMaxColumns(), hdr.length - sh.getMaxColumns());
  sh.getRange(1, 1, all.length, hdr.length).setValues(all);
  return rows.length;
}

// ---------- other sportsbooks (v2026-10-20): DraftKings + Hard Rock prices, deep links and ids for the same rungs -> 'AUTO - Book Odds' ----------
// Book | Key | Player | Market | Alt line (X+) | Odds | Link | Market SID | Outcome SID | Event ID | Game | Updated. The builder shows the
// three-book price strip and the Send-to-DraftKings button from this tab. Add a book key here (The Odds API keys: betmgm, caesars, espnbet,
// fanatics, ...) and it appears in the tab on the next refresh; the site decides what to show.
const BOOKMAKERS = 'fanduel,draftkings,hardrockbet';
// game lines for the other books (DraftKings, Hard Rock): refreshBookGameLines() - main lines in one call, alternates per game.
const GL_MARKETS = {h2h: 'Moneyline', spreads: 'Spread', totals: 'Total', alternate_spreads: 'Spread', alternate_totals: 'Total'};
const BOOK_ODDS_SHEET = 'AUTO - Book Odds';
function writeBookOddsTab_(rows, games, failed, stamp, carry) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(BOOK_ODDS_SHEET);
  if (!sh) {
    sh = ss.insertSheet(BOOK_ODDS_SHEET);
    sh.getRange(1, 1, 1, 12).setValues([['Book', 'Key', 'Player', 'Market', 'Alt line (X+)', 'Odds', 'Link', 'Market SID', 'Outcome SID', 'Event ID', 'Game', 'Updated']]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  if (carry) {   // v2026-11-10: the other games' prop rows stay (game lines are kept below as always)
    const have = {}; rows.forEach(function (r) { have[r[0] + '|' + r[1]] = true; });
    rows = rows.concat(carried_(sh, 12, 10, carry, have, function (r) { return r[0] + '|' + r[1]; }).filter(function (r) { return String(r[1]).indexOf('gl|') !== 0; }));
  }
  rows.sort(function (a, b) { return (a[0] + a[10] + a[2] + a[3]).localeCompare(b[0] + b[10] + b[2] + b[3]) || a[4] - b[4]; });
  const perBook = {}; rows.forEach(function (r) { perBook[r[0]] = (perBook[r[0]] || 0) + 1; });
  // v2026-10-22: keep the gl| game-line rows refreshBookGameLines() wrote - this refresh only replaces the PROP rows. (Before, every odds
  // refresh wiped the game lines, so no spread / total / ML leg could go to DraftKings or Hard Rock between game-line runs.)
  const last = Math.max(sh.getLastRow(), 2);
  const gl = sh.getRange(2, 1, last - 1, 12).getValues().filter(function (r) { return r[0] && String(r[1]).indexOf('gl|') === 0; });
  const all = gl.concat(rows);   // game lines first, so a reader with a short range still sees them
  if (sh.getMaxRows() < all.length + 1) sh.insertRowsAfter(sh.getMaxRows(), all.length + 1 - sh.getMaxRows());
  sh.getRange(2, 1, last - 1, 12).clearContent();
  if (all.length) {
    sh.getRange(2, 8, all.length, 3).setNumberFormat('@');   // ids as text
    sh.getRange(2, 1, all.length, 12).setValues(all);
  }
  sh.getRange('N1:O4').setValues([
    ['Status', 'Last refresh ' + stamp + ' CT'],
    ['Games', games + (failed ? ' (' + failed + ' failed)' : '')],
    ['Rows per book', Object.keys(perBook).map(function (k) { return k + ' ' + perBook[k]; }).join(', ') || 'none'],
    ['Note', 'Written by FanDuelOdds.gs on every odds refresh (player markets cost nothing extra: charged per market, not per book; the game-line markets add 5 credits per game). FanDuel stays the reference; these feed the builder\'s price strip and Send to DraftKings / Hard Rock, game lines included (Key gl|Game|Market|Side|Point).']
  ]);
  return rows.length;
}

// ---------- Game lines at the other books (DraftKings, Hard Rock) -> 'AUTO - Book Odds' (gl| rows). Own job: own execution, own trigger ----------
function refreshBookGameLines() {
  const key = PropertiesService.getScriptProperties().getProperty('ODDS_API_KEY');
  if (!key) throw new Error('Add ODDS_API_KEY under Project Settings > Script properties');
  const base = 'https://api.the-odds-api.com/v4', auth = '?apiKey=' + key, opt = {muteHttpExceptions: true};
  const now = new Date(), until = new Date(now.getTime() + DAYS_AHEAD * 864e5);
  const stamp = Utilities.formatDate(now, 'America/Chicago', 'yyyy-MM-dd HH:mm');
  const books = 'draftkings,hardrockbet', rows = [], seen = {}; let failed = 0, remaining = '';
  const push = function (bk, game, eid, m) {
    const gm = GL_MARKETS[m.key]; if (!gm) return;
    (m.outcomes || []).forEach(function (o) {
      const side = o.name, pt = gm === 'Moneyline' ? 0 : Number(o.point), price = Number(o.price);
      if (!side || !isFinite(price) || !isFinite(pt)) return;
      const kg = 'gl|' + game + '|' + gm + '|' + side + '|' + pt, dg = bk + '|' + kg;
      if (seen[dg]) return; seen[dg] = true;
      rows.push([bk, kg, side, gm, pt, price, o.link || '', m.sid || '', o.sid || '', eid || '', game, stamp]);
    });
  };
  // main lines: one call for every game (3 credits)
  const r0 = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/odds' + auth + '&regions=us&bookmakers=' + books + '&markets=h2h,spreads,totals&oddsFormat=american&includeLinks=true&includeSids=true', opt);
  if (r0.getResponseCode() !== 200) throw new Error('game lines HTTP ' + r0.getResponseCode() + ' ' + r0.getContentText().slice(0, 200));
  const h0 = r0.getHeaders(); remaining = h0['x-requests-remaining'] || h0['X-Requests-Remaining'] || remaining;
  const events = JSON.parse(r0.getContentText()).filter(function (e) { const d = new Date(e.commence_time); return d > now && d < until; });
  events.forEach(function (e) { const game = e.away_team + ' @ ' + e.home_team; (e.bookmakers || []).forEach(function (b) { (b.markets || []).forEach(function (m) { push(b.key, game, e.id, m); }); }); });
  // alternate spreads / totals: per game (2 credits each)
  events.forEach(function (e) {
    const r = UrlFetchApp.fetch(base + '/sports/' + SPORT + '/events/' + e.id + '/odds' + auth + '&bookmakers=' + books + '&markets=alternate_spreads,alternate_totals&oddsFormat=american&includeLinks=true&includeSids=true', opt);
    const h = r.getHeaders(); remaining = h['x-requests-remaining'] || h['X-Requests-Remaining'] || remaining;
    if (r.getResponseCode() !== 200) { failed++; return; }
    const d = JSON.parse(r.getContentText()), game = (d.away_team || e.away_team) + ' @ ' + (d.home_team || e.home_team);
    (d.bookmakers || []).forEach(function (b) { (b.markets || []).forEach(function (m) { push(b.key, game, e.id, m); }); });
  });
  // merge: keep the prop rows the odds refresh wrote, replace every gl| row
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(BOOK_ODDS_SHEET);
  if (!sh) { sh = ss.insertSheet(BOOK_ODDS_SHEET); sh.getRange(1, 1, 1, 12).setValues([['Book', 'Key', 'Player', 'Market', 'Alt line (X+)', 'Odds', 'Link', 'Market SID', 'Outcome SID', 'Event ID', 'Game', 'Updated']]).setFontWeight('bold'); sh.setFrozenRows(1); }
  const last = sh.getLastRow();
  const old = last > 1 ? sh.getRange(2, 1, last - 1, 12).getValues().filter(function (r) { return r[0] && String(r[1]).indexOf('gl|') !== 0; }) : [];
  const all = old.concat(rows);
  if (sh.getMaxRows() < all.length + 1) sh.insertRowsAfter(sh.getMaxRows(), all.length + 1 - sh.getMaxRows());
  if (last > 1) sh.getRange(2, 1, last - 1, 12).clearContent();
  if (all.length) { sh.getRange(2, 8, all.length, 3).setNumberFormat('@'); sh.getRange(2, 1, all.length, 12).setValues(all); }
  sh.getRange('N5:O6').setValues([['Game lines', rows.length + ' DK/HR rows (ML/spread/total + alternates) · ' + events.length + ' games' + (failed ? ' (' + failed + ' alt pulls failed)' : '') + ' · ' + stamp + ' CT · credits left ' + remaining],
                                  ['Game lines note', 'Written by refreshBookGameLines() in FanDuelOdds.gs (own job, so the odds refresh stays under the 6-minute limit). Key gl|Game|Market|Side|Point; betsweep.co sends spread/total/ML legs to DraftKings and Hard Rock from these.']]);
  saveCredits_(remaining);
  Logger.log('game lines: ' + rows.length + ' rows, ' + events.length + ' games, credits left ' + remaining);
  return rows.length;
}

// Every FanDuel rung with its betslip IDs -> 'AUTO - FanDuel Links'
// (Key | Player | Market | Alt line (X+) | FanDuel link | Market ID | Selection ID | FanDuel odds | Game | Updated; status in L1:M5).
// No price window: this is what gives betsweep.co its one-tap "Send to FanDuel" links and the anytime TD prices beyond the Leg Board.
const LINKS_SHEET = 'AUTO - FanDuel Links';
function writeFanDuelLinksTab_(rows, games, failed, remaining, withId, stamp, carry) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(LINKS_SHEET);
  if (!sh) {
    sh = ss.insertSheet(LINKS_SHEET);
    sh.getRange(1, 1, 1, 10).setValues([['Key', 'Player', 'Market', 'Alt line (X+)', 'FanDuel link', 'Market ID', 'Selection ID', 'FanDuel odds', 'Game', 'Updated']]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  if (carry) {   // v2026-11-10: the other games' rungs stay, with the stamp of the pull that priced them
    const have = {}; rows.forEach(function (r) { have[r[0]] = true; });
    const old = carried_(sh, 10, 8, carry, have, function (r) { return String(r[0]); });
    old.forEach(function (r) { if (r[4] || (r[5] && r[6])) withId++; }); rows = rows.concat(old);
  }
  rows.sort(function (a, b) { return (a[8] + a[1] + a[2]).localeCompare(b[8] + b[1] + b[2]) || a[3] - b[3]; });
  if (sh.getMaxRows() < rows.length + 1) sh.insertRowsAfter(sh.getMaxRows(), rows.length + 1 - sh.getMaxRows());
  const last = Math.max(sh.getLastRow(), 2);
  sh.getRange(2, 1, last - 1, 10).clearContent();
  if (rows.length) {
    sh.getRange(2, 6, rows.length, 2).setNumberFormat('@');   // keep the IDs as text (42.616225575 must not round)
    sh.getRange(2, 1, rows.length, 10).setValues(rows);
  }
  sh.getRange('L1:M5').setValues([
    ['Status', 'Last refresh ' + stamp + ' CT'],
    ['Games', games + (failed ? ' (' + failed + ' failed)' : '')],
    ['Legs with FanDuel IDs', withId + ' of ' + rows.length],
    ['API credits left', remaining],
    ['Note', 'Written by FanDuelOdds.gs on every odds refresh. marketId/selectionId feed the betsweep.co builder "Send to FanDuel" button and its anytime TD prices.']
  ]);
  return rows.length;
}

// First touchdown scorer prices -> 'AUTO - First TD Odds' (Key | Player | FanDuel odds | link | Market ID | Selection ID | Game | Kickoff | Book updated | Pulled at).
function writeFirstTdTab_(rows, games, failed, stamp, carry) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(FIRST_TD_SHEET);
  if (!sh) {
    sh = ss.insertSheet(FIRST_TD_SHEET);
    sh.getRange(1, 1, 1, 10).setValues([['Key (name|First TD|1)', 'Player', 'FanDuel odds', 'FanDuel link', 'Market ID', 'Selection ID', 'Game', 'Kickoff (CT)', 'Book updated', 'Pulled at (CT)']]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  if (carry) { const have = {}; rows.forEach(function (r) { have[r[0]] = true; }); rows = rows.concat(carried_(sh, 10, 6, carry, have, function (r) { return String(r[0]); })); }
  rows.sort(function (a, b) { return (a[6] + a[1]).localeCompare(b[6] + b[1]) || a[2] - b[2]; });
  const last = Math.max(sh.getLastRow(), 2);
  sh.getRange(2, 1, last - 1, 10).clearContent();
  if (rows.length) { sh.getRange(2, 5, rows.length, 2).setNumberFormat('@'); sh.getRange(2, 1, rows.length, 10).setValues(rows); }
  sh.getRange('L1:M4').setValues([
    ['Status', 'Last refresh ' + stamp + ' CT'],
    ['Games', games + (failed ? ' (' + failed + ' failed)' : '')],
    ['Rows', rows.length],
    ['Note', 'FanDuel first touchdown scorer market from The Odds API (player_1st_td). Feeds V2 - First TD Board and betsweep.co/firsttd/. Not scored by the Leg Board.']
  ]);
  return rows.length;
}

// Map provider market keys to the sheet's market names (skips 1st-half / quarter markets).
function mapMarket_(key) {
  const k = String(key || '').toLowerCase();
  if (!k || /(1st|first|half|_h1|_h2|quarter|_q[1-4])/.test(k)) return '';
  if (MARKETS[k]) return MARKETS[k];
  if (/anytime/.test(k)) return 'Anytime TD';
  if (/rush/.test(k) && /rec/.test(k) && /y(ar)?ds/.test(k)) return 'Rush + Rec Yards';
  if (/longest/.test(k) && /rec/.test(k)) return 'Longest Reception';
  if (/pass/.test(k) && /y(ar)?ds/.test(k) && !/longest|comp|att/.test(k)) return 'Passing Yards';
  if (/rush/.test(k) && /y(ar)?ds/.test(k) && !/longest|att|\+|rec/.test(k)) return 'Rushing Yards';
  if (/rec/.test(k) && /y(ar)?ds/.test(k) && !/rush|longest/.test(k)) return 'Receiving Yards';
  if (/^player_receptions/.test(k)) return 'Receptions';
  return '';
}

function setupTrigger() {
  // One hourly trigger per job; gameDayRefresh() decides when to spend credits. FULL refreshes: 6 AM CT daily, Sunday 10/11 AM, 1/2 PM,
  // 6 PM, and 6 PM on Thursday and Monday - 14 a week, about 2,500 credits. v2026-11-10 adds TODAY'S-GAMES pulls in the other hours
  // from 9 AM to 7 PM when four or fewer games kick off within 9 hours (about 21 credits a game; about 450 a week), credit guard on.
  removeTriggers();
  ScriptApp.newTrigger('gameDayRefresh').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('gameDayRefreshLines').timeBased().everyHours(1).create();   // game lines in their own execution
  SpreadsheetApp.getActiveSpreadsheet().toast("Scheduled refresh on: daily 6 AM CT + Sun 10/11 AM, 1/2 PM, 6 PM + Thu/Mon 6 PM, and hourly pulls of that day's games on small-slate days");
}

function removeTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (['refreshFanDuelOdds', 'gameDayRefresh', 'gameDayRefreshLines', 'refreshBookGameLines'].indexOf(t.getHandlerFunction()) >= 0) ScriptApp.deleteTrigger(t);
  });
}

// ---------- Game-day refresh (feeds the Sunday inactives check) ----------
// An hourly trigger calls gameDayRefresh(); it only spends an API call in the windows when inactives
// are posted (about 90 minutes before kickoff): Sunday 10 AM, 11 AM, 1 PM, 2 PM and 6 PM CT (noon, 3 PM
// and 7:20 PM slates), plus 6 PM CT on Thursday and Monday for the night games. About 8 calls a week.
// The scheduled inactives check compares who still has FanDuel props against the frozen leg snapshots.
function setupGameDayTrigger() {
  // v2026-10-29: same as setupTrigger - installs BOTH jobs. (Until 10/29 this older item installed only the props job, so the
  // DK/HR game lines written on 10/22 were never refreshed and no spread/total/ML leg had a DraftKings or Hard Rock price in Week 8.)
  setupTrigger();
}

// the fixed windows (Central): day 1 = Mon ... 7 = Sun
function coreWindow_(day, hour) {
  return hour === 6 || (day === 7 && [10, 11, 13, 14, 18].indexOf(hour) >= 0) || ((day === 4 || day === 1) && hour === 18);
}
function gameDayRefresh() {
  var now = new Date();
  var day = Number(Utilities.formatDate(now, 'America/Chicago', 'u')); // 1 = Mon ... 7 = Sun
  var hour = Number(Utilities.formatDate(now, 'America/Chicago', 'H'));
  var go = coreWindow_(day, hour);
  if (go) refreshFanDuelOdds();
  // v2026-11-10: every other hour from 9 AM to 7 PM, the games kicking off within 9 hours - when that is a small slate and the
  // credits allow (refreshFanDuelOdds decides and writes why in row 7 of the odds tab's status block). The events list it reads
  // first is free, so an hour with nothing to do costs nothing.
  else if (hour >= EXTRA_FROM && hour <= EXTRA_TO) {
    try { refreshFanDuelOdds({todayHours: TODAY_HOURS}); } catch (e) { Logger.log("today's games: " + e); }
  }
  // Game weather (GameWeather.gs): once a day at 6 AM CT plus the pre-kickoff windows. Free, no credits.
  if ((hour === 6 || go) && typeof refreshGameWeather === 'function') {
    try { refreshGameWeather(); } catch (e) { Logger.log('weather: ' + e); }
  }
}

function gameDayRefreshLines() {   // the fixed windows only, run as a separate execution
  var now = new Date();
  var day = Number(Utilities.formatDate(now, 'America/Chicago', 'u')), hour = Number(Utilities.formatDate(now, 'America/Chicago', 'H'));
  if (coreWindow_(day, hour)) refreshBookGameLines();
}

// ================= SGP pricing =================
// ---- SGP linked probability (Gaussian copula, Genz 1992 separation of variables, deterministic lattice) ----
function sgpNormCdf_(x) {           // Cody-style erf via Abramowitz-Stegun 7.1.26 refined (max err ~1e-7 using erfc series)
  var t = 1 / (1 + 0.5 * Math.abs(x) / Math.SQRT2), z = Math.abs(x) / Math.SQRT2;
  var r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 +
          t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
  return x >= 0 ? 1 - r / 2 : r / 2;
}
function sgpNormInv_(p) {           // Acklam's inverse normal
  if (p <= 0) return -8; if (p >= 1) return 8;
  var a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
  var b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
  var c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
  var d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
  var q, r, pl = 0.02425;
  if (p < pl) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
  if (p > 1 - pl) { q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
  q = p - 0.5; r = q * q;
  return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
}
function sgpChol_(C) {
  var n = C.length, L = [];
  for (var i = 0; i < n; i++) { L.push(new Array(n).fill(0)); }
  for (var i = 0; i < n; i++) for (var j = 0; j <= i; j++) {
    var s = C[i][j]; for (var k = 0; k < j; k++) s -= L[i][k] * L[j][k];
    if (i === j) { if (s <= 1e-10) return null; L[i][i] = Math.sqrt(s); } else L[i][j] = s / L[j][j];
  }
  return L;
}
function sgpMvn_(p, C) {            // P(all legs hit) = P(Z_i < Phi^-1(p_i) for all i), Z ~ N(0, C)
  var n = p.length; if (n === 0) return 1;
  var L = null, shrink = 1, C2;
  while (!L && shrink > 0) {        // keep the matrix valid: shrink links slightly if needed
    C2 = C.map(function (row, i) { return row.map(function (v, j) { return i === j ? 1 : v * shrink; }); });
    L = sgpChol_(C2); if (!L) shrink -= 0.05;
  }
  var b = p.map(function (x) { return sgpNormInv_(Math.min(0.9999, Math.max(0.0001, x))); });
  var primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71];
  var N = 4000, reps = 8, seed = 12345, total = 0;
  function rnd() { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; }
  for (var r = 0; r < reps; r++) {
    var shift = []; for (var k = 0; k < n; k++) shift.push(rnd());
    var sum = 0;
    for (var m = 1; m <= N; m++) {
      var f = 1, y = [];
      for (var i = 0; i < n; i++) {
        var s = 0; for (var j = 0; j < i; j++) s += L[i][j] * y[j];
        var e = sgpNormCdf_((b[i] - s) / L[i][i]);
        f *= e; if (f === 0) break;
        if (i < n - 1) {
          var w = (m * Math.sqrt(primes[i]) + shift[i]) % 1; w = Math.abs(2 * w - 1);   // baker's transform
          y.push(sgpNormInv_(Math.min(0.999999, Math.max(1e-6, w * e))));
        }
      }
      sum += f;
    }
    total += sum / N;
  }
  return total / reps;
}

/**
 * Exact same-game parlay hit chance for the Alt Line Checker parlay box (legs with Y in column Q).
 * Gaussian copula with the links in 'AUTO - SGP Correlations'; legs in different games are independent.
 * Matches scipy's multivariate normal to within ~0.03% on 2-10 leg tests.
 * @customfunction
 */
function SGP_LINKED(probs, use, players, teams, games, codes, corrKeys, corrVals) {
  var flat = function (a) { return Array.isArray(a) ? a.map(function (r) { return Array.isArray(r) ? r[0] : r; }) : [a]; };
  probs = flat(probs); use = flat(use); players = flat(players); teams = flat(teams); games = flat(games); codes = flat(codes);
  var tbl = {}; var ks = flat(corrKeys), vs = flat(corrVals);
  for (var t = 0; t < ks.length; t++) if (ks[t] && typeof vs[t] === 'number') tbl[String(ks[t])] = vs[t];
  var legs = [];
  for (var i = 0; i < probs.length; i++) {
    if (String(use[i]).toUpperCase() === 'Y' && typeof probs[i] === 'number' && probs[i] > 0) legs.push(i);
  }
  if (legs.length === 0) return '';
  var p = legs.map(function (i) { return probs[i]; });
  var C = legs.map(function (i) { return legs.map(function (j) {
    if (i === j) return 1;
    if (String(games[i]) === '' || String(games[i]) !== String(games[j])) return 0;
    var rel = String(players[i]) === String(players[j]) ? 'SP' : (String(teams[i]) === String(teams[j]) ? 'TM' : 'OPP');
    var a = String(codes[i]), b = String(codes[j]); var key = rel + '|' + (a < b ? a + '|' + b : b + '|' + a);
    return tbl[key] || 0;
  }); });
  return sgpMvn_(p, C);
}