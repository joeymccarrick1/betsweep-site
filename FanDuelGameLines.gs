/**
 * BetSweep - FanDuel game lines (moneyline, spread, total) for the NFL slate.
 *
 * Paste this whole file into the sheet's Apps Script project as a NEW file (Extensions > Apps Script > + > Script,
 * name it FanDuelGameLines) and save. It uses the same The Odds API key the props pull already uses.
 *
 * Run once by hand: choose refreshFanDuelGameLines in the function menu and press Run (approve access the first time).
 * That first run also installs its own trigger (every 6 hours) - nothing else to set up. It never makes a second copy:
 * if a trigger for refreshFanDuelGameLines already exists it leaves it alone. To change or stop it, run
 * removeGameLinesTrigger(), or installGameLinesTrigger() after editing GAMELINES_EVERY_HOURS.
 *
 * Cost: 3 credits for the main lines (h2h + spreads + totals, FanDuel only) plus 2 credits per game for the alternate spreads and
 * totals (ALT_MARKETS below; set ALT_MARKETS = '' to skip them) - about 31 credits a pull, 4 pulls a day.
 * Market column: Moneyline | Spread | Total | Alt Spread | Alt Total.
 * Writes 'AUTO - FanDuel Game Lines' (Key | Game | Kickoff (CT) | Market | Side | Point | FanDuel odds | Link | Market ID | Selection ID | Pulled at (CT)).
 */
var GAMELINES_EVERY_HOURS = 6;   // 4 pulls a day
var ALT_MARKETS = 'alternate_spreads,alternate_totals';   // FanDuel alternate lines, pulled per game ('' = skip)

