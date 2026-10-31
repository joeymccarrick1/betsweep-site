"""social.py - BetSweep Social (owner 10/26): users post their betslips, others tail and upvote; the most-upvoted open slips sit on top;
a slip leaves the feed as soon as one leg loses or once every leg's game is over.

Pieces:
  SQL           run once in the Supabase SQL editor (also gen/social.sql) - tables feed_posts / feed_votes / feed_reports, row-level security,
                vote counting, a posting limit, and auto-hide at 3 reports.
  POST_JS       added to the Parlay Builder: "Post to Social" in the slip panel (sign-in required; a handle, an optional title, and the
                FanDuel price the poster actually got).
  page()        the /social/ page body: reads the feed from Supabase (anon key, public read), grades every leg live from ESPN while games
                are on (same grader as the home page's promoted bets), hides a slip once it's busted or finished, Tail on FanDuel /
                Load into my slip / upvote / report / delete-your-own.
Nothing here touches the model. Posts are user content: the Terms (build_legal.py) cover them, reports hide a post automatically at 3,
and the owner can hide anything with:  update public.feed_posts set status = 'hidden' where id = <id>;
"""
import json

SQL = r"""-- BetSweep Social: run once in the Supabase SQL editor (Project fuwiqijgkgbzvnfnsans > SQL editor > New query > paste > Run)
create table if not exists public.feed_posts (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  handle text not null check (handle ~ '^[A-Za-z0-9_.]{2,20}$'),
  title text check (title is null or char_length(title) <= 60),
  week int not null check (week between 1 and 23),
  legs jsonb not null check (jsonb_typeof(legs) = 'array' and jsonb_array_length(legs) between 1 and 15),
  fd_odds int check (fd_odds is null or fd_odds between -100000 and 10000000),
  first_ko timestamptz not null,
  last_ko timestamptz not null,
  score int not null default 0,
  status text not null default 'open' check (status in ('open', 'hidden')),
  created_at timestamptz not null default now()
);
create index if not exists feed_posts_open on public.feed_posts (status, last_ko, score desc, created_at desc);
create table if not exists public.feed_votes (
  post_id bigint not null references public.feed_posts(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);
create table if not exists public.feed_reports (
  post_id bigint not null references public.feed_posts(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  reason text check (reason is null or char_length(reason) <= 200),
  created_at timestamptz not null default now(),
  primary key (post_id, user_id)
);
alter table public.feed_posts enable row level security;
alter table public.feed_votes enable row level security;
alter table public.feed_reports enable row level security;
drop policy if exists "read open" on public.feed_posts;
create policy "read open" on public.feed_posts for select using (status = 'open' or auth.uid() = user_id);
drop policy if exists "post own" on public.feed_posts;
create policy "post own" on public.feed_posts for insert to authenticated with check (auth.uid() = user_id and status = 'open' and score = 0);
drop policy if exists "delete own" on public.feed_posts;
create policy "delete own" on public.feed_posts for delete to authenticated using (auth.uid() = user_id);
drop policy if exists "read votes" on public.feed_votes;
create policy "read votes" on public.feed_votes for select using (true);
drop policy if exists "vote own" on public.feed_votes;
create policy "vote own" on public.feed_votes for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "unvote own" on public.feed_votes;
create policy "unvote own" on public.feed_votes for delete to authenticated using (auth.uid() = user_id);
drop policy if exists "report own" on public.feed_reports;
create policy "report own" on public.feed_reports for insert to authenticated with check (auth.uid() = user_id);
-- posting rules enforced on the server: no slip whose first game has already kicked off, at most 10 posts a day per account
create or replace function public.feed_post_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.first_ko <= now() then raise exception 'A leg in this slip has already kicked off'; end if;
  if new.last_ko < new.first_ko or new.last_ko > now() + interval '14 days' then raise exception 'Bad kickoff times'; end if;
  if (select count(*) from public.feed_posts where user_id = new.user_id and created_at > now() - interval '1 day') >= 10 then
    raise exception 'Posting limit reached (10 a day)'; end if;
  new.score := 0; new.status := 'open'; new.created_at := now();
  return new;
end $$;
drop trigger if exists feed_post_guard on public.feed_posts;
create trigger feed_post_guard before insert on public.feed_posts for each row execute function public.feed_post_guard();
-- upvote count kept on the post (users cannot write it directly)
create or replace function public.feed_vote_count() returns trigger language plpgsql security definer set search_path = public as $$
begin
  update public.feed_posts set score = (select count(*) from public.feed_votes where post_id = coalesce(new.post_id, old.post_id))
   where id = coalesce(new.post_id, old.post_id);
  return null;
end $$;
drop trigger if exists feed_vote_count on public.feed_votes;
create trigger feed_vote_count after insert or delete on public.feed_votes for each row execute function public.feed_vote_count();
-- three reports from different accounts hide a post until the owner looks at it
create or replace function public.feed_report_hide() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if (select count(*) from public.feed_reports where post_id = new.post_id) >= 3 then
    update public.feed_posts set status = 'hidden' where id = new.post_id; end if;
  return null;
end $$;
drop trigger if exists feed_report_hide on public.feed_reports;
create trigger feed_report_hide after insert on public.feed_reports for each row execute function public.feed_report_hide();

-- ---- v2 (10/27): assigned handles + clean titles ----------------------------------------------------------------------------
-- Users no longer type a handle: every account gets one made from its id (BlitzRaven42 style - football words + two digits), the
-- same one every time, and the insert trigger overwrites whatever the client sends. Titles are checked against a profanity list
-- on the server (the builder checks the same list first for instant feedback); a dirty title is refused, not posted.
create or replace function public.feed_handle(u uuid) returns text language sql immutable as $$
  select (array['Blitz','Slant','Wheel','Dagger','Flea','Shovel','Sweep','Scramble','Audible','Hurry','Goal','Fourth','Hail','Zone','Press','Dime','Chalk','Fade','Tail','Hammer','Lock','Edge','Pocket','Cover','Prime','Red','Deep','Quick','Iron','Wild'])
         [1 + mod(('x' || substr(md5(u::text), 1, 8))::bit(32)::int::bigint & 2147483647, 30)]
      || (array['Raven','Hawk','Bronco','Jet','Ram','Lion','Bear','Colt','Titan','Viking','Saint','Falcon','Eagle','Giant','Packer','Charger','Chief','Dolphin','Panther','Jaguar','Texan','Bengal','Cowboy','Steeler','Seahawk','Buc','Cardinal','Raider','Bill','Niner'])
         [1 + mod(('x' || substr(md5(u::text), 9, 8))::bit(32)::int::bigint & 2147483647, 30)]
      || lpad((mod(('x' || substr(md5(u::text), 17, 8))::bit(32)::int::bigint & 2147483647, 90) + 10)::text, 2, '0');
$$;
grant execute on function public.feed_handle(uuid) to anon, authenticated;
create or replace function public.feed_clean(t text) returns boolean language plpgsql immutable as $$
declare n text; w text;
begin
  if t is null then return true; end if;
  -- normalise: lowercase, leetspeak -> letters, drop everything that is not a letter
  n := lower(t); n := translate(n, '0134578@$!|', 'oieastbasil');
  n := regexp_replace(n, '[^a-z ]', '', 'g');
  foreach w in array array['fuck','fck','fuk','fvck','phuck','shit','cunt','bitch','asshole','pussy','whore','slut','nigg','retard','kike','chink','wetback','tranny','dyke','twat','jizz','rape','nazi','hitler','porn','blowjob','handjob','motherf','bastard','douche','wank','bollock','arsehole','pedo','paedo'] loop
    if position(w in replace(n, ' ', '')) > 0 then return false; end if;
  end loop;
  foreach w in array array['ass','damn','piss','tit','hoe','sex','anal','nig','fag','coon','dick','cock','cum','spic','cox'] loop
    if n ~ ('(^|\s)' || w || 's?(\s|$)') then return false; end if;
  end loop;
  return true;
end $$;
grant execute on function public.feed_clean(text) to anon, authenticated;
create or replace function public.feed_post_guard() returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.first_ko <= now() then raise exception 'A leg in this slip has already kicked off'; end if;
  if new.last_ko < new.first_ko or new.last_ko > now() + interval '14 days' then raise exception 'Bad kickoff times'; end if;
  if (select count(*) from public.feed_posts where user_id = new.user_id and created_at > now() - interval '1 day') >= 10 then
    raise exception 'Posting limit reached (10 a day)'; end if;
  if not public.feed_clean(new.title) then raise exception 'Keep the title clean'; end if;
  new.handle := public.feed_handle(new.user_id);
  new.score := 0; new.status := 'open'; new.created_at := now();
  return new;
end $$;
drop trigger if exists feed_post_guard on public.feed_posts;
create trigger feed_post_guard before insert on public.feed_posts for each row execute function public.feed_post_guard();
"""
SQL_V2 = SQL[SQL.index("-- ---- v2"):]   # gen/social_v2.sql - the owner runs just this part on top of the 10/26 install


