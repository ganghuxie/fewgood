# YouTuber 2.0 自定义栏目 MVP 实施计划

## 0. 范围、证据与结论

本文件是实施前计划，**不是实现结果**。本次只检查了仓库内与需求直接相关的源码、配置、工作流和既有文档；未读取 `.env`、凭据或机器账户文件，未执行网络、YouTube API、Supabase 或认证测试，也没有运行真实回归测试。本文件不构成 production migration 或部署记录。

标记约定：`[已检查]` 是由下列路径可复核的事实；`[用户提供]` 来自任务说明、仓库中未找到同等证据；`[协调方官方页证据]` 是协调方本轮已公开打开并于 2026-11-07（Asia/Shanghai）核对的官方页，本文**未自行抓取**；`[待确认]` 不作事实假设，须在实施前确认。

结论：保持 Astro 静态站、GitHub Pages 部署和当前 Supabase Auth/浏览器本地库不变是可行的。自定义主题的采集必须在本机完成，页面只读取随 Git 推送发布的静态主题 JSON；浏览器不得持有 YouTube 凭据。建议将“主题配置/归属”与“公开视频内容池”分离，默认不公开某用户订阅了什么主题。

## 1. 当前架构审查（需求二）

### 1.1 前端、路由与数据流

- [已检查] 前端为 Astro 5 静态输出（`site/astro.config.mjs`，`output: 'static'`，生产 `base: /youtuber`）；构建会先生成搜索/目录 JSON（`site/package.json`、`site/scripts/build-catalog.mjs`）。
- [已检查] 公共栏目由编译期导入 `trending.json`、`ai.json`、`podcast.json`、`music.json`、`videos.json`，通过 catch-all 静态路由渲染；社区的“最多推荐/最新入选”排序现状不得改变（`site/src/pages/[...path].astro`、`site/src/components/VideoPage.astro`）。
- [已检查] 浏览器运行时还会读取 `catalog.json`、`channels.json`、`search-index.json`，供搜索、收藏页、侧栏关注等使用（`site/scripts/build-catalog.mjs`、`site/src/pages/search.astro`、`site/src/components/Sidebar.astro`、`site/src/components/LibraryPage.astro`）。自定义主题应沿用这种“静态页面 + 浏览器 fetch 静态 JSON”的模式，而非给 Pages 加动态后端。
- [已检查] 视频页使用站内的 `youtube-nocookie` 嵌入，并提供前往 YouTube 的链接（`site/src/components/VideoPage.astro`、`README.md`）。必须保留播放器、来源及跳转完整性；仅展示 YouTube 缩略图/元数据，不下载、转码、重托管视频。
- [已检查] 品牌名与标语已有集中常量（`site/src/lib/brand.mjs`），但栏目中文字散落在 `VideoPage.astro`、`build-catalog.mjs` 等。2.0 新文案与潜在改名应继续收口到品牌/栏目定义模块，避免分散硬编码。
- [已检查] 390px 搜索页截图已存在（`screenshots/search_ai_390.png`），任务说明指出该宽度头部溢出；这是新增双模式控件前必须修复/回归的已知 UI 风险。

### 1.2 内容来源、缓存和刷新作业

- [已检查] 公共“社区推荐”源是 Hacker News Algolia：爬取 story/comment 中的 YouTube 链接，持久化到 SQLite，按作者、月份和时间跨度筛选（`ytrec/core.py` 的 `crawl`/`extract`/`aggregate`，`README.md`）。仓库和说明中没有其他社区抓取模块、配置或输出；不得把当前来源标为其他社区。
- [已检查] HN SQLite 缓存位于 `data/ytrec.sqlite`，含原始项、已完成时间窗、mentions、视频 metadata、配额记录与入选时间；`metadata` 缓存默认 30 天（`ytrec/core.py`、`config.yaml`）。
- [已检查] 趋势、播客、音乐各使用五个六日窗口、每窗两个 duration bucket（`medium`、`long`）的 YouTube `search`，再用 `videos` 批量补全；所以日常 `refresh()` 的这三条路径是 `3 × 5 × 2 = 30` 次 `search`，不是 15 次。若把“一条 feed 的五个窗口”误计为 5，则三条 feed 是 15 个逻辑窗口，但每个窗口实际发两次 search。AI 通过已审核频道的 uploads playlist 取得近期视频（`ytrec/core.py` 的 `windowed_viewcount_feed`、`ai_feed`）。这类短窗口栏目有意直接输出提交的 JSON，而非复用社区 SQLite metadata 缓存。
- [已检查] `Client` 有至少约 1 秒（HN）或 0.05 秒（feed）的节流、最多 7 次尝试、指数退避、90 秒请求截止；请求异常不会输出 URL/密钥（`ytrec/core.py`）。现有实现只在第一次尝试记一次 API 单位，故计划中的主题作业需另行记录“尝试数、实际调用数、失败原因类别”，不可把现有近似账当成服务端权威账。
- [已检查] 本地 `data/quota.json` 按 `America/Los_Angeles` 日期累计，达到 `metadata.daily_quota_limit: 8000` 前拒绝新调用（`ytrec/core.py`、`config.yaml`）。这是本机防线，不是 Google 的实时配额证明，也没有跨进程锁。
- [用户提供] 已部署分支为 `master`；本机每日运行 `python3 -m ytrec refresh` 后提交/推送，GitHub Actions Pages 构建发布。[已检查] `refresh` 会刷新五类数据、构建、只在数据有变化时 `git add/commit/push`（`ytrec/__main__.py`）；工作流同时监听 `main` 和 `master`，Pages job 的并发组为 `pages`（`.github/workflows/pages.yml`）。仓库内未发现 crontab/systemd/调度脚本，故每日调度时间、锁与运行账户均为 [待确认]。

