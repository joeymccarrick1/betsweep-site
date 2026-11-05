window.TCOL={"ARI":["#97233F","#000000"],"ATL":["#A71930","#000000"],"BAL":["#241773","#9E7C0C"],"BUF":["#00338D","#C60C30"],"CAR":["#0085CA","#101820"],"CHI":["#0B162A","#C83803"],"CIN":["#FB4F14","#000000"],"CLE":["#311D00","#FF3C00"],"DAL":["#003594","#869397"],"DEN":["#FB4F14","#002244"],"DET":["#0076B6","#B0B7BC"],"GB":["#203731","#FFB612"],"HOU":["#03202F","#A71930"],"IND":["#002C5F","#A2AAAD"],"JAX":["#006778","#D7A22A"],"KC":["#E31837","#FFB81C"],"LA":["#003594","#FFA300"],"LAC":["#0080C6","#FFC20E"],"LV":["#000000","#A5ACAF"],"MIA":["#008E97","#FC4C02"],"MIN":["#4F2683","#FFC62F"],"NE":["#002244","#C60C30"],"NO":["#D3BC8D","#101820"],"NYG":["#0B2265","#A71930"],"NYJ":["#125740","#000000"],"PHI":["#004C54","#A5ACAF"],"PIT":["#FFB612","#101820"],"SEA":["#002244","#69BE28"],"SF":["#AA0000","#B3995D"],"TB":["#D50A0A","#34302B"],"TEN":["#0C2340","#4B92DB"],"WAS":["#5A1414","#FFB612"]};
(function(){
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function nm(p){ return p.s ? '<a href="/player/' + p.s + '/">' + esc(p.n) + '</a>' : esc(p.n); }
  function n0(v){ return (Math.round(v * 10) / 10).toString(); }
  function tbl(title, cols, rows){ if (!rows.length) return ''; return '<h3>' + title + '</h3><div class="tw"><table><thead><tr><th>Player</th>' + cols.map(function(c){ return '<th>' + c[0] + '</th>'; }).join('') + '</tr></thead><tbody>' +
    rows.map(function(r){ return '<tr><td>' + nm(r) + ' <small style="color:var(--mute)">' + esc(r.p) + '</small></td>' + cols.map(function(c){ return '<td>' + c[1](r) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table></div>'; }
  function side(b, label, t){ return '<div><h4><span class="tb sm" style="' + (window.TCOL && TCOL[t] ? '--p:' + TCOL[t][0] + ';--s:' + TCOL[t][1] : '') + '">' + esc(t) + '</span>' + esc(label) + '</h4>' +
    tbl('Passing', [['C/Att', function(r){ return r.c + '/' + r.a; }], ['Yds', function(r){ return n0(r.y); }], ['TD', function(r){ return r.td; }], ['INT', function(r){ return r.i; }], ['Sk', function(r){ return r.sk; }]], b.pass) +
    tbl('Rushing', [['Car', function(r){ return r.c; }], ['Yds', function(r){ return n0(r.y); }], ['Avg', function(r){ return r.c ? (r.y / r.c).toFixed(1) : '-'; }], ['TD', function(r){ return r.td; }]], b.rush) +
    tbl('Receiving', [['Rec/Tgt', function(r){ return r.r + '/' + r.t; }], ['Yds', function(r){ return n0(r.y); }], ['TD', function(r){ return r.td; }]], b.rec) +
    tbl('Defense', [['Tkl', function(r){ return r.tk; }], ['Sk', function(r){ return r.sk; }], ['INT', function(r){ return r.i; }], ['PD', function(r){ return r.pd; }]], b.def) +
    tbl('Kicking', [['FG', function(r){ return r.fg; }], ['Long', function(r){ return r.lg || '-'; }], ['XP', function(r){ return r.xp; }]], b.k) + '</div>'; }
  document.querySelectorAll('details.gm[data-g]').forEach(function(d){ d.addEventListener('toggle', function(){ if (!d.open || d._ld) return; d._ld = 1; var box = d.querySelector('.pbox');
    fetch('/teams/box/' + d.getAttribute('data-g') + '.json').then(function(r){ if (!r.ok) throw 0; return r.json(); }).then(function(j){ var t = d.getAttribute('data-t'), o = d.getAttribute('data-o');
      box.innerHTML = '<div class="two">' + side(j[t] || {pass:[],rush:[],rec:[],def:[],k:[]}, '', t) + side(j[o] || {pass:[],rush:[],rec:[],def:[],k:[]}, '', o) + '</div>'; })
    .catch(function(){ box.innerHTML = '<p class="ld">The player box score for this game is not posted yet.</p>'; }); }); });
  // directory: sortable league table
  var lt = document.getElementById('leaguet'); if (lt){ var ths = lt.querySelectorAll('th.sort'); ths.forEach(function(th, i){ th.addEventListener('click', function(){ var col = +th.getAttribute('data-c'), asc = th.getAttribute('data-a') === '1';
    var tb = lt.querySelector('tbody'), rows = Array.prototype.slice.call(tb.rows); rows.sort(function(a, b){ var x = +a.cells[col].getAttribute('data-v'), y = +b.cells[col].getAttribute('data-v'); return asc ? x - y : y - x; });
    rows.forEach(function(r){ tb.appendChild(r); }); ths.forEach(function(h){ h.classList.remove('on'); }); th.classList.add('on'); }); }); }
})();
