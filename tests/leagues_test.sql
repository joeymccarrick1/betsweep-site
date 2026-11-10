\set ON_ERROR_STOP on
-- tests/leagues_test.sql - sql/betsweep-leagues.sql against a minimal stand-in for Supabase (auth schema, anon / authenticated roles,
-- auth.uid() from the request claim). Run on any local Postgres 15+:  psql -v sqlfile=sql/betsweep-leagues.sql -f tests/leagues_test.sql
-- Every block prints what it expects; the last line is LEAGUES TEST PASSED only when the assertions held.
drop database if exists bs_leagues_test;
create database bs_leagues_test;
\c bs_leagues_test
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;
grant usage on schema public, auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to anon, authenticated;   -- Supabase's default grants
insert into auth.users select ('00000000-0000-0000-0000-0000000000' || lpad(to_hex(g), 2, '0'))::uuid from generate_series(1, 40) g;
-- the two tables of the 11/5 script the leagues read
create table public.beat_picks (user_id uuid not null references auth.users(id) on delete cascade, week int not null, keys jsonb not null, name text,
  submitted_at timestamptz not null default now(), hits int, graded_at timestamptz, primary key (user_id, week));
create table public.beat_model (week int primary key, keys jsonb not null, hits int, frozen_at timestamptz not null default now());
\i :sqlfile
\i :sqlfile
\echo '--- the script ran twice'
create table public._t (k text primary key, v text);
create function public._ok(c boolean, msg text) returns text language plpgsql as $$ begin if c is not true then raise exception 'ASSERTION FAILED: %', msg; end if; return 'ok: ' || msg; end $$;
-- week 9 was graded BEFORE the league exists: it must not count
insert into public.beat_picks values ('00000000-0000-0000-0000-000000000001', 9, '[]', 'Ace', now() - interval '8 days', 5, now() - interval '2 days');
insert into public.beat_model values (9, '[]', 3);
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
insert into public._t select 'code', code from public.beat_league_create('  The Office  ');
reset role;
select v as code from public._t where k = 'code' \gset
\echo '--- A created a league; code is 8 characters:' :code
select public._ok((select char_length(v) = 8 from public._t where k = 'code'), 'code length');
-- B joins with the code typed in capitals and with spaces; C does not join
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select name as joined_name from public.beat_league_join('  ' || upper(:'code') || ' ') \gset
select count(*) as b_leagues from public.beat_league_mine() \gset
reset role;
select public._ok(:'joined_name' = 'The Office', 'join returns the trimmed name');
select public._ok(:b_leagues = 1, 'B has one league');
-- week 10 graded after creation
insert into public.beat_picks values ('00000000-0000-0000-0000-000000000001', 10, '[]', 'Ace', now(), 4, now() + interval '1 second'),
                                     ('00000000-0000-0000-0000-000000000002', 10, '[]', '  ', now(), 2, now() + interval '1 second'),
                                     ('00000000-0000-0000-0000-000000000003', 10, '[]', 'Outsider', now(), 5, now() + interval '1 second');
insert into public.beat_model values (10, '[]', 3);
insert into public.beat_picks values ('00000000-0000-0000-0000-000000000001', 11, '[]', 'Ace', now(), null, null);
\echo '--- the board as B for week 11: Ace 4 (1 week, has picked), The model 3 (1 week), Player 2 (me, not picked). Week 9 and the outsider are not in it.'
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select * from public.beat_league_board(:'code', 11);
select string_agg(name || ':' || hits || ':' || weeks || ':' || picked || ':' || me || ':' || model, ' | ') as board from public.beat_league_board(:'code', 11) \gset
select count(*) as c_rows from (select 1) x where false \gset
reset role;
select public._ok(:'board' = 'Ace:4:1:true:false:false | The model:3:1:false:false:true | Player:2:1:false:true:false', 'board rows: ' || :'board');
\echo '--- C is not a member: the board is empty, and so is "my leagues"'
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000003';
select count(*) as c_board from public.beat_league_board(:'code', 11) \gset
select count(*) as c_mine from public.beat_league_mine() \gset
reset role;
select public._ok(:c_board = 0 and :c_mine = 0, 'non-member sees nothing');
\echo '--- nobody reads the tables directly, anon cannot call anything (four errors expected below)'
\set ON_ERROR_STOP off
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000003';
select * from public.beat_leagues;
select * from public.beat_league_members;
reset role; set role anon;
select * from public.beat_league_mine();
select * from public.beat_league_join('abcdef12');
reset role;
\echo '--- a wrong code and an empty name are refused (two errors expected below)'
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000003';
select * from public.beat_league_join('nosuchcd');
select * from public.beat_league_create('   ');
reset role;
\set ON_ERROR_STOP on
\echo '--- rename: not by B (false), by A (true)'
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select public.beat_league_rename(:'code', 'Mine now') as b_rename \gset
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
select public.beat_league_rename(:'code', 'Sunday Crew') as a_rename \gset
select name as new_name, members, owner from public.beat_league_mine() \gset
reset role;
select public._ok(not :'b_rename'::boolean and :'a_rename'::boolean and :'new_name' = 'Sunday Crew' and :members = 2 and :'owner'::boolean, 'rename / mine');
\echo '--- the 11th league for one account is refused; a 201st member is refused'
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000004';
do $$ begin for i in 1..10 loop perform public.beat_league_create('L' || i); end loop; end $$;
\set ON_ERROR_STOP off
select * from public.beat_league_create('one too many');
\set ON_ERROR_STOP on
select count(*) as d_owned from public.beat_league_mine() \gset
reset role;
select public._ok(:d_owned = 10, 'ten leagues');
insert into auth.users select gen_random_uuid() from generate_series(1, 198);
insert into public.beat_league_members (league_id, user_id) select (select id from public.beat_leagues where code = :'code'), u.id from auth.users u
  where u.id not in (select user_id from public.beat_league_members where league_id = (select id from public.beat_leagues where code = :'code')) and u.id::text not like '00000000-0000-0000-0000-0000000000%' limit 198;
select count(*) as n_members from public.beat_league_members where league_id = (select id from public.beat_leagues where code = :'code') \gset
select public._ok(:n_members = 200, 'league at 200: ' || :n_members);
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000005';
\set ON_ERROR_STOP off
select * from public.beat_league_join(:'code');
\set ON_ERROR_STOP on
select count(*) as e_mine from public.beat_league_mine() \gset
reset role;
select public._ok(:e_mine = 0, 'full league refused');
\echo '--- the owner leaves: the next member owns it; the last member leaves: the league is gone'
delete from public.beat_league_members where league_id = (select id from public.beat_leagues where code = :'code') and user_id::text not like '00000000-0000-0000-0000-0000000000%';
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
select public.beat_league_leave(:'code') as a_left \gset
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select owner as b_owner, members as b_members from public.beat_league_mine() \gset
select public.beat_league_leave(:'code') as b_left \gset
reset role;
select count(*) as left_over from public.beat_leagues where code = :'code' \gset
select public._ok(:'a_left'::boolean and :'b_owner'::boolean and :b_members = 1 and :'b_left'::boolean and :left_over = 0, 'leave / hand over / close');
\echo '--- delete by the owner removes it and its members'
set role authenticated; set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000004';
select code as dcode from public.beat_league_mine() limit 1 \gset
select public.beat_league_delete(:'dcode') as d_del \gset
select count(*) as d_after from public.beat_league_mine() \gset
reset role;
select public._ok(:'d_del'::boolean and :d_after = 9, 'delete');
\echo 'LEAGUES TEST PASSED'
