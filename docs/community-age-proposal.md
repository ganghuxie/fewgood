# 社区推荐：年限筛选提案（仅分析，未改配置）

- 分析日期：2026-11-09（Asia/Shanghai）
- 样本：现有社区推荐 70 条（HN 规则：≥30 人 / ≥36 个月 / 跨度 ≥365 天；发布满 365 天；时长 ≥300 秒）
- 发布时间来源：`ytrec.sqlite` metadata 缓存中的 `snippet.publishedAt`（70/70 命中）
- YouTube API 用量：**0 units**（未调用 `videos.list`）
- HN 30 人 / 36 个月门槛：**本提案不改**
- 状态：**只提案，不改 config、不 commit、不部署**

## 1. 现状：按 YouTube 上传年份分布

| 上传年 | 条数 |
| --- | ---: |
| 2007 | 1 |
| 2008 | 3 |
| 2009 | 7 |
| 2010 | 3 |
| 2011 | 5 |
| 2012 | 16 |
| 2013 | 7 |
| 2014 | 9 |
| 2015 | 4 |
| 2016 | 6 |
| 2017 | 2 |
| 2018 | 1 |
| 2019 | 4 |
| 2021 | 2 |

年龄分桶（相对 2026-11-09）：

| 上传年龄 | 条数 |
| --- | ---: |
| 0–5 年 | 0 |
| 5–8 年 | 6 |
| 8–10 年 | 5 |
| 10–12 年 | 10 |
| 12–15 年 | 32 |
| 15–20 年 | 17 |

要点：
- 最新一条上传于 **2021**（约 5.2 年）；**没有** 0–5 年的视频。HN 的「长期反复推荐」门槛天然偏向老片。
- 主体集中在 2011–2014 上传（约 12–15 年）。

## 2. 上传年 ≠ 内容年代（再上传）

至少 **15** 条标题/已知史料显示为旧录像再上传。YouTube `publishedAt` 只是上架日。

| 内容年代（估） | 上传年 | 标题 |
| --- | --- | --- |
| ~1937 | 2009 | Around The Corner - How Differential Steering Works (1937) |
| ~1953 | 2011 | Mechanical Computer (All Parts) - Basic Mechanisms In Fire Control Com |
| ~1968 | 2012 | The Mother of All Demos, presented by Douglas Engelbart (1968) |
| ~1977 | 2010 | Powers of Ten™ (1977) |
| ~1983 | 2009 | Richard Feynman Magnets |
| ~1983 | 2012 | Richard Feynman. Why. |
| ~1985 | 2012 | Richard Feynman Computer Science Lecture - Hardware, Software and Heur |
| ~1986 | 2009 | Lecture 1A | MIT 6.001 Structure and Interpretation, 1986 |
| ~1995 | 2012 | Hamming, "You and Your Research" (June 6, 1995) |
| ~1997 | 2013 | Alan Kay at OOPSLA 1997 - The computer revolution hasnt happened yet |
| ~1997 | 2016 | Steve Jobs Insult Response - Highest Quality |
| ~1998 | 2012 | Growing a Language, by Guy Steele |
| ~2005 | 2008 | Steve Jobs' 2005 Stanford Commencement Address |
| ~2010 | 2019 | How to Speak |
| ~2011 | 2021 | "Simple Made Easy" - Rich Hickey (2011) |

按**内容年代**大致分布：1930s×1，1950s×1，1960s×1，1970s×1，1980s×4，1990s×4，2000s×8，2010s×49，2020s×1。

## 3. 候选截止线（上传年龄）

规则草案：`上传年龄 < N 年` **或** 命中「名人演讲/经典讲座」豁免。

