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
    // a slip read from a screenshot on Social (bs_postnow): the price on the picture is offered only while the slip is exactly those legs
    try{ var pn = JSON.parse(sessionStorage.getItem('bs_postnow') || 'null'), ks = ls.map(function(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); }).sort();
      if(pn && pn.odds && Date.now() - (+pn.t || 0) < 30 * 60e3 && !$('sdO').value && pn.keys && pn.keys.length === ks.length && pn.keys.every(function(k, i){ return k === ks[i]; })) $('sdO').value = (pn.odds > 0 ? '+' : '') + pn.odds; }catch(e){}
    if(!A || !A.client){ alertish('Accounts are not available right now.'); return; }
    if(!A.user){ var s = document.querySelector('#bsacct button'); if(s) s.click(); return; }   // opens the sign-in dialog
    var started = ls.filter(function(l){ return window.bsGameKo && window.bsGameKo(l.g) && Date.now() >= window.bsGameKo(l.g); });
    msg(started.length ? 'Remove the legs from games that already kicked off first.' : '', !!started.length);
    $('sdH').textContent = '…'; A.client.from('feed_profiles').select('handle').eq('user_id', A.user.id).then(function(q){ var h = q && q.data && q.data[0] && q.data[0].handle;   // 11/16: the name the account chose (sql/social_v4.sql), else the assigned one
      if(h){ $('sdH').textContent = '@' + h; return; } return A.client.rpc('feed_handle', {u: A.user.id}).then(function(r){ $('sdH').textContent = r.data ? '@' + r.data : '(assigned when you post)'; }); }, function(){ $('sdH').textContent = '(assigned when you post)'; });
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
    var A = window.bsAccount, ls = legsNow(); if(ls.length > 25){ msg('Social posts take up to 25 legs - this slip has ' + ls.length + '.', true); return; } var h = ($('sdH').textContent || '').replace(/^@/, ''), t = $('sdT').value.trim(), o = $('sdO').value.trim().replace(/[^0-9+-]/g, '');
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
      if(r.error){ var em = r.error.message || '', ec = r.error.code || ''; msg((ec === '42P01' || ec === 'PGRST205') ? 'Social is still being set up - try again soon.' : /title_check/.test(em) ? 'That title is too long (60 characters max).' : /legs_check/.test(em) ? 'Social posts take 1 to 25 legs.' : /fd_odds_check/.test(em) ? 'That price looks off - check the odds.' : 'Could not post: ' + em + (ec ? ' (' + ec + ')' : ''), true); try{ console.error('feed post', r.error); }catch(e){} return; }
      msg('Posted! Opening Social…'); setTimeout(function(){ location.href = '/social/#p' + ((r.data && r.data[0] && r.data[0].id) || ''); }, 600);
    });
  });
})();</script>"""

# ---------------- /social/ page ----------------
PAGE_CSS = """.soc .house{margin:0 0 14px} .soc .house .lab{display:block;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--mute);margin:0 0 8px}
.soc .hcard{background:var(--card);border:2px solid var(--red);border-radius:14px;padding:14px 14px 12px;margin:0 0 12px}
.soc .hcard header{display:flex;align-items:center;gap:10px} .soc .hcard header b{display:block;font-weight:700;font-size:16px;line-height:1.1;color:var(--ink)} .soc .hcard header span{display:block;color:var(--mute);font-size:12.5px;margin-top:2px}
.soc .hcard .av{flex:none;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:var(--red);color:#fff;font-family:var(--display);font-weight:700;font-size:14px;font-style:normal}
.soc .hcard h3{font-family:var(--display);font-weight:800;font-size:22px;line-height:1.1;margin:12px 0 6px;color:var(--ink)}
.soc .hcard ul{list-style:none;margin:0;padding:0} .soc .hcard li{display:flex;align-items:center;gap:9px;padding:9px 0;border-top:1px solid var(--line);font-size:14.5px;line-height:1.25;color:var(--ink)}
.soc .hcard li em{margin-left:auto;font-family:var(--display);font-weight:700;font-size:16px;font-style:normal}
.soc .hcard li.more{display:block} .soc .hcard li.more summary{cursor:pointer;color:var(--mute);font-weight:600;font-size:13.5px} .soc .hcard li.more ul{margin-top:6px}
.soc .hcard .dot{flex:none;width:10px;height:10px;border-radius:50%;border:2px solid var(--line)}
.soc .hfoot{display:flex;align-items:baseline;gap:10px;border-top:1px solid var(--line);padding-top:10px} .soc .hfoot .px{font-family:var(--display);font-weight:800;font-size:34px;line-height:1;color:var(--ink)} .soc .hfoot .meta{color:var(--mute);font-size:12.5px}
.soc .hacts{display:flex;gap:8px;margin-top:12px} .soc .hacts a{border-radius:10px;padding:12px;font-family:var(--display);font-weight:700;font-size:14px;letter-spacing:.08em;text-transform:uppercase;border:1.5px solid var(--ink);color:var(--ink);text-decoration:none;text-align:center} .soc .hacts a.tail{flex:1;background:var(--red);border-color:var(--red);color:#fff}
.soc .skel{display:block;height:92px;border-radius:14px;margin:0 0 10px;background:linear-gradient(90deg,var(--card) 25%,var(--line) 50%,var(--card) 75%);background-size:200% 100%;animation:bsskel 1.2s ease-in-out infinite} @keyframes bsskel{0%{background-position:200% 0}100%{background-position:-200% 0}} @media (prefers-reduced-motion:reduce){.soc .skel{animation:none}}
.soc a:active,.soc button:active{transform:scale(.98)}
.sharps h2{font-family:var(--display);font-size:22px;margin:4px 0 2px} .sharps ol{list-style:none;margin:8px 0 10px;padding:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--card)}
.sharps li{display:grid;grid-template-columns:28px minmax(0,1fr) auto;align-items:center;gap:10px;padding:10px 14px;border-top:1px solid var(--line)} .sharps li:first-child{border-top:0}
.sharps .rk{font-family:var(--display);font-weight:800;font-size:18px;color:var(--mute);text-align:center} .sharps li:nth-child(-n+3) .rk{color:var(--red)}
.sharps .who b{font-size:15px} .sharps .who small{display:block;color:var(--mute);font-size:12px;margin-top:1px}
.sharps .cv{text-align:right} .sharps .cv b{display:block;font-family:var(--display);font-size:20px;font-weight:800} .sharps .cv small{color:var(--mute);font-size:11px}
.sharps li.up .cv b{color:var(--good)} .sharps li.dn .cv b{color:var(--bad)}
.shp{display:inline-block;margin-left:6px;padding:1px 7px;border-radius:999px;font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;vertical-align:2px;background:color-mix(in srgb,var(--good) 18%,transparent);color:var(--good)}

.soc{max-width:760px;margin:0 auto;padding:6px 0 40px}
.soc h1{font-family:var(--display);font-size:32px;margin:16px 0 2px;letter-spacing:.02em}
.soc .lede{color:var(--mute);font-size:13.5px;line-height:1.5;margin:0 0 12px}
.soc .bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 12px}
.soc .bar a,.soc .bar button{font:inherit;font-weight:700;font-size:13px;padding:9px 13px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--ink);text-decoration:none;cursor:pointer}
.soc .bar a.pri{background:#d7332a;border-color:#d7332a;color:#fff}
.soc .bar .seg button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.soc .empty{padding:26px 16px;text-align:center;color:var(--mute);border:1px dashed var(--line);border-radius:12px}
.soc .empty b{display:block;font-family:var(--display);font-size:20px;color:var(--ink);margin-bottom:4px} .soc .empty .act{display:inline-block;margin-top:14px;background:var(--red);color:#fff;font-weight:700;text-decoration:none;border-radius:10px;padding:12px 18px}
.post .av,.soc .prof .av{flex:none;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-family:var(--display);font-weight:700;font-size:13px;font-style:normal;color:#fff;letter-spacing:.02em}
.av.c0{background:#c2410c}.av.c1{background:#0f766e}.av.c2{background:#1d4ed8}.av.c3{background:#7e22ce}.av.c4{background:#be123c}.av.c5{background:#4d7c0f}.av.c6{background:#b45309}.av.c7{background:#334155}
.post .who b.h{cursor:pointer;text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px} .post .who .rec{display:inline-block;margin-left:7px;font-size:12px;font-weight:700;color:var(--mute);font-variant-numeric:tabular-nums}
.post .rx{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:4px 14px 2px} .post .rx button{display:inline-flex;align-items:center;gap:5px;min-height:36px;min-width:44px;justify-content:center;border:1px solid var(--line);border-radius:999px;background:none;color:var(--ink);font:inherit;font-size:14px;padding:4px 10px;cursor:pointer}
.post .rx button i{font-style:normal} .post .rx button b{font-size:12.5px;font-variant-numeric:tabular-nums} .post .rx button.on{border-color:var(--ink);background:color-mix(in srgb,var(--ink) 10%,transparent)} .post .rx .tn{margin-left:auto;font-size:12.5px;color:var(--mute);font-weight:600}
.post .pf button.tl.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.av.em{font-size:17px;letter-spacing:0} .av.big.em{font-size:27px}
.soc .pedit{grid-column:1 / -1;border-top:1px solid var(--line);padding-top:12px;margin-top:2px} .soc .pedit label[for]{display:block;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin-bottom:4px}
.soc .pedit input#peh{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:11px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.soc .pedit .hint{margin:5px 0 10px;font-size:12.5px;color:var(--mute)} .soc .pedit fieldset{border:0;padding:0;margin:0 0 10px} .soc .pedit legend{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);padding:0;margin-bottom:6px}
.soc .pedit .sw,.soc .pedit .em{display:flex;flex-wrap:wrap;gap:8px} .soc .pedit .sw label,.soc .pedit .em label{position:relative;cursor:pointer} .soc .pedit input[type=radio]{position:absolute;opacity:0;inset:0;margin:0;cursor:pointer}
.soc .pedit .sw i{display:block;width:40px;height:40px;border-radius:50%;border:3px solid transparent} .soc .pedit .sw input:checked + i{border-color:var(--ink)} .soc .pedit .sw input:focus-visible + i,.soc .pedit .em input:focus-visible + i{outline:2px solid var(--red);outline-offset:2px}
.soc .pedit .em i{display:grid;place-items:center;width:44px;height:44px;border-radius:10px;border:1px solid var(--line);font-style:normal;font-size:22px;color:var(--ink)} .soc .pedit .em input:checked + i{border-color:var(--ink);background:color-mix(in srgb,var(--ink) 12%,transparent)}
.soc .pedit .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)} .soc .pedit .msg{min-height:18px;margin:4px 0 8px;font-size:13.5px;color:var(--mute)} .soc .pedit .msg.err{color:var(--bad);font-weight:700}
.soc .pedit .pbtn{display:flex;gap:8px} .soc .pedit .pbtn button{font:inherit;font-weight:700;font-size:14px;min-height:44px;padding:0 18px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer} .soc .pedit .pbtn .sv{background:var(--red);border-color:var(--red);color:#fff}
.soc .gfbar{margin:0 0 10px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font-size:14px;display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline} .soc .gfbar a{margin-left:auto;color:var(--ink);font-weight:700}
.soc a.back{display:inline-block;margin:0 0 10px;color:var(--ink);font-weight:700;font-size:14px;text-decoration:none;padding:8px 0}
.soc .prof{display:grid;grid-template-columns:auto 1fr auto;gap:10px 12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:0 0 14px}
.soc .prof .av.big{width:52px;height:52px;font-size:19px} .soc .prof h2{margin:0;font-family:var(--display);font-size:22px;color:var(--ink);overflow-wrap:anywhere} .soc .prof .pn p{margin:2px 0 0;color:var(--mute);font-size:13px}
.soc .prof .fol{font:inherit;font-weight:700;font-size:13.5px;min-height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--red);background:var(--red);color:#fff;cursor:pointer} .soc .prof .fol.on{background:none;color:var(--ink);border-color:var(--line)}
.soc .prof .pstats{grid-column:1 / -1;display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:4px 0 0} .soc .prof .pstats div{border:1px solid var(--line);border-radius:10px;padding:8px 10px} .soc .prof dt{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--mute);font-weight:700} .soc .prof dd{margin:2px 0 0;font-family:var(--display);font-weight:800;font-size:24px;color:var(--ink)} .soc .prof dd.up{color:var(--good)} .soc .prof dd.dn{color:var(--bad)}
.soc .prof .pnote{grid-column:1 / -1;margin:0;color:var(--mute);font-size:12.5px}
.soc h2.sec{font-family:var(--display);font-size:20px;margin:22px 0 10px;color:var(--ink)}
.soc details.bust{margin:6px 0 12px} .soc details.bust summary{cursor:pointer;color:var(--mute);font-weight:700;font-size:14px;padding:12px 2px;min-height:44px} .soc details.bust[open] summary{margin-bottom:6px}
.post.over.busted{opacity:.78} .post.over.cashed{border-color:var(--good)}
.post .pf .res{font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:.02em;color:var(--mute);margin-right:auto} .post .pf .res.won{color:var(--good)} .post .pf .res.lost{color:var(--bad)}
.soc .hcard li.hit .dot{background:var(--good);border-color:var(--good)} .soc .hcard li.dead .dot{background:var(--bad);border-color:var(--bad)} .soc .hcard li.dead{opacity:.6}
.soc .hcard .hst{color:var(--mute);font-size:13px} .soc .hcard .hst.live{color:var(--ink);font-weight:700} .soc .hcard .hst.cashed{color:var(--good);font-weight:800} .soc .hcard .hst.busted{color:var(--bad);font-weight:800}
.soc .house[hidden],.soc .hcard[hidden]{display:none} .soc .bar .seg{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;max-width:100%} .soc .bar .seg::-webkit-scrollbar{display:none} .soc .bar .seg button{flex:none} .soc .hcard.over{border-color:var(--line)} .soc .hcard a[hidden]{display:none}
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
  var sort = 'top', POSTS = [], MYV = {}, A = null, G = {}, BOX = {}, FIRST = {}, SUMOK = {};
  // alpha step 2 (11/16, after the owner ran sql/social_v3.sql): people. V3 turns false if the database does not have the new columns,
  // and the page then behaves exactly as before.
  var V3 = true, PROF = {}, REC = {}, MYT = {}, MYRX = {}, FOL = {}, VIEW = null, UPOSTS = null;
  // alpha step 5 (11/16): a game card on Boards links here with #g=<game>; the feed then shows only slips with a leg in that game
  var GF = (function(){ var m = location.hash.match(/^#g=([A-Z]{2,3}-[A-Z]{2,3})$/); return m ? m[1] : null; })();
  function inGame(p){ if(!GF) return true; var alt = GF.split('-').reverse().join('-'); return (p.legs || []).some(function(l){ return l.g === GF || l.g === alt; }); }
  function gfBar(){ return GF ? '<p class="gfbar">Slips with a leg in <b>' + esc(GF.replace('-', ' vs ')) + '</b> <a href="#" data-go="allgames">Show every game</a></p>' : ''; }
  var COLS = 'id,user_id,handle,title,week,legs,fd_odds,first_ko,last_ko,score,created_at', COLS3 = COLS + ',tails,rx,result,units';
  var RXK = [['fire', '🔥', 'Fire'], ['lock', '🔒', 'Lock'], ['fade', '👎', 'Fade'], ['rip', '🪦', 'RIP']];
  function hcol(p){ var q = PROF[p.user_id]; if(q) return q.color; var h = 0, t = String(p.handle || ''); for(var i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) % 8; return h; }
  function inits(h){ var m = String(h || '').match(/[A-Z]/g) || []; return (m.slice(0, 2).join('') || String(h || '?').slice(0, 2)).toUpperCase(); }
  // alpha 11/16 (owner: "make it so users can create their own username and avatar"): sql/social_v4.sql. V4 turns false if it has not been run.
  var V4 = true, EDIT = false, EMOJI = ['🏈','🔥','🔒','💰','🎯','🚀','🐐','👑','💎','🍀','⚡','🧠','🎲','🦅','🐻','🦁','🐯','🐬','🐴','🏴‍☠️','🤠','😎','🥶','🤑'];
  function av(p, big){ var q = PROF[p.user_id] || {}; return '<i class="av' + (big ? ' big' : '') + ' c' + hcol(p) + (q.emoji ? ' em' : '') + '" aria-hidden="true">' + (q.emoji ? esc(q.emoji) : esc(inits(p.handle))) + '</i>'; }
  function profs(ids){ return A.client.from('feed_profiles').select(V4 ? 'user_id,handle,color,emoji' : 'user_id,handle,color').in('user_id', ids).then(function(r){
      if(r.error && V4){ V4 = false; return profs(ids); } (r.data || []).forEach(function(x){ PROF[x.user_id] = x; }); }); }
  function recTxt(uid){ var r = REC[uid]; if(!r || !r.graded) return ''; var u = +r.units || 0; return r.won + '-' + r.lost + ' · ' + (u >= 0 ? '+' : '') + u.toFixed(1) + 'u'; }
  try { sort = localStorage.getItem('bs_social_sort') || 'top'; } catch(e){}
  function client(cb, n){ n = n || 0; if(window.bsAccount && window.bsAccount.client) return cb(window.bsAccount); if(n > 60){ info.textContent = 'Could not reach the feed - check your connection and reload.'; return; } setTimeout(function(){ client(cb, n + 1); }, 150); }
  // owner 11/14 ("Can this show the games? How do we tell what under it's taking?"): every leg names its game
  function gameTxt(l){ return l.g ? ' · ' + esc(String(l.g).replace('-', ' vs ')) : ''; }
  function legText(l){ return legText0(l).replace(/<\/small>$/, gameTxt(l) + '</small>'); }
  function legText0(l){
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
  function fdIds(l){ var f = l.k && ((l.g && FDMAP[l.k + '@' + l.g]) || (l.gl ? null : FDMAP[l.k])); if(f) return {m: f[0], s: f[1], fresh: true}; return l.fd && l.fd.m && l.fd.s ? {m: l.fd.m, s: l.fd.s, fresh: false} : null; }
  function fdUrl(ls){ var ok = ls.map(function(l){ return (l.ko && Date.now() >= l.ko) ? null : fdIds(l); }).filter(Boolean); if(!ok.length) return null;
    return 'https://sportsbook.fanduel.com/addToBetslip?' + ok.map(function(f, i){ return 'marketId[' + i + ']=' + encodeURIComponent(f.m) + '&selectionId[' + i + ']=' + encodeURIComponent(f.s); }).join('&'); }
  function ago(t){ var m = Math.round((Date.now() - new Date(t).getTime()) / 6e4); return m < 60 ? m + 'm ago' : m < 1440 ? Math.round(m / 60) + 'h ago' : Math.round(m / 1440) + 'd ago'; }
  // ---- owner 11/6 sharp leaderboard: every poster ranked by closing-line value - how much better each posted leg's price was than FanDuel's
  // final price before kickoff (data/closing-w<W>.json, the price-moves job's last pull before each game). Beating the close is the earliest
  // reliable sign of a sharp bettor; win-loss records need hundreds of bets to say the same thing. Score = total CLV / (legs + 15), so a
  // handful of lucky legs cannot top the board. Proven sharps (15+ graded legs, positive score) get a badge on their posts.
  var SHARP = null, SHARP_BUSY = false, SHARP_BADGE = {};
  function imp(o){ o = +o; return o > 0 ? 100 / (o + 100) : -o / (-o + 100); }
  function closeKeys(l){ var ln = +l.ln, out = [], m = String(l.m || '').toLowerCase(), pl = String(l.pl || '').toLowerCase();
    [String(l.ln), String(Math.round(ln)), ln % 1 ? ln.toFixed(1) : String(ln)].forEach(function(x){ var k = pl + '|' + m + '|' + x; if(out.indexOf(k) < 0) out.push(k); }); return out; }
  function sharpLoad(cb){
    if(SHARP){ cb && cb(); return; } if(SHARP_BUSY){ setTimeout(function(){ sharpLoad(cb); }, 400); return; }
    if(!A || !A.client){ client(function(a){ A = a; sharpLoad(cb); }); return; }   // audit 11/10: the tab could be tapped before the account client loaded (threw on A.client)
    SHARP_BUSY = true;
    A.client.from('feed_posts').select('handle,week,legs,created_at').eq('status', 'open').order('created_at', {ascending: false}).limit(1000).then(function(r){
      var posts = (r && r.data) || [], weeks = {}; posts.forEach(function(p){ if(p.week) weeks[p.week] = 1; });
      return Promise.all(Object.keys(weeks).map(function(w){ return fetch('/data/closing-w' + w + '.json', {cache: 'no-cache'}).then(function(x){ return x.ok ? x.json() : null; }).catch(function(){ return null; })
        .then(function(j){ return [w, (j && j.rows) || {}]; }); })).then(function(cl){
        var C = {}; cl.forEach(function(x){ C[x[0]] = x[1]; }); var H = {};
        posts.forEach(function(p){ var rows = C[p.week] || {}, h = H[p.handle] || (H[p.handle] = {h: p.handle, n: 0, sum: 0, beat: 0, posts: 0, last: p.created_at}), used = false;
          (p.legs || []).forEach(function(l){ if(l.gl || l.o == null) return; var c = null; closeKeys(l).some(function(k){ c = rows[k]; return !!c; }); if(!c || c.o == null) return;
            var d = (imp(c.o) - imp(l.o)) * 100; h.n++; h.sum += d; if(d > 0.05) h.beat++; used = true; });
          if(used) h.posts++; });
        SHARP = Object.keys(H).map(function(k){ var x = H[k]; x.avg = x.n ? x.sum / x.n : 0; x.score = x.sum / (x.n + 15); return x; }).filter(function(x){ return x.n >= 5; }).sort(function(a, b){ return b.score - a.score; });
        SHARP_BADGE = {}; SHARP.filter(function(x){ return x.n >= 15 && x.score > 0.3; }).slice(0, 5).forEach(function(x){ SHARP_BADGE[x.h] = 1; });
        SHARP_BUSY = false; cb && cb(); }); }).catch(function(){ SHARP = []; SHARP_BUSY = false; cb && cb(); });
  }
  function sharps(){
    if(!SHARP){ list.innerHTML = '<div class="empty">Grading every posted leg against FanDuel\'s closing price…</div>'; sharpLoad(function(){ if(sort === 'sharp') sharps(); }); return; }
    info.textContent = 'Closing-line value of every posted leg, this season';
    var me = A && A.user ? A.user.id : null;
    list.innerHTML = '<section class="sharps"><h2>Sharpest posters</h2><p class="lede">Ranked by <b>closing-line value</b>: how much better each posted leg\'s price was than FanDuel\'s last price before kickoff. Beating the close is the earliest reliable sign of a sharp bettor - a win-loss record needs hundreds of bets to say the same thing. Player props only; at least 5 graded legs to be listed.</p>' +
      (SHARP.length ? '<ol>' + SHARP.slice(0, 25).map(function(x, i){ return '<li class="' + (x.avg > 0 ? 'up' : 'dn') + '"><span class="rk">' + (i + 1) + '</span><span class="who"><b>@' + esc(x.h) + '</b>' + (SHARP_BADGE[x.h] ? '<span class="shp">Sharp</span>' : '') + '<small>beat the close on ' + x.beat + ' of ' + x.n + ' legs (' + Math.round(x.beat / x.n * 100) + '%) · ' + x.posts + ' slip' + (x.posts > 1 ? 's' : '') + '</small></span><span class="cv"><b>' + (x.avg >= 0 ? '+' : '') + x.avg.toFixed(1) + '</b><small>pts / leg</small></span></li>'; }).join('') + '</ol>'
        : '<div class="empty">Not enough graded legs yet - closing prices are captured for player props from Week 9 on. Post slips before the lines move to climb this board.</div>') +
      '<p class="rules">CLV = FanDuel\'s closing chance minus the chance in the price when the slip was posted (the BetSweep price at that moment), in points per leg. Game lines are not counted yet.</p></section>';
  }
  // owner 11/16 (alpha, Social step 1 - never empty): a slip no longer disappears when it settles. Every post of the week is loaded,
  // graded on the page, and sorted into open / live (Top and New) or settled (the Cashed tab: winners first, busted slips folded under).
  function stateOf(p, C){ var ls = p.legs || [], dead = 0, hits = 0, fin = ls.length > 0, live = false;
    ls.forEach(function(l){ var s = gradeLeg(l, C); if(s === 'hit') hits++; if(s === 'dead') dead++; var g = (C || CUR).G[l.g]; if(!g || g.st !== 'post') fin = false; if(g && g.st !== 'pre') live = true; });
    return {hits: hits, n: ls.length, st: dead ? 'busted' : (ls.length && hits === ls.length) ? 'cashed' : fin ? 'done' : live ? 'live' : 'open'}; }
  function settled(x){ return x.st === 'busted' || x.st === 'cashed' || x.st === 'done'; }
  function card(p, me, C, old){
    var ls = p.legs || [], x = p.result ? {st: p.result === 'won' ? 'cashed' : p.result === 'lost' ? 'busted' : 'done', hits: p.result === 'won' ? ls.length : 0, n: ls.length, graded: 1} : stateOf(p, C), over = settled(x), url = over || old ? null : fdUrl(ls), started = ls.some(function(l){ return l.ko && Date.now() >= l.ko; });
    var badge = x.st === 'cashed' ? '<span class="res won">Cashed' + (p.units != null ? ' · +' + (+p.units).toFixed(1) + 'u' : '') + '</span>' : x.st === 'busted' ? '<span class="res lost">Busted' + (x.graded ? '' : ' · ' + x.hits + ' of ' + x.n + ' hit') + '</span>' : x.st === 'done' ? '<span class="res">Final · ' + x.hits + ' of ' + x.n + ' graded hits</span>' : '';
    return '<article class="post' + (p.user_id === me ? ' mine' : '') + (over ? ' over ' + x.st : '') + '" id="p' + p.id + '" data-id="' + p.id + '">' +
      '<div class="ph">' + (old ? '' : '<button type="button" class="vote' + (MYV[p.id] ? ' on' : '') + '" data-v="' + p.id + '" aria-pressed="' + !!MYV[p.id] + '" aria-label="Upvote"><i>▲</i><b>' + p.score + '</b></button>') +
      av(p) +
      '<div class="who"><b' + (V3 ? ' class="h" data-u="' + esc(p.user_id) + '" role="link" tabindex="0"' : '') + '>@' + esc(p.handle) + '</b>' + (recTxt(p.user_id) ? '<span class="rec">' + esc(recTxt(p.user_id)) + '</span>' : '') + (SHARP_BADGE[p.handle] ? '<span class="shp" title="Top closing-line value on Social this season">Sharp</span>' : '') + (p.title ? '<span class="t">' + esc(p.title) + '</span>' : '') + '<small>' + ls.length + ' leg' + (ls.length > 1 ? 's' : '') + ' · ' + ago(p.created_at) + '</small></div>' +
      '<div class="od">' + esc(am(p.fd_odds)) + '</div></div>' +
      '<ul>' + ls.map(function(l, i){ var g = gradeLeg(l, C); return '<li data-i="' + i + '"' + (g === 'hit' ? ' class="hit"' : g === 'dead' ? ' class="dead"' : '') + '><span class="lg">' + legText(l) + '</span><small>' + esc(am(l.o)) + '</small></li>'; }).join('') + '</ul>' +
      (V3 && !old ? '<div class="rx">' + RXK.map(function(k){ var n = (p.rx || {})[k[0]] || 0; return '<button type="button" data-rx="' + p.id + '|' + k[0] + '" class="' + (MYRX[p.id] === k[0] ? 'on' : '') + '" aria-pressed="' + (MYRX[p.id] === k[0]) + '" aria-label="' + k[2] + (n ? ', ' + n : '') + '"><i>' + k[1] + '</i>' + (n ? '<b>' + n + '</b>' : '') + '</button>'; }).join('') +
        (p.tails ? '<span class="tn">' + p.tails + ' tailing</span>' : '') + '</div>' : '') +
      '<div class="pf">' + badge + (V3 && !old && !started && !over && p.user_id !== me ? '<button type="button" class="tl' + (MYT[p.id] ? ' on' : '') + '" data-tail="' + p.id + '" aria-pressed="' + !!MYT[p.id] + '">' + (MYT[p.id] ? 'Tailing ✓' : 'I\'m tailing') + '</button>' : '') + (url ? '<a class="fd" href="' + url + '" target="_blank" rel="noopener">Tail on FanDuel' + (function(){ var n = ls.filter(function(l){ return fdIds(l) && !(l.ko && Date.now() >= l.ko); }).length; return n < ls.length ? ' <small>(' + n + ' of ' + ls.length + ' legs - add the rest by hand)</small>' : ''; })() + '</a>' : '') +
      (!started && !old ? '<button type="button" data-load="' + p.id + '">Load into my slip</button>' : '') +
      (old ? '' : (p.user_id === me ? '<button type="button" class="mini" data-del="' + p.id + '">Delete</button>' : (me && !over ? '<button type="button" class="mini" data-rep="' + p.id + '">Report</button>' : ''))) +
      '<a class="open" href="/b/?p=' + p.id + '">Open slip →</a>' + (over ? '' : '<span class="st' + (x.st === 'live' ? ' live' : '') + '">' + (x.st === 'live' ? 'Live · ' + x.hits + '/' + x.n + ' hit' : 'Kicks off ' + new Date(p.first_ko).toLocaleString([], {weekday: 'short', hour: 'numeric', minute: '2-digit'})) + '</span>') + '</div></article>';
  }
  var POSTBTN = '<a class="act" href="/build/">Build a slip and post it</a>';
  function lastWeekHtml(me){
    if(!LAST) return '';
    var won = LAST.posts.filter(function(p){ return stateOf(p, LAST.C).st === 'cashed'; }).sort(function(a, b){ return (+b.fd_odds || 0) - (+a.fd_odds || 0); }).slice(0, 5);
    return won.length ? '<h2 class="sec">Last week\'s winners</h2>' + won.map(function(p){ return card(p, me, LAST.C, true); }).join('') : '';
  }
  function sig(){ return sort + '|' + POSTS.map(function(p){ var x = stateOf(p); return p.id + x.st + x.hits + (MYV[p.id] ? 'v' : '') + p.score + (MYT[p.id] ? 't' : '') + (p.tails || 0) + (MYRX[p.id] || '') + JSON.stringify(p.rx || {}) + (FOL[p.user_id] ? 'f' : ''); }).join(',') + '|' + (LAST ? LAST.posts.length : '-'); }
  var SIG = null;
  function render(){
    var hb = document.querySelector('.soc .house'); if(hb) hb.hidden = sort === 'cashed' || sort === 'lost' || sort === 'sharp';   // the pinned house slips belong to the open feed
    if(VIEW){ SIG = null; if(hb) hb.hidden = true; profile(); return; }
    if(sort === 'sharp'){ SIG = null; sharps(); return; }
    SIG = sig();
    var me = A && A.user ? A.user.id : null, by = sort === 'new' ? function(a, b){ return new Date(b.created_at) - new Date(a.created_at); } : function(a, b){ return (b.score - a.score) || (new Date(b.created_at) - new Date(a.created_at)); };
    var open = [], won = [], lost = [];
    POSTS.filter(inGame).sort(by).forEach(function(p){ var x = p.result ? {st: p.result === 'won' ? 'cashed' : 'busted'} : stateOf(p); (x.st === 'cashed' ? won : settled(x) ? lost : open).push(p); });
    if(sort === 'following'){
      var mine = open.filter(function(p){ return FOL[p.user_id]; }), nf = Object.keys(FOL).length;
      if(hb) hb.hidden = true;
      info.textContent = !me ? 'Sign in to follow people' : nf ? 'Open slips from the ' + nf + ' ' + (nf === 1 ? 'person' : 'people') + ' you follow' : 'You are not following anyone yet';
      list.innerHTML = mine.length ? mine.map(function(p){ return card(p, me); }).join('')
        : '<div class="empty"><b>' + (!me ? 'Follow the people whose slips you like.' : nf ? 'Nobody you follow has an open slip.' : 'Nobody followed yet.') + '</b>' + (!me ? 'Sign in, then tap a name on any slip to see their record and follow them.' : 'Tap a name on any slip to see their record and follow them.') + '<a class="act" href="#" data-go="top">See the top slips</a></div>';
      return;
    }
    won.sort(function(a, b){ return (+b.fd_odds || 0) - (+a.fd_odds || 0); });
    var cb = document.querySelector('.soc .seg button[data-s="cashed"]'); if(cb) cb.textContent = 'Cashed' + (won.length ? ' ' + won.length : '');
    var lb = document.querySelector('.soc .seg button[data-s="lost"]'); if(lb) lb.textContent = 'Lost' + (lost.length ? ' ' + lost.length : '');
    if(sort === 'cashed'){
      info.textContent = won.length ? won.length + ' slip' + (won.length === 1 ? '' : 's') + ' cashed this week' : 'Slips that hit every leg land here';
      if(!won.length && !lost.length && !LAST) loadLast();
      list.innerHTML = (won.length ? won.map(function(p){ return card(p, me); }).join('') : '<div class="empty"><b>Nothing has cashed yet this week.</b>A posted slip moves here the moment its last leg hits.' + POSTBTN + '</div>') +
        (won.length ? '' : lastWeekHtml(me));
    } else if(sort === 'lost'){
      // owner 11/16: "Once one leg kills it, the bet should be off the pages or put into a lost tab"
      info.textContent = lost.length ? lost.length + ' slip' + (lost.length === 1 ? '' : 's') + ' busted this week' : 'A slip lands here the moment one leg kills it';
      list.innerHTML = lost.length ? lost.map(function(p){ return card(p, me); }).join('') : '<div class="empty"><b>Nothing has busted this week.</b>Every posted slip is still alive.' + POSTBTN + '</div>';
    } else if(GF){
      // one game asked for (a Boards card says "3 slips on Social"): show every slip on it - open first, then cashed, then lost - so the count on the card is what the reader finds
      var allg = open.concat(won, lost);
      info.textContent = allg.length + ' slip' + (allg.length === 1 ? '' : 's') + ' on this game' + (open.length ? ' · ' + open.length + ' open' : '') + (won.length ? ' · ' + won.length + ' cashed' : '') + (lost.length ? ' · ' + lost.length + ' lost' : '');
      list.innerHTML = allg.length ? allg.map(function(p){ return card(p, me); }).join('') : '<div class="empty"><b>No slips on this game yet.</b>Build one and post it so others can tail it.' + POSTBTN + '</div>';
    } else {
      info.textContent = open.length + ' open slip' + (open.length === 1 ? '' : 's') + (won.length ? ' · ' + won.length + ' cashed this week' : '') + ' · sorted by ' + (sort === 'new' ? 'newest' : 'upvotes');
      if(!open.length && !LAST) loadLast();
      list.innerHTML = open.length ? open.map(function(p){ return card(p, me); }).join('')
        : '<div class="empty"><b>No open slips right now.</b>' + (won.length ? won.length + ' cashed this week - they are under the Cashed tab. ' : '') + 'Be the first on the board for the next game.' + POSTBTN + '</div>' + (won.length ? '' : lastWeekHtml(me));
    }
    if(GF){ list.insertAdjacentHTML('afterbegin', gfBar()); if(hb && sort !== 'cashed' && sort !== 'lost') hb.hidden = true; }   // one game asked for: the pinned house slips step aside
    gradeHouse();
    if(location.hash && !GF){ var el = document.getElementById(location.hash.slice(1)); if(el) el.scrollIntoView({block: 'center'}); }
  }
  function profile(){
    var me = A && A.user ? A.user.id : null, u = VIEW, d = UPOSTS && UPOSTS.u === u ? UPOSTS : null;
    info.textContent = '';
    if(!d){ list.innerHTML = '<p class="lede"><span class="skel"></span><span class="skel"></span></p>';
      Promise.all([A.client.from('feed_posts').select(COLS3).eq('status', 'open').eq('user_id', u).order('created_at', {ascending: false}).limit(40),
                   A.client.from('feed_records').select('user_id,handle,graded,won,lost,units,posts').eq('user_id', u),
                   A.client.from('feed_profiles').select(V4 ? 'user_id,handle,color,emoji' : 'user_id,handle,color').eq('user_id', u),
                   A.client.from('feed_follows').select('follower').eq('followee', u)])
        .then(function(r){ UPOSTS = {u: u, posts: ((r[0] || {}).data || []).map(function(p){ (p.legs || []).forEach(function(l){ if(l.ko) l.ko = +l.ko; }); return p; }), rec: (((r[1] || {}).data || [])[0]) || null, prof: (((r[2] || {}).data || [])[0]) || null, fans: (((r[3] || {}).data || []).length)};
          if(UPOSTS.prof) PROF[u] = UPOSTS.prof; else if(PROF[u]) UPOSTS.prof = PROF[u]; if(UPOSTS.rec) REC[u] = UPOSTS.rec; if(VIEW === u) render(); })
        .catch(function(){ UPOSTS = {u: u, posts: [], rec: null, prof: null, fans: 0}; if(VIEW === u) render(); });
      return; }
    var h = (d.prof && d.prof.handle) || (d.rec && d.rec.handle) || (d.posts[0] && d.posts[0].handle) || 'user', r = d.rec || {graded: 0, won: 0, lost: 0, units: 0, posts: d.posts.length}, un = +r.units || 0;
    list.innerHTML = '<a class="back" href="#" data-go="back">← Back to the feed</a>' +
      '<section class="prof">' + av({user_id: u, handle: h}, true) + '<div class="pn"><h2>@' + esc(h) + '</h2><p>' + d.fans + ' follower' + (d.fans === 1 ? '' : 's') + ' · ' + (r.posts || d.posts.length) + ' slip' + ((r.posts || d.posts.length) === 1 ? '' : 's') + ' posted</p></div>' +
      (u !== me ? '<button type="button" class="fol' + (FOL[u] ? ' on' : '') + '" data-fol="' + esc(u) + '" aria-pressed="' + !!FOL[u] + '">' + (FOL[u] ? 'Following ✓' : 'Follow') + '</button>' : (V4 && !EDIT ? '<button type="button" class="fol on" data-edit="1">Edit profile</button>' : '')) +
      (u === me && EDIT ? editForm(h) : '') +
      '<dl class="pstats"><div><dt>Record</dt><dd>' + (r.graded ? r.won + '-' + r.lost : '—') + '</dd></div><div><dt>Units</dt><dd class="' + (r.graded ? (un >= 0 ? 'up' : 'dn') : '') + '">' + (r.graded ? (un >= 0 ? '+' : '') + un.toFixed(1) : '—') + '</dd></div><div><dt>Graded</dt><dd>' + (r.graded || 0) + '</dd></div></dl>' +
      (r.graded ? '' : '<p class="pnote">No graded slips yet. A slip is graded after its last game ends; the record counts one unit a slip.</p>') + '</section>' +
      (d.posts.length ? '<h2 class="sec">Slips</h2>' + d.posts.map(function(p){ return card(p, me, null, p.week !== W); }).join('') : '<div class="empty"><b>No slips posted yet.</b></div>');
  }
  function editForm(h){ var q = PROF[A.user.id] || {}, c = q.color == null ? hcol({user_id: A.user.id, handle: h}) : q.color;
    return '<form class="pedit" id="pedit" autocomplete="off"><label for="peh">Username</label><input id="peh" name="h" value="' + esc(h) + '" maxlength="20" inputmode="text" autocapitalize="off" spellcheck="false">' +
      '<p class="hint">3 to 20 letters, numbers or underscores. You can change it once every 30 days.</p>' +
      '<fieldset><legend>Colour</legend><div class="sw">' + [0,1,2,3,4,5,6,7].map(function(i){ return '<label><input type="radio" name="c" value="' + i + '"' + (i === c ? ' checked' : '') + '><i class="av c' + i + '" aria-hidden="true"></i><span class="sr">Colour ' + (i + 1) + '</span></label>'; }).join('') + '</div></fieldset>' +
      '<fieldset><legend>Avatar</legend><div class="em"><label><input type="radio" name="e" value=""' + (!q.emoji ? ' checked' : '') + '><i>Aa</i><span class="sr">My initials</span></label>' + EMOJI.map(function(x){ return '<label><input type="radio" name="e" value="' + x + '"' + (q.emoji === x ? ' checked' : '') + '><i>' + x + '</i></label>'; }).join('') + '</div></fieldset>' +
      '<p class="msg" id="pemsg" role="status"></p><div class="pbtn"><button type="submit" class="sv">Save profile</button><button type="button" data-edit="0">Cancel</button></div></form>'; }
  list.addEventListener('submit', function(e){ if(e.target.id !== 'pedit') return; e.preventDefault();
    var f = e.target, msg = document.getElementById('pemsg'), h = f.h.value.trim(), c = +(f.querySelector('input[name=c]:checked') || {}).value || 0, em = (f.querySelector('input[name=e]:checked') || {}).value || null, sv = f.querySelector('.sv');
    if(!/^[A-Za-z0-9_]{3,20}$/.test(h)){ msg.textContent = 'Usernames are 3 to 20 letters, numbers or underscores.'; msg.className = 'msg err'; return; }
    sv.disabled = true; msg.textContent = 'Saving…'; msg.className = 'msg';
    A.client.rpc('feed_profile_set', {p_handle: h, p_color: c, p_emoji: em}).then(function(r){ sv.disabled = false;
      if(r.error){ msg.textContent = (r.error.message || 'Could not save.').replace(/^.*?: /, ''); msg.className = 'msg err'; return; }
      var me = A.user.id; PROF[me] = r.data && r.data.user_id ? r.data : Object.assign(PROF[me] || {}, {handle: h, color: c, emoji: em});
      POSTS.concat((UPOSTS || {}).posts || []).forEach(function(p){ if(p.user_id === me) p.handle = PROF[me].handle; });
      if(UPOSTS && UPOSTS.u === me){ UPOSTS.prof = PROF[me]; if(UPOSTS.rec) UPOSTS.rec.handle = PROF[me].handle; }
      EDIT = false; render(); }); });
  function openUser(u){ EDIT = false; VIEW = u; UPOSTS = null; try { history.pushState({u: u}, '', '#u=' + u); } catch(e){} render(); window.scrollTo(0, 0); }
  function closeUser(){ VIEW = null; try { history.replaceState({}, '', location.pathname); } catch(e){} render(); }
  window.addEventListener('popstate', function(){ var m = location.hash.match(/^#u=([0-9a-f-]{36})$/); VIEW = m ? m[1] : null; if(A) render(); });
  window.addEventListener('hashchange', function(){ var m = location.hash.match(/^#g=([A-Z]{2,3}-[A-Z]{2,3})$/); if(m && m[1] !== GF){ GF = m[1]; if(A) render(); } });
  var LAST = null, LAST_BUSY = false;
  function loadLast(){
    if(LAST || LAST_BUSY || !A || W < 2) return; LAST_BUSY = true;
    Promise.all([fetch('/data/box-w' + (W - 1) + '.json').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }),
                 A.client.from('feed_posts').select('id,user_id,handle,title,week,legs,fd_odds,first_ko,last_ko,score,created_at').eq('status', 'open').eq('week', W - 1).order('score', {ascending: false}).limit(100)])
      .then(function(r){ var d = r[0], q = r[1]; if(!d || !q || q.error){ LAST = {posts: [], C: CUR}; return; }
        var C = {G: {}, BOX: {}, FIRST: {}};
        Object.keys(d.box || {}).forEach(function(n){ var v = d.box[n]; C.BOX[norm(n)] = {pass: v[0], ptd: v[1], rush: v[3], rtd: v[4], rec: v[5], recy: v[6], ctd: v[7], long: v[8]}; });
        Object.keys(d.games || {}).forEach(function(k){ var t = k.split('-'), v = d.games[k]; C.G[k] = {st: 'post', a: t[0], b: t[1], sa: v[0], sb: v[1]}; C.G[t[1] + '-' + t[0]] = {st: 'post', a: t[1], b: t[0], sa: v[1], sb: v[0]}; });
        LAST = {posts: (q.data || []), C: C}; if(sort !== 'sharp') render(); })
      .catch(function(){ LAST = {posts: [], C: CUR}; });
  }
  function people(done){
    var ids = {}; POSTS.forEach(function(p){ ids[p.user_id] = 1; }); ids = Object.keys(ids); var me = A.user ? A.user.id : null, jobs = [];
    if(!V3 || !ids.length){ done(); return; }
    jobs.push(A.client.from('feed_records').select('user_id,graded,won,lost,units').in('user_id', ids).then(function(r){ REC = {}; (r.data || []).forEach(function(x){ REC[x.user_id] = x; }); }));
    jobs.push(profs(me && ids.indexOf(me) < 0 ? ids.concat([me]) : ids));
    if(me){ var pids = POSTS.map(function(p){ return p.id; });
      jobs.push(A.client.from('feed_tails').select('post_id').eq('user_id', me).in('post_id', pids).then(function(r){ MYT = {}; (r.data || []).forEach(function(x){ MYT[x.post_id] = 1; }); }));
      jobs.push(A.client.from('feed_reactions').select('post_id,kind').eq('user_id', me).in('post_id', pids).then(function(r){ MYRX = {}; (r.data || []).forEach(function(x){ MYRX[x.post_id] = x.kind; }); }));
      jobs.push(A.client.from('feed_follows').select('followee').eq('follower', me).then(function(r){ FOL = {}; (r.data || []).forEach(function(x){ FOL[x.followee] = 1; }); }));
      if(A.client.rpc) jobs.push(A.client.rpc('feed_profile_me').then(function(r){ if(r && r.data && r.data.user_id) PROF[r.data.user_id] = Object.assign(PROF[r.data.user_id] || {}, r.data); })); }
    Promise.all(jobs.map(function(j){ return Promise.resolve(j).catch(function(){}); })).then(function(){ meBtn(); done(); }, done);
  }
  function meBtn(){ var b = document.getElementById('mebtn'); if(b) b.hidden = !(V3 && A && A.user); }
  function load(){
    A.client.from('feed_posts').select(V3 ? COLS3 : COLS).eq('status', 'open').eq('week', W)
      .order('score', {ascending: false}).order('created_at', {ascending: false}).limit(200).then(function(r){
        if(r.error && V3 && (r.error.code === '42703' || r.error.code === 'PGRST204' || /column/i.test(r.error.message || ''))){ V3 = false; load(); return; }   // the database is still on v2
        if(r.error){ info.textContent = (r.error.code === '42P01' || r.error.code === 'PGRST205') ? 'Social is being set up - check back soon.' : 'Could not load the feed (' + r.error.message + (r.error.code ? ', ' + r.error.code : '') + ').'; try{ console.error('feed load', r.error); }catch(e){} list.innerHTML = '<div class="empty"><b>The feed did not load.</b>Check your connection and try again.<a class="act" href="/social/">Reload</a></div>'; return; }
        POSTS = (r.data || []).map(function(p){ (p.legs || []).forEach(function(l){ if(l.ko) l.ko = +l.ko; }); return p; });
        if(!SHARP && !SHARP_BUSY) setTimeout(function(){ sharpLoad(function(){ if(sort !== 'sharp' && Object.keys(SHARP_BADGE).length) render(); }); }, 1200);
        var me = A.user ? A.user.id : null;
        if(!me || !POSTS.length){ MYV = {}; people(function(){ render(); poll(); }); return; }
        A.client.from('feed_votes').select('post_id').eq('user_id', me).in('post_id', POSTS.map(function(p){ return p.id; })).then(function(v){ MYV = {}; (v.data || []).forEach(function(x){ MYV[x.post_id] = 1; }); people(function(){ render(); poll(); }); });
      });
  }
  function needSignIn(){ var s = document.querySelector('#bsacct button'); if(s) s.click(); }
  list.addEventListener('click', function(e){
    var go = e.target.closest('[data-go]'); if(go){ e.preventDefault(); if(go.dataset.go === 'back') closeUser(); else if(go.dataset.go === 'allgames'){ GF = null; try { history.replaceState({}, '', location.pathname); } catch(e2){} render(); } else { var tb = document.querySelector('.soc .seg button[data-s="' + go.dataset.go + '"]'); if(tb) tb.click(); } return; }
    var hu = e.target.closest('b.h[data-u]'); if(hu){ openUser(hu.dataset.u); return; }
    var ed = e.target.closest('[data-edit]'); if(ed){ EDIT = ed.dataset.edit === '1'; render(); if(EDIT){ var i0 = document.getElementById('peh'); if(i0) i0.focus(); } return; }
    var tl = e.target.closest('[data-tail]'), rx = e.target.closest('[data-rx]'), fo = e.target.closest('[data-fol]');
    if(tl || rx || fo){ if(!A.user){ needSignIn(); return; } }
    if(tl){ var tid = +tl.dataset.tail, tp = POSTS.concat((UPOSTS || {}).posts || []).filter(function(x){ return x.id === tid; }); if(!tp.length) return; tl.disabled = true;
      (MYT[tid] ? A.client.from('feed_tails').delete().eq('post_id', tid).eq('user_id', A.user.id) : A.client.from('feed_tails').insert({post_id: tid})).then(function(r){ tl.disabled = false;
        if(r.error){ tl.textContent = /kicked off/i.test(r.error.message || '') ? 'Already kicked off' : 'Try again'; return; }
        var d = MYT[tid] ? -1 : 1; if(MYT[tid]) delete MYT[tid]; else MYT[tid] = 1; tp.forEach(function(x){ x.tails = Math.max(0, (x.tails || 0) + d); }); render(); }); return; }
    if(rx){ var pr = rx.dataset.rx.split('|'), rid = +pr[0], kind = pr[1], rp = POSTS.concat((UPOSTS || {}).posts || []).filter(function(x){ return x.id === rid; }); if(!rp.length) return; var was = MYRX[rid]; rx.disabled = true;
      (was === kind ? A.client.from('feed_reactions').delete().eq('post_id', rid).eq('user_id', A.user.id) : A.client.from('feed_reactions').upsert({post_id: rid, user_id: A.user.id, kind: kind}, {onConflict: 'post_id,user_id'})).then(function(r){ rx.disabled = false; if(r.error) return;
        rp.forEach(function(x){ var o = Object.assign({}, x.rx || {}); if(was){ o[was] = Math.max(0, (o[was] || 0) - 1); if(!o[was]) delete o[was]; } if(was !== kind) o[kind] = (o[kind] || 0) + 1; x.rx = o; });
        if(was === kind) delete MYRX[rid]; else MYRX[rid] = kind; render(); }); return; }
    if(fo){ var fu = fo.dataset.fol; fo.disabled = true;
      (FOL[fu] ? A.client.from('feed_follows').delete().eq('follower', A.user.id).eq('followee', fu) : A.client.from('feed_follows').insert({followee: fu})).then(function(r){ fo.disabled = false; if(r.error) return;
        if(FOL[fu]){ delete FOL[fu]; if(UPOSTS && UPOSTS.u === fu) UPOSTS.fans = Math.max(0, UPOSTS.fans - 1); } else { FOL[fu] = 1; if(UPOSTS && UPOSTS.u === fu) UPOSTS.fans++; } render(); }); return; }
    if(!e.target.closest('button, a, input') && (e.target.closest('.post .who') || e.target.closest('.post ul'))){ var art = e.target.closest('article.post'); if(art){ location.href = '/b/?p=' + art.dataset.id; return; } }
    var v = e.target.closest('[data-v]'), ld = e.target.closest('[data-load]'), del = e.target.closest('[data-del]'), rep = e.target.closest('[data-rep]');
    if(v){ if(!A.user){ needSignIn(); return; } var id = +v.dataset.v, p = POSTS.filter(function(x){ return x.id === id; })[0]; if(!p) return; v.disabled = true;
      var q = MYV[id] ? A.client.from('feed_votes').delete().eq('post_id', id).eq('user_id', A.user.id) : A.client.from('feed_votes').insert({post_id: id});
      q.then(function(r){ v.disabled = false; if(r.error) return; if(MYV[id]){ delete MYV[id]; p.score = Math.max(0, p.score - 1); } else { MYV[id] = 1; p.score++; }
        v.classList.toggle('on', !!MYV[id]); v.setAttribute('aria-pressed', !!MYV[id]); v.querySelector('b').textContent = p.score; }); return; }
    if(ld){ var p2 = POSTS.filter(function(x){ return x.id === +ld.dataset.load; })[0]; if(!p2) return;
      try { localStorage.setItem('bs_slipk_w' + W, JSON.stringify(p2.legs.map(function(l){ return l.k; }))); localStorage.removeItem('bs_slip_w' + W);
        var gm = {}; p2.legs.forEach(function(l){ if(l.gl && l.g) (gm[l.k] = gm[l.k] || []).push(l.g); });   // 11/14: totals load into their own game (bs_slipg, as the builder keeps it)
        if(Object.keys(gm).length) localStorage.setItem('bs_slipg_w' + W, JSON.stringify(gm)); else localStorage.removeItem('bs_slipg_w' + W); } catch(err){}
      location.href = '/build/'; return; }
    if(del){ if(!confirmInline(del, 'Delete?')) return; A.client.from('feed_posts').delete().eq('id', +del.dataset.del).then(function(r){ if(!r.error){ POSTS = POSTS.filter(function(x){ return x.id !== +del.dataset.del; }); render(); } }); return; }
    if(rep){ if(!confirmInline(rep, 'Report?')) return; A.client.from('feed_reports').insert({post_id: +rep.dataset.rep}).then(function(){ rep.textContent = 'Reported'; rep.disabled = true; }); }
  });
  function confirmInline(b, q){ if(b.dataset.armed) return true; b.dataset.armed = 1; var t = b.textContent; b.textContent = q + ' tap again'; setTimeout(function(){ delete b.dataset.armed; if(!b.disabled) b.textContent = t; }, 3000); return false; }
  document.querySelectorAll('.soc .seg button').forEach(function(b){ b.classList.toggle('on', b.dataset.s === sort); b.addEventListener('click', function(){ sort = b.dataset.s; try { localStorage.setItem('bs_social_sort', sort); } catch(e){}
    document.querySelectorAll('.soc .seg button').forEach(function(x){ x.classList.toggle('on', x === b); }); if(VIEW){ VIEW = null; try { history.replaceState({}, '', location.pathname); } catch(e){} } render(); }); });
  (function(){ var m = location.hash.match(/^#u=([0-9a-f-]{36})$/); if(m) VIEW = m[1]; })();
  (function(){ var b = document.getElementById('mebtn'); if(b) b.addEventListener('click', function(){ if(A && A.user) openUser(A.user.id); else needSignIn(); }); })();
  // ---- live grading (same rules as the home page's promoted bets): a slip leaves the feed when a leg loses or every game is over ----
  var ESPN = {WSH: 'WAS', LAR: 'LA'}; function ab(x){ return ESPN[x] || x; }
  function norm(n){ return String(n || '').toLowerCase().replace(/\./g, '').replace(/\s+(jr|sr|ii|iii|iv|v)$/, '').replace(/[^a-z ]/g, '').replace(/\s+/g, ' ').trim(); }
  function num(v){ var m = String(v == null ? '' : v).match(/-?\d+(\.\d+)?/); return m ? +m[0] : 0; }
  function parseBox(js, gid){ try {
    (js.boxscore.players || []).forEach(function(tm){ (tm.statistics || []).forEach(function(cat){ var keys = cat.keys || cat.labels || [];
      (cat.athletes || []).forEach(function(a){ var n = norm(a.athlete && (a.athlete.displayName || a.athlete.shortName)); if(!n) return;
        var r = BOX[n] = BOX[n] || {pass: 0, ptd: 0, rush: 0, rec: 0, recy: 0, long: 0, rtd: 0, ctd: 0}; var S = {}; keys.forEach(function(k, i){ S[k] = a.stats[i]; });
        // 11/16: touchdowns are SET per category, not added - the box is re-read every minute and "+=" doubled a scorer's TDs on the second read
        if(cat.name === 'passing'){ r.pass = num(S.passingYards != null ? S.passingYards : S.YDS); r.ptd = num(S.passingTouchdowns != null ? S.passingTouchdowns : S.TD); }
        if(cat.name === 'rushing'){ r.rush = num(S.rushingYards != null ? S.rushingYards : S.YDS); r.rtd = num(S.rushingTouchdowns != null ? S.rushingTouchdowns : S.TD); }
        if(cat.name === 'receiving'){ r.rec = num(S.receptions != null ? S.receptions : S.REC); r.recy = num(S.receivingYards != null ? S.receivingYards : S.YDS); r.long = num(S.longReception != null ? S.longReception : S.LONG); r.ctd = num(S.receivingTouchdowns != null ? S.receivingTouchdowns : S.TD); }
        if(cat.name === 'kickReturns' || cat.name === 'puntReturns'){ var tk = Object.keys(S).filter(function(k){ return /touchdown/i.test(k) || k === 'TD'; })[0]; if(tk) r[cat.name === 'kickReturns' ? 'krtd' : 'prtd'] = num(S[tk]); }   // 11/17: a return touchdown pays an anytime-TD leg too
      }); }); });
    var sp = (js.scoringPlays || []).filter(function(p){ return (p.type && /touchdown/i.test(p.type.text || '')) || /\bTD\b|touchdown/i.test(p.text || ''); });
    if(sp.length){ var m = (sp[0].text || '').match(/^([A-Z][\w.'-]+(?:\s[A-Z][\w.'-]+){0,3}?)\s+\d+\s+(?:Yd|Yard)/i); FIRST[gid] = m ? norm(m[1]) : '?'; }
    if((js.boxscore.players || []).length) SUMOK[gid] = 1;   // 11/17: this game's box score really was read
  } catch(e){} }
  var CUR = {G: G, BOX: BOX, FIRST: FIRST};
  function gradeLeg(l, C){
    C = C || CUR;
    if(/^Under /.test(l.m)){ var s0 = gradeLeg(Object.assign({}, l, {m: l.m.slice(6), ln: Math.floor(l.ln) + 1}), C); return s0 === 'hit' ? 'dead' : s0 === 'dead' ? 'hit' : s0; }   // unders: the other side of the (X+1)+ over
    var g = C.G[l.g]; if(!g || g.st === 'pre') return 'open'; var fin = g.st === 'post';
    if(l.gl){ var sa = +g.sa || 0, sb = +g.sb || 0, tot = sa + sb, x = l.gl, ln = +l.ln || 0;
      if(x.k !== 'M'){ var over = String(x.side).toUpperCase() === 'OVER'; return over ? (tot > ln ? 'hit' : fin ? 'dead' : 'open') : (tot > ln ? 'dead' : fin ? 'hit' : 'open'); }
      if(!fin) return 'open'; var me = x.side === g.a ? sa : sb, them = x.side === g.a ? sb : sa; return (me - them + (l.m === 'Moneyline' ? 0 : ln)) > 0 ? 'hit' : 'dead'; }
    var r = C.BOX[norm(l.pl)], sure = C !== CUR;   // live box: a player we cannot find is left open, never called a miss (a name mismatch must not bust a slip); a graded week's file is complete
    if(l.m === 'First TD'){ var f = C.FIRST[l.g]; if(!f) return (fin && !sure && SUMOK[l.g]) ? 'dead' : 'open'; return f === norm(l.pl) ? 'hit' : 'dead'; }   // 11/17: "no first TD" only once that game's box score has been read - a final whose box did not load used to bust the leg
    if(l.m === 'Passing TDs'){ if(r && (r.ptd || 0) >= Math.round(l.ln)) return 'hit'; return fin && (r || sure) ? 'dead' : 'open'; }
    if(l.m === 'Either TD'){ var rs = String(l.pl).split(/\s+or\s+/).map(function(n){ return C.BOX[norm(n)]; });
      if(rs.some(function(q){ return q && (q.rtd || 0) + (q.ctd || 0) + (q.krtd || 0) + (q.prtd || 0) >= 1; })) return 'hit'; return fin && (sure || rs.every(Boolean)) ? 'dead' : 'open'; }
    if(/TD$/.test(l.m)){ var needT = l.m === '2+ TD' ? 2 : l.m === '3+ TD' ? 3 : 1; if(r && (r.rtd || 0) + (r.ctd || 0) + (r.krtd || 0) + (r.prtd || 0) >= needT) return 'hit'; return fin && (r || sure) ? 'dead' : 'open'; }
    var v = !r ? (fin && sure ? 0 : null) : l.m === 'Passing Yards' ? r.pass : l.m === 'Rushing Yards' ? r.rush : l.m === 'Receiving Yards' ? r.recy : l.m === 'Receptions' ? r.rec : l.m === 'Longest Reception' ? r.long : l.m === 'Rush + Rec Yards' ? r.rush + r.recy : null;
    if(['Passing Yards', 'Rushing Yards', 'Receiving Yards', 'Receptions', 'Longest Reception', 'Rush + Rec Yards'].indexOf(l.m) < 0) return 'open';   // a market this page cannot grade stays open
    if(v == null) return 'open'; return v >= Math.round(l.ln) ? 'hit' : (fin ? 'dead' : 'open');
  }
  // house slips (pinned by the build): the same grading, so a slip stays up through its game with a live count and its result
  var HOUSE = window.__BS_HOUSE || [];
  function gradeHouse(){
    HOUSE.forEach(function(h){ var c = document.getElementById('h' + h.id); if(!c) return; var x = stateOf(h);
      (h.legs || []).forEach(function(l, i){ var li = c.querySelector('li[data-i="' + i + '"]'), s = gradeLeg(l); if(li){ li.classList.toggle('hit', s === 'hit'); li.classList.toggle('dead', s === 'dead'); } });
      var st = c.querySelector('.hst'); if(!st) return;
      // 11/17: with no word from the score feed the clock still knows the slip has started - it kept "Tail on FanDuel" on a slip whose game was over
      var kos = (h.legs || []).map(function(l){ return +l.ko || 0; }).filter(Boolean), f0 = kos.length ? Math.min.apply(null, kos) : 0, l0 = kos.length ? Math.max.apply(null, kos) : 0, nowH = Date.now();
      var byClock = x.st !== 'open' ? '' : (l0 && nowH >= l0 + 4.5 * 36e5) ? 'Final · grading' : (f0 && nowH >= f0) ? 'In play' : '';
      st.textContent = x.st === 'cashed' ? 'Cashed' : x.st === 'busted' ? 'Busted · ' + x.hits + ' of ' + x.n + ' hit' : x.st === 'done' ? 'Final' : x.st === 'live' ? 'Live · ' + x.hits + '/' + x.n + ' hit' : byClock || st.getAttribute('data-pre') || '';
      st.className = 'hst ' + x.st; c.classList.toggle('over', settled(x)); c.hidden = x.st === 'busted';   // owner 11/16: a busted slip comes off the page (it is under Lost on Today)
      var t = c.querySelector('a.tail'); if(t && (x.st !== 'open' || byClock)) t.hidden = true; });
  }
  function grade(){ if(sort === 'sharp'){ gradeHouse(); return; } if(sig() !== SIG) render(); else gradeHouse(); }
  var busy = false, DONE = {};
  function ymd(t){ var d = new Date(t); return d.getFullYear() + String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0'); }
  function poll(){
    var legs = []; POSTS.concat(HOUSE).forEach(function(p){ (p.legs || []).forEach(function(l){ legs.push(l); }); });
    var now = Date.now(), live = legs.filter(function(l){ return l.ko && l.g && now >= l.ko - 9e5 && !(DONE[l.g]); }); if(busy || !live.length) return; busy = true;
    var t0 = Math.min.apply(null, live.map(function(l){ return l.ko; })), t1 = Math.max.apply(null, live.map(function(l){ return l.ko; }));
    fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=' + ymd(t0 - 864e5) + '-' + ymd(t1 + 864e5), {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(js){
      if(!js){ busy = false; return; } var want = {}; live.forEach(function(l){ want[l.g] = 1; });
      (js.events || []).forEach(function(ev){ var c = (ev.competitions || [])[0]; if(!c) return; var by = {}; (c.competitors || []).forEach(function(x){ by[ab(x.team && x.team.abbreviation)] = x.score; });
        Object.keys(want).forEach(function(gid){ var p = gid.split('-'); if(!(p[0] in by) || !(p[1] in by)) return; var ty = ((ev.status || c.status || {}).type) || {};
          G[gid] = {eid: ev.id, st: ty.state || 'pre', a: p[0], b: p[1], sa: by[p[0]], sb: by[p[1]]}; }); });
      var on = Object.keys(want).filter(function(gid){ return G[gid] && G[gid].st !== 'pre'; });
      return Promise.all(on.map(function(gid){ return fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=' + G[gid].eid, {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(s){ if(s){ parseBox(s, gid); if(G[gid].st === 'post') DONE[gid] = 1; } }).catch(function(){}); }));   // a final game is read once
    }).then(function(){ busy = false; grade(); }).catch(function(){ busy = false; });
  }
  client(function(acc){ A = acc; load(); setInterval(poll, 60000); setInterval(load, 180000); });
  setTimeout(poll, 1200);   // house slips grade even before the feed answers
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
        if l.get("gl") and l.get("g"): m[f"{k}@{l['g']}"] = [fd["m"], fd["s"]]   # 11/14: a total's key is in several games ("Over 49.5" was DET-NE and CIN-PIT) - the game picks the right one
    return m

def _house_leg(l):
    """a promo leg (out/promos.json) in the shape the feed grades: pl, m, ln, g, ko and gl for game lines. None = cannot be graded here."""
    import re
    key = str(l.get("key") or ""); who = str(l.get("who") or ""); mk = str(l.get("market") or ""); g = l.get("gid") or ""; ko = l.get("ko")
    if not g or not ko: return None
    base = {"g": g, "ko": float(ko), "o": l.get("o")}
    if mk == "Total":
        m = re.match(r"\s*(Over|Under)\s+(\d+(?:\.\d+)?)", who, re.I)
        return dict(base, pl=who, m="Total", ln=float(m.group(2)), gl={"k": "T", "side": m.group(1).upper()}) if m else None
    if mk in ("Moneyline", "Spread"):
        try:
            import gamelines as GLM
            ab = {n.lower(): a for a, n in GLM.NICK.items()}
        except Exception: ab = {}
        t = who.split()[0] if who else ""; side = t if t.upper() in g.split("-") else ab.get(t.lower())
        if not side or side.upper() not in g.split("-"): return None
        m = re.search(r"([+-]\d+(?:\.\d+)?)", who) if mk == "Spread" else None
        if mk == "Spread" and not m: return None
        return dict(base, pl=who, m=mk, ln=float(m.group(1)) if m else 0, gl={"k": "M", "side": side.upper()})
    parts = key.split("|")
    if len(parts) != 3: return None
    try: ln = float(parts[2])
    except Exception: return None
    return dict(base, pl=parts[0], m=parts[1], ln=ln)


HOUSE_HOURS = 12   # a house slip stays pinned this long after its last kickoff (the next build drops it); its result shows meanwhile


def house_html(OUT, week, limit=3, _records=None, _now=None):
    """owner 11/16 (Social, step 1 - never empty): this week's house slips (the Daily Sweep first, then promos) pinned above the feed as
    posts from BetSweep. Built from out/promos.json at build time, so there is no database change. Step 1 finished (11/16): the card is
    graded on the page with the feed's own grader (window.__BS_HOUSE carries the legs), so a slip stays pinned through its game with a
    live count and then its result, until HOUSE_HOURS after its last kickoff. A slip with a leg the page cannot grade (no game or
    kickoff on the leg, e.g. a week-old cross-game slip) is pinned only while every kickoff is still ahead."""
    import os, time, html
    try: allp = _records if _records is not None else json.load(open(os.path.join(OUT, "promos.json")))
    except Exception: return ""
    now = (_now if _now is not None else time.time()) * 1000; E = html.escape
    def legs_of(p):
        ls = [_house_leg(l) for l in p.get("legs") or []]
        return ls if ls and all(ls) else None
    def live(p):
        if str(p.get("week")) != str(week) or p.get("status", "LIVE") != "LIVE" or (p.get("checks") or {}).get("block"): return False
        kos = [float(l["ko"]) for l in p.get("legs") or [] if l.get("ko")]
        if not kos or len(kos) != len(p.get("legs") or []): return False
        if now < min(kos): return not (p.get("result") or "").strip()
        return legs_of(p) is not None and now < max(kos) + HOUSE_HOURS * 36e5
    def am(x):
        try: x = float(x); return f"+{x:.0f}" if x > 0 else f"{x:.0f}"
        except Exception: return ""
    is_sweep = lambda p: str(p.get("title", "")).lower().startswith("daily sweep")
    ps = sorted([p for p in allp if live(p)], key=lambda p: (0 if is_sweep(p) else 1, -float(p.get("slot") or 0)))[:limit]
    cards, data = [], []
    for p in ps:
        hid = f'{p.get("week")}-{p.get("slot")}'; gl = legs_of(p)
        if gl: data.append({"id": hid, "legs": gl})
        li = [f'<li data-i="{i}"><span class="dot"></span><span>{E(str(l.get("disp") or l.get("who") or "").replace(" tds", " TDs"))}</span><em>{E(am(l.get("o")))}</em></li>' for i, l in enumerate(p["legs"])]
        legs = "".join(li[:4]) + (f'<li class="more"><details><summary>+{len(li) - 4} more legs</summary><ul>{"".join(li[4:])}</ul></details></li>' if len(li) > 4 else "")   # a 12-leg slip must not fill the screen
        _pd = str(p.get("posted") or ""); _pd = f"{int(_pd[5:7])}/{int(_pd[8:10])}" if len(_pd) >= 10 and _pd[4] == "-" else _pd
        meta = ("graded chance under 1%" if p["hp"] < 0.01 else f'graded chance about {p["hp"] * 100:.0f}%') if p.get("hp") else (f'model {p["p"] * 100:.0f}% to hit' if p.get("p") else f'{len(p["legs"])} legs')
        tail = f'<a class="tail" href="{E(str(p["link"]))}" target="_blank" rel="noopener">Tail on FanDuel</a>' if p.get("link") else ""
        cards.append(f'<article class="hcard" id="h{E(hid)}"><header><i class="av">BS</i><div><b>BetSweep</b><span>House slip · {"Daily Sweep" if is_sweep(p) else "Promo"}{(" · posted " + E(_pd)) if _pd else ""}</span></div></header>'
                     f'<h3>{E(str(p.get("name") or p.get("title") or ""))}</h3><ul>{legs}</ul><div class="hfoot"><span class="px">{E(am(p.get("fd")))}</span><span class="hst open" data-pre="{E(meta)}">{E(meta)}</span></div>'
                     f'<div class="hacts">{tail}<a href="/#promo">See it on Today</a></div></article>')
    if not cards: return ""
    return ('<div class="house"><span class="lab">House slips</span>' + "".join(cards) + "</div>"
            + "<script>window.__BS_HOUSE = " + json.dumps(data, separators=(",", ":")).replace("</", "<\\/") + ";</script>")


# ---------- alpha plan step 5 (owner 11/16: "I want people to use social and that be a prominent piece"): Social on other pages ----------
# strip_html(): "Top on Social" on Today - the three most-upvoted slips whose games are still to come or running, each a link to the
# slip; when nobody has posted, an invitation with the button. cards_js(): on Boards every game card says how many posted slips have a
# leg in that game and links to them (/social/#g=<gid>); an upcoming game with none offers "Post a slip for this game". Both read the
# feed with the page's own account client (window.bsAccount) and stay silent if it is not there or the read fails.
STRIP_CSS = """.socstrip .ssl{display:grid;gap:8px}
.socstrip a.ssp{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;min-height:60px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;text-decoration:none;color:var(--ink)}
.socstrip a.ssp:active{transform:scale(.99)} .socstrip .av{flex:none;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;font-family:var(--display);font-weight:700;font-size:13px;font-style:normal;color:#fff}
.socstrip .av.c0{background:#c2410c}.socstrip .av.c1{background:#0f766e}.socstrip .av.c2{background:#1d4ed8}.socstrip .av.c3{background:#7e22ce}.socstrip .av.c4{background:#be123c}.socstrip .av.c5{background:#4d7c0f}.socstrip .av.c6{background:#b45309}.socstrip .av.c7{background:#334155} .socstrip .av.em{font-size:18px}
.socstrip .ssp .w{min-width:0} .socstrip .ssp .w b{display:block;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .socstrip .ssp .w small{display:block;color:var(--mute);font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.socstrip .ssp .od{text-align:right;font-family:var(--display);font-weight:800;font-size:20px;line-height:1.05;font-variant-numeric:tabular-nums} .socstrip .ssp .od small{display:block;font-family:var(--body,inherit);font-weight:600;font-size:11.5px;color:var(--mute)}
.socstrip .ssempty{border:1px dashed var(--line);border-radius:12px;padding:14px;color:var(--mute);font-size:14px;line-height:1.4} .socstrip .ssempty b{display:block;font-family:var(--display);font-size:18px;line-height:1.2;color:var(--ink);margin-bottom:2px}
.socstrip .ssempty span{display:block} .socstrip .ssempty a{display:inline-block;margin-top:12px;background:var(--red);color:#fff;font-weight:700;text-decoration:none;border-radius:10px;padding:12px 18px;min-height:44px;box-sizing:border-box}
.socstrip .sk{display:block;height:60px;border-radius:12px;background:color-mix(in srgb,var(--ink) 7%,transparent)}
@media (prefers-reduced-motion:no-preference){ .socstrip .sk{animation:sspulse 1.2s ease-in-out infinite alternate} @keyframes sspulse{from{opacity:.55}to{opacity:1}} }"""

STRIP_JS = r"""(function(){
  var W = __WEEK__, box = document.getElementById('socstrip'); if(!box) return; var list = box.querySelector('.ssl'), all = box.querySelector('.seeall');
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function am(o){ o = +o; return !o ? '' : (o > 0 ? '+' : '') + Math.round(o); }
  function inits(h){ var m = String(h || '').match(/[A-Z]/g) || []; return (m.slice(0, 2).join('') || String(h || '?').slice(0, 2)).toUpperCase(); }
  function hcol(h){ var x = 0, t = String(h || ''); for(var i = 0; i < t.length; i++) x = (x * 31 + t.charCodeAt(i)) % 8; return x; }
  function leg(l){ if(!l) return ''; if(l.gl || /TD$/.test(l.m)) return l.pl + (l.gl ? '' : ' ' + String(l.m).toLowerCase()); if(/^Under /.test(l.m)) return l.pl + ' under ' + l.ln; return l.pl + ' ' + Math.round(l.ln) + '+'; }
  function wait(cb, n){ n = n || 0; if(window.bsAccount && window.bsAccount.client) return cb(window.bsAccount.client); if(n > 40){ box.hidden = true; return; } setTimeout(function(){ wait(cb, n + 1); }, 150); }
  function empty(){ list.innerHTML = '<div class="ssempty"><b>No slips up for the games left this week.</b><span>Build one and post it so others can tail it.</span><a href="/build/">Post the first slip</a></div>'; }
  function draw(rows, prof){
    // the database returns kickoff times as text ("2026-11-17T01:15:00+00:00"), never as a number: "+p.last_ko" is NaN and hid every real post (11/16, live 21:28Z until fixed)
    function ms(v){ var t = typeof v === 'number' ? v : Date.parse(v); return isNaN(t) ? 0 : t; }
    var now = Date.now(), live = rows.filter(function(p){ return ms(p.last_ko) > now - 4.5 * 3600e3; });   // games still to come, or running
    if(all) all.textContent = live.length > 3 ? 'All ' + live.length + ' slips' : 'Open Social';
    if(!live.length){ empty(); return; }
    list.innerHTML = live.slice(0, 3).map(function(p){ var ls = p.legs || [], q = prof[p.user_id] || {}, pre = ms(p.first_ko) > now;
      return '<a class="ssp" href="/b/?p=' + p.id + '"><i class="av c' + (q.color != null ? q.color : hcol(p.handle)) + (q.emoji ? ' em' : '') + '" aria-hidden="true">' + esc(q.emoji || inits(p.handle)) + '</i>' +
        '<span class="w"><b>' + esc(p.title || leg(ls[0]) + (ls.length > 1 ? ' + ' + (ls.length - 1) + ' more' : '')) + '</b><small>@' + esc(p.handle) + ' · ' + ls.length + ' leg' + (ls.length === 1 ? '' : 's') + (p.tails ? ' · ' + p.tails + ' tailing' : '') + (pre ? '' : ' · live') + '</small></span>' +
        '<span class="od">' + esc(am(p.fd_odds)) + '<small>▲ ' + (p.score || 0) + '</small></span></a>'; }).join('');
  }
  wait(function(sb){
    function read(cols){ return sb.from('feed_posts').select(cols).eq('status', 'open').eq('week', W).order('score', {ascending: false}).order('created_at', {ascending: false}).limit(60); }
    read('id,user_id,handle,title,legs,fd_odds,first_ko,last_ko,score,tails').then(function(r){
      if(r.error) return read('id,user_id,handle,title,legs,fd_odds,first_ko,last_ko,score');   // a database still on the older columns
      return r; }).then(function(r){
      if(!r || r.error){ box.hidden = true; return; }
      var rows = r.data || [], ids = {}; rows.slice(0, 12).forEach(function(p){ ids[p.user_id] = 1; }); ids = Object.keys(ids);
      if(!ids.length){ draw(rows, {}); return; }
      function pr(cols){ return sb.from('feed_profiles').select(cols).in('user_id', ids); }
      pr('user_id,color,emoji').then(function(q){ return q && q.error ? pr('user_id,color') : q; })   // before sql/social_v4.sql there is no emoji column
        .then(function(q){ var m = {}; ((q && q.data) || []).forEach(function(x){ m[x.user_id] = x; }); draw(rows, m); }, function(){ draw(rows, {}); });
    }, function(){ box.hidden = true; });
  });
})();"""

def strip_html(week):
    return ('<section class="sec socstrip" id="socstrip"><style>' + STRIP_CSS + '</style><div class="sech"><h2 class="t">Top on Social <small class="tsub">slips people posted</small></h2><a class="seeall" href="/social/">Open Social</a></div>'
            '<div class="ssl" aria-live="polite"><span class="sk"></span><span class="sk"></span></div>'
            '<script>' + STRIP_JS.replace("__WEEK__", str(int(week))) + '</script></section>')


CARDS_CSS = """.ginfo a.socn{color:var(--mute);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;white-space:nowrap} .ginfo a.socn.has{color:var(--ink);font-weight:700;text-decoration-color:var(--red)}"""
CARDS_JS = r"""(function(){
  var W = __WEEK__, cards = document.querySelectorAll('section.card[id][data-ko]'); if(!cards.length) return;
  function wait(cb, n){ n = n || 0; if(window.bsAccount && window.bsAccount.client) return cb(window.bsAccount.client); if(n > 40) return; setTimeout(function(){ wait(cb, n + 1); }, 150); }
  wait(function(sb){ sb.from('feed_posts').select('id,legs').eq('status', 'open').eq('week', W).limit(300).then(function(r){
    if(!r || r.error) return; var n = {};
    (r.data || []).forEach(function(p){ var seen = {}; (p.legs || []).forEach(function(l){ if(l && l.g && !seen[l.g]){ seen[l.g] = 1; n[l.g] = (n[l.g] || 0) + 1; } }); });
    cards.forEach(function(c){ var gid = c.id, k = n[gid] || n[gid.split('-').reverse().join('-')] || 0, gi = c.querySelector('.ginfo'), pre = (+c.dataset.ko || 0) > Date.now();
      if(!gi || gi.querySelector('.socn') || (!k && !pre)) return;
      var sep = document.createElement('i'); sep.textContent = '·'; var a = document.createElement('a'); a.className = 'socn' + (k ? ' has' : '');
      a.href = k ? '/social/#g=' + gid : '/build/#g-' + gid; a.textContent = k ? k + (k === 1 ? ' slip' : ' slips') + ' on Social' : 'Post a slip for this game';
      gi.appendChild(sep); gi.appendChild(a); }); }, function(){}); });
})();"""

def cards_js(week):
    return "<style>" + CARDS_CSS + "</style><script>" + CARDS_JS.replace("__WEEK__", str(int(week))) + "</script>"


# 11/16 (alpha plan step 3): post a slip from a FanDuel screenshot. The picture is read on the phone by the same reader My BetSweep uses
# (/import.js, slipimport.py); the legs that are on this week's board and have not kicked off are loaded into the Parlay Builder, which
# opens its own post form with the price from the picture filled in. Nothing is posted until the reader presses Post there.
SHOT_CSS = """.soc .bar #shotbtn{font:inherit;font-weight:700;font-size:14px;min-height:44px;padding:0 14px;border-radius:10px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer}
.soc .shot{margin:0 0 14px;padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--card)} .soc .shot h2{margin:0 0 4px;font-family:var(--display);font-size:20px;color:var(--ink)}
.soc .shot p{margin:0 0 10px;color:var(--mute);font-size:14px;line-height:1.45} .soc .shot .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.soc .shot .pick,.soc .shot .go{display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border-radius:10px;border:0;background:var(--red);color:#fff;font:inherit;font-weight:700;cursor:pointer}
.soc .shot #shotx{min-height:44px;padding:0 14px;border-radius:10px;border:1px solid var(--line);background:none;color:var(--ink);font:inherit;font-weight:600;cursor:pointer}
.soc .shot #shotout{margin-top:10px} .soc .shot #shotout .st{margin:0 0 8px;font-size:14px;color:var(--ink)} .soc .shot #shotout .st.err{color:var(--bad)}
.soc .shot ul{list-style:none;margin:0 0 10px;padding:0;display:grid;gap:6px} .soc .shot li{padding:9px 11px;border:1px solid var(--line);border-radius:10px;font-size:14px;line-height:1.35;color:var(--ink)}
.soc .shot li b{font-variant-numeric:tabular-nums;margin-left:4px} .soc .shot li small{display:block;color:var(--mute);font-size:12.5px} .soc .shot li.no{color:var(--mute)} .soc .shot li.no small{color:var(--bad)}"""
SHOT_JS = r"""<script>(function(){
  var $ = function(id){ return document.getElementById(id); }, btn = $('shotbtn'), box = $('shot'), f = $('shotf'), out = $('shotout'); if(!btn || !box) return;
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function am(o){ o = +o; return isNaN(o) || !o ? '' : (o > 0 ? '+' + o : String(o)); }
  function say(t, err){ out.innerHTML = '<p class="st' + (err ? ' err' : '') + '">' + t + '</p>'; }
  function open(on){ box.hidden = !on; btn.setAttribute('aria-expanded', on ? 'true' : 'false'); if(on) box.scrollIntoView({block: 'nearest'}); }
  btn.addEventListener('click', function(){ open(box.hidden); }); $('shotx').addEventListener('click', function(){ open(false); out.innerHTML = ''; });
  function show(R, BS){
    var now = Date.now(), G = BS.games || {}, rows = (R.legs || []).map(function(l){
      if(!l.ok) return {no: 1, text: l.raw, why: l.why || 'not a market BetSweep prices'};
      var g = l.leg && l.leg.g, ko = g && G[g] && G[g].ko;
      if(l.unpriced || !l.leg) return {no: 1, text: l.label, why: "not on this week's board at that exact line, so it cannot be posted"};
      if(ko && now >= ko) return {no: 1, text: l.label, why: 'that game has already kicked off'};
      return {l: l, text: l.label}; });
    var good = rows.filter(function(r){ return !r.no; });
    if(!rows.length){ say('No FanDuel legs found in that picture. Use a screenshot of the betslip, or of the bet under My Bets, with the leg names showing.', 1); return; }
    var h = '<p class="st">' + (good.length ? good.length + ' of ' + rows.length + ' legs can be posted' : 'None of these legs can be posted') + (R.odds ? ' · FanDuel ' + am(R.odds) : '') + '</p><ul>' + rows.map(function(r){
      return r.no ? '<li class="no">✗ ' + esc(r.text) + '<small>' + esc(r.why) + '</small></li>' : '<li>✓ ' + esc(r.text) + (r.l.odds ? '<b>' + am(r.l.odds) + '</b>' : '') + '</li>'; }).join('') + '</ul>';
    if(!good.length){ out.innerHTML = h; return; }
    var part = good.length < rows.length;
    out.innerHTML = h + (part && R.odds ? '<p class="st">The ' + am(R.odds) + ' on the picture is for the whole slip, so it is left off a post with fewer legs.</p>' : '') + '<div class="row"><button type="button" class="go" id="shotgo">Post ' + (good.length === 1 ? 'this leg' : 'these ' + good.length + ' legs') + '</button></div>';
    $('shotgo').addEventListener('click', function(){ var ls = good.map(function(r){ return r.l; }), keys = ls.map(function(x){ return x.key; });
      // the builder opens its post form for exactly these legs (single use, two minutes); the price is only carried when every leg came along
      try{ sessionStorage.setItem('bs_postnow', JSON.stringify({odds: part ? null : (R.odds || null), keys: keys.slice().sort(), t: Date.now()})); }catch(e){}
      say('Opening the Parlay Builder with your slip…'); window.BSLoadSlip(keys, window.BSImport.gmap ? window.BSImport.gmap(BS, ls) : {}); }); }
  f.addEventListener('change', function(){ var file = f.files && f.files[0]; f.value = ''; if(!file) return;
    if(!window.BSImport){ say('The reader did not load. Check your connection and try again.', 1); return; }
    say('Reading your slip… the first time takes a few seconds.');
    window.BSImport.read(file).then(function(r){ show(r.R, r.BS); }, function(e){ say('Could not read that picture. Try a full, uncropped screenshot of the slip.', 1); }); });
})();</script>"""

def page(week, house=""):
    return (f"""<title>BetSweep Social</title>
<script>window.__BS_FDMAP = {json.dumps(fdmap(), separators=(",", ":"))};</script>
<meta name="description" content="Betslips posted by BetSweep users - tail them on FanDuel, upvote the best ones, and see which ones cashed. Graded live from the box score.">
__BASE__
<style>__BASECSS__{PAGE_CSS}{SHOT_CSS}</style>
<div class="soc">
 <h1>Social</h1>
 <p class="lede">Slips people are riding this week. Tail one in a tap, upvote the good ones.</p>
 <div class="bar"><a class="pri" href="/build/">+ Post a slip</a><button type="button" id="shotbtn" aria-controls="shot" aria-expanded="false">From a screenshot</button><button type="button" id="mebtn" hidden>My profile</button><span class="seg"><button type="button" data-s="top">Top</button> <button type="button" data-s="new">New</button> <button type="button" data-s="following">Following</button> <button type="button" data-s="cashed">Cashed</button> <button type="button" data-s="lost">Lost</button> <button type="button" data-s="sharp">Sharps</button></span></div>
 <section class="shot" id="shot" hidden aria-label="Post a slip from a screenshot">
  <h2>Post from a screenshot</h2>
  <p>Screenshot your FanDuel betslip and choose the picture. Your phone reads it; the picture never leaves this device.</p>
  <div class="row"><label class="pick">Choose screenshot<input type="file" accept="image/*" id="shotf" hidden></label><button type="button" id="shotx">Close</button></div>
  <div id="shotout" aria-live="polite"></div>
 </section>
 {house}
 <p class="lede" id="feedinfo"><span class="skel"></span><span class="skel"></span></p>
 <div id="feed"></div>
 <p class="rules">How it works: the most-upvoted slips sit on top. Load any slip into the Parlay Builder to see our price for it. Slips are graded live from the box score: a slip that hits every leg moves to Cashed, and one that loses a leg moves to Lost right away. Posted slips are users' own picks, not BetSweep's, and are not checked by the model. Sign in to post, upvote or report; a post with three reports is hidden for review. No harassment, spam, ads or personal info - see the <a href="/terms/">Terms</a>. 21+. Bet only what you can afford to lose; 1-800-GAMBLER.</p>
</div>
<script defer src="/import.js"></script>
""" + PAGE_JS.replace("__WEEK__", json.dumps(int(week))) + SHOT_JS)