# ---------------- Parlay Builder: "Post to Social" ----------------
POST_CSS = """
.sdlg{position:fixed;inset:0;z-index:120;background:rgba(10,12,16,.55);display:flex;align-items:center;justify-content:center;padding:16px}
.sdlg[hidden]{display:none}
.sdlg .box{background:var(--card,#f7f3e8);color:var(--ink,#141a24);border:1px solid var(--line,#d3cbb8);border-radius:14px;max-width:420px;width:100%;padding:18px 18px 14px;box-shadow:0 20px 60px rgba(0,0,0,.4)}
.sdlg h3{margin:0 0 4px;font-family:var(--display,'Barlow Condensed',sans-serif);font-size:22px}
.sdlg p{margin:0 0 10px;font-size:13px;color:var(--mute,#5d6676);line-height:1.45}
.sdlg label{display:block;font-size:12px;font-weight:600;margin:8px 0 3px}
.sdlg input{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:9px 11px;border:1px solid var(--line,#d3cbb8);border-radius:9px;background:var(--bg,#fff);color:var(--ink,#141a24)}
.sdlg .row{display:flex;gap:8px;margin-top:12px}.sdlg .row button{flex:1;font:inherit;font-weight:700;padding:11px;border-radius:9px;border:1px solid var(--line,#d3cbb8);background:none;color:var(--ink,#141a24);cursor:pointer}
.sdlg .row button.go{background:#d7332a;border-color:#d7332a;color:#fff}.sdlg .row button[disabled]{opacity:.6}
.sdlg .asn{font-size:13px;color:var(--ink,#141a24)} .sdlg .asn b{font-weight:700}
.sdlg .msg{font-size:13px;margin-top:8px;min-height:1.2em}.sdlg .msg.err{color:#d7332a}
"""
POST_HTML = """<div class="sdlg" id="sdlg" hidden><div class="box" role="dialog" aria-modal="true" aria-labelledby="sdlgT">
 <h3 id="sdlgT">Post to BetSweep Social</h3>
 <p>Your slip goes on the Social page for others to tail and upvote. It comes down on its own when a leg loses or every game is over. Keep it clean - posts can be reported and removed.</p>
 <p class="asn">Posting as <b id="sdH">…</b> <small>(your BetSweep handle - assigned, the same on every post)</small></p>
 <label for="sdT">Title <small>(optional)</small></label><input id="sdT" maxlength="60" placeholder="e.g. Sunday ladder">
 <label for="sdO">FanDuel price you got <small>(optional, e.g. +650)</small></label><input id="sdO" inputmode="text" maxlength="9" placeholder="+650">
 <div class="msg" id="sdM"></div>
 <div class="row"><button type="button" id="sdX">Cancel</button><button type="button" class="go" id="sdGo">Post</button></div>
</div></div>"""
POST_JS = r"""<script>(function(){
  var btn = document.getElementById('postsl'), dlg = document.getElementById('sdlg'); if(!btn || !dlg) return;
  var $ = function(id){ return document.getElementById(id); };
  function legsNow(){ return (window.bsSlipLegs ? window.bsSlipLegs() : []); }
  function msg(t, err){ var m = $('sdM'); m.textContent = t || ''; m.className = 'msg' + (err ? ' err' : ''); }
  btn.addEventListener('click', function(){
    var A = window.bsAccount; var ls = legsNow();
    if(!ls.length){ alertish('Add some legs first.'); return; }
    if(!A || !A.client){ alertish('Accounts are not available right now.'); return; }
    if(!A.user){ var s = document.querySelector('#bsacct button'); if(s) s.click(); return; }   // opens the sign-in dialog
    var started = ls.filter(function(l){ return window.bsGameKo && window.bsGameKo(l.g) && Date.now() >= window.bsGameKo(l.g); });
    msg(started.length ? 'Remove the legs from games that already kicked off first.' : '', !!started.length);
    $('sdH').textContent = '…'; A.client.rpc('feed_handle', {u: A.user.id}).then(function(r){ $('sdH').textContent = r.data ? '@' + r.data : '(assigned when you post)'; }, function(){ $('sdH').textContent = '(assigned when you post)'; });
    $('sdGo').disabled = !!started.length; dlg.hidden = false; $('sdT').focus();
  });
  function alertish(t){ var f = document.getElementById('flags') || document.getElementById('bslipFlags'); if(f){ f.innerHTML = '⚠ ' + t; } }
  // same list and normalisation as feed_clean() in the SQL: instant feedback here, the server has the final say
  var BAD1 = ['fuck','fck','fuk','fvck','phuck','shit','cunt','bitch','asshole','pussy','whore','slut','nigg','retard','kike','chink','wetback','tranny','dyke','twat','jizz','rape','nazi','hitler','porn','blowjob','handjob','motherf','bastard','douche','wank','bollock','arsehole','pedo','paedo'];
  var BAD2 = ['ass','damn','piss','tit','hoe','sex','anal','nig','fag','coon','dick','cock','cum','spic','cox'];
  function clean(t){ if(!t) return true; var n = t.toLowerCase(); var L = {'0':'o','1':'i','3':'e','4':'a','5':'s','7':'t','8':'b','@':'a','$':'s','!':'i','|':'l'}; n = n.replace(/[01345789@$!|]/g, function(c){ return L[c] || c; }).replace(/[^a-z ]/g, '');
    var j = n.replace(/ /g, ''); for(var i = 0; i < BAD1.length; i++) if(j.indexOf(BAD1[i]) >= 0) return false;
    for(i = 0; i < BAD2.length; i++) if(new RegExp('(^|\\s)' + BAD2[i] + 's?(\\s|$)').test(n)) return false; return true; }
  $('sdX').addEventListener('click', function(){ dlg.hidden = true; });
  dlg.addEventListener('click', function(e){ if(e.target === dlg) dlg.hidden = true; });
  $('sdGo').addEventListener('click', function(){
    var A = window.bsAccount, ls = legsNow(); var h = ($('sdH').textContent || '').replace(/^@/, ''), t = $('sdT').value.trim(), o = $('sdO').value.trim().replace(/[^0-9+-]/g, '');
    if(!/^[A-Za-z0-9_.]{2,20}$/.test(h)) h = 'sweeper';   // the server assigns the real one on insert
    if(!clean(t)){ msg('Keep the title clean - that one will not post.', true); return; }
    var odds = o ? parseInt(o, 10) : null; if(o && (isNaN(odds) || Math.abs(odds) < 100)){ msg('Price looks off - use American odds like +650 or -120.', true); return; }
    var kos = ls.map(function(l){ return window.bsGameKo ? window.bsGameKo(l.g) : null; }).filter(Boolean);
    if(!kos.length){ msg('Could not read kickoff times for these legs.', true); return; }
    var legs = ls.map(function(l){ return {k: l.pl + '|' + l.m + '|' + Math.round(l.ln || 1), pl: l.pl, m: l.m, ms: l.ms, ln: l.ln, o: l.o, g: l.g, tm: l.tm, opp: l.opp,
      fd: l.fd && l.fd.m && l.fd.s ? {m: l.fd.m, s: l.fd.s} : null, gl: l.gl ? {k: l.gl.k, side: l.gl.side} : null, ko: window.bsGameKo ? window.bsGameKo(l.g) : null}; });
    var dec = ls.reduce(function(a, l){ return a * (l.o > 0 ? 1 + l.o / 100 : 1 + 100 / -l.o); }, 1);
    var row = {handle: h, title: t || null, week: ((window.__BS || {}).week || (window.__BSL || {}).week || +window.__BSW || null), legs: legs, fd_odds: odds != null ? odds : Math.round(dec >= 2 ? (dec - 1) * 100 : -100 / (dec - 1)),
      first_ko: new Date(Math.min.apply(null, kos)).toISOString(), last_ko: new Date(Math.max.apply(null, kos)).toISOString()};
    $('sdGo').disabled = true; msg('Posting…');
    A.client.from('feed_posts').insert(row).select('id').then(function(r){
      $('sdGo').disabled = false;
      if(r.error){ msg(/relation|does not exist/i.test(r.error.message) ? 'Social is still being set up - try again soon.' : r.error.message, true); return; }
      msg('Posted! Opening Social…'); setTimeout(function(){ location.href = '/social/#p' + ((r.data && r.data[0] && r.data[0].id) || ''); }, 600);
    });
  });
})();</script>"""