### 1.3 登录、个人数据和部署

- [已检查] 认证为 Supabase JS 的既有邮箱密码（可选 OAuth）会话；前端仅读取 `PUBLIC_SUPABASE_URL` 和 `PUBLIC_SUPABASE_ANON_KEY`，无配置则降级（`site/src/scripts/supabase.js`、`site/src/components/AuthMenu.astro`）。必须保留此认证，不替换为新身份系统。
- [已检查] 匿名的历史、收藏、稍后看、关注、频道已看使用 `localStorage`；登录后同步同名类型到 `library_items`（`site/src/scripts/library.js`、`site/src/scripts/sync.js`）。历史上限 100。自定义主题的匿名方案只能保存“已有已发布主题的排列/显示偏好”到 `localStorage`；未命中缓存的主题请求必须登录。
- [已检查] `public.library_items` 已有 `(user_id, kind, item_id)` 唯一约束与只允许本人增删改查的 RLS（`supabase/schema.sql`）。2.0 不改其语义，不将 topic 数据塞入该表。
- [已检查] Pages 在 GitHub Actions 中 `npm ci`、Astro build、上传 `site/dist` 并部署（`.github/workflows/pages.yml`）。CI 不需要 YouTube 凭据；这也是新作业应继续遵守的边界。

## 2. 可复用模块与建议边界

| 目标 | 复用 | 2.0 增补 |
|---|---|---|
| 双模式 UI/页面壳 | `Layout.astro`、`Header.astro`、全局网格样式 | 客户端切换而非整页刷新；将栏目标签集中定义 |
| 视频卡片/播放 | `VideoPage.astro`、`pagination.mjs`、频道头像 | 提取可供“我的空间”使用的卡片渲染/格式化函数，保留 `from` 来源与嵌入规则 |
| 搜索与静态索引 | `build-catalog.mjs`、`feeds.mjs` | 把已发布主题视频合并/去重进索引；不要以用户历史影响探索排序 |
| 匿名/登录状态 | `library.js`、`supabase.js`、`AuthMenu.astro`、`sync.js` | 新建独立 `topics.js`；复用 session 获取，不改 `library_items` 同步协议 |
| API 限制/容错 | `Client`、`charge_quota`、`pacific_today` | 主题 job 的持久化队列、进程锁、预算预留、有限重试、原子发布 |
| 品牌与部署 | `brand.mjs`、`refresh()`、Pages workflow | 集中品牌/栏目字符串；主题静态产物随既有 Git push 发布 |

## 3. 建议的数据模型、SQL 草案与权限

### 3.1 设计选择

主题分三层：

1. **公共规范主题池**：只保存可公开的规范标题、经验证的检索表达式和别名；它是跨用户复用和静态内容的索引，不保存请求者、私人原文、作业诊断、“谁订阅”或发布状态。发布时间/版本只以已发布静态主题 JSON/索引为事实来源；不保留会与它漂移的 `published_version` 或 DB `published_at` 字段。
2. **用户主题关系**：保存 `user_id`、显示名、排序、默认排序、删除标记；仅本人可见。一个用户最多 5 个活动主题，值由数据库配置/函数参数集中控制，前端只作辅助提示。
3. **本机作业状态**：`pending/running/succeeded/empty/retryable_failed/exhausted`、尝试次数、下次尝试、预算和错误类别仅写进发布的静态状态 JSON（对外只暴露主题级、非用户级摘要）。不把 `user_id`、请求文本、job token 或 API 失败细节发布到 JSON。

这样公开的只是规范化后、可在站点上被任何人浏览的主题及其视频；用户订阅关系仍受 RLS 保护。输入提示应明确“创建的规范主题和公开视频结果可能被复用/公开”，并避免把敏感个人问题、医疗/身份/地点等原文直接变成公共主题。若产品要支持私人主题，需单独产品决策和非公开数据/成本模型，本 MVP 不暗中承诺。

### 3.2 两种最小权限方案比较

**方案 A（推荐）：一个净化的 worker read-only、definer-owned 视图 + 认证 RLS/受限 RPC 提交 + 静态 job 状态。**