| 截止线 N | 截止内 | 靠豁免留下 | 合计保留 | 去掉 | 评价 |
| ---: | ---: | ---: | ---: | ---: | --- |
| 8 年 | 6 | 24 | 30 | 40 | 过狠，列表偏短 |
| 10 年 | 11 | 22 | 33 | 37 | 仍偏短 |
| 12 年 | 21 | 20 | 41 | 29 | 推荐：经典与过时大致对半 |
| 15 年 | 53 | 8 | 61 | 9 | 温和，只去掉最明显的老片/段子 |

若**不加豁免**、只砍上传年龄：8 年仅剩 6 条，10 年 11 条，12 年 21 条，15 年 53 条。说明硬砍必须配豁免，否则社区页会空很多。

## 4. 建议方案

**建议采用：上传年龄 < 12 年，或命中豁免。**

- 预计保留 **41 / 70**，去掉 **29**。
- 备选：15 年截止 → 保留 61、去掉 9（更保守，先试水温可用）。
- 截止日期按「今天往回算整年」实现即可（配置项如 `max_upload_age_days: 4383` ≈12×365.25，或 `max_upload_age_years: 12`）。
- **不改** HN 的 30 人 / 36 个月 / 365 天跨度门槛。

### 豁免规则（规则化、可解释，不做个案点名）

超过年限的视频，仅当满足以下任一条款时保留，并在「推荐依据」中写明命中条款：

**A. 演讲型标题 +（名人 或 大学/博物馆频道）**
- 标题含：`lecture` / `keynote` / `commencement` / `address` / `speech` / `seminar` / `presentation` / `last lecture` / `inventing on principle` / `you and your research` / `structure and interpretation` / `mother of all demos` / `how to speak` / `full lecture`
- 且：命中名人名单，或频道属于大学/博物馆白名单

**B. 大学/博物馆频道 + 时长 ≥ 20 分钟**
- 频道白名单：Stanford、MIT OpenCourseWare、MIT Club of Northern California、Carnegie Mellon University、Computer History Museum、Royal Society of Arts、University of California Television (UCTV)、UChicago Social Sciences

**C. 名人 + 时长 ≥ 20 分钟**
- 避免把「Feynman Magnets」这类 7 分钟短片当演讲留下

**D. 经典演示**：标题含 Mother of All Demos / Engelbart（且命中名人名单）

### 名人名单（策展、写进配置，可后续增删）

Steve Jobs, Abraham Lincoln, Richard Feynman, Randy Pausch, Richard Hamming, Alan Kay, Douglas Engelbart, Bret Victor, Rich Hickey, Robert Sapolsky, Guy Steele, Joe Armstrong, Linus Torvalds, John Cleese, David Heinemeier Hansson, Jonathan Blow, Philip Wadler, Mike Acton, Patrick Winston, Robert Lustig

刻意未列入：Ray Dalio（《Economic Machine》是动画解说，不是演讲）。

Lincoln 目前 70 条里没有样本，名单预留以符合你举的例子。

## 5. 12 年方案：靠豁免留下的标题

共 20 条：

