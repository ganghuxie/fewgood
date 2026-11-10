-- Staging-only seed of curated V2 sub-topics.
-- Idempotent. Does not touch production. Follows can reuse these rows
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

insert into public.topic_aliases(alias_nfc,topic_id) values
 ('AI Agent','4660cad4-3482-5245-b2ba-2ef89efc3027')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('AI 产业动态','23226029-d190-59b1-8395-075803112a5f')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('AI 产品与应用','03fed865-3d5e-5f9b-9439-cddaec2acdb3')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('AI 模型与研究','64b00469-42cf-5904-821f-f217454a8db9')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('AI 编程','b799219f-0e80-5e17-bff2-ff6909d46fb2')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Agent 学习','51238008-d1dc-5982-955f-f54a69751924')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('EDM','607c4718-d49a-5f92-9a64-ed74740807ed')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('First Take','f9b17219-20c7-566e-a8d9-47eecab3a9f6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Hip-hop','e7ed0a05-8ef6-56b5-af95-709075f8dcdf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Hip-hop / 说唱','e7ed0a05-8ef6-56b5-af95-709075f8dcdf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('K-pop','c0ed68dd-bac3-5b7b-a286-176caed7f840')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Kpop','c0ed68dd-bac3-5b7b-a286-176caed7f840')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('R&B','f09b9f6b-2d93-5388-905d-65338c9f812a')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('R&B / Soul','f09b9f6b-2d93-5388-905d-65338c9f812a')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Soul','f09b9f6b-2d93-5388-905d-65338c9f812a')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('TED','6ab347a3-9c16-5895-8279-4b268856e4cf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('THE FIRST TAKE','f9b17219-20c7-566e-a8d9-47eecab3a9f6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Tiny Desk','945a53bb-2609-5526-8caa-ea1999bd719f')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('Tiny Desk 现场','945a53bb-2609-5526-8caa-ea1999bd719f')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('hiphop','e7ed0a05-8ef6-56b5-af95-709075f8dcdf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('k-pop','c0ed68dd-bac3-5b7b-a286-176caed7f840')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('ted talk','6ab347a3-9c16-5895-8279-4b268856e4cf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('tiny desk','945a53bb-2609-5526-8caa-ea1999bd719f')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('中文 AI','3e0475dd-78ac-5fa0-bbf9-55a28e65fb6d')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('中文播客','04d07c7c-55d8-5bb8-a1c2-8c893dd93482')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('中文说唱','e7ed0a05-8ef6-56b5-af95-709075f8dcdf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('人文社会','4db82635-6f0e-5556-ae53-f2f1a9ed1772')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('华语','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('华语流行','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('古典','5909d410-0fd4-52ea-9830-7a9d092cf7fe')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('周杰伦','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('周杰倫','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('商业创业','df6cb6ea-1a5b-5789-94c3-63ed6c176a19')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('商业访谈','96d9ade4-d7a6-58df-9e37-af0cbe2cdc1f')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('嘻哈','e7ed0a05-8ef6-56b5-af95-709075f8dcdf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('国语歌','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('國語歌','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('大学公开课','77c320ae-8cbc-5179-ad0e-fb8236da4ae1')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('广东歌','1e7c6415-ee70-5649-944b-a90ac2721fe6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('廣東歌','1e7c6415-ee70-5649-944b-a90ac2721fe6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('开源模型与本地部署','54f7c610-20dd-53b5-acbe-91cde1bbc136')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('日系','f9b17219-20c7-566e-a8d9-47eecab3a9f6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('日系现场','f9b17219-20c7-566e-a8d9-47eecab3a9f6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('林俊傑','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('林俊杰','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('欧美','5a75ee37-cc90-592a-8a63-74cac4c72920')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('欧美流行','5a75ee37-cc90-592a-8a63-74cac4c72920')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('民謠','1d66449c-9237-50af-9c2e-1cdd28b33565')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('民谣','1d66449c-9237-50af-9c2e-1cdd28b33565')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('爵士','5909d410-0fd4-52ea-9830-7a9d092cf7fe')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('爵士 / 古典','5909d410-0fd4-52ea-9830-7a9d092cf7fe')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('独立 / 民谣','1d66449c-9237-50af-9c2e-1cdd28b33565')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('独立音乐','1d66449c-9237-50af-9c2e-1cdd28b33565')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('獨立音樂','1d66449c-9237-50af-9c2e-1cdd28b33565')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('电子','607c4718-d49a-5f92-9a64-ed74740807ed')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('电子音乐','607c4718-d49a-5f92-9a64-ed74740807ed')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('科学与健康','0e4ac8a6-f93c-5327-b5d6-77b73548acc1')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('科学科普','cc6a4e24-5c16-577b-b71d-cb650f13c480')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('科技与 AI','b4482a20-82ad-59bd-807a-b27ae9016af5')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('粤语','1e7c6415-ee70-5649-944b-a90ac2721fe6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('粤语歌','1e7c6415-ee70-5649-944b-a90ac2721fe6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('粵語','1e7c6415-ee70-5649-944b-a90ac2721fe6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('经典演讲','cd298155-41d9-5097-a04a-245e445da58a')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('華語','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('華語流行','7722c78b-b74d-5cec-a4d8-c5de64bf1877')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('西方流行','5a75ee37-cc90-592a-8a63-74cac4c72920')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('說唱','e7ed0a05-8ef6-56b5-af95-709075f8dcdf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('说唱','e7ed0a05-8ef6-56b5-af95-709075f8dcdf')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('陈奕迅','1e7c6415-ee70-5649-944b-a90ac2721fe6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('陳奕迅','1e7c6415-ee70-5649-944b-a90ac2721fe6')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('電子音樂','607c4718-d49a-5f92-9a64-ed74740807ed')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
insert into public.topic_aliases(alias_nfc,topic_id) values
 ('韩流','c0ed68dd-bac3-5b7b-a286-176caed7f840')
on conflict (alias_nfc) do update set topic_id = excluded.topic_id;
commit;
