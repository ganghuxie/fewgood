-- Run this in the Supabase SQL editor before enabling cloud sync.
create table if not exists public.library_items (
  id bigserial primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  kind text not null check (kind in ('history', 'favorites', 'watchLater', 'following', 'channelSeen')),
  item_id text not null,
  snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz not null default now(),
  deleted boolean not null default false,
  unique (user_id, kind, item_id)
);

create index if not exists library_items_user_kind_idx on public.library_items (user_id, kind);

create or replace function public.set_library_items_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists library_items_updated_at on public.library_items;
create trigger library_items_updated_at
before update on public.library_items
for each row execute function public.set_library_items_updated_at();

alter table public.library_items enable row level security;

drop policy if exists "Users can select their own library" on public.library_items;
create policy "Users can select their own library" on public.library_items
for select to authenticated using (user_id = auth.uid());

drop policy if exists "Users can insert their own library" on public.library_items;
create policy "Users can insert their own library" on public.library_items
for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "Users can update their own library" on public.library_items;
create policy "Users can update their own library" on public.library_items
for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "Users can delete their own library" on public.library_items;
create policy "Users can delete their own library" on public.library_items
for delete to authenticated using (user_id = auth.uid());
