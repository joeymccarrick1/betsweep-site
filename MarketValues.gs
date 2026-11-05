// MarketValues.gs - BetSweep: pull FantasyCalc trade values into 'AUTO - Market Values' (v2026-10-20)
// Install once: Extensions > Apps Script > paste as a new file > run setupMarketTrigger (authorise) - it refreshes daily at 5 AM
// and you can run refreshMarketValues any time. The trade calculator (gen/build_trade.py) reads this tab as in/market.json and
// shows 70% our value / 30% market, with a "vs market" chip per player. Four pulls: dynasty & redraft x 1QB & superflex (PPR, 12 teams).
var MV_SHEET = 'AUTO - Market Values';
var MV_URL = 'https://api.fantasycalc.com/values/current?isDynasty=DYN&numQbs=QBS&numTeams=12&ppr=1';

function refreshMarketValues() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(MV_SHEET) || ss.insertSheet(MV_SHEET);
  var pulls = [['d1', 'true', 1], ['d2', 'true', 2], ['r1', 'false', 1], ['r2', 'false', 2]];
  var by = {}, n = 0;
  pulls.forEach(function (p) {
    var url = MV_URL.replace('DYN', p[1]).replace('QBS', p[2]);
    var res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: { 'Accept': 'application/json' } });
    if (res.getResponseCode() !== 200) throw new Error('FantasyCalc ' + p[0] + ' HTTP ' + res.getResponseCode());
    JSON.parse(res.getContentText()).forEach(function (x) {
      var pl = x.player || {}; if (!pl.name || !pl.position) return;
      var key = pl.name + '|' + pl.position;
      var row = by[key] || (by[key] = { name: pl.name, pos: pl.position, team: pl.maybeTeam || '', sid: pl.sleeperId || '', age: pl.maybeAge || '', d1: '', d2: '', r1: '', r2: '' });
      row[p[0]] = x.value; n++;
    });
  });
  var stamp = Utilities.formatDate(new Date(), 'America/Chicago', 'yyyy-MM-dd HH:mm');
  var out = [['Player', 'Pos', 'Team', 'Sleeper ID', 'Age', 'Dynasty 1QB', 'Dynasty SF', 'Redraft 1QB', 'Redraft SF', 'Updated']];
  Object.keys(by).map(function (k) { return by[k]; }).sort(function (a, b) { return (b.d1 || 0) - (a.d1 || 0); })
    .forEach(function (r) { out.push([r.name, r.pos, r.team, r.sid, r.age, r.d1, r.d2, r.r1, r.r2, stamp]); });
  sh.clearContents();
  sh.getRange(1, 1, out.length, out[0].length).setValues(out);
  sh.setFrozenRows(1);
  Logger.log('Market values: ' + (out.length - 1) + ' players, ' + n + ' values, ' + stamp);
}

function setupMarketTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'refreshMarketValues') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('refreshMarketValues').timeBased().atHour(5).everyDays(1).inTimezone('America/Chicago').create();
  refreshMarketValues();
}