- 已发布页面只读 Git 发布的静态 topic index/JSON，绝不读数据库 catalog。`public_topic_worker_queue` 仅给本机 anon-key worker 读候选主题；它只输出 `topic_id`、验证后的 `search_query`、canonical name 和 `created_at`，绝不输出 `user_id`、原输入、计数或诊断。worker 因而确实能取得搜索所需 query，且无需表的直接 SELECT。
- 该视图必须是默认的 **security-definer**（不是 `security_invoker`），由专用无登录、无 `BYPASSRLS` 的 owner 拥有；底表 `FORCE ROW LEVEL SECURITY`，仅为该 owner 建立只允许 queue 行的 SELECT policy。只给 `anon` 该视图的 `SELECT`，撤销 anon/authenticated 对表的全部权限。这样即使 topics 表没有 anon SELECT、也没有给它开读 RLS，视图仍按受限 owner 的固定行集工作；不可把它替换成 `security_invoker=true`，否则当前“表 SELECT 已 revoke、无 anon RLS”的设计会让 worker 空读/报权限错误。
- `request_topic` 在数据库事务中进行 Unicode 规范化、验证、受管别名匹配、活动数和每日用户/全局新增上限检查，再创建或复用规范主题和用户关系。客户端没有对 topics/counters/user_topics 的写权限，不能绕过该检查；提交 RPC 不接受或返回任何作业密钥。
- 本机只读取 `public_topic_worker_queue`，调用 YouTube 后生成静态 JSON、构建、提交并推送；它不回写 Supabase job 状态。pending 的完成判定来自已发布的 topic index/本地 SQLite journal：单采集者将“已发布且未过期”从候选清单排除。它可在没有 DB status write 的情况下工作，但多采集者不允许；诊断保留在本地安全日志。

**方案 B：`SECURITY DEFINER` 作业 RPC + 专用本机 job token。**

- 前端仍以方案 A 的 RLS/用户 RPC 提交；仅本机可调用的 claim/complete/fail RPC 以 `SECURITY DEFINER` 运行，必须验证独立 job token（令牌只在本机环境和 Supabase 非公开机密设置中存储，绝不可放入 `PUBLIC_*`、静态 JSON、日志或 Git）。RPC 固定 `search_path`、撤销 `PUBLIC` execute、只授予受限调用角色；逐次检查 token、主题 ID、状态迁移和乐观版本，绝不接受任意 SQL/用户 ID。
- 优点：可由数据库原子租约/状态机跨进程协调；缺点：实现和密钥保管风险更高，token 泄露会扩大为作业写权限。

**推荐方案 A 作为 MVP 的安全默认**：满足“本机采集、Pages 静态发布、不得用 service_role/secret key”，权限面最小且作业状态本来只需静态反馈。若以后需要多台采集机或数据库级租约，再经安全审查升级到 B；不能以方便为由在浏览器或 Actions 放 service_role、secret key，也不能把 service_role 换名后使用。

### 3.3 SQL 草案（实施前需在隔离项目审阅/演练）

以下是迁移设计草案，不在本次执行。实际 SQL 需符合现有 Supabase/Postgres 版本，并先备份/检查现有 policy 名称。`max_active_topics`、输入规则和日上限应写为受控配置，不能只靠 JS。

```sql
-- 公开可复用主题；不得放 user_id、原始私人输入或作业报错。
create table public.topics (
  id uuid primary key default gen_random_uuid(),
  canonical_name text not null,
  normalized_key text not null unique,
  search_query text not null,
  aliases text[] not null default '{}',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  constraint topics_name_len check (char_length(canonical_name) between 2 and 80),
  constraint topics_query_len check (char_length(search_query) between 2 and 120),
  constraint topics_normalized_key_format check (normalized_key ~ '^[a-z0-9_-]{32,128}$')
);

create table public.user_topics (
  user_id uuid not null references auth.users(id) on delete cascade,
  topic_id uuid not null references public.topics(id) on delete restrict,
  display_name text,
  position integer not null,
  default_sort text not null default 'relevance'
    check (default_sort in ('relevance', 'newest', 'popular')),
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, topic_id),
  constraint user_topics_position_nonnegative check (position >= 0),
  constraint user_topics_display_name_len check (display_name is null or char_length(display_name) between 1 and 80)
);
create unique index user_topics_active_position
  on public.user_topics(user_id, position) where deleted_at is null;

-- 两张计数表：避免 composite primary key 把 user_id 隐式变成 NOT NULL，
-- 因而无法表达假想的“global NULL row”。每日按 Pacific date 写入。
create table public.topic_creation_user_counters (
  pacific_day date not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  created_count integer not null default 0 check (created_count >= 0),
  primary key (pacific_day, user_id)
);
create table public.topic_creation_global_counters (
  pacific_day date primary key,
  created_count integer not null default 0 check (created_count >= 0)
);

alter table public.topics enable row level security;
alter table public.user_topics enable row level security;
alter table public.topic_creation_user_counters enable row level security;
alter table public.topic_creation_global_counters enable row level security;

-- 示意：下列 view 的 owner 必须是 topic_view_owner（NOLOGIN、非表 owner、无
-- BYPASSRLS）；topics 还须 FORCE RLS，并为该 owner 制定窄 SELECT policy。
-- 默认 security_invoker=false 是这里的设计要点。此片段不是可直接执行 migration。
create view public.public_topic_worker_queue with (security_barrier = true, security_invoker = false) as
select id as topic_id, canonical_name, search_query, created_at
from public.topics where active;

-- Essential access shape (role provisioning/ownership order is deliberately omitted;
-- test it in staging before treating any of this as a migration):
alter table public.topics force row level security;
create policy "topic_view_owner reads active topics" on public.topics
  for select to topic_view_owner using (active);
grant select on public.topics to topic_view_owner;

-- topics/counters 不给客户端直接写；user_topics 仅本人读，写动作经 RPC。
create policy "read own user topics" on public.user_topics
  for select to authenticated using (user_id = auth.uid());
revoke all on public.topics, public.topic_creation_user_counters,
  public.topic_creation_global_counters from anon, authenticated;
revoke insert, update, delete on public.user_topics from authenticated;
grant select on public.public_topic_worker_queue to anon;
grant select on public.user_topics to authenticated;
```

