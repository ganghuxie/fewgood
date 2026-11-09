# Fewgood 第 2 轮 · 博主优先内容池

按 Jason 11-08 的新思路：细分主题固定 → 从 X 找国内外知名博主，查是否有 YouTube → 在 YouTube 按高播放、高订阅扩展同类博主 → 视频只从这些博主的 uploads 中筛选。

- 运行时间：2026-11-08 21:09:54–21:11:02（北京时间），真实 API 只跑 1 次，之后的规则调整都用 `select` 零 API 重放。
- 完整名单见 [creator-pool-table.md](creator-pool-table.md)。配置文件：
  - [`config/fewgood_creator_seeds.yaml`](../../config/fewgood_creator_seeds.yaml)（种子线索）
  - [`config/fewgood_creator_rules.yaml`](../../config/fewgood_creator_rules.yaml)（入池规则）
  - [`config/fewgood_discovery.yaml`](../../config/fewgood_discovery.yaml)（发现用的搜索词）
  - [`config/fewgood_creators.yaml`](../../config/fewgood_creators.yaml)（入池结果）

## 1. 来源与核验流程
1. **X 公共资料**（Grok Bot 内置的 X 公开读取，2 次批量用户查询 + 1 次帖子搜索）。
   - 共查了约 170 个 X 账号，其中 159 个存在。
   - **只有 25 个账号的 X 资料里直接链接了 YouTube**，例如 Lex Fridman、Two Minute Papers、bycloud、Dwarkesh、Fireship、ThePrimeagen、Matt Wolfe、AI超元域、howie.serious。
   - 大多数专家的 X 资料不链接 YouTube，例如吴恩达、Karpathy、宝玉、歸藏，他们的频道只能靠已知信息去 YouTube 核验。
   - 中文 X 圈的 AI 博主大多没有 YouTube，或者没在 X 上写出来。X 帖子搜索在中文方面产出很低，只找到 Machine Learning Street Talk 等少量线索。
2. **YouTube 核验**：每个种子都要经过 `channels.list` 确认存在，有频道 ID 的批量查，只有 handle 的逐个查。**绝不收录未经核验的频道。**
   - 113 个种子里有 12 个 handle 查不到，标为 unverified，不进池。其中 10 个是我凭记忆猜的中文 handle，例如 量子位、老范讲故事、李自然说、跟李沐学AI、技术爬爬虾、林亦LYi，另外 2 个是 Welch Labs 和 Cline。
3. **YouTube 扩展**：做了 15 次 search.list。
   - 10 次视频搜索：近 90 天、按播放量排序，每个主题英文、中文各 1 次。
   - 5 次中文频道搜索。
   - 一共发现约 510 个新频道，再统一过一遍入池规则。

## 2. 入池规则（`config/fewgood_creator_rules.yaml`）

| 规则 | 种子（X、已有名单、已知线索） | YouTube 发现的频道 |
| --- | --- | --- |
| 必须经 API 核验存在 | ✅ | ✅ |
| 订阅数门槛 | 个人博主一律 ≥ 1,000（R2b 起取消 X 链接/原有名单豁免）；官方/品牌频道（`official_channels`）豁免 | 英文 ≥ 100,000；中文 ≥ 20,000 |
| 主题匹配 | 人工标注了细分主题 | 发现结果中有 ≥ 2 条标题命中该主题，或 1 条命中且播放 ≥ 20 万；中文频道搜索的结果，要求频道名或简介命中 AI 词 |
| 排除模式 | — | 频道名或简介含 赚钱、副业、crypto、股票、kids 等 |
| 每个主题的上限 | — | 最多 8 个，按订阅数取前 8 |
| 活跃度 | 最近 90 天内有上传 | 同左 |
| 专注度（第 2 轮新增，select 阶段生效） | 不适用 | 近 30 天至少 3 条视频，且至少 40% 的标题命中 AI 主题关键词 |
| 语言（第 2 轮新增） | 近 30 天标题有一半以上是中英文以外的文字时排除 | 同左 |
| 人工排除 | `manual_exclude_channel_ids` | 同左 |

