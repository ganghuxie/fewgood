# Fewgood MVP · 主题与筛选配置

完整配置以 [`config/fewgood_topics.yaml`](../../config/fewgood_topics.yaml) 为准（关键词、排除词、搜索词、可信频道都在里面）。这里只汇总规则。

## 五个细分主题（大主题：AI 前沿）

| 主题 | 定义 | 搜索表达（实验用前 2 个） | A 组基线词 |
| --- | --- | --- | --- |
| AI 模型与研究 | 模型能力、训练方法、评测与研究进展 | AI model research；LLM research | AI models |
| AI Agent | 能规划、调用工具或执行任务的 AI Agent | AI agents；agentic AI tutorial | AI Agent |
| AI 编程 | AI 辅助开发、代码生成与工程实践 | AI coding tools；coding agents | AI coding |
| AI 产品与应用 | 面向真实用户的 AI 产品、功能与使用案例 | new AI products；AI application demo | AI products |
| AI 产业动态 | AI 公司、政策、融资、合作与行业变化 | AI industry news；AI company news | AI industry |

每个主题的「包含」分 strong / weak 两级关键词。「排除」列出容易误判的内容，例如 real estate agent、travel agent、learn python、make money with AI、stock to buy、3d model。

## 统一条件
- **发布时间**：近 30 天。A 组不限时间，以模拟普通搜索。
- **类型和时长**：4 分钟到 2 小时，排除直播中或即将开播的视频，也排除 Shorts。videos.list 没有返回播放器尺寸时，不按横竖屏排除，靠 4 分钟的最短时长挡掉 Shorts。
- **内容不足**：宁缺毋滥。不足 6 条就按实际数量展示，并标注「候选不足」，不降低相关性门槛。本轮 5 个主题都凑满了 6 条。

## 候选来源（按成本从低到高）
1. **已有站点数据（0 单位）**：ai.json 全部，加上其他 feed 中标题命中主题词的记录，共 129 条。
2. **可信频道 uploads**：config/ai_channels.yaml 的 42 个频道，每个调用一次 playlistItems，共 42 单位。
3. **限定搜索**：每个主题 2 次，共 10 次 search.list。参数为 relevance 排序、近 30 天、relevanceLanguage=en、每次 25 条。
4. 所有候选用 videos.list 补全详情，每 50 条 1 单位。

## 筛选与排序（无综合评分）
1. **有效性**：视频公开，不在直播中或即将开播，时长合格，在 30 天内。
2. **相关性分级**：
   - tier1：strong 词命中标题。
   - tier2：strong 词命中标签或描述前 500 字，或 weak 词命中标题。
   - tier3：weak 词只命中描述，只计入统计，不展示。
   - 命中排除词的直接淘汰。
3. **跨主题唯一**：同一视频只归入 tier 最好的主题（平局按配置顺序），推荐依据里写「也匹配：…」。
4. **去重**：同一 ID 合并来源。标题归一化后相同，或词集合 Jaccard ≥ 0.8，视为重复，保留播放量高的那条。
5. **排序**：按 tier 升序 → 可信频道优先 → 发现来源数多者优先 → 发布时间新者优先。**播放量只展示，不参与排序。**
6. **多样性**：Top 6 中同一频道最多 2 条。

每条推荐都附可核验的「推荐依据」：命中的关键词和位置、是否来自可信频道、发布日期和天数、时长、被哪些来源发现。
