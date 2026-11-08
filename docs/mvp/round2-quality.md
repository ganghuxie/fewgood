# Fewgood 第 2 轮质量报告

## usage

| 项目 | 值 |
| --- | --- |
| search.list 次数 | 15 |
| 其中 baseline / topic | 0 / 0 |
| 其他端点单位（按 endpoint） | channels: 87<br>playlistItems: 135<br>videos: 58 |
| HTTP 状态分布 | HTTP 200: 295 |
| 按旧模型 search=100 折算总单位 | 1780 |
| aborted_reason | 无 |

## AI 模型与研究

### stats

| 指标 | 值 |
| --- | --- |
| creators_in_topic | 24 |
| candidates_from_creators | 1453 |
| matched_tier1 | 15 |
| matched_tier2 | 182 |
| matched_tier3 | 0 |
| matched | 197 |
| eligible | 36 |
| shown | 6 |
| excluded_by_rule | {'duration': 62, 'creator_not_topic_tier2': 56, 'exclude:make money': 1, 'exclude:3d model': 1} |
| excluded_creators_by_rule | {'not_focused': 4} |
| channel_distribution_shown | {'bycloud': 1, 'Cohere': 1, 'Sebastian Raschka': 1, '最佳拍档': 1, 'IBM Technology': 1, 'TheAIGRID': 1} |
| relaxed_channel_cap | False |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 | 播放量 | 推荐依据 | 初步相关性 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [DeepSeek's New LLM Engine Just Made GPUs 3x More Valuable](https://www.youtube.com/watch?v=2K_Rm8cho1I) | bycloud | 2026-11-04 | 19:19 | 227,900 | 来自精选博主 bycloud（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「LLM」<br>发布于 2026-11-03（4 天前）<br>时长 19:19<br>订阅数 238000（入池时） | 相关：DeepSeek 推理引擎；标题偏夸张 |
| 2 | [Matthew Kowal - Interpretability Across the Model Design Pipeline](https://www.youtube.com/watch?v=jrApblKyLSQ) | Cohere | 2026-10-23 | 56:11 | 531 | 来自精选博主 Cohere（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「interpretability」<br>发布于 2026-10-22（16 天前）<br>时长 56:11<br>订阅数 19000（入池时） | 相关：可解释性研究演讲（Cohere）；播放量很低 |
| 3 | [Build A Reasoning Model From Scratch 8: Distillation](https://www.youtube.com/watch?v=msp69FR5NZs) | Sebastian Raschka | 2026-10-17 | 81:18 | 18,768 | 来自精选博主 Sebastian Raschka（入池依据：X 认证资料 + YouTube 核验；本主题博主）<br>标题含关键词「reasoning model」<br>发布于 2026-10-17（22 天前）<br>时长 81:18<br>订阅数 102000（入池时） | 相关：从零构建推理模型系列，研究/教学向 |
| 4 | [意识会不会在算法里醒来？\| 意识 \| 机器意识 \| Joscha Bach \| Transformer \| 因果模式 \| 整合信息理论 \| 自组织学习 \| 表征收敛 \| 大语言模型 \| 哲学僵尸](https://www.youtube.com/watch?v=WMD90rttSaw) | 最佳拍档 | 2026-11-06 | 20:07 | 12,050 | 来自精选博主 最佳拍档（入池依据：公开线索 + YouTube 核验；本主题博主）<br>标题含关键词「大语言模型」<br>发布于 2026-11-06（2 天前）<br>时长 20:07<br>订阅数 250000（入池时） | 部分相关：机器意识的哲学讨论，研究边缘 |
| 5 | [What Is LLM Inference? How AI Models Generate Responses](https://www.youtube.com/watch?v=615-yWyS1n0) | IBM Technology | 2026-10-22 | 7:46 | 119,578 | 来自精选博主 IBM Technology（入池依据：公开线索 + YouTube 核验；本主题博主）<br>标题含关键词「LLM」<br>发布于 2026-10-22（17 天前）<br>时长 7:46<br>订阅数 1840000（入池时） | 相关：LLM 推理原理讲解 |
| 6 | [Something Strange Is Happening With GPT-6.2](https://www.youtube.com/watch?v=R-OeFlyzveI) | TheAIGRID | 2026-11-06 | 24:54 | 60,160 | 来自精选博主 TheAIGRID（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「GPT」<br>发布于 2026-11-06（2 天前）<br>时长 24:54<br>订阅数 405000（入池时） | 部分相关：模型传闻/猜测，标题悬念式 |

## AI Agent

### stats

| 指标 | 值 |
| --- | --- |
| creators_in_topic | 24 |
| candidates_from_creators | 1453 |
| matched_tier1 | 89 |
| matched_tier2 | 76 |
| matched_tier3 | 0 |
| matched | 165 |
| eligible | 87 |
| shown | 6 |
| excluded_by_rule | {'duration': 48, 'creator_not_topic_tier2': 16, 'live_or_upcoming': 1} |
| excluded_creators_by_rule | {'not_focused': 7} |
| channel_distribution_shown | {'AI Engineer': 1, 'Siraj Raval': 1, 'Latent Space': 1, 'Nate Herk': 1, 'Hugging Face': 1, 'Cole Medin': 1} |
| relaxed_channel_cap | False |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 | 播放量 | 推荐依据 | 初步相关性 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [How Agents Cut Hour-Long Data Checks to 5 Minutes - Amol Kapoor & Clifford Ressel, Nori Agentic](https://www.youtube.com/watch?v=kIlVNGZZr8o) | AI Engineer | 2026-11-07 | 19:34 | 5,334 | 来自精选博主 AI Engineer（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「agentic」<br>边界规则：含 Agent 信号 → AI Agent<br>发布于 2026-11-07（1 天前）<br>时长 19:34<br>订阅数 1000000（入池时） | 相关：AI Engineer 实践演讲 |
| 2 | [I Gave My AI Agent Live Internet Access (Here Is What Broke First)](https://www.youtube.com/watch?v=ibdmyMFd_z8) | Siraj Raval | 2026-11-06 | 19:14 | 2,295 | 来自精选博主 Siraj Raval（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「AI agent」<br>边界规则：含 Agent 信号 → AI Agent<br>发布于 2026-11-06（1 天前）<br>时长 19:14<br>订阅数 768000（入池时） | 相关：Agent 联网实验 |
| 3 | [What 90,000 Rollouts Reveal About AI Agents Doing Science - Ian Quigley, Leash Bio](https://www.youtube.com/watch?v=vhPCo-8K78U) | Latent Space | 2026-10-26 | 16:34 | 29,879 | 来自精选博主 Latent Space（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「AI agents」<br>边界规则：含 Agent 信号 → AI Agent<br>发布于 2026-10-26（12 天前）<br>时长 16:34<br>订阅数 450000（入池时） | 相关：科研 Agent 实践（Latent Space） |
| 4 | [AI Agents Just Became Multiplayer. Here's How to Build Them.](https://www.youtube.com/watch?v=KZiF2J83zaY) | Nate Herk \| AI Automation | 2026-10-15 | 22:24 | 106,486 | 来自精选博主 Nate Herk（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「AI agents」<br>边界规则：含 Agent 信号 → AI Agent<br>发布于 2026-10-15（23 天前）<br>时长 22:24<br>订阅数 1120000（入池时） | 相关：多人 Agent 构建教程 |
| 5 | [How to Build Your Own AI Agent (Like PewDiePie)](https://www.youtube.com/watch?v=EuN8WCWQf7g) | Hugging Face | 2026-10-13 | 24:09 | 18,671 | 来自精选博主 Hugging Face（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「AI agent」<br>边界规则：含 Agent 信号 → AI Agent<br>发布于 2026-10-13（26 天前）<br>时长 24:09<br>订阅数 150000（入池时） | 相关：Hugging Face Agent 教程 |
| 6 | [Let Your AI Agent Do ITS OWN Harness Engineering (Here's How)](https://www.youtube.com/watch?v=TVhhmhvCovg) | Cole Medin | 2026-10-21 | 16:19 | 32,268 | 来自精选博主 Cole Medin（入池依据：X 认证资料 + YouTube 核验；本主题博主）<br>标题含关键词「AI agent」<br>边界规则：含 Agent 信号 → AI Agent<br>发布于 2026-10-20（18 天前）<br>时长 16:19<br>订阅数 231000（入池时） | 相关：Agent harness 工程；标题有全大写 |

## AI 编程

### stats

| 指标 | 值 |
| --- | --- |
| creators_in_topic | 29 |
| candidates_from_creators | 1453 |
| matched_tier1 | 66 |
| matched_tier2 | 28 |
| matched_tier3 | 0 |
| matched | 94 |
| eligible | 25 |
| shown | 6 |
| excluded_by_rule | {'creator_not_topic_tier2': 6, 'duration': 52} |
| excluded_creators_by_rule | {'not_focused': 4} |
| channel_distribution_shown | {'AI Engineer': 1, '雪踏乌云': 1, 'ArjanCodes': 1, 'GitHub': 1, 'Android Developers': 1, 'Visual Studio Code': 1} |
| relaxed_channel_cap | False |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 | 播放量 | 推荐依据 | 初步相关性 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [Your Coding Agent Can't Undo Its Own Mistakes - Tanmay Sah & Dolly Sah](https://www.youtube.com/watch?v=BT1Mo-fD-g0) | AI Engineer | 2026-11-08 | 16:38 | 1,575 | 来自精选博主 AI Engineer（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「coding agent」<br>边界规则：含编程 Agent 信号 → AI 编程<br>发布于 2026-11-08（0 天前）<br>时长 16:38<br>订阅数 1000000（入池时） | 相关：编码 Agent 实践演讲 |
| 2 | [Codex+Blender自动搭3D白模，让AI视频抽卡率暴涨](https://www.youtube.com/watch?v=kXJ1iOM89fs) | 雪踏乌云 | 2026-10-10 | 9:27 | 743 | 来自精选博主 雪踏乌云（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「Codex」<br>边界规则：含编程 Agent 信号 → AI 编程<br>发布于 2026-10-09（29 天前）<br>时长 9:27<br>订阅数 12（入池时） | 部分相关：用 Codex 驱动 Blender 建模，偏 AI 视频创作 |
| 3 | [7 Things AI Coding Agents Get Wrong (Because You Let Them)](https://www.youtube.com/watch?v=oFtTodDCbkE) | ArjanCodes | 2026-11-07 | 13:56 | 24,839 | 来自精选博主 ArjanCodes（入池依据：X 认证资料 + YouTube 核验；本主题博主）<br>标题含关键词「AI coding」<br>边界规则：含编程 Agent 信号 → AI 编程<br>发布于 2026-11-06（1 天前）<br>时长 13:56<br>订阅数 345000（入池时） | 相关：编码 Agent 常见错误 |
| 4 | [Work together, your way, with GitHub Copilot](https://www.youtube.com/watch?v=VJBTPepfWUI) | GitHub | 2026-11-07 | 32:51 | 4,980 | 来自精选博主 GitHub（入池依据：公开线索 + YouTube 核验；本主题博主）<br>标题含关键词「Copilot」<br>发布于 2026-11-07（0 天前）<br>时长 32:51<br>订阅数 706000（入池时） | 相关：GitHub Copilot 协作功能（官方） |
| 5 | [Agentic engineering with Claude Code and Android CLI](https://www.youtube.com/watch?v=Mb9H43ia0kE) | Android Developers | 2026-10-30 | 30:23 | 14,687 | 来自精选博主 Android Developers（入池依据：YouTube 高播放发现「AI Agent 智能体」 / YouTube 高播放发现「AI coding agent」；本主题博主）<br>标题含关键词「Claude Code」<br>边界规则：含编程 Agent 信号 → AI 编程<br>发布于 2026-10-29（9 天前）<br>时长 30:23<br>订阅数 1440000（入池时） | 相关：Claude Code + Android CLI（官方） |
| 6 | [Write and Optimize PostgreSQL Queries Faster in VS Code with Copilot](https://www.youtube.com/watch?v=lLp58sDAixQ) | Visual Studio Code | 2026-10-26 | 6:01 | 7,414 | 来自精选博主 Visual Studio Code（入池依据：YouTube 高播放发现「AI 编程 教程」；本主题博主）<br>标题含关键词「Copilot」<br>发布于 2026-10-26（12 天前）<br>时长 6:01<br>订阅数 1040000（入池时） | 相关：VS Code Copilot 写 SQL（官方，6 分钟） |

## AI 产品与应用

### stats

| 指标 | 值 |
| --- | --- |
| creators_in_topic | 29 |
| candidates_from_creators | 1453 |
| matched_tier1 | 55 |
| matched_tier2 | 34 |
| matched_tier3 | 0 |
| matched | 89 |
| eligible | 24 |
| shown | 6 |
| excluded_by_rule | {'duration': 39, 'creator_not_topic_tier2': 7, 'live_or_upcoming': 1, 'exclude:get rich': 1} |
| excluded_creators_by_rule | {'not_focused': 4, 'unsupported_language': 3} |
| channel_distribution_shown | {'MattVidPro AI': 1, 'The AI Advantage': 1, 'AI超元域': 1, 'AI Engineer': 1, 'Riley Brown': 1, 'Kevin Stratvert': 1} |
| relaxed_channel_cap | False |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 | 播放量 | 推荐依据 | 初步相关性 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [ChatGPT Can Make GIFs Now (Images 2.6 Tested)](https://www.youtube.com/watch?v=fQnrdr2DcqQ) | MattVidPro | 2026-11-08 | 17:58 | 5,979 | 来自精选博主 MattVidPro AI（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「ChatGPT」<br>发布于 2026-11-07（0 天前）<br>时长 17:58<br>订阅数 305000（入池时） | 相关：ChatGPT Images 2.6 实测；与另 2 条同题 |
| 2 | [ChatGPT Images 2.6 Is Here: GIFs, Dot Upgrades & More](https://www.youtube.com/watch?v=5LkRDoGVook) | The AI Advantage | 2026-11-07 | 11:33 | 24,248 | 来自精选博主 The AI Advantage（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「ChatGPT」<br>发布于 2026-11-06（1 天前）<br>时长 11:33<br>订阅数 493000（入池时） | 相关：ChatGPT Images 2.6 介绍；同题 |
| 3 | [🚀ChatGPT Images 2.6全方位实测！原生GIF生成、图像编辑一致性、电影分镜生成、产品摄影和UI界面原型生成、书法作品生成、换场景、改光影、多轮P图！样样精通！取代设计师！开发者效率倍增](https://www.youtube.com/watch?v=9fGwwQaaLSQ) | AI超元域 | 2026-11-05 | 10:27 | 14,105 | 来自精选博主 AI超元域（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「ChatGPT」<br>发布于 2026-11-05（3 天前）<br>时长 10:27<br>订阅数 78100（入池时） | 相关：中文 ChatGPT Images 2.6 实测；同题 |
| 4 | [78% Wanted This AI Feature. Almost Nobody Used It - Supriya Subudhi, Bumble](https://www.youtube.com/watch?v=CvmZtAPmAW4) | AI Engineer | 2026-10-31 | 14:44 | 10,095 | 来自精选博主 AI Engineer（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「AI feature」<br>发布于 2026-10-31（8 天前）<br>时长 14:44<br>订阅数 1000000（入池时） | 相关：Bumble AI 功能采用数据 |
| 5 | [ChatGPT Just Changed A LOT AGAIN (Here’s What’s New)](https://www.youtube.com/watch?v=vMvkR8WEOpE) | Riley Brown | 2026-10-31 | 16:59 | 144,754 | 来自精选博主 Riley Brown（入池依据：公开线索 + YouTube 核验；本主题博主）<br>标题含关键词「ChatGPT」<br>发布于 2026-10-31（7 天前）<br>时长 16:59<br>订阅数 310000（入池时） | 相关：ChatGPT 更新汇总 |
| 6 | [How to Use Remotion with ChatGPT](https://www.youtube.com/watch?v=9PwpJpJJ3IY) | Kevin Stratvert | 2026-10-30 | 8:01 | 43,948 | 来自精选博主 Kevin Stratvert（入池依据：公开线索 + YouTube 核验；本主题博主）<br>标题含关键词「ChatGPT」<br>发布于 2026-10-30（9 天前）<br>时长 8:01<br>订阅数 4490000（入池时） | 部分相关：Remotion + ChatGPT 做视频，偏编程教程 |

## AI 产业动态

### stats

| 指标 | 值 |
| --- | --- |
| creators_in_topic | 29 |
| candidates_from_creators | 1453 |
| matched_tier1 | 16 |
| matched_tier2 | 137 |
| matched_tier3 | 0 |
| matched | 153 |
| eligible | 48 |
| shown | 6 |
| excluded_by_rule | {'creator_not_topic_tier2': 16, 'duration': 60, 'clickbait': 1} |
| excluded_creators_by_rule | {'not_focused': 8} |
| channel_distribution_shown | {'All-In Podcast': 1, 'Matt Wolfe': 1, 'TheAIGRID': 1, 'Latent Space': 1, 'NVIDIA': 1, 'Dwarkesh Patel': 1} |
| relaxed_channel_cap | False |

### Top 6

| # | 标题 | 频道 | 发布日期 | 时长 | 播放量 | 推荐依据 | 初步相关性 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [Midterm Blood Bath, $4T AI Sell Off, Data Center Freeze, What’s Next for Trump](https://www.youtube.com/watch?v=2v8b062QzTI) | All-In Podcast | 2026-11-08 | 93:04 | 465,638 | 来自精选博主 All-In Podcast（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「data center」<br>边界规则：含产业动态信号 → AI 产业动态<br>发布于 2026-11-07（0 天前）<br>时长 93:04<br>订阅数 1170000（入池时） | 部分相关：政治与 AI 市场混合话题 |
| 2 | [AI News: New ChatGPT & Google Models (14 Updates Worth Knowing)](https://www.youtube.com/watch?v=IrAHINf0M6E) | Matt Wolfe | 2026-11-07 | 24:44 | 101,529 | 来自精选博主 Matt Wolfe（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「AI news」<br>边界规则：含产业动态信号 → AI 产业动态<br>发布于 2026-11-06（1 天前）<br>时长 24:44<br>订阅数 1030000（入池时） | 相关：每周 AI 新闻汇总 |
| 3 | [The AI Godfather Just Proved The Entire AI Industry Wrong](https://www.youtube.com/watch?v=_fEqQa5hBmI) | TheAIGRID | 2026-11-05 | 30:01 | 155,634 | 来自精选博主 TheAIGRID（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「AI industry」<br>发布于 2026-11-05（3 天前）<br>时长 30:01<br>订阅数 405000（入池时） | 部分相关：观点视频，标题 clickbait |
| 4 | [The Programmable Data Center — Evan Conrad, SF Compute](https://www.youtube.com/watch?v=EAtLq9_vrE0) | Latent Space | 2026-10-20 | 36:44 | 62,014 | 来自精选博主 Latent Space（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「data center」<br>边界规则：含产业动态信号 → AI 产业动态<br>发布于 2026-10-20（18 天前）<br>时长 36:44<br>订阅数 450000（入池时） | 相关：算力/数据中心产业访谈 |
| 5 | [NVIDIA GTC Berlin 2026 \| Live Keynote Pregame](https://www.youtube.com/watch?v=rySnll4sgu4) | NVIDIA | 2026-10-24 | 115:14 | 4,965,183 | 来自精选博主 NVIDIA（入池依据：原有 X→YouTube 名单；本主题博主）<br>标题含关键词「Nvidia」<br>发布于 2026-10-24（15 天前）<br>时长 115:14<br>订阅数 2260000（入池时） | 部分相关：GTC 柏林主题演讲前的预热直播回放，近 2 小时 |
| 6 | [What will computer chips look like in 2045?](https://www.youtube.com/watch?v=frYSOKvNiiE) | Dwarkesh Patel | 2026-10-23 | 69:01 | 319,420 | 来自精选博主 Dwarkesh Patel（入池依据：X 资料直接链接 YouTube；本主题博主）<br>标题含关键词「chips」<br>发布于 2026-10-22（16 天前）<br>时长 69:01<br>订阅数 1460000（入池时） | 相关：芯片产业未来（Dwarkesh） |
