-- Staging-only seed of curated V2 sub-topics.
-- Idempotent. Does not touch production.
-- Alias rows resolve topic_id by normalized_key so preexisting staging topics keep their ids. Follows can reuse these rows
-- so request_topic does not consume daily_new caps or fail as invalid_input.
begin;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('64b00469-42cf-5904-821f-f217454a8db9','AI 模型与研究','v1:' || encode(sha256(convert_to('AI 模型与研究', 'UTF8')), 'hex'),'AI 模型与研究')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('4660cad4-3482-5245-b2ba-2ef89efc3027','AI Agent','v1:' || encode(sha256(convert_to('AI Agent', 'UTF8')), 'hex'),'AI Agent')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('b799219f-0e80-5e17-bff2-ff6909d46fb2','AI 编程','v1:' || encode(sha256(convert_to('AI 编程', 'UTF8')), 'hex'),'AI 编程')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('03fed865-3d5e-5f9b-9439-cddaec2acdb3','AI 产品与应用','v1:' || encode(sha256(convert_to('AI 产品与应用', 'UTF8')), 'hex'),'AI 产品与应用')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('23226029-d190-59b1-8395-075803112a5f','AI 产业动态','v1:' || encode(sha256(convert_to('AI 产业动态', 'UTF8')), 'hex'),'AI 产业动态')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('51238008-d1dc-5982-955f-f54a69751924','Agent 学习','v1:' || encode(sha256(convert_to('Agent 学习', 'UTF8')), 'hex'),'Agent 学习')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('54f7c610-20dd-53b5-acbe-91cde1bbc136','开源模型与本地部署','v1:' || encode(sha256(convert_to('开源模型与本地部署', 'UTF8')), 'hex'),'开源模型与本地部署')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('3e0475dd-78ac-5fa0-bbf9-55a28e65fb6d','中文 AI','v1:' || encode(sha256(convert_to('中文 AI', 'UTF8')), 'hex'),'中文 AI')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('6ab347a3-9c16-5895-8279-4b268856e4cf','TED','v1:' || encode(sha256(convert_to('TED', 'UTF8')), 'hex'),'TED')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('96d9ade4-d7a6-58df-9e37-af0cbe2cdc1f','商业访谈','v1:' || encode(sha256(convert_to('商业访谈', 'UTF8')), 'hex'),'商业访谈')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('b4482a20-82ad-59bd-807a-b27ae9016af5','科技与 AI','v1:' || encode(sha256(convert_to('科技与 AI', 'UTF8')), 'hex'),'科技与 AI')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('df6cb6ea-1a5b-5789-94c3-63ed6c176a19','商业创业','v1:' || encode(sha256(convert_to('商业创业', 'UTF8')), 'hex'),'商业创业')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('0e4ac8a6-f93c-5327-b5d6-77b73548acc1','科学与健康','v1:' || encode(sha256(convert_to('科学与健康', 'UTF8')), 'hex'),'科学与健康')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('4db82635-6f0e-5556-ae53-f2f1a9ed1772','人文社会','v1:' || encode(sha256(convert_to('人文社会', 'UTF8')), 'hex'),'人文社会')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('04d07c7c-55d8-5bb8-a1c2-8c893dd93482','中文播客','v1:' || encode(sha256(convert_to('中文播客', 'UTF8')), 'hex'),'中文播客')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('945a53bb-2609-5526-8caa-ea1999bd719f','Tiny Desk 现场','v1:' || encode(sha256(convert_to('Tiny Desk 现场', 'UTF8')), 'hex'),'Tiny Desk 现场')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('f9b17219-20c7-566e-a8d9-47eecab3a9f6','日系现场','v1:' || encode(sha256(convert_to('日系现场', 'UTF8')), 'hex'),'日系现场')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('5a75ee37-cc90-592a-8a63-74cac4c72920','欧美流行','v1:' || encode(sha256(convert_to('欧美流行', 'UTF8')), 'hex'),'欧美流行')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('c0ed68dd-bac3-5b7b-a286-176caed7f840','K-pop','v1:' || encode(sha256(convert_to('K-pop', 'UTF8')), 'hex'),'K-pop')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('e7ed0a05-8ef6-56b5-af95-709075f8dcdf','Hip-hop / 说唱','v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex'),'Hip-hop / 说唱')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('7722c78b-b74d-5cec-a4d8-c5de64bf1877','华语流行','v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex'),'华语流行')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('1e7c6415-ee70-5649-944b-a90ac2721fe6','粤语','v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex'),'粤语')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('1d66449c-9237-50af-9c2e-1cdd28b33565','独立 / 民谣','v1:' || encode(sha256(convert_to('独立 / 民谣', 'UTF8')), 'hex'),'独立 / 民谣')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('5909d410-0fd4-52ea-9830-7a9d092cf7fe','爵士 / 古典','v1:' || encode(sha256(convert_to('爵士 / 古典', 'UTF8')), 'hex'),'爵士 / 古典')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('f09b9f6b-2d93-5388-905d-65338c9f812a','R&B / Soul','v1:' || encode(sha256(convert_to('R&B / Soul', 'UTF8')), 'hex'),'R&B / Soul')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('607c4718-d49a-5f92-9a64-ed74740807ed','电子','v1:' || encode(sha256(convert_to('电子', 'UTF8')), 'hex'),'电子')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('cd298155-41d9-5097-a04a-245e445da58a','经典演讲','v1:' || encode(sha256(convert_to('经典演讲', 'UTF8')), 'hex'),'经典演讲')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('77c320ae-8cbc-5179-ad0e-fb8236da4ae1','大学公开课','v1:' || encode(sha256(convert_to('大学公开课', 'UTF8')), 'hex'),'大学公开课')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;
insert into public.topics(id,canonical_name,normalized_key,search_query)
values ('cc6a4e24-5c16-577b-b71d-cb650f13c480','科学科普','v1:' || encode(sha256(convert_to('科学科普', 'UTF8')), 'hex'),'科学科普')
on conflict (normalized_key) do update set
  canonical_name = excluded.canonical_name,
  search_query = excluded.search_query;

