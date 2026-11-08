# Fewgood MVP · YouTube API 合规风险（初步）

依据：[YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)（页面标注 2026-11-06 更新，2026-11-08 读取）和 [Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)。以下是工程侧的初步阅读，不是法律意见。上线公开版本前，建议再读一遍完整的 Terms of Service 和 Branding Guidelines。

| # | 条款 | 与 Fewgood 的关系 | 风险 | 本 MVP 的处理 |
| --- | --- | --- | --- | --- |
| 1 | III.E.4.h：不得用 API Data 创建新的或衍生的数据/指标，例如把点赞、播放等算成分数；自有指标必须清楚披露“不是来自 YouTube” | 如果做“视频优质分”这类综合分，会直接触碰此条 | **高**（如果做评分） | 不计算任何分数。播放量只原样展示，不参与排序。排序只用自有的关键词规则、可信频道名单和发布时间顺序。页面披露“主题分组和推荐依据由 fewgood 按公开规则生成，不是 YouTube 的数据或评分”。 |
| 2 | III.L：额外的衍生指标和统计数据存储，只适用于已经通过审计、并单独申请过的 analytics 用例（2026-06-01 起） | 我们没有经过审计 | 中 | 不做衍生指标。如果以后要做“质量分”或趋势统计，需要先评估是否申请。 |
| 3 | III.E.2：不得聚合 API Data（除同一内容所有者等例外），也不得借此洞察 YouTube 的业务 | 频道分布、命中数等统计只用于内部实验报告 | 中低 | 统计不放进公开产品，只放在内部文档。公开页面只显示每个主题的候选数和展示数。正式版应删掉跨频道的统计展示。 |
| 4 | III.E.4.d/e/f：未授权的 API Data 最多保存 30 天，之后必须刷新或删除；展示时要尽量用最新数据 | 实验原始数据（4.3 MB）和结果 JSON | 中 | 原始候选 `data/experiments/fewgood-mvp-raw.json` 只留在 box 上，被 .gitignore 忽略，**不提交到公开仓库**。结果 JSON 小，提交在实验分支上，应在 30 天内（2026-12-08 前）刷新或删除。正式版要每天刷新。 |
| 5 | III.C.5：使用搜索功能时不得修改或替换搜索结果，也不得把其他来源混进来冒充 YouTube 搜索结果 | A 组是 YouTube 搜索结果 | 低 | A 组原样展示返回顺序和标题，并标明“A 组为 YouTube 搜索 API 默认相关度前 6，原样展示”。B 组明确标为 fewgood 自己的筛选结果，不叫“YouTube 搜索结果”。 |
| 6 | III.F.2：展示 YouTube 内容时要标明来源是 YouTube，并遵守 Branding Guidelines | Demo 卡片 | 中 | 页面有“数据来自 YouTube”的披露和“在 YouTube 观看 ↗”入口，但还没有使用官方 YouTube 品牌标识。公开前需要按 Branding Guidelines 补上。 |
| 7 | III.A：要有自己的服务条款和隐私政策，链接 YouTube ToS 和 Google 隐私政策，并说明使用了 YouTube API Services | 正式站点 | 中 | Demo 只链接了 YouTube ToS。如果正式站点还没有满足这一条，公开 Fewgood 前需要补齐（正式站点已经有登录功能，这一条同样适用）。 |
| 8 | III.I.1：不得做 YouTube 的替代品，也不得照搬浏览体验，除非能带来显著的独立价值 | Fewgood 是“精选和主题化发现” | 中 | 价值主张必须是筛选和解释（推荐依据），而不是再做一个 YouTube 首页。A/B 对比正是用来证明这种独立价值。 |
| 9 | III.D.1.d：不得在开源项目中嵌入 API 凭证 | 仓库是公开的 | 低 | key 只从环境变量读取，代码、日志和 usage 文件里都没有 key（有测试覆盖）。 |
| 10 | 额度 / III.D.3：额度扩容需要做 API Compliance Audit，并且只能用于获批的用例 | 规模化时 | 中（以后） | 当前 15 次搜索加 55 单位，远低于默认额度。扩展到更多主题时，优先用频道 uploads（1 单位/频道），尽量少用 search。 |

**结论**：在“不做综合评分、原样展示 API 数据、披露自有分类、30 天内刷新或删除”的前提下，本 MVP 没有发现阻断性的合规问题。会阻断的情况是：做“视频质量分”或衍生指标，或者把实验数据长期存在公开仓库里。

## 第 2 轮补充（博主池）
- **订阅数**：只用作入池门槛，不参与排序，也不计算衍生分数。页面上按 API 原值展示，并标注「来自 YouTube」，符合 III.E.4.h 的“使用 API 返回的原数”。
- **专注度**：指“近 30 天标题里命中 AI 关键词的比例”，基于 fewgood 自己的关键词分类，只用于内部入池判断，不展示。它不是 YouTube 统计指标的再计算，属于灰区但风险低。如果以后要展示“专注度”，必须标明这是 fewgood 自己的指标（III.E.4.h）。
- **频道统计的存储**：`data/experiments/fewgood-r2-creators.json`（3 MB，含 625 个频道的统计）和 r2 原始数据（13.8 MB）只放在 box 上，不提交到仓库。提交的只有入池的 93 个频道和 Demo 数据，并且要在 30 天内刷新或删除（III.E.4.b/d：非授权数据中的统计最多保存 30 天）。
- **X 数据**：只用了 X 的公开资料（简介和链接）作为线索，没有存储或展示 X 内容。
