# Fewgood MVP · 代码与额度审计

审计时间：2026-11-08 20:00（北京时间）。代码基线：origin/master `c45c6a4`。分支：`mvp-fewgood`。

## 1. 当前 AI 频道与视频如何抓取？
- `ytrec/core.py::ai_feed`：读取 `config/ai_channels.yaml`（42 个由 X 账号映射的 AI 公司/创作者频道），每个频道调用 `channels.list`（取 uploads 播放列表）+ `playlistItems.list`（最近 50 条），只保留近 7 天发布、时长 ≥60 秒的视频，再用 `videos.list`（50 一批）补详情，按播放量降序写入 `site/src/data/ai.json`。**不使用 search.list**。
- 2026-11-07 的 ai.json：42 个频道、80 条视频，约 80 单位。
- 已知 6 个频道的 uploads 返回 404（Mistral AI、Perplexity、Character.AI、Jim Fan、swyx、Rowan Cheung），本次实验再次确认。

## 2. 是否已有可复用的 AI 候选池？
有，但规模小、无主题标签：
- `site/src/data/ai.json`（近 7 天 80 条，完整记录）——全部复用。
- `ai.json / videos.json / trending.json / podcast.json / catalog.json` 共 783 条记录中，复用 129 条：ai.json 的 80 条全部复用，其他文件只取标题命中任一主题词的 49 条。这些记录只送去 `videos.list` 刷新详情，不额外搜索。
- 现有记录没有描述/标签，不能直接做主题判断，需要 `videos.list` 补全（每 50 条 1 单位，很便宜）。

## 3. 当前每日刷新使用多少次 search.list？
- `trending_feed` / `podcast_feed` / `music_feed` 各做 5 个时间窗 × 2 个时长桶 = **10 次**，合计 **30 次/天**。`ai_feed` 与 `channels_feed` 不搜索。
- 本地护栏 `data/quota.json` 仍按旧口径（search=100 单位）记账，上限 8000；2026-11-07 记账 6698（≈30×100 + 3698 其他）。上下文中记录的真实其他端点用量约 3344 单位。

## 4. Google Cloud 项目的实际额度是多少？
- **无法从 box 核实。** box 上只有 API key，没有 Cloud Console 访问权限，API 也不返回剩余额度。必须由 Jason 在 Google Cloud Console → APIs & Services → YouTube Data API v3 → Quotas 查看。
- 官方文档（[Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)，2026-11-08 读取）写明默认分配：`search.list` 独立桶 **100 次/天，每次 1**；`videos.insert` 100 次/天；其他端点合计 **10,000 单位/天**；太平洋时间午夜重置（= 北京时间 16:00，夏令时结束后）。

## 5. 当天剩余额度是多少？
- 无法直接查询，只能按已知调用推算（以 Cloud Console 为准）。
- 当前太平洋日从北京时间 11-08 16:00 开始，至 11-09 16:00 结束。明早 07:00 的 GitHub Actions 正式刷新落在同一太平洋日。
- 本日已知用量：本实验 15 次 search + 55 单位。正式刷新预计 30 次 search + ~3,344 单位。合计约 **45/100 次 search、~3,400/10,000 单位**，留有余量。11-08 16:00 之后本地定时任务已暂停，GitHub 上只跑过 11-08 08:27 的 check 模式（属于上一太平洋日）。

## 6. 每日 GitHub Actions 刷新是否已端到端成功？
**尚未。** 11-08 08:27（北京时间）的手动运行是 check 模式（成功，42 秒）。首次 schedule 触发的 full 刷新在 11-09 07:00（北京时间），另有验收任务 08:00 检查。本 MVP 不依赖它，也没有触发或修改任何 workflow。

## 7. 哪些代码能复用，哪些需要新增？
- 复用：`core.duration`、`core.landscape_video`、现有频道配置 `config/ai_channels.yaml`、Astro 站点构建与 base 路径、现有 site 数据作为零配额候选池。
- 不复用：`core.Client`（会把调用记到生产 `data/quota.json`）。
- 新增（全部 Codex 编写）：
  - `config/fewgood_topics.yaml`：5 个细分主题配置
  - `ytrec/fewgood.py`：独立实验管线，带硬上限计数器（`pool` / `run` / `select` / `--dry-run`）
  - `ytrec/fewgood_report.py`：根据结果生成质量表与 A/B 表
  - `site/src/pages/demo/fewgood.astro`：独立 Demo（noindex，首页无链接）
  - `tests/test_fewgood.py`

## 实施方案（已执行）
1. 零配额复用池 + 可信频道 uploads（`playlistItems`，用 `UU…` 直接推导 uploads ID，省掉 `channels.list`）。
2. 每个主题 2 次限定搜索（近 30 天，英语相关度）+ 每主题 1 次 A 组“普通搜索”基线，共 15 次，代码里硬上限 15，第 16 次直接抛异常、不发请求。
3. 透明规则筛选（无综合评分）→ 每主题最多 6 条 → 结果 JSON → Demo。
4. 原始候选落盘后，`select` 可零 API 重复执行。