- Randy Pausch's Last Lecture: Achieving Your Childhood Dreams （上传 2007，内容~2007，63 人，命中 A_speech+famous_or_univ, B_univ_museum_20min+, C_famous_20min+）
- Steve Jobs' 2005 Stanford Commencement Address （上传 2008，内容~2005，67 人，命中 A_speech+famous_or_univ）
- David Heinemeier Hansson at Startup School 08 （上传 2008，内容~2008，46 人，命中 C_famous_20min+）
- Secret History of Silicon Valley （上传 2008，内容~2008，84 人，命中 B_univ_museum_20min+）
- Lecture 1A | MIT 6.001 Structure and Interpretation, 1986 （上传 2009，内容~1986，48 人，命中 A_speech+famous_or_univ, B_univ_museum_20min+）
- Sugar: THE BITTER TRUTH （上传 2009，内容~2009，198 人，命中 B_univ_museum_20min+）
- Stanford's Sapolsky On Depression in U.S. (Full Lecture) （上传 2009，内容~2009，56 人，命中 A_speech+famous_or_univ, B_univ_museum_20min+, C_famous_20min+）
- 1. Introduction to Human Behavioral Biology （上传 2011，内容~2011，36 人，命中 B_univ_museum_20min+）
- Bret Victor - Inventing on Principle （上传 2012，内容~2012，77 人，命中 A_speech+famous_or_univ, C_famous_20min+）
- Rails Conf 2012 Keynote: Simplicity Matters by Rich Hickey （上传 2012，内容~2012，38 人，命中 A_speech+famous_or_univ, C_famous_20min+）
- Richard Feynman Computer Science Lecture - Hardware, Software and Heuristics （上传 2012，内容~1985，53 人，命中 A_speech+famous_or_univ, C_famous_20min+）
- The Mother of All Demos, presented by Douglas Engelbart (1968) （上传 2012，内容~1968，108 人，命中 A_speech+famous_or_univ, C_famous_20min+, D_classic_demo）
- Growing a Language, by Guy Steele （上传 2012，内容~1998，79 人，命中 C_famous_20min+）
- Hamming, "You and Your Research" (June 6, 1995) （上传 2012，内容~1995，48 人，命中 A_speech+famous_or_univ, C_famous_20min+）
- Hammock Driven Development - Rich Hickey （上传 2012，内容~2012，109 人，命中 C_famous_20min+）
- Alan Kay at OOPSLA 1997 - The computer revolution hasnt happened yet （上传 2013，内容~1997，52 人，命中 C_famous_20min+）
- Bret Victor   The Future of Programming （上传 2013，内容~2013，72 人，命中 C_famous_20min+）
- LEADERSHIP LAB: The Craft of Writing Effectively （上传 2014，内容~2014，56 人，命中 B_univ_museum_20min+）
- "The Mess We're In" by Joe Armstrong （上传 2014，内容~2014，69 人，命中 C_famous_20min+）
- CppCon 2014: Mike Acton "Data-Oriented Design and C++" （上传 2014，内容~2014，98 人，命中 C_famous_20min+）

## 6. 12 年方案：会被去掉的标题

共 29 条。其中符合「太老非演讲」预期的包括：

- Around The Corner - How Differential Steering Works (1937)（上传 2009，73 人，9 分钟；再上传自 ~1937）
- Mechanical Computer (All Parts) - Basic Mechanisms In Fire Control Computers（上传 2011，51 人，41 分钟；再上传自 ~1953）
- Powers of Ten™ (1977)（上传 2010，73 人，9 分钟；再上传自 ~1977）
- Richard Feynman Magnets（上传 2009，45 人，7 分钟；再上传自 ~1983；有名人但时长/形态不符（Richard Feynman, Feynman））
- Richard Feynman. Why.（上传 2012，41 人，7 分钟；再上传自 ~1983；有名人但时长/形态不符（Richard Feynman, Feynman））
- Conway's Game Of Life in APL（上传 2009，82 人，7 分钟）
- Axis of Awesome - 4 Four Chord Song (with song titles)（上传 2009，48 人，5 分钟）
- RSA ANIMATE: Drive: The surprising truth about what motivates us（上传 2010，104 人，10 分钟）
- Episode 1 - Mongo DB Is Web Scale（上传 2010，184 人，5 分钟）
- Why Your Vote Doesn't Count（上传 2011，59 人，6 分钟）
- LISA11 - Fork Yeah! The Rise and Development of illumos（上传 2011，180 人，64 分钟）
- 28c3: The coming war on general computation（上传 2011，64 人，54 分钟）
- Node.js Is Bad Ass Rock Star Tech（上传 2012，36 人，5 分钟）
- AT&T Archives: The UNIX Operating System（上传 2012，81 人，27 分钟）
- Stop Writing Classes（上传 2012，38 人，27 分钟）
- Don't Talk to the Police（上传 2012，216 人，46 分钟）
- Mike Monteiro: F*ck You, Pay Me（上传 2012，75 人，37 分钟）
- Indistinguishable From Magic: Manufacturing Modern Computer Chips（上传 2012，62 人，61 分钟）
- A Tour of the Acme Editor（上传 2012，43 人，23 分钟）
- Wealth Inequality in America（上传 2012，46 人，6 分钟）
- Using Python to Code by Voice（上传 2013，66 人，28 分钟）
- 15 Sorting Algorithms in 6 Minutes（上传 2013，54 人，5 分钟）
- Symbolics Lisp Machine demo Jan 2013（上传 2013，33 人，13 分钟）
- How The Economic Machine Works by Ray Dalio（上传 2013，110 人，31 分钟）
- The Problem with Time & Timezones - Computerphile（上传 2013，83 人，10 分钟）
- The Expert (Short Comedy Sketch)（上传 2014，98 人，7 分钟）
- What Happened to Horses Is Happening to Us（上传 2014，128 人，15 分钟）
- Linus Torvalds says GPL v3 violates everything that GPLv2 stood for（上传 2014，35 人，9 分钟；有名人但时长/形态不符（Linus Torvalds））
- "Testing Distributed Systems w/ Deterministic Simulation" by Will Wilson（上传 2014，40 人，40 分钟）