# ---------------- /social/ page ----------------
PAGE_CSS = """
.soc{max-width:760px;margin:0 auto;padding:6px 0 40px}
.soc h1{font-family:var(--display);font-size:32px;margin:16px 0 2px;letter-spacing:.02em}
.soc .lede{color:var(--mute);font-size:13.5px;line-height:1.5;margin:0 0 12px}
.soc .bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 12px}
.soc .bar a,.soc .bar button{font:inherit;font-weight:700;font-size:13px;padding:9px 13px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--ink);text-decoration:none;cursor:pointer}
.soc .bar a.pri{background:#d7332a;border-color:#d7332a;color:#fff}
.soc .bar .seg button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.soc .empty{padding:26px 16px;text-align:center;color:var(--mute);border:1px dashed var(--line);border-radius:12px}
.post{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:0 0 12px;overflow:hidden}
/* owner 10/30: tap a post -> its short-link page (/b/?p=<id>): FanDuel / DraftKings / Hard Rock buttons, Save slip, Load into the builder */
.post .ph .who,.post ul{cursor:pointer} .post:hover{border-color:color-mix(in srgb,var(--red) 55%,var(--line))} .post a.open{font-size:12.5px;font-weight:700;color:var(--ink);text-decoration:none;white-space:nowrap}
.post[hidden]{display:none}
.post .ph{display:flex;align-items:center;gap:10px;padding:12px 14px 6px}
.post .vote{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:46px;min-height:52px;border:1px solid var(--line);border-radius:10px;background:none;color:var(--ink);cursor:pointer;font:inherit;padding:4px}
.post .vote i{font-style:normal;font-size:15px;line-height:1}.post .vote b{font-family:var(--display);font-size:19px;line-height:1.1}
.post .vote.on{background:#d7332a;border-color:#d7332a;color:#fff}
.post .who{flex:1;min-width:0}.post .who b{font-size:15px}.post .who small{display:block;color:var(--mute);font-size:12px}
.post .who .t{display:block;font-family:var(--display);font-size:19px;line-height:1.15;margin-top:1px;overflow-wrap:anywhere}
.post .od{font-family:var(--display);font-weight:800;font-size:24px;white-space:nowrap}
.post ul{list-style:none;margin:0;padding:2px 14px 6px}
.post li{display:flex;gap:8px;align-items:baseline;padding:6px 0;border-top:1px solid var(--line);font-size:13.5px}
.post li:first-child{border-top:0}
.post li .lg{flex:1;min-width:0}.post li small{color:var(--mute)}
.post li.hit .lg::before{content:"✓ ";color:var(--good);font-weight:800}.post li.dead .lg::before{content:"✗ ";color:var(--bad);font-weight:800}
.post li.dead{opacity:.6}
.post .pf{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 14px 12px}
.post .pf a,.post .pf button{font:inherit;font-size:12.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border:1px solid var(--line);border-radius:7px;padding:8px 11px;color:var(--ink);background:none;text-decoration:none;cursor:pointer}
.post .pf a.fd{background:#1493ff;border-color:#1493ff;color:#0b0f15}
.post .pf .mini{font-size:11px;text-transform:none;letter-spacing:0;color:var(--mute);border:0;padding:8px 4px}
.post .st{font-size:12px;font-weight:700;color:var(--mute);margin-left:auto}.post .st.win{color:var(--good)}.post .st.live{color:#d7332a}
.post.mine{border-color:#d7332a}
.soc .rules{font-size:12px;color:var(--mute);line-height:1.5;margin-top:18px}
"""

