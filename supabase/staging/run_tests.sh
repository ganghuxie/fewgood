#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PG_BIN=/workspace/codex/pg-local/postgresql-18.6.1-x86_64-unknown-linux-gnu/bin
export LD_LIBRARY_PATH=/workspace/codex/pg-local/postgresql-18.6.1-x86_64-unknown-linux-gnu/lib
PSQL=("$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d ytrec_v2_staging)

"${PSQL[@]}" -f "$ROOT/supabase/staging/00_auth_shim.sql"
"${PSQL[@]}" -f "$ROOT/supabase/migrations/20261110083000_v2_topics_down.sql"
"${PSQL[@]}" -f "$ROOT/supabase/migrations/20261110083000_v2_topics.sql"
"${PSQL[@]}" -f "$ROOT/supabase/staging/seed_aliases.sql"
"${PSQL[@]}" -f "$ROOT/supabase/staging/tests.sql"
# Rollback and reapply once to prove the migration can be cleanly reversed.
"${PSQL[@]}" -f "$ROOT/supabase/migrations/20261110083000_v2_topics_down.sql"
"${PSQL[@]}" -f "$ROOT/supabase/migrations/20261110083000_v2_topics.sql"
echo 'Down/up smoke: passed'
