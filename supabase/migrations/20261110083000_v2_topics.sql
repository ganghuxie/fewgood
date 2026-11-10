-- Apply this file only on real Supabase; do NOT apply supabase/staging/00_auth_shim.sql.
-- V2 Space topics, scheme A: clients only call RPCs; no service_role is needed.
create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'topic_view_owner') then
    create role topic_view_owner nologin nobypassrls;
  end if;
end $$;
alter role topic_view_owner nologin nobypassrls;
-- Supabase PG16: the migrating role needs SET on topic_view_owner to make it a view owner.
do $$
begin
  execute format('grant topic_view_owner to %I with set true', current_user);
exception when others then
  execute format('grant topic_view_owner to %I', current_user);
end $$;

grant usage on schema public to anon, authenticated;

create table if not exists public.topic_policy (
  singleton boolean primary key default true check (singleton),
  max_active integer not null default 5 check (max_active > 0),
  daily_new_per_user integer not null default 3 check (daily_new_per_user > 0),
  daily_new_global integer not null default 50 check (daily_new_global > 0)
);
insert into public.topic_policy(singleton) values (true) on conflict (singleton) do nothing;

create table if not exists public.topics (
  id uuid primary key default gen_random_uuid(),
  canonical_name text not null check (char_length(canonical_name) between 2 and 80),
  normalized_key text not null unique check (normalized_key ~ '^[a-z0-9:_-]{32,128}$'),
  search_query text not null,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.user_topics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  topic_id uuid not null references public.topics(id),
  display_name text,
  sort_order integer not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  removed_at timestamptz,
  unique (user_id, topic_id)
);
create index if not exists user_topics_active_user_idx on public.user_topics(user_id) where active;

create table if not exists public.topic_creation_user_counters (
  user_id uuid not null references auth.users(id),
  pacific_day date not null,
  new_topics integer not null default 0 check (new_topics >= 0),
  primary key (user_id, pacific_day)
);
create table if not exists public.topic_creation_global_counters (
  pacific_day date primary key,
  new_topics integer not null default 0 check (new_topics >= 0)
);

-- Repo-synced seed data maps normalized NFC aliases to a canonical topic.
-- Production deployment imports config/topic-aliases.json before opening the queue.
create table if not exists public.topic_aliases (
  alias_nfc text primary key,
  topic_id uuid not null references public.topics(id)
);

alter table public.topics enable row level security;
alter table public.topics force row level security;
alter table public.user_topics enable row level security;
alter table public.user_topics force row level security;
alter table public.topic_creation_user_counters enable row level security;
alter table public.topic_creation_user_counters force row level security;
alter table public.topic_creation_global_counters enable row level security;
alter table public.topic_creation_global_counters force row level security;
alter table public.topic_aliases enable row level security;
alter table public.topic_aliases force row level security;
alter table public.topic_policy enable row level security;
alter table public.topic_policy force row level security;

drop policy if exists worker_reads_active_topics on public.topics;
create policy worker_reads_active_topics on public.topics for select to topic_view_owner using (active);
drop policy if exists users_read_their_topics on public.user_topics;
create policy users_read_their_topics on public.user_topics for select to authenticated using (user_id = auth.uid());
-- Counters, aliases, policy, and base topics deliberately have no client policies.

revoke all on public.topics, public.user_topics, public.topic_creation_user_counters,
  public.topic_creation_global_counters, public.topic_aliases, public.topic_policy from anon, authenticated;
grant select on public.user_topics to authenticated;

drop view if exists public.public_topic_worker_queue;
create view public.public_topic_worker_queue
  with (security_barrier = true, security_invoker = false) as
  select id as topic_id, canonical_name, search_query, created_at
  from public.topics where active;
alter view public.public_topic_worker_queue owner to topic_view_owner;
grant usage on schema public to topic_view_owner;
grant select on public.topics to topic_view_owner;
grant select on public.public_topic_worker_queue to anon;

create or replace function public.request_topic(p_name text, p_sort text default 'relevance')
returns jsonb language plpgsql security definer set search_path = pg_catalog, public as $$
declare
  v_user uuid := auth.uid(); v_name text; v_key text; v_topic uuid; v_direct uuid;
  v_new boolean := false; v_day date := (now() at time zone 'America/Los_Angeles')::date;
  v_policy public.topic_policy; v_active integer; v_user_new integer; v_global_new integer;
