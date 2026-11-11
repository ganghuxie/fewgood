-- fewgood P1: user topic affinity + cloud column store (staging only).
-- Do NOT run against production zdctckubirrlukbbrlwx until Jason approves.
-- Run this in the Supabase SQL editor on staging first.

-- P1-6: optional cloud home for the 我的空间 columns. The client keeps working
-- with localStorage even if this table does not exist. Merge uses local-wins.
create table if not exists public.user_topics (
  id bigserial primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  column_id text not null,
  source text not null,
  kind text not null default 'topic' check (kind in ('feed', 'topic')),
  topic_id text,
  label text,
  enabled boolean not null default true,
  position integer not null default 0,
  updated_at timestamptz not null default now(),
  unique (user_id, column_id)
);

create index if not exists user_topics_user_idx on public.user_topics (user_id);

alter table public.user_topics enable row level security;

drop policy if exists "Users can select their own topics" on public.user_topics;
create policy "Users can select their own topics" on public.user_topics
for select to authenticated using (user_id = auth.uid());

drop policy if exists "Users can insert their own topics" on public.user_topics;
create policy "Users can insert their own topics" on public.user_topics
for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "Users can update their own topics" on public.user_topics;
create policy "Users can update their own topics" on public.user_topics
for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "Users can delete their own topics" on public.user_topics;
create policy "Users can delete their own topics" on public.user_topics
for delete to authenticated using (user_id = auth.uid());

-- P1-3: optional cloud home for favorite -> subscribe affinity.
create table if not exists public.user_topic_affinity (
  user_id uuid not null references auth.users(id) on delete cascade,
  topic_id text not null,
  favorite_count integer not null default 0,
  last_suggested_at timestamptz,
  muted_until timestamptz,
  primary key (user_id, topic_id)
);

alter table public.user_topic_affinity enable row level security;

drop policy if exists "Users can select their own affinity" on public.user_topic_affinity;
create policy "Users can select their own affinity" on public.user_topic_affinity
for select to authenticated using (user_id = auth.uid());

drop policy if exists "Users can insert their own affinity" on public.user_topic_affinity;
create policy "Users can insert their own affinity" on public.user_topic_affinity
for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "Users can update their own affinity" on public.user_topic_affinity;
create policy "Users can update their own affinity" on public.user_topic_affinity
for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