PAGE_JS = r"""<script>(function(){
  var W = __WEEK__, list = document.getElementById('feed'), info = document.getElementById('feedinfo');
  var esc = function(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); };
  var am = function(o){ return o == null ? '' : (o > 0 ? '+' + o : '' + o); };
  var sort = 'top', POSTS = [], MYV = {}, A = null, G = {}, BOX = {}, FIRST = {};
  try { sort = localStorage.getItem('bs_social_sort') || 'top'; } catch(e){}
  function client(cb, n){ n = n || 0; if(window.bsAccount && window.bsAccount.client) return cb(window.bsAccount); if(n > 60){ info.textContent = 'Could not reach the feed - check your connection and reload.'; return; } setTimeout(function(){ client(cb, n + 1); }, 150); }
  function legText(l){
    if(l.gl) return esc(l.pl) + ' <small>' + esc(l.m === 'Total' ? 'game total' : l.m.toLowerCase()) + '</small>';
    if(/TD$/.test(l.m)) return esc(l.pl) + ' <small>' + esc(l.m.toLowerCase()) + '</small>';
    if(/^Under /.test(l.m)) return esc(l.pl) + ' <small>' + esc((l.ms || l.m.slice(6)).toLowerCase()) + ' under ' + l.ln + '</small>';
    return esc(l.pl) + ' <small>' + esc((l.ms || l.m).toLowerCase()) + ' ' + Math.round(l.ln) + '+</small>';
  }
  // owner 10/29 ("Halloween weekend parlay isn't loading on FanDuel"): a post freezes each leg's FanDuel market / selection ids at post time, and
  // FanDuel re-issues player-prop markets during the week (new ids) - one dead id and addToBetslip loads nothing. So every render re-resolves each
  // leg by its key (player|market|line) against the latest odds pull (FDMAP, embedded at build time, refreshed every rebuild) and only falls back
  // to the frozen ids when the leg is no longer in the pull. The slip bar says when some legs could not be re-priced.
  var FDMAP = window.__BS_FDMAP || {};
  function fdIds(l){ var f = l.k && FDMAP[l.k]; if(f) return {m: f[0], s: f[1], fresh: true}; return l.fd && l.fd.m && l.fd.s ? {m: l.fd.m, s: l.fd.s, fresh: false} : null; }
  function fdUrl(ls){ var ok = ls.map(function(l){ return (l.ko && Date.now() >= l.ko) ? null : fdIds(l); }).filter(Boolean); if(!ok.length) return null;
    return 'https://sportsbook.fanduel.com/addToBetslip?' + ok.map(function(f, i){ return 'marketId[' + i + ']=' + encodeURIComponent(f.m) + '&selectionId[' + i + ']=' + encodeURIComponent(f.s); }).join('&'); }
  function ago(t){ var m = Math.round((Date.now() - new Date(t).getTime()) / 6e4); return m < 60 ? m + 'm ago' : m < 1440 ? Math.round(m / 60) + 'h ago' : Math.round(m / 1440) + 'd ago'; }
  function render(){
    var me = A && A.user ? A.user.id : null;
    var ps = POSTS.slice().sort(sort === 'new' ? function(a, b){ return new Date(b.created_at) - new Date(a.created_at); }
                                              : function(a, b){ return (b.score - a.score) || (new Date(b.created_at) - new Date(a.created_at)); });
    if(!ps.length){ list.innerHTML = '<div class="empty">No open slips right now. Build one in the <a href="/build/">Parlay Builder</a> and tap <b>Post to Social</b> - the first post of the week sits at the top.</div>'; return; }
    list.innerHTML = ps.map(function(p){
      var ls = p.legs || [], url = fdUrl(ls), started = ls.some(function(l){ return l.ko && Date.now() >= l.ko; });
      return '<article class="post' + (p.user_id === me ? ' mine' : '') + '" id="p' + p.id + '" data-id="' + p.id + '">' +
        '<div class="ph"><button type="button" class="vote' + (MYV[p.id] ? ' on' : '') + '" data-v="' + p.id + '" aria-pressed="' + !!MYV[p.id] + '" aria-label="Upvote"><i>▲</i><b>' + p.score + '</b></button>' +
        '<div class="who"><b>@' + esc(p.handle) + '</b>' + (p.title ? '<span class="t">' + esc(p.title) + '</span>' : '') + '<small>' + ls.length + ' leg' + (ls.length > 1 ? 's' : '') + ' · ' + ago(p.created_at) + '</small></div>' +
        '<div class="od">' + esc(am(p.fd_odds)) + '</div></div>' +
        '<ul>' + ls.map(function(l, i){ return '<li data-i="' + i + '"><span class="lg">' + legText(l) + '</span><small>' + esc(am(l.o)) + '</small></li>'; }).join('') + '</ul>' +
        '<div class="pf">' + (url ? '<a class="fd" href="' + url + '" target="_blank" rel="noopener">Tail on FanDuel' + (function(){ var n = ls.filter(function(l){ return fdIds(l) && !(l.ko && Date.now() >= l.ko); }).length; return n < ls.length ? ' <small>(' + n + ' of ' + ls.length + ' legs - add the rest by hand)</small>' : ''; })() + '</a>' : '') +
        (!started ? '<button type="button" data-load="' + p.id + '">Load into my slip</button>' : '') +
        (p.user_id === me ? '<button type="button" class="mini" data-del="' + p.id + '">Delete</button>' : (me ? '<button type="button" class="mini" data-rep="' + p.id + '">Report</button>' : '')) +
        '<a class="open" href="/b/?p=' + p.id + '">Open slip →</a><span class="st" data-st="' + p.id + '">' + (started ? 'Live' : 'Kicks off ' + new Date(p.first_ko).toLocaleString([], {weekday: 'short', hour: 'numeric', minute: '2-digit'})) + '</span></div></article>';
    }).join('');
    grade();
    if(location.hash){ var el = document.getElementById(location.hash.slice(1)); if(el) el.scrollIntoView({block: 'center'}); }
  }
  function load(){
    var since = new Date(Date.now() - 4.5 * 36e5).toISOString();
    A.client.from('feed_posts').select('id,user_id,handle,title,week,legs,fd_odds,first_ko,last_ko,score,created_at').eq('status', 'open').gte('last_ko', since)
      .order('score', {ascending: false}).order('created_at', {ascending: false}).limit(150).then(function(r){
        if(r.error){ info.textContent = /relation|does not exist/i.test(r.error.message) ? 'Social is being set up - check back soon.' : 'Could not load the feed (' + r.error.message + ').'; list.innerHTML = ''; return; }
        POSTS = (r.data || []).map(function(p){ (p.legs || []).forEach(function(l){ if(l.ko) l.ko = +l.ko; }); return p; });
        info.textContent = POSTS.length + ' open slip' + (POSTS.length === 1 ? '' : 's') + ' · sorted by ' + (sort === 'new' ? 'newest' : 'upvotes');
        var me = A.user ? A.user.id : null;
        if(!me || !POSTS.length){ MYV = {}; render(); return; }
        A.client.from('feed_votes').select('post_id').eq('user_id', me).in('post_id', POSTS.map(function(p){ return p.id; })).then(function(v){ MYV = {}; (v.data || []).forEach(function(x){ MYV[x.post_id] = 1; }); render(); });
      });
  }
  function needSignIn(){ var s = document.querySelector('#bsacct button'); if(s) s.click(); }
  list.addEventListener('click', function(e){
    if(!e.target.closest('button, a, input') && (e.target.closest('.post .who') || e.target.closest('.post ul'))){ var art = e.target.closest('article.post'); if(art){ location.href = '/b/?p=' + art.dataset.id; return; } }
    var v = e.target.closest('[data-v]'), ld = e.target.closest('[data-load]'), del = e.target.closest('[data-del]'), rep = e.target.closest('[data-rep]');
    if(v){ if(!A.user){ needSignIn(); return; } var id = +v.dataset.v, p = POSTS.filter(function(x){ return x.id === id; })[0]; if(!p) return; v.disabled = true;
      var q = MYV[id] ? A.client.from('feed_votes').delete().eq('post_id', id).eq('user_id', A.user.id) : A.client.from('feed_votes').insert({post_id: id});
      q.then(function(r){ v.disabled = false; if(r.error) return; if(MYV[id]){ delete MYV[id]; p.score = Math.max(0, p.score - 1); } else { MYV[id] = 1; p.score++; }
        v.classList.toggle('on', !!MYV[id]); v.setAttribute('aria-pressed', !!MYV[id]); v.querySelector('b').textContent = p.score; }); return; }
    if(ld){ var p2 = POSTS.filter(function(x){ return x.id === +ld.dataset.load; })[0]; if(!p2) return;
      try { localStorage.setItem('bs_slipk_w' + W, JSON.stringify(p2.legs.map(function(l){ return l.k; }))); localStorage.removeItem('bs_slip_w' + W); } catch(err){}
      location.href = '/build/'; return; }
    if(del){ if(!confirmInline(del, 'Delete?')) return; A.client.from('feed_posts').delete().eq('id', +del.dataset.del).then(function(r){ if(!r.error){ POSTS = POSTS.filter(function(x){ return x.id !== +del.dataset.del; }); render(); } }); return; }
    if(rep){ if(!confirmInline(rep, 'Report?')) return; A.client.from('feed_reports').insert({post_id: +rep.dataset.rep}).then(function(){ rep.textContent = 'Reported'; rep.disabled = true; }); }
  });
  function confirmInline(b, q){ if(b.dataset.armed) return true; b.dataset.armed = 1; var t = b.textContent; b.textContent = q + ' tap again'; setTimeout(function(){ delete b.dataset.armed; if(!b.disabled) b.textContent = t; }, 3000); return false; }
  document.querySelectorAll('.soc .seg button').forEach(function(b){ b.classList.toggle('on', b.dataset.s === sort); b.addEventListener('click', function(){ sort = b.dataset.s; try { localStorage.setItem('bs_social_sort', sort); } catch(e){}
    document.querySelectorAll('.soc .seg button').forEach(function(x){ x.classList.toggle('on', x === b); }); info.textContent = POSTS.length + ' open slips · sorted by ' + (sort === 'new' ? 'newest' : 'upvotes'); render(); }); });
  // ---- live grading (same rules as the home page's promoted bets): a slip leaves the feed when a leg loses or every game is over ----
  var ESPN = {WSH: 'WAS', LAR: 'LA'}; function ab(x){ return ESPN[x] || x; }
  function norm(n){ return String(n || '').toLowerCase().replace(/\./g, '').replace(/\s+(jr|sr|ii|iii|iv|v)$/, '').replace(/[^a-z ]/g, '').replace(/\s+/g, ' ').trim(); }
  function num(v){ var m = String(v == null ? '' : v).match(/-?\d+(\.\d+)?/); return m ? +m[0] : 0; }
  function parseBox(js, gid){ try {
    (js.boxscore.players || []).forEach(function(tm){ (tm.statistics || []).forEach(function(cat){ var keys = cat.keys || cat.labels || [];
      (cat.athletes || []).forEach(function(a){ var n = norm(a.athlete && (a.athlete.displayName || a.athlete.shortName)); if(!n) return;
        var r = BOX[n] = BOX[n] || {pass: 0, rush: 0, rec: 0, recy: 0, long: 0, td: 0}; var S = {}; keys.forEach(function(k, i){ S[k] = a.stats[i]; });
        if(cat.name === 'passing') r.pass = num(S.passingYards != null ? S.passingYards : S.YDS);
        if(cat.name === 'rushing'){ r.rush = num(S.rushingYards != null ? S.rushingYards : S.YDS); r.td += num(S.rushingTouchdowns != null ? S.rushingTouchdowns : S.TD); }
        if(cat.name === 'receiving'){ r.rec = num(S.receptions != null ? S.receptions : S.REC); r.recy = num(S.receivingYards != null ? S.receivingYards : S.YDS); r.long = Math.max(r.long, num(S.longReception != null ? S.longReception : S.LONG)); r.td += num(S.receivingTouchdowns != null ? S.receivingTouchdowns : S.TD); }
      }); }); });
    var sp = (js.scoringPlays || []).filter(function(p){ return (p.type && /touchdown/i.test(p.type.text || '')) || /\bTD\b|touchdown/i.test(p.text || ''); });
    if(sp.length){ var m = (sp[0].text || '').match(/^([A-Z][\w.'-]+(?:\s[A-Z][\w.'-]+){0,3}?)\s+\d+\s+(?:Yd|Yard)/i); FIRST[gid] = m ? norm(m[1]) : '?'; }
  } catch(e){} }
  function gradeLeg(l){
    if(/^Under /.test(l.m)){ var s0 = gradeLeg(Object.assign({}, l, {m: l.m.slice(6), ln: Math.floor(l.ln) + 1})); return s0 === 'hit' ? 'dead' : s0 === 'dead' ? 'hit' : s0; }   // unders: the other side of the (X+1)+ over
    var g = G[l.g]; if(!g || g.st === 'pre') return 'open'; var fin = g.st === 'post';
    if(l.gl){ var sa = +g.sa || 0, sb = +g.sb || 0, tot = sa + sb, x = l.gl, ln = +l.ln || 0;
      if(x.k !== 'M'){ var over = String(x.side).toUpperCase() === 'OVER'; return over ? (tot > ln ? 'hit' : fin ? 'dead' : 'open') : (tot > ln ? 'dead' : fin ? 'hit' : 'open'); }
      if(!fin) return 'open'; var me = x.side === g.a ? sa : sb, them = x.side === g.a ? sb : sa; return (me - them + (l.m === 'Moneyline' ? 0 : ln)) > 0 ? 'hit' : 'dead'; }
    var r = BOX[norm(l.pl)];
    if(l.m === 'First TD'){ var f = FIRST[l.g]; if(!f) return fin ? 'dead' : 'open'; return f === norm(l.pl) ? 'hit' : 'dead'; }
    if(/TD$/.test(l.m)){ var needT = l.m === '2+ TD' ? 2 : l.m === '3+ TD' ? 3 : 1; if(r && r.td >= needT) return 'hit'; return fin && r ? 'dead' : 'open'; }
    if(!r) return 'open';
    var v = l.m === 'Passing Yards' ? r.pass : l.m === 'Rushing Yards' ? r.rush : l.m === 'Receiving Yards' ? r.recy : l.m === 'Receptions' ? r.rec : l.m === 'Longest Reception' ? r.long : l.m === 'Rush + Rec Yards' ? r.rush + r.recy : null;
    if(v == null) return 'open'; return v >= Math.round(l.ln) ? 'hit' : (fin ? 'dead' : 'open');
  }
  function grade(){
    POSTS.forEach(function(p){ var card = document.getElementById('p' + p.id); if(!card) return; var dead = null, hits = 0, allFin = true;
      (p.legs || []).forEach(function(l, i){ var s = gradeLeg(l), li = card.querySelector('li[data-i="' + i + '"]'); if(li){ li.classList.toggle('hit', s === 'hit'); li.classList.toggle('dead', s === 'dead'); }
        if(s === 'hit') hits++; if(s === 'dead' && !dead) dead = l; if(!G[l.g] || G[l.g].st !== 'post') allFin = false; });
      var st = card.querySelector('[data-st]');
      if(dead || allFin && (p.legs || []).length){ card.hidden = true; return; }   // owner rule: off the feed once it loses or every leg's game is over
      if(st && (p.legs || []).some(function(l){ return G[l.g] && G[l.g].st !== 'pre'; })){ st.textContent = 'Live · ' + hits + '/' + p.legs.length + ' hit'; st.className = 'st live'; }
    });
    var shown = POSTS.filter(function(p){ var c = document.getElementById('p' + p.id); return c && !c.hidden; }).length;
    if(POSTS.length && !shown) list.insertAdjacentHTML('beforeend', '<div class="empty">Every open slip has settled. Post the next one from the <a href="/build/">Parlay Builder</a>.</div>');
  }
  var busy = false;
  function ymd(t){ var d = new Date(t); return d.getFullYear() + String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0'); }
  function poll(){
    var legs = []; POSTS.forEach(function(p){ (p.legs || []).forEach(function(l){ legs.push(l); }); });
    var now = Date.now(), live = legs.filter(function(l){ return l.ko && now >= l.ko - 9e5; }); if(busy || !live.length) return; busy = true;
    var t0 = Math.min.apply(null, live.map(function(l){ return l.ko; })), t1 = Math.max.apply(null, live.map(function(l){ return l.ko; }));
    fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=' + ymd(t0 - 864e5) + '-' + ymd(t1 + 864e5), {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(js){
      if(!js){ busy = false; return; } var want = {}; live.forEach(function(l){ want[l.g] = 1; });
      (js.events || []).forEach(function(ev){ var c = (ev.competitions || [])[0]; if(!c) return; var by = {}; (c.competitors || []).forEach(function(x){ by[ab(x.team && x.team.abbreviation)] = x.score; });
        Object.keys(want).forEach(function(gid){ var p = gid.split('-'); if(!(p[0] in by) || !(p[1] in by)) return; var ty = ((ev.status || c.status || {}).type) || {};
          G[gid] = {eid: ev.id, st: ty.state || 'pre', a: p[0], b: p[1], sa: by[p[0]], sb: by[p[1]]}; }); });
      var on = Object.keys(G).filter(function(gid){ return G[gid].st !== 'pre'; });
      return Promise.all(on.map(function(gid){ return fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=' + G[gid].eid, {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(s){ if(s) parseBox(s, gid); }).catch(function(){}); }));
    }).then(function(){ busy = false; grade(); }).catch(function(){ busy = false; });
  }
  client(function(acc){ A = acc; load(); setInterval(poll, 60000); setTimeout(poll, 1500); setInterval(load, 180000); });
  document.addEventListener('bs-account', function(){ if(A) load(); });
})();</script>"""