`request_topic(p_name, p_sort)`、`rename_user_topic`、`move_user_topic`、`remove_user_topic` 是**待实施的 RPC 规格/伪代码，不是本次可执行 SQL migration**；应以受审阅的 SQL/PLpgSQL 实现、固定 `search_path = pg_catalog, public`，并只授予 `authenticated` execute。必需的底层 RLS/privilege 也包括：`user_topics` 仅 `user_id = auth.uid()` SELECT；anon/authenticated 对三个底表及 counters 无 direct write；`PUBLIC` 无 RPC execute；view owner 无登录、无超管/绕过 RLS 权限。函数 owner、表 owner、`FORCE RLS` 与 policy 的组合须在 staging 以 anon key 实测，不能只凭 SQL 外观判断安全或可读。

其原子逻辑如下（每一步都在单一事务，任一失败回滚）：

- 检查 `auth.uid()`；将名称作 Unicode NFC（不做 ASCII/CJK regex 过滤、不删除标点、不做小写语义折叠），trim 并折叠 Unicode 空白，拒绝控制字符、URL、HTML、换行及仅符号输入；验证 2–80 grapheme-ish 字符。`search_query` 由该经验证的显示名或**人工维护的精确 alias**生成，长度 2–120。不会假定 “C++” 和 “C#”、大小写/语言变体或翻译具有语义等价。
- 以 UTF-8 的 NFC 显示名（可加版本前缀）计算 SHA-256/hex `normalized_key`；它是稳定、非空、低碰撞的技术键而非可读 slug。仅 curated alias 表显式映射到已有主题；没有 alias 时创建新 key。hash 碰撞/同 key 不同 canonical bytes 时必须拒绝并人工处理。
- 先对用户的活动关系集合取得事务/咨询锁，再锁定或 `INSERT ... ON CONFLICT ... RETURNING` 当日 user/global 两张 counter 行；在 Pacific 日界同时判断 `count(active) < 5`、复用或新增主题、以及两个 cap。新建主题时 user 与 global counter 在同一事务各加一；复用不消耗“新 API 主题”计数但仍受活动上限。初值应为 `per_user_daily_new_topics=3`，与“新用户能创建至少 3 个”验收一致；若坚持 2，验收必须明确第三个是预先存在主题的订阅，而不是新建。全局 cap 由第 5 节 guard 推导。
- 新关系选择未占 position 或在同事务重新编号；并发第 6 个请求失败。删除只软删关系，重加可恢复位置；改名只改 user display label，不能改公共 `canonical_name`/`search_query`；移动和删除同样锁住该用户关系集合再更新，避免 position 冲突。
- 不允许客户端自行更新 `topic_id`、`position`、`deleted_at` 或 counters；函数以固定 `search_path = pg_catalog, public`，明确 privileges，错误只返回可展示的枚举码（如 `limit_reached`、`invalid_input`、`daily_cap`）。

实际的 grapheme 计数、NFC/sha256 extension、role ownership、`FORCE RLS` 与 Supabase migration 权限均为 [待确认]。若 staging 不能证明上述 definer-view 方案对 anon worker 可读且不越权，应改为一个只返回固定 sanitized shape 的受限只读 RPC；不得以关闭 RLS、给 anon 表 SELECT 或含糊的 `security_invoker` 代替。

## 4. 静态主题内容与本机刷新设计

### 4.1 发布格式和前端读取

建议产物（均为 Git 跟踪、由本机构建生成）：

- `site/src/data/topics/index.json`：已发布的公共主题清单、更新时间、每主题静态文件 URL；不含用户关系、pending 请求者或内部错误。
- `site/public/topics/<topic-id>.json`：主题元数据、视频列表、`published_at`、`next_refresh_after`、对外状态（`ready`/`empty`/`refreshing`/`quota_deferred`）；每主题独立文件利于小缓存和局部更新。
- `site/public/topics/status.json`：只含主题级等待/预算降级摘要和最后成功发布时间；不得含 job token、API 错误响应、用户 ID/IP 或原输入。

主题内容可按现有 `catalog.json` 结构映射为统一视频字段，供“我的空间”即时加载；构建脚本再把 `ready` 主题视频合入全站搜索索引。探索世界继续只消费其现有五个公共 feed，排序、行为和推荐规则保持不变；不得因合入搜索索引而把主题视频注入探索 feed，观看/点击/收藏也绝不改写主题或探索排序。

