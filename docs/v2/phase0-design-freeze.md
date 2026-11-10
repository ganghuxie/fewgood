# YouTuber 2.0 Space：Phase 0 设计冻结（本地 MVP）

## 核验结论

- [已检查] 站点是 Astro 静态构建；公开数据可随 Git 发布。浏览器不应也不会持有 YouTube key。
- [已检查] `refresh()` 依序刷新 trending、AI、podcast、music、channels；前三者为 `3 × 5 × 2 = 30` 个 `search.list`。AI 是频道 uploads playlist 路径，频道/playlistItems/videos 为低成本端点。
- [已检查] fewgood 当前采用 curated creator pool 的 uploads-first 路径，`fewgood_r3.py` 配置 search cap 为零；自定义主题沿用这个方向，不采用旧计划的 search-heavy 设计。
- [已检查] 本地 `core.py` 仍将 search 记作 100 legacy units，`data/quota.json` 上限 8000；这是本地守卫，非官方计费证明。
- [已检查] daily refresh 是 GitHub Actions `17 23 * * *`（约上海 07:17），不是本机 cron；Pages workflow 只从 main/master 发布。本分支没有改这些 workflow。
- [官方页已核] YouTube 默认有独立的 `search.list` 日桶 100 calls（每次 1），其余端点共享 10,000 units/day；按 Pacific 午夜重置。项目 Console 实际配额仍未在此机器核验。
- [已冻结] YouTube ToS 对缓存保留的最新精确措辞未重新做法律核验；沿用计划的 30 天 metadata intent，不作法律结论。

## MVP 冻结决定

1. 架构：Astro 静态 + Git 发布 topic JSON；浏览器绝不保存 YouTube key。后续 Phase 1 固定走方案 A（无 `service_role`）。
2. 主题采集：先匹配受管 creator/channel pool 的 uploads，再做 playlistItems/videos 批量补全。仅在 pool miss 时允许有上限的 search fallback；优先已发布 30 天缓存与 curated alias 复用。
3. 规范化：Unicode NFC、trim、压缩空白；拒绝控制符、URL、HTML。仅 curated alias table；绝不自动把 C++、C# 或未经治理的同义词合并。
4. 默认上限（Jason 已确认）：每用户最多 5 个 active topic、每日新建 3 个；metadata TTL 30 天；最多 2 次 retry；单 collector `flock`/独占文件锁。Phase 1 staging 的全局每日新建默认 50，生产应在上线前按实际预算复核。隐私文案已确认可用。先为 daily refresh 预留预算，再领取 pending topics。
5. 调度（Jason 已确认）：topic-refresh 跑在 GitHub Actions。当前 workflow 仅 `workflow_dispatch`；小时 cron 作为注释保留，未经 Jason 授权不得启用，更不得带 schedule 合入 master。
6. 隐私文案草案：**“创建主题可能发布可复用的公开规范主题及其公开视频结果；你的订阅关系保持私密，后续由 RLS 保护。”**

## 配额模型（更新）

官方模型是独立 search bucket **100/day** 与其它端点 shared **10,000 units/day**。每日 refresh 已消耗约 30 次 search，AI/channels 与视频补全只用低成本端点；旧模型会把约 30 次 search 记为约 3.3k legacy units。

主题 job 双重守卫：(a) 在迁移前继续检查 legacy `quota.json`，(b) 像 fewgood Fetcher 一样分别统计 `search_calls` 与 `other_units`。本地默认保留 **35 search calls、2,000 shared units**（以及约 3,500 legacy units）给 refresh，故 pending job 不能挤占日常栏目。一个命中 creator pool 的新主题消耗 0 search，成本约为 `O(channel × playlist pages + videos batches)` shared units。

Search fallback 已冻结：只在 uploads-first 少于 6 个结果时才可调用 `search.list`；每个 topic 最多 2 次、topic-refresh 合计每日最多 15 次；任何一次会触及为 daily-refresh 预留的约 35 次 search 时一律禁止。对应可审计配置在 `config.yaml` 的 `topics.search_fallback_*`。

## Jason 决策记录（2026-11-10）

- [已回答/冻结] Phase 1 可使用隔离 Supabase staging；本轮用 box-local Postgres shim，真实 Supabase staging 后建。
- [已回答/冻结] topic-refresh 在 GitHub Actions。
- [已回答/冻结] 5 active / 每日 3 new / 30d TTL / 2 retries 与上述隐私文案：可以。
- [已回答/冻结] alias 由仓库内 curated 文件维护；可用 search fallback，cap 如上。

Alias 源文件是 `config/topic-aliases.json`（初始种子来自 `tests/fixtures/v2/aliases.json`）。Jason/我们通过 PR 编辑它；仅这里的明确映射可合并，C++ 与 C# 永远是两个不同 key。staging seed 将此文件同步到 `topic_aliases`；真实环境同样须先同步再开放 queue。

## 日后建立真实 Supabase staging（Jason）

1. 新建一个空的 Supabase project，确认它不是生产项目 `zdctckubirrlukbbrlwx`。
2. 先应用 Phase 1 migration（并导入 `config/topic-aliases.json` 的 seed）。
3. GitHub Actions 仅设置 `SUPABASE_URL` 与 `SUPABASE_ANON_KEY`；不要设置或使用 `service_role`。
4. 先只启用 `workflow_dispatch` 验证；schedule 必须等 Jason 再次授权，且不得未经授权进入 master。
