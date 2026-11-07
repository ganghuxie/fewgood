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

export function emailRedirectTo() {
  return new URL(import.meta.env.BASE_URL, window.location.origin).href;
}
