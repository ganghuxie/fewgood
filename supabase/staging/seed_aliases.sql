-- Generated from config/topic-aliases.json for the initial local staging seed.
-- Keep C++ and C# absent: they must never be auto-merged.
insert into public.topics(id,canonical_name,normalized_key,search_query) values
 ('10000000-0000-0000-0000-000000000001','Café','v1:' || encode(digest('Café','sha256'),'hex'),'Café');
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Café','10000000-0000-0000-0000-000000000001'),
 ('espresso','10000000-0000-0000-0000-000000000001');
