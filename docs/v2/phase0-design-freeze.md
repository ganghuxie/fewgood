# YouTuber 2.0 Space：Phase 0 设计冻结（本地 MVP）

## 核验结论

- [已检查] 站点是 Astro 静态构建；公开数据可随 Git 发布。浏览器不应也不会持有 YouTube key。
- [已检查] `refresh()` 依序刷新 trending、AI、podcast、music、channels；前三者为 `3 × 5 × 2 = 30` 个 `search.list`。AI 是频道 uploads playlist 路径，频道/playlistItems/videos 为低成本端点。
- [已检查] fewgood 当前采用 curated creator pool 的 uploads-first 路径，`fewgood_r3.py` 配置 search cap 为零；自定义主题沿用这个方向，不采用旧计划的 search-heavy 设计。
- [已检查] 本地 `core.py` 仍将 search 记作 100 legacy units，`data/quota.json` 上限 8000；这是本地守卫，非官方计费证明。
- [已检查] daily refresh 是 GitHub Actions `17 23 * * *`（约上海 07:17），不是本机 cron；Pages workflow 只从 main/master 发布。本分支没有改这些 workflow。
- [官方页已核] YouTube 默认有独立的 `search.list` 日桶 100 calls（每次 1），其余端点共享 10,000 units/day；按 Pacific 午夜重置。项目 Console 实际配额仍未在此机器核验。
- [待 Jason] YouTube ToS 对缓存保留的最新精确措辞未重新做法律核验；沿用计划的 30 天 metadata intent，不作法律结论。

## MVP 冻结决定

1. 架构：Astro 静态 + Git 发布 topic JSON；浏览器绝不保存 YouTube key。后续 Phase 1 固定走方案 A（无 `service_role`）。
2. 主题采集：先匹配受管 creator/channel pool 的 uploads，再做 playlistItems/videos 批量补全。仅在 pool miss 时允许有上限的 search fallback；优先已发布 30 天缓存与 curated alias 复用。
3. 规范化：Unicode NFC、trim、压缩空白；拒绝控制符、URL、HTML。仅 curated alias table；绝不自动把 C++、C# 或未经治理的同义词合并。
4. 默认上限（[待 Jason] 确认）：每用户最多 5 个 active topic、每日新建 3 个；全局每日新建数由实际剩余预算推导；metadata TTL 30 天；最多 2 次 retry；单 collector `flock`/独占文件锁。先为 daily refresh 预留预算，再领取 pending topics。
5. 调度：daily refresh 已在 GHA。Phase 2 只写本地 queue 文件；每小时 topic refresh 延后，需 Jason 确认跑在 GHA 还是 box，未授权不新增 cron。
6. 隐私文案草案：**“创建主题可能发布可复用的公开规范主题及其公开视频结果；你的订阅关系保持私密，后续由 RLS 保护。”**

## 配额模型（更新）

官方模型是独立 search bucket **100/day** 与其它端点 shared **10,000 units/day**。每日 refresh 已消耗约 30 次 search，AI/channels 与视频补全只用低成本端点；旧模型会把约 30 次 search 记为约 3.3k legacy units。

主题 job 双重守卫：(a) 在迁移前继续检查 legacy `quota.json`，(b) 像 fewgood Fetcher 一样分别统计 `search_calls` 与 `other_units`。本地默认保留 **35 search calls、2,000 shared units**（以及约 3,500 legacy units）给 refresh，故 pending job 不能挤占日常栏目。一个命中 creator pool 的新主题消耗 0 search，成本约为 `O(channel × playlist pages + videos batches)` shared units。

## Jason 的短问题

- [待 Jason] 是否授权隔离 Supabase staging project 及 Phase 1 migration/RLS 演练？
- [待 Jason] topic-refresh 最终排程在 GHA 还是 box？
- [待 Jason] 上述公开/私密隐私文案是否可用？5/3/30 天/2 retry caps 是否确认？
- [待 Jason] curated alias table 由谁维护？search fallback 是否允许、每天最多 N 次？
