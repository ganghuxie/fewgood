import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.PUBLIC_SUPABASE_URL;
const key = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;
let client;

// A placeholder is deliberately treated as absent, so checked-in config stays safe.
export const supabaseEnabled = Boolean(url && key && key !== '__FILL__');

export function getSupabase() {
  if (!supabaseEnabled) return null;
  client ||= createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } });
  return client;
}

export function safeRedirect(value, fallback = `${location.pathname}${location.search}`) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\') || value.includes('\\')) return fallback;
  return value;
}
export function emailRedirectTo() {
  const current = new URL(location.href);
  current.searchParams.delete('redirect');
  const redirect = safeRedirect(`${current.pathname}${current.search}`, new URL(import.meta.env.BASE_URL, location.origin).pathname);
  const callback = new URL(import.meta.env.BASE_URL, location.origin);
  callback.searchParams.set('redirect', redirect);
  return callback.href;
}