### 边界样本（建议你拍板）

| 视频 | 12 年方案结果 | 说明 |
| --- | --- | --- |
| Don't Talk to the Police（216 人） | 去掉 | 法学院讲座，但不在大学白名单、标题也不走演讲关键词；若要留可把 Regent University 加进白名单 |
| RSA ANIMATE: Drive（104 人） | 去掉 | RSA 在白名单但片长约 10 分钟 <20；属动画摘要不是演讲 |
| How The Economic Machine Works by Ray Dalio | 去掉 | 名人动画解说，名单刻意不含 Dalio |
| Richard Feynman Magnets / Why（约 7 分钟） | 去掉 | 名人短片；完整 Feynman CS Lecture 仍豁免留下 |
| Steve Jobs Insult Response | **保留**（上传年龄约 9.9 年，未超 12 年） | 不是演讲；若讨厌可另加「短片/名场面」排除 |
| Smart Pipe / Adult Swim | **保留**（约 11.97 年，卡在 12 年边缘） | 搞笑广告；可选内容类型黑名单（comedy/parody/music） |

## 15 年温和备选：只去掉 9 条

- Conway's Game Of Life in APL（上传 2009）
- Richard Feynman Magnets（上传 2009）
- Around The Corner - How Differential Steering Works (1937)（上传 2009）
- Axis of Awesome - 4 Four Chord Song (with song titles)（上传 2009）
- RSA ANIMATE: Drive: The surprising truth about what motivates us（上传 2010）
- Powers of Ten™ (1977)（上传 2010）
- Episode 1 - Mongo DB Is Web Scale（上传 2010）
- Why Your Vote Doesn't Count（上传 2011）
- Mechanical Computer (All Parts) - Basic Mechanisms In Fire Control Computers（上传 2011）

## 7. 实现时注意

1.  enrichment 已有 `publishedAt` 缓存；筛选加在 community 选片阶段即可。
2. 推荐依据文案示例：`上传于 2008 年，因命中名人演讲豁免（Steve Jobs + commencement + Stanford）而保留`。
3. 豁免看的是标题/频道/时长规则，不看 HN 引用次数；避免「因为很火所以破例」。
4. 再上传片用上传日做主截止；内容年代只用于展示提示（可选），避免解析标题年份的误伤。
5. 列表变短后，社区页仍按 recommenders / newest 排序，无需改前端。

## 8. 请你选

1. **采用 12 年 + 上述豁免**（推荐）
2. **先用 15 年 + 同一豁免**（更保守）
3. **改名单/白名单后再算一版**（例如：加入 Regent University；或把 Dalio / Jobs Insult / Adult Swim 单独排除）
4. **先不动**

你选定前：不改配置、不提交、不上线。