**自定义视频的静态路由闭环。** 当前 `site/src/pages/v/[id].astro` 的 `getStaticPaths()` 只从五个 editorial feeds 生成 `/v/<id>/`，而搜索页会将非静态条目外跳 YouTube；因此只把 topic JSON 加入搜索会让 topic 视频的站内 `/v/` 链接 404。每次发布 topic JSON 时，构建还须生成 Git 跟踪的 `site/src/data/topic-video-catalog.json`：按 `video_id` 去重，保存完整播放卡快照和所属 `topic_id[]`。`/v/[id]` 的 `getStaticPaths()` 合并该文件和现有 feeds；`from=topic:<topic-id>` 选择主题来源，保留 nocookie 播放器/库快照，并从主题编译索引取相关视频。`build-catalog.mjs` 把它合入 `catalog.json`/`search-index.json`，为该项生成该 `from` 参数。这样搜索、我的空间、收藏/历史/稍后看和播放都有非 404 的站内路径；如果编译索引缺失或主题已到期，搜索卡必须安全外跳 YouTube 或显示不可用，不能链接不存在的内部页面。

### 4.2 作业调度、延迟与并发

- [用户提供] 日全量刷新继续每天执行 `python3 -m ytrec refresh`；2.0 新增每小时一次的 `python3 -m ytrec topic-refresh --pending-only`。建议各任务使用同一明确的本机 `flock`/PID 锁、超时和 trap 清理，防止小时任务与日任务同时写 `data/quota.json`、主题 JSON 或 Git index。
- 每小时 job：先在本地 journal、已发布 index 和 `public_topic_worker_queue` 中找 pending、到期主题；先复用规范主题和已有 30 天视频缓存，再按预算领取少量新主题。成功写临时文件，校验 JSON，再原子 rename；最后一次性 build、`git add`、commit/push。推送前 rebase/串行化，失败不得覆盖别的工作树改动。
- 每日 job：保留既有公共 feed 顺序，并在相同锁内运行主题的全量到期扫描、旧数据清理和一次构建/推送。它不应在小时 job 正在运行时启动第二份 Python 进程。
- 预计延迟：新主题提交后，通常是“距离下一整点 + 搜索/构建/推送 + Pages 队列”。粗略目标为 10–90 分钟；若排队、预算预留不足、重试或 Pages 部署拥塞，则延至下一窗口/次日。页面必须显示“已排队/上次成功/预算稍后再试”，不承诺即时完整结果。
- 并发安全：采用**单采集者**（锁），主题键唯一、每个主题版本/`updated_at` 比较，写文件 temp+rename，Git 推送前检查工作树；Pages 已按 `pages` 并发组串行（`.github/workflows/pages.yml`），但这不保护本机两个刷新进程或两个 Git push。多采集者是 [待确认]，发生前不要启用方案 B 的租约协议。

### 4.3 刷新、保留、去重和失败

- 数据/元数据按 YouTube API 条款和最新政策核对后，采用最大 **30 天**刷新或删除：已发布主题的视频/元数据带 `fetched_at`，超过 30 天必须重新验证或从该主题静态 JSON 删除；不可用、私有、删除视频立即在下一次验证删除。合规审计范围还包括 `library_items` 的视频快照、`catalog.json`/search index、所有生成物、备份、日志、部署 artifact/cache 和 Git 历史；当前文件 pruning 不会擦除既有 Git commit 的 API metadata。保留、重写历史或清理过期 artifact 的处置须经法律/运维审阅另行决定，不能暗示此计划已删除它们。不得把“30 天”表述为已验证的最新政策结论。
- MVP 不让 anon worker 读取私有 `user_topics`，所以它不能以真实订阅数、用户活跃度或显示偏好决定刷新层级。改用公开、无身份的固定层级：operator curated priority 每日、已发布不足 7 天的主题每日、其余主题每 7 天；30 天无 operator priority 的主题停止主动刷新，最后快照到期后删除/归档。未来若按需求排序，只能使用经安全审查、不返回 user_id 的聚合阈值，不能假设 hidden stats 可读。
- 每次先按 `normalized_key`/别名去重，再按 `video_id` 去重；同视频可在多个主题出现，但单主题只保留一次。复用 30 天内同一规范主题结果，避免重复 `search.list`；视频补全使用最多 50 个 ID 一批的 `videos.list`。
- 每个主题单次运行最多 1 次搜索 + 必要 metadata 批次；可重试错误最多 2 次（含指数退避，最大运行窗口内），429/配额/永久 4xx 不重试或仅按明确 `Retry-After` 延后。记录类别而非响应原文。达到有限重试后状态为 `retryable_failed`，下次计划窗口才再试；预算耗尽为 `quota_deferred`，不循环失败。
- 无匹配结果发布 `empty` 及检查时间，仍按较低频率刷新；JSON 损坏、构建失败或 Git push 失败时保留上一版本并报警/写本地安全日志，绝不发布半成品。

## 5. 配额预算与降级

