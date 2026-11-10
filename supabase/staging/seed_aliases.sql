-- Generated from config/topic-aliases.json for the staging seed.
-- Keep C++ and C# absent: they must never be auto-merged.
insert into public.topics(id,canonical_name,normalized_key,search_query) values
 ('10000000-0000-0000-0000-000000000001','Café','v1:' || encode(sha256(convert_to('Café', 'UTF8')), 'hex'),'Café')
on conflict (id) do update set
  canonical_name = excluded.canonical_name,
  normalized_key = excluded.normalized_key,
  search_query = excluded.search_query;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Café','10000000-0000-0000-0000-000000000001'),
 ('espresso','10000000-0000-0000-0000-000000000001')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