function refreshFanDuelGameLines() {
  installGameLinesTrigger();   // no-op once the trigger exists
  var key = findOddsApiKey_();
  if (!key) throw new Error('No The Odds API key found in Script Properties. Add one named ODDS_API_KEY (Project Settings > Script Properties).');
  var url = 'https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds' +
            '?regions=us&markets=h2h,spreads,totals&bookmakers=fanduel&oddsFormat=american' +
            '&includeLinks=true&includeSids=true&apiKey=' + encodeURIComponent(key);
  var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) throw new Error('The Odds API ' + resp.getResponseCode() + ': ' + resp.getContentText().slice(0, 300));
  var events = JSON.parse(resp.getContentText());
  var tz = 'America/Chicago';
  var now = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd H:mm');
  var NAMES = { h2h: 'Moneyline', spreads: 'Spread', totals: 'Total' };
  var rows = [];
  events.forEach(function (ev) {
    var game = ev.away_team + ' @ ' + ev.home_team;
    var kick = Utilities.formatDate(new Date(ev.commence_time), tz, 'EEE M/d HH:mm');
    (ev.bookmakers || []).forEach(function (bk) {
      if (bk.key !== 'fanduel') return;
      (bk.markets || []).forEach(function (mk) {
        var market = NAMES[mk.key]; if (!market) return;
        (mk.outcomes || []).forEach(function (o) {
          var link = o.link || '';
          var mId = (link.match(/[?&]marketId=([^&#]+)/) || [])[1] || mk.sid || '';
          var sId = (link.match(/[?&]selectionId=([^&#]+)/) || [])[1] || o.sid || '';
          var point = (market === 'Moneyline' || o.point === undefined || o.point === null) ? '' : o.point;
          var side = o.name;   // team name for Moneyline/Spread, "Over"/"Under" for Total
          var keyTxt = side.toLowerCase() + '|' + market + '|' + (point === '' ? 0 : point) + '|' + game.toLowerCase();
          rows.push([keyTxt, game, kick, market, side, point, o.price, link, String(mId), String(sId), now]);
        });
      });
    });
  });
  // Alternate spreads / totals: The Odds API serves these only from the per-event endpoint, one call per game.
  var altRows = 0, altFailed = 0;
  if (ALT_MARKETS) {
    var ALT_NAMES = { alternate_spreads: 'Alt Spread', alternate_totals: 'Alt Total' };
    events.forEach(function (ev) {
      if (!(ev.bookmakers || []).some(function (b) { return b.key === 'fanduel'; })) return;   // no FanDuel main lines = not on the board
      var r = UrlFetchApp.fetch('https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events/' + ev.id + '/odds' +
        '?regions=us&markets=' + ALT_MARKETS + '&bookmakers=fanduel&oddsFormat=american&includeLinks=true&includeSids=true&apiKey=' + encodeURIComponent(key), { muteHttpExceptions: true });
      if (r.getResponseCode() !== 200) { altFailed++; return; }
      var d = JSON.parse(r.getContentText());
      var game = ev.away_team + ' @ ' + ev.home_team;
      var kick = Utilities.formatDate(new Date(ev.commence_time), tz, 'EEE M/d HH:mm');
      (d.bookmakers || []).forEach(function (bk) {
        if (bk.key !== 'fanduel') return;
        (bk.markets || []).forEach(function (mk) {
          var market = ALT_NAMES[mk.key]; if (!market) return;
          (mk.outcomes || []).forEach(function (o) {
            if (o.point === undefined || o.point === null) return;
            var link = o.link || '';
            var mId = (link.match(/[?&]marketId=([^&#]+)/) || [])[1] || mk.sid || '';
            var sId = (link.match(/[?&]selectionId=([^&#]+)/) || [])[1] || o.sid || '';
            var keyTxt = o.name.toLowerCase() + '|' + market + '|' + o.point + '|' + game.toLowerCase();
            rows.push([keyTxt, game, kick, market, o.name, o.point, o.price, link, String(mId), String(sId), now]); altRows++;
          });
        });
      });
    });
  }
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName('AUTO - FanDuel Game Lines') || ss.insertSheet('AUTO - FanDuel Game Lines');
  var header = ['Key', 'Game', 'Kickoff (CT)', 'Market', 'Side', 'Point', 'FanDuel odds', 'Link', 'Market ID', 'Selection ID', 'Pulled at (CT)'];
  sh.clearContents();
  sh.getRange(1, 1, 1, header.length).setValues([header]);
  if (rows.length) {
    if (sh.getMaxRows() < rows.length + 1) sh.insertRowsAfter(sh.getMaxRows(), rows.length + 1 - sh.getMaxRows());
    sh.getRange(2, 9, rows.length, 2).setNumberFormat('@');   // keep IDs as text (set before writing so 42.578347306 isn't rounded)
    sh.getRange(2, 1, rows.length, header.length).setValues(rows);
  }
  var left = resp.getHeaders()['x-requests-remaining'] || resp.getHeaders()['X-Requests-Remaining'] || '';
  sh.getRange('M1').setValue('Last refresh ' + now + ' CT · ' + rows.length + ' rows (' + altRows + ' alternate lines' + (altFailed ? ', ' + altFailed + ' games failed' : '') + ')' + (left ? ' · credits left ' + left : ''));
  return rows.length;
}

// Finds the key the existing props pull already stores (any Script Property whose name mentions ODDS and KEY).
function findOddsApiKey_() {
  var props = PropertiesService.getScriptProperties().getProperties();
  var names = Object.keys(props);
  var exact = ['ODDS_API_KEY', 'THE_ODDS_API_KEY', 'ODDSAPI_KEY', 'oddsApiKey', 'ODDS_KEY'];
  for (var i = 0; i < exact.length; i++) if (props[exact[i]]) return props[exact[i]];
  for (var j = 0; j < names.length; j++) { var n = names[j].toUpperCase(); if (n.indexOf('ODDS') >= 0 && n.indexOf('KEY') >= 0 && props[names[j]]) return props[names[j]]; }
  return '';
}

// Creates one time-driven trigger for refreshFanDuelGameLines (skips if one is already there).
function installGameLinesTrigger() {
  var has = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'refreshFanDuelGameLines'; });
  if (has) return false;
  ScriptApp.newTrigger('refreshFanDuelGameLines').timeBased().everyHours(GAMELINES_EVERY_HOURS).create();
  return true;
}

// Removes every trigger that runs refreshFanDuelGameLines.
function removeGameLinesTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'refreshFanDuelGameLines') ScriptApp.deleteTrigger(t);
  });
}