begin
  if v_user is null then return jsonb_build_object('status','invalid_input','error','invalid_input'); end if;
  v_name := regexp_replace(btrim(normalize(coalesce(p_name, ''), NFC)), '[[:space:]]+', ' ', 'g');
  if char_length(v_name) not between 2 and 80 or v_name ~ '[[:cntrl:]]' or
     v_name ~* '(https?://|www\\.)' or v_name ~ '[<>]' or v_name !~ '[[:alnum:]]' then
    return jsonb_build_object('status','invalid_input','error','invalid_input');
  end if;
  if coalesce(p_sort, 'relevance') not in ('relevance','newest') then
    return jsonb_build_object('status','invalid_input','error','invalid_input');
  end if;
  perform pg_advisory_xact_lock(hashtextextended(v_user::text, 83000));
  select * into v_policy from public.topic_policy where singleton;
  select count(*) into v_active from public.user_topics where user_id=v_user and active;
  if v_active >= v_policy.max_active then return jsonb_build_object('status','limit_reached','error','limit_reached'); end if;

  v_key := 'v1:' || encode(digest(v_name, 'sha256'), 'hex');
  select id into v_direct from public.topics where normalized_key=v_key;
  select a.topic_id into v_topic from public.topic_aliases a where a.alias_nfc=v_name;
  if v_topic is not null and v_direct is not null and v_topic <> v_direct then
    return jsonb_build_object('status','alias_conflict','error','alias_conflict');
  end if;
  v_topic := coalesce(v_topic, v_direct);
  if v_topic is null then
    perform pg_advisory_xact_lock(hashtextextended('global-topic-new:' || v_day::text, 83000));
    select new_topics into v_user_new from public.topic_creation_user_counters where user_id=v_user and pacific_day=v_day for update;
    if coalesce(v_user_new, 0) >= v_policy.daily_new_per_user then return jsonb_build_object('status','daily_cap','error','daily_cap'); end if;
    select new_topics into v_global_new from public.topic_creation_global_counters where pacific_day=v_day for update;
    if coalesce(v_global_new, 0) >= v_policy.daily_new_global then return jsonb_build_object('status','daily_cap','error','daily_cap'); end if;
    insert into public.topics(canonical_name, normalized_key, search_query) values (v_name, v_key, v_name) returning id into v_topic;
    insert into public.topic_creation_user_counters(user_id,pacific_day,new_topics) values(v_user,v_day,1)
      on conflict(user_id,pacific_day) do update set new_topics=public.topic_creation_user_counters.new_topics+1;
    insert into public.topic_creation_global_counters(pacific_day,new_topics) values(v_day,1)
      on conflict(pacific_day) do update set new_topics=public.topic_creation_global_counters.new_topics+1;
    v_new := true;
  end if;
  insert into public.user_topics(user_id,topic_id,active,removed_at,updated_at)
    values(v_user,v_topic,true,null,now())
    on conflict(user_id,topic_id) do update set active=true, removed_at=null, updated_at=now();
  return jsonb_build_object('status','ok','topic_id',v_topic,'created',v_new);
end $$;

create or replace function public.rename_user_topic(p_user_topic_id uuid, p_display_name text)
returns jsonb language plpgsql security definer set search_path = pg_catalog, public as $$
begin
  update public.user_topics set display_name=nullif(btrim(p_display_name),''), updated_at=now()
   where id=p_user_topic_id and user_id=auth.uid() and active;
  if not found then return jsonb_build_object('status','invalid_input','error','invalid_input'); end if;
  return jsonb_build_object('status','ok');
end $$;
create or replace function public.move_user_topic(p_user_topic_id uuid, p_sort_order integer)
returns jsonb language plpgsql security definer set search_path = pg_catalog, public as $$
begin
  update public.user_topics set sort_order=p_sort_order, updated_at=now()
   where id=p_user_topic_id and user_id=auth.uid() and active;
  if not found then return jsonb_build_object('status','invalid_input','error','invalid_input'); end if;
  return jsonb_build_object('status','ok');
end $$;
create or replace function public.remove_user_topic(p_user_topic_id uuid)
returns jsonb language plpgsql security definer set search_path = pg_catalog, public as $$
begin
  update public.user_topics set active=false, removed_at=now(), updated_at=now()
   where id=p_user_topic_id and user_id=auth.uid() and active;
  if not found then return jsonb_build_object('status','invalid_input','error','invalid_input'); end if;
  return jsonb_build_object('status','ok');
end $$;

revoke all on function public.request_topic(text,text), public.rename_user_topic(uuid,text),
  public.move_user_topic(uuid,integer), public.remove_user_topic(uuid) from public, anon, authenticated, topic_view_owner;
grant execute on function public.request_topic(text,text), public.rename_user_topic(uuid,text),
  public.move_user_topic(uuid,integer), public.remove_user_topic(uuid) to authenticated;

create table if not exists public.schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);
insert into public.schema_migrations(version) values ('20261110083000')
  on conflict (version) do nothing;
