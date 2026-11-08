# Fewgood MVP 质量报告

数据刷新时间：2026-11-08 20:12:51 北京时间

## pool_stats

| 指标 | 值 |
| --- | --- |
| existing_pool_raw | 783 |
| existing_pool_selected | 129 |
| channel_upload_raw | 364 |
| search_raw | 250 |
| merged_unique | 587 |
| after_title_dedup | 573 |
| fetched_details | 609 |
| missing_details | 0 |
| duplicates_removed | 14 |

## timing

| 指标 | 秒 |
| --- | --- |
| collect_seconds | 19.14751 |
| select_seconds | 1.655549 |

## usage 汇总

| 项目 | 值 |
| --- | --- |
| search.list 次数 | 15 |
| 其中 baseline / topic | 5 / 10 |
| 其他端点单位（按 endpoint） | playlistItems: 42<br>videos: 13 |
| HTTP 状态分布 | HTTP 200: 64<br>HTTP 404: 6 |
| 按旧模型 search=100 折算总单位 | 1555 |
| aborted_reason | 无 |

## AI 模型与研究

### stats

| 指标 | 值 |
| --- | --- |
| searches | 2 |
| baseline_searches | 1 |
| topic_search_results | 50 |
| matched | 112 |
| matched_tier1 | 25 |
| matched_tier2 | 76 |
| matched_tier3 | 11 |
| eligible | 64 |
| shown | 6 |
| duplicates_in_topic | 0 |
| excluded_by_rule | duration: 69<br>exclude:make money: 3<br>live_or_upcoming: 1 |
| channel_distribution_eligible 前 10 | AI Research Roundup: 2<br>Breach FM - der Infosec Podcast: 1<br>Hugging Face: 1<br>The Pretrained Pod: 1<br>bycloud: 1 |
| channel_distribution_shown | Hugging Face: 1<br>The Pretrained Pod: 1<br>AI Research Roundup: 2<br>bycloud: 1<br>Breach FM - der Infosec Podcast: 1 |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 m:ss | 播放量 | 发现来源 | 推荐依据 | 初步相关性（Grok Bot，待 Jason 复核） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [Hugging Face Journal Club: Score Centering Stabilizes Off-policy Reinforcement Learning](https://www.youtube.com/watch?v=mEtRe_KKYm0) | Hugging Face | 2026-10-26 | 32:26 | 3,008 | channel_uploads:Hugging Face | 标题含关键词「reinforcement learning」<br>也匹配：AI 产业动态<br>来自可信频道：Hugging Face<br>发布于 2026-10-26（13 天前）<br>时长 32:26，非 Shorts<br>被 1 个来源发现：频道上传 | 相关：RL 论文研读，研究向 |
| 2 | [The Shelf Life of LLM Findings](https://www.youtube.com/watch?v=bR5mzluCO5I) | The Pretrained Pod | 2026-11-05 | 22:08 | 376 | search:LLM research | 标题含关键词「LLM」<br>发布于 2026-11-05（3 天前）<br>时长 22:08，非 Shorts<br>被 1 个来源发现：搜索「LLM research」 | 相关：讨论 LLM 研究结论时效性 |
| 3 | [IdeaTaste: Benchmarking LLM Research Taste](https://www.youtube.com/watch?v=YphV2bVmHhc) | AI Research Roundup | 2026-11-05 | 4:46 | 54 | search:LLM research | 标题含关键词「LLM」<br>也匹配：AI Agent<br>发布于 2026-11-05（3 天前）<br>时长 4:46，非 Shorts<br>被 1 个来源发现：搜索「LLM research」 | 相关：评测论文解读；频道播放量极低，像自动化论文摘要 |
| 4 | [DeepSeek's New LLM Engine Just Made GPUs 3x More Valuable](https://www.youtube.com/watch?v=2K_Rm8cho1I) | bycloud | 2026-11-04 | 19:19 | 227,350 | search:LLM research | 标题含关键词「LLM」<br>也匹配：AI Agent、AI 编程、AI 产业动态<br>发布于 2026-11-03（5 天前）<br>时长 19:19，非 Shorts<br>被 1 个来源发现：搜索「LLM research」 | 相关：DeepSeek 推理引擎；标题偏夸张 |
| 5 | [LLM scaling, agent reliability and Europe’s AI stack ft. Daniel Gillblad](https://www.youtube.com/watch?v=cdW2CYF6fhM) | Breach FM - der Infosec Podcast | 2026-10-28 | 95:54 | 19 | search:LLM research | 标题含关键词「LLM」<br>也匹配：AI Agent<br>发布于 2026-10-28（11 天前）<br>时长 95:54，非 Shorts<br>被 1 个来源发现：搜索「LLM research」 | 部分相关：信息安全播客，混合谈 scaling/agent/欧洲 AI 栈 |
| 6 | [AutoTavern: LLM Agents Build Top Hearthstone Bot](https://www.youtube.com/watch?v=o3Z8ajFXAgU) | AI Research Roundup | 2026-10-28 | 4:43 | 160 | search:LLM research | 标题含关键词「LLM」<br>也匹配：AI Agent<br>发布于 2026-10-28（11 天前）<br>时长 4:43，非 Shorts<br>被 1 个来源发现：搜索「LLM research」 | 部分相关：论文内容是 LLM Agent，更贴近 AI Agent |

初步主题相关率 = 4/6（部分相关单独计数：2）

## AI Agent

### stats

| 指标 | 值 |
| --- | --- |
| searches | 2 |
| baseline_searches | 1 |
| topic_search_results | 50 |
| matched | 167 |
| matched_tier1 | 92 |
| matched_tier2 | 66 |
| matched_tier3 | 9 |
| eligible | 104 |
| shown | 6 |
| duplicates_in_topic | 0 |
| excluded_by_rule | duration: 79 |
| channel_distribution_eligible 前 10 | AI Engineer: 15<br>Grace Leung: 1<br>IBM Technology: 1<br>Metics Media: 1<br>Siraj Raval: 1 |
| channel_distribution_shown | AI Engineer: 2<br>Grace Leung: 1<br>Siraj Raval: 1<br>Metics Media: 1<br>IBM Technology: 1 |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 m:ss | 播放量 | 发现来源 | 推荐依据 | 初步相关性（Grok Bot，待 Jason 复核） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [How Agents Cut Hour-Long Data Checks to 5 Minutes - Amol Kapoor & Clifford Ressel, Nori Agentic](https://www.youtube.com/watch?v=kIlVNGZZr8o) | AI Engineer | 2026-11-07 | 19:34 | 5,334 | existing:ai.json<br>existing:catalog.json<br>channel_uploads:AI Engineer | 标题含关键词「agentic」<br>来自可信频道：AI Engineer<br>发布于 2026-11-07（1 天前）<br>时长 19:34，非 Shorts<br>被 3 个来源发现：已有数据 ai.json / 已有数据 catalog.json / 频道上传 | 相关：AI Engineer 实践演讲 |
| 2 | [Your AI Agent Is Hiding Its Mistakes From You - Ben Holmes, Warp](https://www.youtube.com/watch?v=pz74r-4dGfQ) | AI Engineer | 2026-11-07 | 19:20 | 29,625 | existing:ai.json<br>existing:catalog.json<br>channel_uploads:AI Engineer | 标题含关键词「AI agent」<br>也匹配：AI 模型与研究、AI 编程<br>来自可信频道：AI Engineer<br>发布于 2026-11-06（2 天前）<br>时长 19:20，非 Shorts<br>被 3 个来源发现：已有数据 ai.json / 已有数据 catalog.json / 频道上传 | 相关：Agent 可靠性实践演讲 |
| 3 | [Claude Code: Build Your First AI Agent in 20 Minutes (100% No Coding)](https://www.youtube.com/watch?v=F8jidmEkIeM) | Grace Leung | 2026-10-30 | 20:01 | 250,782 | search:AI agents<br>search:agentic AI tutorial<br>search:AI coding tools<br>search:coding agents<br>search:AI application demo | 标题含关键词「AI agent」<br>也匹配：AI 模型与研究、AI 编程、AI 产品与应用<br>发布于 2026-10-30（9 天前）<br>时长 20:01，非 Shorts<br>被 5 个来源发现：搜索「AI agents」 / 搜索「agentic AI tutorial」 / 搜索「AI coding tools」 / 搜索「coding agents」 / 搜索「AI application demo」 | 相关：入门无代码教程；与 rCkYVxOX-dI 内容相近 |
| 4 | [I Gave My AI Agent Live Internet Access (Here Is What Broke First)](https://www.youtube.com/watch?v=ibdmyMFd_z8) | Siraj Raval | 2026-11-06 | 19:14 | 2,296 | existing:ai.json<br>existing:catalog.json<br>channel_uploads:Siraj Raval | 标题含关键词「AI agent」<br>也匹配：AI 模型与研究<br>发布于 2026-11-06（2 天前）<br>时长 19:14，非 Shorts<br>被 3 个来源发现：已有数据 ai.json / 已有数据 catalog.json / 频道上传 | 相关：Agent 联网实验 |
| 5 | [Build Your First AI Agent in 20 Minutes (No Coding)](https://www.youtube.com/watch?v=rCkYVxOX-dI) | Metics Media | 2026-10-19 | 21:14 | 670,936 | search:agentic AI tutorial<br>search:AI coding tools<br>search:coding agents | 标题含关键词「AI agent」<br>也匹配：AI 编程<br>发布于 2026-10-19（20 天前）<br>时长 21:14，非 Shorts<br>被 3 个来源发现：搜索「agentic AI tutorial」 / 搜索「AI coding tools」 / 搜索「coding agents」 | 相关：入门无代码教程；与 F8jidmEkIeM 相近 |
| 6 | [What Is Loop Engineering? Building Better AI Agents](https://www.youtube.com/watch?v=DQBqh6gcx7U) | IBM Technology | 2026-10-19 | 10:48 | 133,156 | search:AI agents<br>search:agentic AI tutorial<br>search:coding agents | 标题含关键词「AI agents」<br>发布于 2026-10-19（20 天前）<br>时长 10:48，非 Shorts<br>被 3 个来源发现：搜索「AI agents」 / 搜索「agentic AI tutorial」 / 搜索「coding agents」 | 相关：IBM 概念讲解 |

初步主题相关率 = 6/6（部分相关单独计数：0）

## AI 编程

### stats

| 指标 | 值 |
| --- | --- |
| searches | 2 |
| baseline_searches | 1 |
| topic_search_results | 50 |
| matched | 49 |
| matched_tier1 | 32 |
| matched_tier2 | 11 |
| matched_tier3 | 6 |
| eligible | 25 |
| shown | 6 |
| duplicates_in_topic | 0 |
| excluded_by_rule | duration: 39<br>too_old: 3<br>exclude:make money with AI: 2 |
| channel_distribution_eligible 前 10 | AI Engineer: 2<br>ArjanCodes: 1<br>EarnixLab: 1<br>Julian Goldie SEO: 1<br>RGSecurityTeam: 1 |
| channel_distribution_shown | AI Engineer: 2<br>RGSecurityTeam: 1<br>EarnixLab: 1<br>Julian Goldie SEO: 1<br>ArjanCodes: 1 |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 m:ss | 播放量 | 发现来源 | 推荐依据 | 初步相关性（Grok Bot，待 Jason 复核） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [当我们什么都能做，还知道自己想做什么吗？When We Can Do Anything, Do We Still Know What We Want? — Ryo Lu, ex-Cursor](https://www.youtube.com/watch?v=y9Sg--RDtks) | AI Engineer | 2026-11-06 | 23:05 | 7,029 | existing:ai.json<br>existing:catalog.json<br>channel_uploads:AI Engineer | 标题含关键词「Cursor」<br>也匹配：AI 产品与应用<br>来自可信频道：AI Engineer<br>发布于 2026-11-06（2 天前）<br>时长 23:05，非 Shorts<br>被 3 个来源发现：已有数据 ai.json / 已有数据 catalog.json / 频道上传 | 不相关：因“ex-Cursor”命中关键词 Cursor；内容是产品/设计理念演讲 |
| 2 | [Your Coding Agent Can't Undo Its Own Mistakes - Tanmay Sah & Dolly Sah](https://www.youtube.com/watch?v=BT1Mo-fD-g0) | AI Engineer | 2026-11-08 | 16:38 | 1,276 | search:coding agents<br>channel_uploads:AI Engineer | 标题含关键词「coding agent」<br>也匹配：AI 模型与研究、AI Agent<br>来自可信频道：AI Engineer<br>发布于 2026-11-08（0 天前）<br>时长 16:38，非 Shorts<br>被 2 个来源发现：搜索「coding agents」 / 频道上传 | 相关：编码 Agent 实践演讲 |
| 3 | [I Jailbroke My AI Coding Agent… It Actually Worked! 😳](https://www.youtube.com/watch?v=DHZECISfaMc) | RGSecurityTeam | 2026-10-31 | 4:49 | 35,842 | search:AI coding tools<br>search:coding agents | 标题含关键词「AI coding」<br>也匹配：AI 模型与研究、AI Agent、AI 产业动态<br>发布于 2026-10-31（8 天前）<br>时长 4:49，非 Shorts<br>被 2 个来源发现：搜索「AI coding tools」 / 搜索「coding agents」 | 相关：编码 Agent 越狱；标题偏 clickbait |
| 4 | [Use Tencent HY4 for FREE! Best New AI Coding Agent (Full Setup Guide)](https://www.youtube.com/watch?v=Wi83iStXpio) | EarnixLab | 2026-11-08 | 9:20 | 7,702 | search:coding agents | 标题含关键词「AI coding」<br>也匹配：AI 模型与研究、AI Agent、AI 产品与应用<br>发布于 2026-11-07（1 天前）<br>时长 9:20，非 Shorts<br>被 1 个来源发现：搜索「coding agents」 | 相关：新编码 Agent 安装教程；偏推广 |
| 5 | [OpenCode Just Made AI Coding Automation INSANE!](https://www.youtube.com/watch?v=QwYKWW17xO8) | Julian Goldie SEO | 2026-11-07 | 8:30 | 8,302 | search:AI coding tools | 标题含关键词「AI coding」<br>也匹配：AI Agent、AI 产品与应用<br>发布于 2026-11-06（2 天前）<br>时长 8:30，非 Shorts<br>被 1 个来源发现：搜索「AI coding tools」 | 相关：OpenCode；标题 clickbait |
| 6 | [7 Things AI Coding Agents Get Wrong (Because You Let Them)](https://www.youtube.com/watch?v=oFtTodDCbkE) | ArjanCodes | 2026-11-07 | 13:56 | 24,626 | search:coding agents | 标题含关键词「AI coding」<br>也匹配：AI 模型与研究、AI Agent<br>发布于 2026-11-06（2 天前）<br>时长 13:56，非 Shorts<br>被 1 个来源发现：搜索「coding agents」 | 相关：编码 Agent 常见错误，实用 |

初步主题相关率 = 5/6（部分相关单独计数：0）

## AI 产品与应用

### stats

| 指标 | 值 |
| --- | --- |
| searches | 2 |
| baseline_searches | 1 |
| topic_search_results | 50 |
| matched | 67 |
| matched_tier1 | 19 |
| matched_tier2 | 25 |
| matched_tier3 | 23 |
| eligible | 15 |
| shown | 6 |
| duplicates_in_topic | 0 |
| excluded_by_rule | duration: 64<br>too_old: 1<br>exclude:make money with AI: 3 |
| channel_distribution_eligible 前 10 | AI Engineer: 2<br>AI with Hassan: 1<br>Latent Space: 1<br>Mikey No Code: 1<br>Zubair Trabzada \| AI Workshop: 1 |
| channel_distribution_shown | AI Engineer: 2<br>AI with Hassan: 1<br>Latent Space: 1<br>Zubair Trabzada \| AI Workshop: 1<br>Mikey No Code: 1 |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 m:ss | 播放量 | 发现来源 | 推荐依据 | 初步相关性（Grok Bot，待 Jason 复核） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [Build Your Own Finance Agent Inside ChatGPT - Stefano Fabbri & Oliver Steffmann, OpenAI](https://www.youtube.com/watch?v=ZJjRgvjhq3M) | AI Engineer | 2026-11-08 | 110:32 | 9,595 | existing:ai.json<br>existing:catalog.json<br>channel_uploads:AI Engineer | 标题含关键词「ChatGPT」<br>也匹配：AI Agent、AI 编程、AI 产业动态<br>发布于 2026-11-07（1 天前）<br>时长 110:32，非 Shorts<br>被 3 个来源发现：已有数据 ai.json / 已有数据 catalog.json / 频道上传 | 部分相关：在 ChatGPT 内做金融 Agent 的开发工作坊，偏 Agent/开发 |
| 2 | [Build Complete AI App Frontend, Backend, Payments, Authentication with FREE AI tools (0% Coding)](https://www.youtube.com/watch?v=08XjzXEugNw) | AI with Hassan | 2026-11-07 | 18:31 | 5,716 | search:AI coding tools | 标题含关键词「AI app」<br>也匹配：AI Agent、AI 编程<br>发布于 2026-11-07（1 天前）<br>时长 18:31，非 Shorts<br>被 1 个来源发现：搜索「AI coding tools」 | 部分相关：用 AI 工具做完整 App，更贴近 AI 编程/无代码 |
| 3 | [78% Wanted This AI Feature. Almost Nobody Used It - Supriya Subudhi, Bumble](https://www.youtube.com/watch?v=CvmZtAPmAW4) | AI Engineer | 2026-10-31 | 14:44 | 10,095 | channel_uploads:AI Engineer | 标题含关键词「AI feature」<br>也匹配：AI 模型与研究、AI 产业动态<br>发布于 2026-10-31（8 天前）<br>时长 14:44，非 Shorts<br>被 1 个来源发现：频道上传 | 相关：Bumble AI 功能的真实采用数据 |
| 4 | [Building ChatGPT for Finance — Joseph Kim, OpenAI's Head of Financial Services](https://www.youtube.com/watch?v=v-d1WTqIULs) | Latent Space | 2026-10-31 | 27:35 | 6,413 | channel_uploads:Latent Space | 标题含关键词「ChatGPT」<br>也匹配：AI 产业动态<br>发布于 2026-10-31（8 天前）<br>时长 27:35，非 Shorts<br>被 1 个来源发现：频道上传 | 相关：ChatGPT 金融产品访谈 |
| 5 | [I Gave My AI Assistant the Power to Reverse Engineer ANYTHING!](https://www.youtube.com/watch?v=84CkBM_jF4g) | Zubair Trabzada \| AI Workshop | 2026-10-15 | 18:12 | 381,466 | search:AI application demo | 标题含关键词「AI assistant」<br>也匹配：AI 模型与研究、AI Agent、AI 编程<br>发布于 2026-10-14（25 天前）<br>时长 18:12，非 Shorts<br>被 1 个来源发现：搜索「AI application demo」 | 部分相关：AI 助手工具演示；标题 clickbait |
| 6 | [Best AI App Builder in 2026 (Ranked Worst to Best!)](https://www.youtube.com/watch?v=qxED97f4i7A) | Mikey No Code | 2026-10-13 | 25:07 | 35,443 | search:AI coding tools | 标题含关键词「AI app」<br>也匹配：AI Agent<br>发布于 2026-10-13（26 天前）<br>时长 25:07，非 Shorts<br>被 1 个来源发现：搜索「AI coding tools」 | 相关：AI App Builder 横向比较 |

初步主题相关率 = 3/6（部分相关单独计数：3）

## AI 产业动态

### stats

| 指标 | 值 |
| --- | --- |
| searches | 2 |
| baseline_searches | 1 |
| topic_search_results | 50 |
| matched | 83 |
| matched_tier1 | 15 |
| matched_tier2 | 46 |
| matched_tier3 | 22 |
| eligible | 23 |
| shown | 6 |
| duplicates_in_topic | 0 |
| excluded_by_rule | duration: 107<br>too_old: 2<br>exclude:make money with AI: 1 |
| channel_distribution_eligible 前 10 | AI Decode: 1<br>Bloomberg Television: 1<br>FinnovationZ by Prasad: 1<br>Latent Space: 1<br>Matt Wolfe: 1<br>TheAIGRID: 1 |
| channel_distribution_shown | Latent Space: 1<br>TheAIGRID: 1<br>Matt Wolfe: 1<br>AI Decode: 1<br>Bloomberg Television: 1<br>FinnovationZ by Prasad: 1 |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 m:ss | 播放量 | 发现来源 | 推荐依据 | 初步相关性（Grok Bot，待 Jason 复核） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [The Programmable Data Center — Evan Conrad, SF Compute](https://www.youtube.com/watch?v=EAtLq9_vrE0) | Latent Space | 2026-10-20 | 36:44 | 62,026 | channel_uploads:Latent Space | 标题含关键词「data center」<br>也匹配：AI 模型与研究<br>来自可信频道：Latent Space<br>发布于 2026-10-20（19 天前）<br>时长 36:44，非 Shorts<br>被 1 个来源发现：频道上传 | 相关：算力/数据中心产业访谈 |
| 2 | [Anthropics Model 4 Just Shocked The AI Industry](https://www.youtube.com/watch?v=7eQree8FhKI) | TheAIGRID | 2026-11-07 | 30:01 | 85,918 | search:AI model research<br>search:AI industry news | 标题含关键词「AI industry」<br>发布于 2026-11-06（2 天前）<br>时长 30:01，非 Shorts<br>被 2 个来源发现：搜索「AI model research」 / 搜索「AI industry news」 | 部分相关：实为模型发布新闻；标题 clickbait |
| 3 | [AI News: The Only 6 Stories Worth Knowing This Week](https://www.youtube.com/watch?v=eDiQNFa-zYg) | Matt Wolfe | 2026-10-31 | 29:21 | 130,307 | search:AI industry news<br>search:AI company news | 标题含关键词「AI news」<br>也匹配：AI 模型与研究、AI Agent、AI 产品与应用<br>发布于 2026-10-30（9 天前）<br>时长 29:21，非 Shorts<br>被 2 个来源发现：搜索「AI industry news」 / 搜索「AI company news」 | 相关：每周 AI 新闻汇总 |
| 4 | [HUGE AI NEWS! GPT-7 Rumors, Gemini 4 Breakthroughs, Qwen 4 Leaks & Claude Controversy!”](https://www.youtube.com/watch?v=qMp7Gpu2OXA) | AI Decode | 2026-10-26 | 23:23 | 8,139 | search:AI industry news<br>search:AI company news | 标题含关键词「AI news」<br>也匹配：AI 模型与研究、AI Agent、AI 编程<br>发布于 2026-10-26（13 天前）<br>时长 23:23，非 Shorts<br>被 2 个来源发现：搜索「AI industry news」 / 搜索「AI company news」 | 部分相关：传闻/泄露汇总，可信度低 |
| 5 | [Global Stock Selloff: AI Investment Will Continue, George Colony Says](https://www.youtube.com/watch?v=-604wcjbg6Y) | Bloomberg Television | 2026-11-06 | 10:24 | 129,532 | search:AI company news | 标题含关键词「AI investment」<br>发布于 2026-11-05（3 天前）<br>时长 10:24，非 Shorts<br>被 1 个来源发现：搜索「AI company news」 | 相关：Bloomberg：AI 投资与市场 |
| 6 | [AI bubble finally bursting ?? Market Update !!](https://www.youtube.com/watch?v=Sp3JwHxmtlY) | FinnovationZ by Prasad | 2026-11-05 | 21:52 | 681,186 | search:AI company news | 标题含关键词「AI bubble」<br>发布于 2026-11-05（3 天前）<br>时长 21:52，非 Shorts<br>被 1 个来源发现：搜索「AI company news」 | 部分相关：股市行情角度，偏投资 |

初步主题相关率 = 3/6（部分相关单独计数：3）
