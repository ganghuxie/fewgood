-- Local-only, minimal Supabase auth surface.  Apply this before the migration.
create extension if not exists pgcrypto;

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticator') then create role authenticator nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'topic_view_owner') then create role topic_view_owner nologin nobypassrls; end if;
end $$;

create schema if not exists auth;
create schema if not exists staging;
create table if not exists auth.users (id uuid primary key);

create or replace function auth.uid() returns uuid language sql stable as $$
  select cast(nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub' as uuid)
$$;

create or replace function staging.set_jwt(uid uuid) returns void language plpgsql as $$
begin
  perform set_config('request.jwt.claims', jsonb_build_object('sub', uid)::text, false);
end $$;

revoke all on function staging.set_jwt(uuid) from public;
grant usage on schema public, auth to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