订阅数只用作入池门槛，不参与排序。页面上原样展示，并标注「来自 YouTube」。

## 3. 结果
- 实际入池 **93 个频道**：英文 84 个，中文 9 个。
- 状态分布：included 93 · below_subscribers 318 · not_topical 101 · over_cap 45 · not_focused 26 · excluded_pattern 14 · inactive 13 · unverified 12 · unsupported_language 3。其中 below、not_topical、over_cap 主要是发现来的频道。

| 细分主题 | 入池博主数 | 示例 |
| --- | --- | --- |
| AI 模型与研究 | 24 | DeepLearning.AI、Google DeepMind、OpenAI、Two Minute Papers、AI Explained、Sebastian Raschka、Machine Learning Street Talk、Dwarkesh Patel、bycloud、最佳拍档、AI学长小林 |
| AI Agent | 24 | LangChain、LlamaIndex、CrewAI、AI Engineer、Sam Witteveen、Cole Medin、IndyDevDan、Nate Herk、Prompt Engineering、AI Jason、AI超元域、回到Axton |
| AI 编程 | 29 | Cursor、Anthropic、Fireship、ThePrimeTime、Theo、Matt Pocock、ArjanCodes、freeCodeCamp、GitHub、Visual Studio Code、Android Developers、雪踏乌云 |
| AI 产品与应用 | 29 | Matt Wolfe、The AI Advantage、MattVidPro、Skill Leap AI、Kevin Stratvert、Futurepedia、Jeff Su、Runway、ElevenLabs、零度解说、秋芝2046、howie.serious |
| AI 产业动态 | 29 | All-In、a16z、Y Combinator、Sequoia、No Priors、20VC、Acquired、Big Technology、Asianometry、ColdFusion、Latent Space、最佳拍档 |

（一个频道可以同时属于多个主题。）

**吴恩达**：
- 个人频道 `@andrewyng`（4.1 万订阅）最后一次上传是 2016-05-06，按 90 天活跃规则标为 inactive，不进池。
- **DeepLearning.AI（74.1 万订阅，11-06 还有更新）已入池**，归在 模型、Agent、编程 三个主题。本轮各主题的 Top 6 里还没有它的视频。
- 同样因为不活跃而落选的还有：Karpathy、LeCun、Chollet、李宏毅、Yannic Kilcher、Jeremy Howard 等。他们是“名人”，但近 90 天在 YouTube 上没有更新。

## 4. 发现扩展的教训（重要）
按播放量排序的搜索，带进来的大多是**泛内容大号**：
- 新闻和娱乐：CNN、BBC、ABC、SNL、Tucker Carlson、Business Insider
- 励志和综合：Peakzmotivation、The Infographics Show
- 印地语频道：Spreading Gyan、Active Rahul 等

加上“专注度”和“语言”两条规则后，这些被剔除了 26 + 3 个。最后只留下 6 个发现来的频道：Android Developers、Visual Studio Code、JavaScript Mastery、Apna College、Ayushman Pandita、AI学长小林。

**结论：“高播放、高订阅”只能当门槛，不能当入池理由，必须同时要求频道专注 AI。** 中文 AI 博主在 YouTube 上数量少、规模小（很多人主要在 B 站），发现只新增了 1 个中文频道。

## 5. 已知问题（需要决定）
- **X 链接豁免太宽**：“X 资料直接链接 YouTube”可以豁免订阅门槛，结果 12 订阅的「雪踏乌云」和 83 订阅的「遁一子」也进了池，前者还上了 AI 编程的 Top 6。**R2b 已修正**：个人博主一律要求 ≥ 1,000 订阅，只有官方/品牌频道豁免。
- **中文池偏薄**：只有 9 个中文频道。需要 Jason 提供他关注的中文 YouTube 博主名单，或者允许下一轮专门做中文发现（预计 5–10 次搜索）。
- **同题扎堆**：AI 产品与应用的 Top 6 里有 3 条都是“ChatGPT Images 2.6”。**R2b 已修正**：新增“同一事件只取 1 条”规则（标题标记重叠，确定性，零 API）。


