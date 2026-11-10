\set ON_ERROR_STOP on
-- Remote staging assertions. This file assumes the V2 migration is already applied.
-- It deliberately ends in ROLLBACK: fixture auth users, topics, aliases, and requests
-- created here never persist in the staging project.

begin;

create or replace function pg_temp.assert_true(ok boolean, label text) returns void language plpgsql as $$
begin
  if not ok then raise exception 'ASSERTION FAILED: %', label; end if;
end $$;

-- auth.users has additional optional columns in Supabase, but these are its required
-- identity fields for a confirmed password user. The enclosing transaction removes them.
insert into auth.users
  (id, aud, role, email, encrypted_password, email_confirmed_at,
   raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values
 ('00000000-0000-0000-0000-0000000000a1', 'authenticated', 'authenticated', 'v2-fixture-a1@example.test', '$2a$10$fixturefixturefixturefixturefixturefixturefixturefixturefixtur', now(), '{}'::jsonb, '{}'::jsonb, now(), now()),
 ('00000000-0000-0000-0000-0000000000b2', 'authenticated', 'authenticated', 'v2-fixture-b2@example.test', '$2a$10$fixturefixturefixturefixturefixturefixturefixturefixturefixtur', now(), '{}'::jsonb, '{}'::jsonb, now(), now()),
 ('00000000-0000-0000-0000-0000000000c3', 'authenticated', 'authenticated', 'v2-fixture-c3@example.test', '$2a$10$fixturefixturefixturefixturefixturefixturefixturefixturefixtur', now(), '{}'::jsonb, '{}'::jsonb, now(), now()),
 ('00000000-0000-0000-0000-0000000000d4', 'authenticated', 'authenticated', 'v2-fixture-d4@example.test', '$2a$10$fixturefixturefixturefixturefixturefixturefixturefixturefixtur', now(), '{}'::jsonb, '{}'::jsonb, now(), now()),
 ('00000000-0000-0000-0000-0000000000e5', 'authenticated', 'authenticated', 'v2-fixture-e5@example.test', '$2a$10$fixturefixturefixturefixturefixturefixturefixturefixturefixtur', now(), '{}'::jsonb, '{}'::jsonb, now(), now()),
 ('00000000-0000-0000-0000-0000000000f6', 'authenticated', 'authenticated', 'v2-fixture-f6@example.test', '$2a$10$fixturefixturefixturefixturefixturefixturefixturefixturefixtur', now(), '{}'::jsonb, '{}'::jsonb, now(), now());

-- Mirror config/topic-aliases.json inside this transaction, so tests do not require
-- a persistent seed. seed_aliases.sql remains the real staging seed command.
insert into public.topics(id, canonical_name, normalized_key, search_query) values
 ('10000000-0000-0000-0000-000000000001', 'Café', 'v1:' || encode(sha256(convert_to('Café', 'UTF8')), 'hex'), 'Café')
on conflict (id) do nothing;
insert into public.topic_aliases(alias_nfc, topic_id) values
 ('Café', '10000000-0000-0000-0000-000000000001'),
 ('espresso', '10000000-0000-0000-0000-000000000001')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topics(canonical_name, normalized_key, search_query)
select 'Cap topic ' || n, 'v1:' || encode(sha256(convert_to('Cap topic ' || n, 'UTF8')), 'hex'), 'Cap topic ' || n
from generate_series(1, 6) n;

-- 1/2: user isolation and direct client writes are denied.
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000b2"}', true);
set local role authenticated;
select public.request_topic('B owned topic');
reset role;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000a1"}', true);
set local role authenticated;
select pg_temp.assert_true(not exists (select 1 from public.user_topics), 'A cannot SELECT B rows');
do $$ begin
  begin update public.user_topics set display_name = 'nope'; raise exception 'UPDATE unexpectedly allowed';
  exception when insufficient_privilege then null; end;
  begin delete from public.user_topics; raise exception 'DELETE unexpectedly allowed';
  exception when insufficient_privilege then null; end;
  begin insert into public.topics(canonical_name, normalized_key, search_query) values ('bad', 'v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'bad'); raise exception 'topics insert unexpectedly allowed';
  exception when insufficient_privilege then null; end;
  begin insert into public.topic_creation_user_counters values (auth.uid(), current_date, 1); raise exception 'counter insert unexpectedly allowed';
  exception when insufficient_privilege then null; end;
end $$;
reset role;
\echo PASS 1 user isolation and direct-write denial
\echo PASS 2 authenticated cannot insert topics/counters directly

-- 3/4: anon sees only the narrow worker queue, never the base topics table.
set local role anon;
select pg_temp.assert_true(exists (select 1 from public.public_topic_worker_queue), 'anon reads queue');
select pg_temp.assert_true(not exists (select 1 from public.public_topic_worker_queue q, lateral jsonb_each(to_jsonb(q)) e where e.key = 'user_id'), 'queue lacks user_id');
do $$ begin
  begin perform * from public.topics; raise exception 'anon topics select unexpectedly allowed';
  exception when insufficient_privilege then null; end;
end $$;
reset role;
\echo PASS 3 anon queue only exposes worker-safe columns
\echo PASS 4 anon cannot read base topics

-- 5: new topic consumes one counter; NFC twin and curated alias reuse it.
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000a1"}', true);
set local role authenticated;
select pg_temp.assert_true((public.request_topic('Created exactly once')->>'status') = 'ok', 'new topic request');
select pg_temp.assert_true((public.request_topic(U&'Cafe\0301')->>'status') = 'ok', 'NFC twin request');
select pg_temp.assert_true((public.request_topic('espresso')->>'status') = 'ok', 'alias request');
reset role;
select pg_temp.assert_true((select new_topics from public.topic_creation_user_counters where user_id = '00000000-0000-0000-0000-0000000000a1') = 1, 'reuse does not consume new counter');
\echo PASS 5 creation plus NFC/alias reuse

-- 6: the active set cannot exceed five for existing global topics.
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000c3"}', true);
set local role authenticated;
select pg_temp.assert_true((public.request_topic('Cap topic 1')->>'status') = 'ok', 'cap 1');
select pg_temp.assert_true((public.request_topic('Cap topic 2')->>'status') = 'ok', 'cap 2');
select pg_temp.assert_true((public.request_topic('Cap topic 3')->>'status') = 'ok', 'cap 3');
select pg_temp.assert_true((public.request_topic('Cap topic 4')->>'status') = 'ok', 'cap 4');
select pg_temp.assert_true((public.request_topic('Cap topic 5')->>'status') = 'ok', 'cap 5');
select pg_temp.assert_true((public.request_topic('Cap topic 6')->>'status') = 'limit_reached', 'sixth active topic rejected');
reset role;
\echo PASS 6 active cap transactional proof

-- 7: three genuinely new topics per Pacific day; existing reuse remains free.
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000d4"}', true);
set local role authenticated;
select pg_temp.assert_true((public.request_topic('Daily new one')->>'status') = 'ok', 'daily 1');
select pg_temp.assert_true((public.request_topic('Daily new two')->>'status') = 'ok', 'daily 2');
select pg_temp.assert_true((public.request_topic('Daily new three')->>'status') = 'ok', 'daily 3');
select pg_temp.assert_true((public.request_topic('Daily new four')->>'status') = 'daily_cap', 'daily fourth rejected');
select pg_temp.assert_true((public.request_topic('Daily new one')->>'status') = 'ok', 'existing topic reuse after daily cap');
reset role;
\echo PASS 7 daily cap and reuse

-- 8: rejected input and inconsistent curated mapping return explicit enums.
insert into public.topics(id, canonical_name, normalized_key, search_query) values
 ('20000000-0000-0000-0000-000000000002', 'Conflict', 'v1:' || encode(sha256(convert_to('Conflict', 'UTF8')), 'hex'), 'Conflict');
insert into public.topic_aliases(alias_nfc, topic_id) values ('Conflict', '10000000-0000-0000-0000-000000000001');
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000e5"}', true);
set local role authenticated;
select pg_temp.assert_true((public.request_topic('https://example.test')->>'status') = 'invalid_input', 'URL rejected');
select pg_temp.assert_true((public.request_topic('Conflict')->>'status') = 'alias_conflict', 'alias conflict rejected');
reset role;
\echo PASS 8 invalid input and alias conflict

-- 9: language punctuation does not collapse C++ and C#.
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000f6"}', true);
set local role authenticated;
select pg_temp.assert_true((public.request_topic('C++')->>'status') = 'ok', 'C++');
select pg_temp.assert_true((public.request_topic('C#')->>'status') = 'ok', 'C#');
select pg_temp.assert_true((select count(distinct topic_id) from public.user_topics where user_id = auth.uid() and active) = 2, 'C++ and C# distinct');
reset role;
\echo PASS 9 language keys remain distinct

-- 10: policy values are inspectable by the migration/session owner and match the freeze.
select pg_temp.assert_true((select max_active = 5 and daily_new_per_user = 3 and daily_new_global = 50 from public.topic_policy), 'policy values');
\echo PASS 10 policy values
\echo SQL remote staging tests: 10 passed, 0 failed; rolling back fixtures

rollback;
