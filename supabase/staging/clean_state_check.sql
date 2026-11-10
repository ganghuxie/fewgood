-- Read-only proof that rollback left no fixture rows; seed aliases may remain.
select 'fixture_users' as check, count(*)::bigint as n
  from auth.users
 where id in (
   '00000000-0000-0000-0000-0000000000a1',
   '00000000-0000-0000-0000-0000000000b2',
   '00000000-0000-0000-0000-0000000000c3',
   '00000000-0000-0000-0000-0000000000d4',
   '00000000-0000-0000-0000-0000000000e5',
   '00000000-0000-0000-0000-0000000000f6'
 ) or email like 'v2-fixture-%@example.test';
select 'fixture_user_topics' as check, count(*)::bigint as n
  from public.user_topics
 where user_id in (
   '00000000-0000-0000-0000-0000000000a1',
   '00000000-0000-0000-0000-0000000000b2',
   '00000000-0000-0000-0000-0000000000c3',
   '00000000-0000-0000-0000-0000000000d4',
   '00000000-0000-0000-0000-0000000000e5',
   '00000000-0000-0000-0000-0000000000f6'
 );
select 'cap_topics' as check, count(*)::bigint as n
  from public.topics
 where canonical_name like 'Cap topic %';
select 'seed_cafe_topic' as check, count(*)::bigint as n
  from public.topics
 where id = '10000000-0000-0000-0000-000000000001';
select 'seed_aliases' as check, count(*)::bigint as n
  from public.topic_aliases
 where topic_id = '10000000-0000-0000-0000-000000000001';