## 6. 第 4 轮：纯中文博主发现（2026-11-09，Jason 11-08 批准）
- 做法：5 个细分主题 × 2 条中文搜索词（简体 zh-Hans、繁体 zh-Hant），共 10 次 search.list（近 90 天、按播放量）；所有频道都用 channels.list 核验，再按既有规则筛选（中文搜索发现的频道 ≥ 20K 订阅、90 天内活跃、≥ 40% 标题命中 AI 主题）。
- 用量：search.list 10/10，其他端点 22/300 单位（channels 2、playlistItems 15、videos 5），无 403/429。详见 `data/experiments/fewgood-zh-usage.json`。
- 结果：核验 15 个新中文频道（订阅 ≥ 20K），**只有 1 个入池：阿石OMP（AI 产品与应用）**；其余 14 个被“主题聚焦度”规则挡掉（多为综合科技/生活频道，只有个别视频谈 AI）。池子 93 → 94，中文频道 9 → 10。

| 频道 | 订阅 | 来源主题 | 结果 | 原因 |
| --- | --- | --- | --- | --- |
| 大有牧森 Austin Chou | 180,000 | ai-products | ❌ 未入池 | 主题标题命中 1/5（要求至少 3 条且比例 ≥ 0.4） |
| Brayden Chen | 95,100 | ai-products | ❌ 未入池 | 主题标题命中 1/5（要求至少 3 条且比例 ≥ 0.4） |
| 工匠先森 | 170,000 | ai-products | ❌ 未入池 | 主题标题命中 0/4（要求至少 3 条且比例 ≥ 0.4） |
| 阿石OMP | 68,500 | ai-products | ✅ 入池 | 近 90 天有更新、标题命中 |
| 孔老師AI研習社 | 81,300 | ai-products | ❌ 未入池 | 主题标题命中 1/3（要求至少 3 条且比例 ≥ 0.4） |
| 莊也雜談 | 74,300 | ai-agents | ❌ 未入池 | 主题标题命中 0/4（要求至少 3 条且比例 ≥ 0.4） |
| Porter科技迷 | 30,600 | ai-products | ❌ 未入池 | 主题标题命中 0/5（要求至少 3 条且比例 ≥ 0.4） |
| 三師爸Sense Bar | 75,300 | ai-products | ❌ 未入池 | 主题标题命中 7/50（要求至少 3 条且比例 ≥ 0.4） |
| 硅谷101 | 475,000 | ai-agents | ❌ 未入池 | 主题标题命中 0/10（要求至少 3 条且比例 ≥ 0.4） |
| 课代表立正 | 122,000 | ai-products | ❌ 未入池 | 主题标题命中 0/50（要求至少 3 条且比例 ≥ 0.4） |
| 技术爬爬虾  TechShrimp | 132,000 | ai-products | ❌ 未入池 | 主题标题命中 1/2（要求至少 3 条且比例 ≥ 0.4） |
| GeekHour | 38,100 | ai-products | ❌ 未入池 | 主题标题命中 0/1（要求至少 3 条且比例 ≥ 0.4） |
| Seven科技生活 | 129,000 | ai-products | ❌ 未入池 | 主题标题命中 0/5（要求至少 3 条且比例 ≥ 0.4） |
| 新聞大視野 | 23,200 | ai-industry | ❌ 未入池 | 主题标题命中 0/50（要求至少 3 条且比例 ≥ 0.4） |
| P & H | 30,500 | ai-products | ❌ 未入池 | 主题标题命中 2/12（要求至少 3 条且比例 ≥ 0.4） |

- 代码：`ytrec/fewgood_zh.py`（命令 `fewgood-zh-fetch` / `fewgood-zh-select`，后者零 API），由 Codex（gpt-5.6-terra）编写。
