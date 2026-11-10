# Phase 1 local staging

本轮没有连接 production Supabase（`zdctckubirrlukbbrlwx`）。演练目标是 box-local PostgreSQL：`127.0.0.1:55432/ytrec_v2_staging`。`supabase/staging/00_auth_shim.sql` 提供最小的 `auth.uid()` JWT claim shim、anon/authenticated roles 和 `pgcrypto`；随后应用 topics up migration，导入仓库管理的 `config/topic-aliases.json` seed（本轮可复现的 SQL 镜像为 `supabase/staging/seed_aliases.sql`），再跑 SQL 断言。

重跑（仅本地 throwaway DB）：

```bash
supabase/staging/run_tests.sh
```

脚本会依次执行 shim、down（若已有对象）、up、seed、`tests.sql`，并作 down + up smoke。它不读取 production secrets、不使用 service_role，也不会调用 YouTube（0 units）。

本次实测结果（2026-11-10，Asia/Shanghai，box-local PG 18.6 on 127.0.0.1:55432）：**10 passed, 0 failed**，随后 down/up smoke 通过。覆盖：用户隔离与 direct-write 拒绝、anon 仅可读 sanitized queue、NFC/alias 复用不耗每日新建额度、活动上限 5、每日新建上限 3、invalid_input/alias_conflict、C++/C# 分离、policy 值。活动上限用例为同用户顺序事务证明（advisory lock）；真并发双连接竞态未单独压测。

## Real Supabase staging (`youtuber-staging`)

Do not use the local auth shim (`supabase/staging/00_auth_shim.sql`) on a real Supabase project. It already provides `auth.users`, `auth.uid()`, and the Supabase roles.

1. Set `SUPABASE_STAGING_DB_URL` to the full **Session pooler** URI. It must begin with `postgresql://` and must not contain the production project ref `zdctckubirrlukbbrlwx`.
2. Apply only the migration:

   ```bash
   psql "$SUPABASE_STAGING_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20261110083000_v2_topics.sql
   ```

3. Persist the curated aliases:

   ```bash
   psql "$SUPABASE_STAGING_DB_URL" -v ON_ERROR_STOP=1 -f supabase/staging/seed_aliases.sql
   ```

4. Run remote assertions:

   ```bash
   bash supabase/staging/run_tests_remote.sh
   ```

   `tests_remote.sql` creates all fixtures inside one transaction and always ends with `ROLLBACK`; a successful run leaves no test users, topics, aliases, counters, or user-topic rows. `SEED=1 bash supabase/staging/run_tests_remote.sh` may be used to run the persistent alias seed first.

5. For the live UI, Jason must also set the project URL and anon key as `PUBLIC_SUPABASE_*` values and corresponding GitHub Actions secrets. These are separate from the database Session pooler URI.