### 5.1 保守算式

本节必须区分官方实际配额与本机遗留护栏。[协调方官方页证据] 协调方本轮已公开打开、于 2026-11-07（Asia/Shanghai）核对 [quota calculator](https://developers.google.com/youtube/data/determine_quota_cost) 和 [revision history](https://developers.google.com/youtube/v3/revision_history)：前者说明默认 `search.list` 是**独立 search bucket** 的每日 100 次、每次成本 1；其他 endpoint 共享每日 10,000 units；后者确认 2026-06-01 的 granular quota transition。本文未自行抓取这些页面。实施前仍必须在项目 console 确认该项目已启用的 transition、实际 bucket、限制和余额，不能从文档推断项目已配置。

仓库当前 `ytrec/core.py` 仍把 `search` 按 100、`videos` 按 1 记账。因此下面 `3344 + 102×N` 和 `45/26` **只是不改变现有部署前提下的 CURRENT LOCAL GUARD accounting，不是官方实际成本、也不是 Google 剩余额度**；它不能替代 console 或新的双 bucket guard。

以用户提供的当日已用约 `3344`、本机保护线 `8000`、且每个新主题按 1 次 search 加最多两次 metadata batch 的保守 `102` 单位计：

```text
3344 + 102 × N < 8000
N < (8000 - 3344) / 102 = 45.647...
```

因此 local-guard 数学绝对上限为 **45 个**新主题；不得把它当作可用配额。必须为旧主题刷新、现有公共 feed、重试误差和日边界预留空间。建议初始策略：先预留至少 1,500–2,000 local units 给日刷新/旧主题与失败缓冲，剩余再给 pending；例如预留 2,000 时 `N <= floor((8000 - 3344 - 2000)/102) = 26`。还应设置更保守的小时领取上限（例如 3–5 个新主题），全局每日创建上限以当日实时预算按上述公式推导而不是硬编码 45。

实施时采用**双 guard，二者都必须通过**：(a) 上述 local guard，保护现有 `quota.json` 行为直到代码迁移；(b) 官方 granular guard：search bucket 以 `100 - 当日实际 search 调用数 - search reserve` 计算，shared-unit bucket 以 `10000 - console/可靠审计的实际 shared 用量 - shared reserve` 计算。当前 full `refresh()` 的趋势/播客/音乐路径实际为 30 次 search（见 1.2），故“15 searches baseline”只能是漏掉两个 duration bucket 的错误粗估；AI `resolve_ai_channels` 若单独运行也可能增加 search，必须纳入实际计数。两 bucket 的 reserve 都应配置化；任何账源缺失、日期/时区不一致或 console 不能确认时，不发起新 search。

配额原子性不应伪装成 DB RPC：外部 console 余额不能由 SQL 锁住。单采集者持有同一 `flock` 后，先重新读取 Pacific-day local journal/`quota.json` 和已确认的 console/可靠审计快照，计算两个 guard；两者都足够才在**发 API 请求前**将最坏 search/shared/local 成本 reservation 写入 journal，再调用 API；最终在同一锁内写实际调用/失败结果或保留 reservation 直到人工核对。DB `request_topic` 的 counter 锁只限制“接受多少新主题”，不宣称已经预留 Google 配额；worker 在实际领取时仍执行上述双 guard。

### 5.2 Pacific 日界、降级和监控

- 所有预算判断、creation counter 和“今日”文案统一 `America/Los_Angeles`，沿用 `pacific_today()` 的定义（`ytrec/core.py`）。在日界附近由锁/事务防止两进程分别看到旧余额。
- 在调用前对 local guard 及 search/shared official guard 各预扣最坏成本，在成功/失败后写审计；若 console、官方 bucket 观测和本机账不一致，优先停止新搜索、保留已发布静态内容，等待人工核对，不猜测可继续调用。
- 额度不足时：已缓存主题照常展示；新主题显示排队；到期主题显示最后成功时间和“稍后刷新”；不删除用户配置，不触发浏览器直连 API，不把错误暴露为密钥/请求 URL。
- 报表至少包含 Pacific 日期、近似已用、预留、各 endpoint/主题尝试数、cache hit、成功/empty/deferred 数、最旧内容年龄和部署版本。日志仍禁止凭据。

## 6. 拟改/新增文件清单（实施时确认后执行）

| 文件 | 动作 | 目的 |
|---|---|---|
| `docs/v2-plan.md` | 已新增 | 本审查与计划 |
| `supabase/schema.sql` | 修改 | 新表、索引、RLS、只读视图、受限 RPC/函数与注释；不改 `library_items` 行为 |
| `ytrec/topics.py` | 新增 | 规范化、别名去重、主题静态产物、30 天缓存/删除、状态机、预算与有限重试 |
| `ytrec/__main__.py` | 修改 | 新增 `topic-refresh` 命令；不改变既有 `refresh` 的公共 feed 顺序 |
| `ytrec/core.py` | 谨慎修改或复用 | 复用安全 Client/配额助手；若抽取共享函数须测试，避免改变 HN 管道 |
| `config.yaml` | 修改 | 不含密钥的 topic 上限、日/小时预算预留、刷新间隔、30 天 TTL、retry 等配置 |
| `site/scripts/build-catalog.mjs` | 修改 | 把已发布主题视频纳入 catalog/search-index，去重并排除内部状态 |
| `site/src/data/topics/index.json` | 新增生成物 | 主题编译期索引/开发回退数据 |
| `site/src/data/topic-video-catalog.json` | 新增生成物 | 供 `/v/[id]` 静态路径、搜索、库与播放使用的 topic 视频快照/来源映射 |
| `site/public/topics/*.json`、`site/public/topics/status.json` | 新增生成物 | Pages 直接读取的主题内容/净化状态 |
| `site/src/lib/topics.mjs` | 新增 | 主题标签、URL、公共 JSON 解析与品牌/栏目文案集中处 |
| `site/src/scripts/topics.js` | 新增 | 登录检查、匿名 localStorage、Supabase RPC、主题 CRUD/顺序及静态 JSON 读取 |
| `site/src/components/Header.astro` | 修改 | 无整页刷新的“探索世界/我的空间”切换入口；修复 390px 溢出 |
| `site/src/components/Layout.astro` | 修改 | 载入模式控制脚本/可访问性状态，尽量不扰动库面板 |
| `site/src/pages/[...path].astro` 或 `site/src/pages/index.astro` | 修改/新增待定 | 承载两种模式；选择取决于现有 catch-all 路由的最小改动方案 |
| `site/src/pages/v/[id].astro` | 修改 | 合并 topic 静态 catalog，支持 `from=topic:<id>`，防止 custom 视频 404 |
| `site/src/components/VideoPage.astro` | 小改 | 若增加主题来源标签，仅扩展 `from`，不改现有 feed 排序/嵌入 |
| `site/src/lib/brand.mjs` | 修改 | 品牌、模式/栏目字符串集中化 |
| `tests/test_topics.py` | 新增 | Python 规范化、预算、缓存、状态、原子输出测试 |
| `tests/test_site.py` | 修改 | 静态产物、索引、现有页面回归 |
| 前端测试文件/工具 | [待确认] | 当前 `site/package.json` 无测试脚本；先确定 Playwright/Vitest 是否获准加入，不能假称已有 |
| `.github/workflows/pages.yml` | 原则上不改 | 既有 push Pages 已足够；仅若构建产物路径/Node 要求变化才最小改动 |
| 本机 scheduler unit/脚本 | 新增位置 [待确认] | 用户要求本机小时任务，但仓库未发现现有定义；须先确认是否版本化及运行账户 |

不计划修改 `site/src/scripts/library.js`、`sync.js` 的历史/收藏/稍后看/关注协议，或重构认证、切换前端框架。当前社区来源保持 Hacker News。

## 7. 分阶段实施与粗略工作量

| 阶段 | 交付/退出条件 | 粗略投入 |
|---|---|---:|
| 0. 核实与设计冻结 | 确认官方 YouTube 配额/缓存政策、Supabase 版本/RPC 权限、调度位置与运行账户、公开主题隐私文案、活跃规则 | 0.5–1.5 天 |
| 1. 数据与安全 | 隔离环境 SQL migration、RLS/RPC 并发/限额测试、无 service_role 的提交路径 | 1–2 天 |
| 2. 本机主题管道 | 规范化/别名、缓存、预算、重试、锁、JSON 原子发布及 dry-run fixture | 2–3 天 |
| 3. 静态构建与 UI | 双模式、创建/改名/删除/排序/状态、匿名已有主题、移动端头部修复 | 2–3 天 |
| 4. 集成与灰度 | 测试、配额护栏、手动小主题集、部署/回滚演练、观察 | 1–2 天 |

合计约 **6.5–11.5 个工程日**，不含新增社区来源、私人主题、多采集者、人工 alias 运营或官方政策变更导致的返工。第 0 阶段还要建立 staging fixtures（固定 topic queue、假 API 响应、预期静态 catalog/路由），再进行 SQL/RLS、quota guard 和 build 测试；本次计划回合没有运行这些或任何真实回归。先完成第 0 阶段才应进行生产 SQL 或定时任务安装。

## 8. 回归、验收与部署配置（需求八）

### 8.1 回归测试清单

- 公共探索：全部、AI、播客、音乐、社区推荐及社区两种排序与无限加载结果不变；不得因历史/点击/收藏改变探索排序。
- 视频：既有 `/v/<id>`、来源参数、`youtube-nocookie` 嵌入、YouTube 外跳、缩略图和无重托管约束正常；topic-only 视频从搜索、我的空间、库/历史入口及 `from=topic:<id>` 播放均不 404，且不进入探索 feed。
- 搜索/频道：`catalog.json`、`search-index.json`、`channels.json` 的加载、全局搜索、频道页/侧栏关注正常；主题内容去重且不泄漏用户主题。
- 个人库：匿名 localStorage 的历史（含上限）、收藏、稍后看未读标记、关注；登录后的 `library_items` 合并、退出和断网降级保持行为。
- 认证：未配置 Supabase 时隐藏/降级；邮箱登录、注册、重置、可选 OAuth 和 session 恢复；未登录只能使用已发布主题，未命中主题明确要求登录。
- 主题：新用户连续创建至少 3 个（初始 per-user new-topic cap 为 3）；5 个上限和可配置变更；相同 NFC 输入及**人工 curated alias**复用同一规范主题，`C++`/`C#`、未维护翻译或看似同义的词绝不自动合并；改名、删除、上下移动、默认排序刷新后保持；空、等待、失败、额度延后可理解。
- 权限：用户 A 不能读/改用户 B 关系；不能直接插入 counter/公共主题或伪造 position；并发创建第 6 个栏目、并发每日 cap、别名冲突均只有一个成功的原子结果；公开视图无 `user_id`/原始输入/job 信息。
- 作业：cache hit 不调用搜索；固定 refresh tier 正确且不读取私有关系；30 天到期重新验证或删除；重复视频去重；2 次有限重试；429/网络/构建/Git push/JSON 失败保留旧版；锁阻止双运行；local 与 official search/shared 双预算守卫在 Pacific 日界正确。先以 staging fixtures 执行，不以生产 key 或真实生产用户数据做自动化测试。
- 响应式与无障碍：1280px 与 390px，尤其 Header/双模式控件不横向溢出；键盘操作、焦点、aria selected/live 状态和错误文案可用。
- 安全审计：仓库/构建产物/console/log 中无 `YOUTUBE_API_KEY`、Supabase secret/service_role、job token；只允许 `PUBLIC_SUPABASE_ANON_KEY` 这类可公开配置。禁止真实生产凭据做自动化测试。

### 8.2 部署与配置步骤（未来实施时）

1. 在隔离 Supabase 项目审阅/执行 migration，运行 RLS/RPC 的正反向测试；确认不需要也不创建 service_role 使用路径。再经授权单独安排生产变更。
2. 仅在本机受控环境配置既有 YouTube API key；若采用方案 B，额外配置独立 job token 并限制文件权限/日志，不使用 `PUBLIC_` 前缀。方案 A 不需 Supabase 写密钥。
3. 在 `config.yaml` 写非机密主题政策（5 个活动主题、输入限制、每日 cap、刷新间隔、30 天 TTL、预算预留、重试）；密钥永不提交。
4. 先用 fixture/dry-run 和小型预批准主题集运行 `topic-refresh`，检查 JSON schema、预算报表和 `npm run build`；不在此阶段调用真实生产 API，除非获得实施授权。
5. 安装/更新本机小时 pending job 和每日全量 job，使用同一锁、超时、最小日志权限；确认日常 `refresh` 的 Git 提交范围包含主题静态产物且不意外加入本地数据库/日志。
6. 推送到 `master` 后由既有 Pages workflow 发布；在 Pages URL `/youtuber/` 验证缓存版本、基础路径、匿名和已登录路径。保留前一 Git commit 作为回滚点；回滚只恢复静态产物，不删除用户关系。

## 9. 风险与明确待确认项

- **官方规则/项目配置风险**：[协调方官方页证据] 已记录官方 granular transition 与默认 buckets，但本文没有自行联网抓取；项目是否迁移、当日实际 search/shared 剩余量、缓存/展示条款仍须以项目 console 和当时官方页确认。不能把“每天约 100 次搜索”误当 shared-units 成本或项目已启用状态。
- **调度风险**：每日命令来自用户说明，仓库没有 scheduler 定义；需确认 cron/systemd、时区、互斥、运行账户、Git 身份与故障告警，但不读取其账户文件或凭据。
- **数据库能力风险**：NFC/hash 所需 extension、definer-view owner + `FORCE RLS` policy、受限 RPC 的 owner/默认权限，以及 anon key 能否只读 sanitized pending queue 都待 staging 验证。若无法原子实施，先停止在 staging，不关闭 RLS。
- **隐私/滥用风险**：公开主题可透露兴趣；需产品确认公开复用提示、敏感输入拦截范围、每用户/全局日 cap、登录门槛和删除后公共缓存的生命周期。匿名新主题请求会被拒绝，避免配额滥用。
- **容量风险**：按 3344/8000 的算式新主题理论上限约 45，但正常运营应远低于此并预留旧刷新；现有 `quota.json` 无跨进程原子性，必须以锁改进。
- **发布风险**：Git push 到 Pages 的端到端延迟非本机可完全控制；状态需诚实表达排队、耗尽和旧内容，不能把提交成功当成已上线。
- **社区来源不确定性**：现有来源是 Hacker News；若要新增其他社区，应另开范围、选择来源方式并检查条款/额度/隐私后再估时。

## 简要总结

建议以“认证用户提交、公共规范主题复用、本机单采集者按小时处理 pending、每日全量刷新、Git/Pages 发布每主题静态 JSON”为 MVP。保持 Astro 静态站、现有认证及所有历史/收藏/稍后看/关注/搜索/嵌入行为；不使用 Supabase service_role 或任何 secret key。当前最大不确定性是官方 YouTube 规则、实际本机调度环境、Supabase RPC 能力，以及是否需要新增社区来源。