def fdmap():
    """leg key (player|market|rounded line, same as the builder's legKey) -> [marketId, selectionId] from the latest odds pull (out/builder_data.json)."""
    import os, math
    try: legs = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "builder_data.json")))["legs"]
    except Exception as e: print("note: social page has no fresh FanDuel id map:", e); return {}
    m = {}
    for l in legs:
        fd = l.get("fd") or {}
        if not (fd.get("m") and fd.get("s")): continue
        try: ln = float(l.get("ln") or 1)
        except Exception: ln = 1.0
        k = f"{l['pl']}|{l['m']}|{int(math.floor((ln or 1) + 0.5))}"
        m.setdefault(k, [fd["m"], fd["s"]])
    return m

def page(week):
    return (f"""<title>BetSweep Social</title>
<script>window.__BS_FDMAP = {json.dumps(fdmap(), separators=(",", ":"))};</script>
<meta name="description" content="Betslips posted by BetSweep users - tail them on FanDuel, upvote the best ones. Slips leave the feed once a leg loses or the games end.">
__BASE__
<style>__BASECSS__{PAGE_CSS}</style>
<div class="soc">
 <h1>Social</h1>
 <p class="lede">Slips posted by BetSweep users this week. Upvote the ones you like - the most-upvoted sit on top. Tail on FanDuel in one tap, or load a slip into the Parlay Builder to see the model's price. A slip comes down on its own once a leg loses or every game in it is over.</p>
 <div class="bar"><a class="pri" href="/build/">+ Post a slip</a><span class="seg"><button type="button" data-s="top">Top</button> <button type="button" data-s="new">New</button></span></div>
 <p class="lede" id="feedinfo">Loading…</p>
 <div id="feed"></div>
 <p class="rules">Posted slips are users' own picks, not BetSweep's, and are not checked by the model. Sign in to post, upvote or report; a post with three reports is hidden for review. No harassment, spam, ads or personal info - see the <a href="/terms/">Terms</a>. 21+. Bet only what you can afford to lose; 1-800-GAMBLER.</p>
</div>
""" + PAGE_JS.replace("__WEEK__", json.dumps(int(week))))
