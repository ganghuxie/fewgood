#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB_URL="${SUPABASE_STAGING_DB_URL:-}"

if [[ -z "$DB_URL" ]]; then
  echo 'SUPABASE_STAGING_DB_URL must be set.' >&2
  exit 1
fi
if [[ "$DB_URL" != postgresql://* ]]; then
  echo 'SUPABASE_STAGING_DB_URL must be a full postgresql:// Session pooler URI.' >&2
  exit 1
fi
if [[ "$DB_URL" == *zdctckubirrlukbbrlwx* ]]; then
  echo 'Refusing production project URL.' >&2
  exit 1
fi

PSQL=(psql -X -v ON_ERROR_STOP=1 "$DB_URL")

if [[ "${SEED:-0}" == '1' ]]; then
  "${PSQL[@]}" -f "$ROOT/supabase/staging/seed_aliases.sql"
fi
"${PSQL[@]}" -f "$ROOT/supabase/staging/tests_remote.sql"