insert into public.topic_aliases(alias_nfc,topic_id)
select 'AI Agent', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('AI Agent', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'AI 产业动态', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('AI 产业动态', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'AI 产品与应用', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('AI 产品与应用', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'AI 模型与研究', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('AI 模型与研究', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'AI 编程', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('AI 编程', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'Agent 学习', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Agent 学习', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'EDM', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('电子', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'First Take', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('日系现场', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'Hip-hop', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'Hip-hop / 说唱', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'K-pop', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('K-pop', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'Kpop', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('K-pop', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'R&B', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('R&B / Soul', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'R&B / Soul', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('R&B / Soul', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'Soul', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('R&B / Soul', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'TED', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('TED', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'THE FIRST TAKE', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('日系现场', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'Tiny Desk', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Tiny Desk 现场', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'Tiny Desk 现场', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Tiny Desk 现场', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'hiphop', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'k-pop', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('K-pop', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'ted talk', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('TED', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select 'tiny desk', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Tiny Desk 现场', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '中文 AI', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('中文 AI', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '中文播客', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('中文播客', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '中文说唱', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '人文社会', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('人文社会', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '华语', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '华语流行', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '古典', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('爵士 / 古典', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '周杰伦', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '周杰倫', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '商业创业', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('商业创业', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '商业访谈', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('商业访谈', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '嘻哈', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '国语歌', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '國語歌', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '大学公开课', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('大学公开课', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '广东歌', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '廣東歌', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '开源模型与本地部署', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('开源模型与本地部署', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '日系', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('日系现场', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '日系现场', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('日系现场', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '林俊傑', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '林俊杰', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '欧美', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('欧美流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '欧美流行', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('欧美流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '民謠', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('独立 / 民谣', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '民谣', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('独立 / 民谣', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '爵士', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('爵士 / 古典', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '爵士 / 古典', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('爵士 / 古典', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '独立 / 民谣', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('独立 / 民谣', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '独立音乐', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('独立 / 民谣', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '獨立音樂', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('独立 / 民谣', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '电子', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('电子', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '电子音乐', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('电子', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '科学与健康', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('科学与健康', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '科学科普', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('科学科普', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '科技与 AI', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('科技与 AI', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '粤语', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '粤语歌', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '粵語', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '经典演讲', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('经典演讲', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '華語', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '華語流行', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('华语流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '西方流行', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('欧美流行', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '說唱', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '说唱', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('Hip-hop / 说唱', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '陈奕迅', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '陳奕迅', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('粤语', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '電子音樂', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('电子', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id)
select '韩流', id from public.topics
where normalized_key = 'v1:' || encode(sha256(convert_to('K-pop', 'UTF8')), 'hex')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
commit;
