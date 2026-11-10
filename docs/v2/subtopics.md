# V2 小主题清单（已定稿）

> 状态：已定稿（Jason t133u，2026-11-10 17:07 Asia/Shanghai）。补抓约 52 单位额度已批准。

- 生成时间：2026-11-10 17:00:54（Asia/Shanghai）
- 数据提交：`a968db14fd6636ad3b4af9e95d9afa5a6f7ca8d1`（branch `v2-space`）
- 计数全部来自仓库已有数据，**没有**调用 YouTube / 外部 API，也尚未执行任何补抓。
- 本文件与 `config/subtopics.json` 为 Jason 于 2026-11-10 17:07（Asia/Shanghai）确认的定稿；补抓已获授权。

## 本轮修订（Jason 2026-11-10）

- 音乐去掉拉美、东南亚、儿童儿歌、印度影视歌曲；官方 MV 过泛，已撤。受众按相对高级/小众来选。保留 Tiny Desk 现场、日系现场（仅 THE FIRST TAKE 官方一发摄）；K-pop 收紧为演出/MV，去掉 vlog/运动会/综艺。新增华语流行、粤语、Hip-hop/说唱、欧美流行，并评估独立/民谣、爵士/古典、R&B/Soul、电子。
- 社区推荐去掉编程大会演讲、计算机史与思想、数学可视化；「全部」也不再列编程大会演讲。
- 跨类去重：每个小主题只保留在最合适的大类。TED、商业访谈只放在播客；Agent 学习只放在 AI前沿；经典演讲、大学公开课、科学科普只放在社区推荐。去重后「全部」不再单列一套小主题，产品上可由各垂类聚合展示。
- 收紧「科技与 AI」「人文社会」：Lex 等综合频道必须标题命中主题词，避免把精神科访谈放进科技、或把产业长谈放进人文。TED 已单独成题，不再计入科学与健康 / 人文社会的频道名单。
- 「AI 安全与对齐」仅 15 条，改列为需要补抓（不必新开 YouTube 抓取）。

## 计数口径

主计数用本地已抓取库存。阈值：主库存 < 8 的进入「需要补抓」。同一视频仍可命中同一大类里的多个小主题，但同一小主题不会在两个大类重复出现。

| 库存 | 视频数 | 频道数 | 说明 |
| --- | ---: | ---: | --- |
| `ai_pool` | 2789 | 86 | AI 入池频道已抓取候选（fewgood-r4-raw + 已上架 AI 条目） |
| `podcast_pool` | 3664 | 38 | 播客入池频道已抓取候选（fewgood-podcast-raw） |
| `community_corpus` | 3792 | 2071 | 社区推荐已抓取语料（sqlite metadata + videos.json） |
| `community_selected` | 41 | 34 | 当前社区推荐精选列表 videos.json |
| `music_local` | 3831 | 85 | 音乐页频道的本地视频（music.json ∪ channels.json 缓存） |
| `union_curated` | 9371 | 2164 | 精选并集：AI 池 ∪ 播客池 ∪ 社区语料 ∪ AI 页 |
| `editorial_ai` | 84 | 15 | AI前沿页 ai.json |
| `editorial_podcast` | 100 | 69 | 播客页 podcast.json（YouTube 热门播客，非精选池） |
| `editorial_music` | 100 | 85 | 音乐页 music.json |
| `editorial_community` | 41 | 34 | 社区推荐页 videos.json |
| `editorial_trending` | 100 | 74 | 全部页 trending.json（YouTube 热门，不作为小主题主计数） |

音乐主库存仍是当前音乐页频道的本地缓存。其中符合新受众方向的正片很少，所以华语、粤语、民谣、爵士、R&B、电子在本地几乎是空的，只能先列补抓方案。

## 建议列表

### 全部

与垂类去重后，不再单独列出小主题。建议在「全部」里聚合展示 AI / 播客 / 音乐 / 社区推荐已采纳的小主题。

### AI前沿

| 小主题 | 匹配规则摘要 | 频道数 | 主库存视频数 | 对应页当前条数 | 示例标题 |
| --- | --- | ---: | ---: | ---: | --- |
| AI 模型与研究 | 频道：AI at Meta、Cohere、最佳拍档、Hugging Face、NVIDIA、IBM Technology、Machine Learning Street Talk、AI Explained、Google DeepMind、Lex Fridman 等 25 个频道（入池 subtopics 含 ai-models 或 trusted_channels）；标题或标签含：large language model、LLM、foundation model、reasoning model、AI research、research paper、interpretability、reinforcement learning、pretraining、fine-tuning、scaling law、open-weight…；匹配方式：频道命中或关键词命中；排除：stock to buy、make money、3d model、model kit、fashion model、role model；时长 ≥ 240 秒 | 36 | 204 | 2 | DeepSeek, China, OpenAI, NVIDIA, xAI, TSMC, Stargate, and AI Megaclusters \| Lex Fridman Podcast #459（Lex Fridman）<br>Ryan Greenblatt – What happens once AI can automate AI research?（Dwarkesh Patel）<br>How Anthropic ships the #1 LLM in the World — with Katelyn Lesse and Angela Jiang（Latent Space） |
| AI Agent | 频道：Nate Herk、Sam Witteveen、Gary Chen、回到Axton、LangChain、Prompt Engineering、Hugging Face、AI超元域、IBM Technology、AI Engineer 等 28 个频道（入池 subtopics 含 ai-agents 或 trusted_channels）；标题或标签含：AI agent、AI agents、agentic AI、agentic、MCP、Model Context Protocol、computer use、agent framework、LangGraph、multi-agent、智能体、AI 智能体…；匹配方式：频道命中或关键词命中；排除：real estate agent、travel agent、valorant agent、movie agent、secret agent、insurance agent、agent 007、free agent；时长 ≥ 240 秒 | 50 | 376 | 22 | DHH: Future of Programming, AI, Agentic Engineering, Vibe Coding & Linux \| Lex Fridman Podcast #501（Lex Fridman）<br>React Native Full Course 2026 \| Build a Real Airbnb-Style App with AI Agents（JavaScript Mastery）<br>AI Engineering Full Course - Build and Deploy a Real AI App（Dave Ebbelaar） |
| AI 编程 | 频道：Tina Huang、Cursor、GitHub、freeCodeCamp.org、Apna College、LangChain、AI超元域、AI Engineer、Riley Brown、Cole Medin 等 31 个频道（入池 subtopics 含 ai-coding 或 trusted_channels）；标题或标签含：AI coding、AI code、coding agent、code agent、Cursor、Copilot、Claude Code、Codex、vibe coding、Windsurf、AI IDE、code review agent…；匹配方式：频道命中或关键词命中；排除：learn python、python for beginners、python tutorial、make money with AI；时长 ≥ 240 秒 | 43 | 251 | 6 | DHH: Future of Programming, AI, Agentic Engineering, Vibe Coding & Linux \| Lex Fridman Podcast #501（Lex Fridman）<br>Live Coding with Wes Bos, Burke Holland, Pierce Boggan & Friends \| GitHub Copilot Day（GitHub）<br>I Gave 3 Coding Agents Full Access \| Build and Deploy a Full Stack SaaS（JavaScript Mastery） |
| AI 产品与应用 | 频道：ElevenLabs、Tina Huang、MattVidPro AI、Lenny's Podcast、The Rundown AI、Gary Chen、回到Axton、Linus Ekenstam、The AI Advantage、AI超元域 等 34 个频道（入池 subtopics 含 ai-products 或 trusted_channels）；标题或标签含：AI product、AI app、AI application、ChatGPT、Claude、Gemini、AI tool、AI tools、AI feature、AI assistant、NotebookLM、AI video generator…；匹配方式：频道命中或关键词命中；排除：make money with AI、passive income、get rich、clickbait、top 10 AI tools to make money；时长 ≥ 240 秒 | 48 | 286 | 6 | Dario Amodei: Anthropic CEO on Claude, AGI & the Future of AI & Humanity \| Lex Fridman Podcast #452（Lex Fridman）<br>AI Engineering Full Course - Build and Deploy a Real AI App（Dave Ebbelaar）<br>Build Your Own Finance Agent Inside ChatGPT - Stefano Fabbri & Oliver Steffmann, OpenAI（AI Engineer） |
| AI 产业动态 | 频道：Asianometry、ColdFusion、Lenny's Podcast、The Rundown AI、a16z、Scale AI、Cohere、All-In Podcast、最佳拍档、NVIDIA 等 28 个频道（入池 subtopics 含 ai-industry 或 trusted_channels）；标题或标签含：AI industry、AI company、AI funding、AI regulation、AI news、AI policy、AI startup、AI chips、data center、AI investment、AI bubble、AI 产业；匹配方式：频道命中或关键词命中；排除：stock to buy、buy this stock、price target、make money with AI；时长 ≥ 240 秒 | 29 | 125 | 1 | DeepSeek, China, OpenAI, NVIDIA, xAI, TSMC, Stargate, and AI Megaclusters \| Lex Fridman Podcast #459（Lex Fridman）<br>Why I couldn't build Jev at OpenAI — Diogo Almeida, TypeSafe Co-founder & CEO（Latent Space）<br>Workshop: Training Agents at the frontier of AI Industry（Hugging Face） |
| Agent 学习 | 标题或标签同时含一类：AI agent / AI agents / agentic / MCP / Model Context Protocol / LangGraph / multi-agent / 智能体；标题同时含一类：tutorial / how to / beginner / guide / walkthrough / hands-on / full course / workshop；匹配方式：两组关键词同时命中；时长 ≥ 240 秒 | 19 | 60 | 0 | React Native Full Course 2026 \| Build a Real Airbnb-Style App with AI Agents（JavaScript Mastery）<br>AI Engineering Full Course - Build and Deploy a Real AI App（Dave Ebbelaar）<br>MCP Security Fundamentals Course（freeCodeCamp.org） |
| 开源模型与本地部署 | 标题或标签含：Ollama、llama.cpp、vLLM、GGUF、LM Studio、Open WebUI、本地部署、开源模型、開源模型、open-weight、local LLM、local model…；时长 ≥ 240 秒 | 11 | 34 | 1 | Hermes Agent: The Ultimate Beginner’s Guide（Metics Media）<br>Who’s afraid of an open-weight model? GLM, context bombing and post-Black Hat attacks（IBM Technology）<br>Kimi K3.1 Pro and Opus 5.5 Made the Same 13 Apps (Raw Results)（Prompt Engineering） |
| 中文 AI | 频道：Gary Chen、回到Axton、最佳拍档、AI超元域、AI学长小林、howie.serious、阿石OMP、秋芝2046、零度解说、傑少 JAY、花叔（入池 lang=zh 的中文频道）；匹配方式：仅频道列表；时长 ≥ 240 秒 | 10 | 250 | 0 | Claude Code 完整教學：新手必學的 15 個核心觀念（傑少 JAY）<br>借我 40 分鐘，讓我告訴你關於 Claude Code 你需要知道的所有觀念（Gary Chen）<br>DeepSeek V4是怎么训练出来的？73页PPT深入解析（花叔） |

需要补抓：

| 小主题 | 本地视频 | 原因 | 建议补抓频道（5–10） | 预估额度 |
| --- | ---: | --- | --- | ---: |
| AI 安全与对齐 | 15 | 入池库存收紧词表后仅 15 条 / 7 个频道，作为可勾选小主题偏薄。 | 不必新开 YouTube 抓取。可继续从已入池 AI 频道里用安全/对齐标题筛选；若要做可勾选，建议先补内容再上架。 | 0 |

### 播客

| 小主题 | 匹配规则摘要 | 频道数 | 主库存视频数 | 对应页当前条数 | 示例标题 |
| --- | --- | ---: | ---: | ---: | --- |
| TED | 频道：TED；频道名等于：TED、TEDx Talks；标题含：TED Talk、TED Talks、TEDTalk、TEDx Talk、\| TED、\| TEDx；匹配方式：频道命中或关键词命中；时长 ≥ 180 秒 | 1 | 55 | 0 | The Joy of Foraging Your Own Food \| Alexis Nikole Nelson \| TED（TED）<br>Why You Fear the Unknown — and What It Can Teach You \| Maya Shankar and Simone Stolzoff \| TED（TED）<br>How to Make Learning Impossibly Fun \| Mark Rober \| TED（TED） |
| 商业访谈 | 频道：Lenny's Podcast、Y Combinator、Sequoia Capital、20VC、Acquired、The Diary Of A CEO、Conversations with Tyler、硅谷101视频专栏、硅谷101播客、Invest Like The Best、a16z（访谈型商业/创投节目）；匹配方式：仅频道列表；时长 ≥ 600 秒 | 11 | 490 | 5 | Google Part III: The AI Company. Google is amazingly well-positioned... will they win in AI? (Audio)（Acquired）<br>AI Experts Debate: The AI Labs Are Lying To Everyone, Is There A 99% Chance Of Human Extinction?（The Diary Of A CEO）<br>再访Dyna Robotics：被部署教训了300天后，找到机器人Scaling Law【101视频播客】（硅谷101） |
| 科技与 AI | 时长 ≥ 600 秒 | 9 | 408 | 0 | State of AI in 2026: LLMs, Coding, Scaling Laws, China, Agents, GPUs, AGI \| Lex Fridman Podcast #490（Lex Fridman）<br>[One Million AI Engineer Special] How Stanford Teaches AI-Native Engineering — Mihail Eric, Monaco（Latent Space）<br>Ajeya Cotra – "This might be the clearest warning shot we ever get"（Dwarkesh Patel） |
| 商业创业 | 频道：Bg2 Pod、Lenny's Podcast、Stratechery、a16z、All-In Podcast、The Diary Of A CEO、Sequoia Capital、Freakonomics Radio Network、Hard Fork、Y Combinator 等 14 个频道；匹配方式：仅频道列表；时长 ≥ 600 秒 | 14 | 647 | 5 | Google Part III: The AI Company. Google is amazingly well-positioned... will they win in AI? (Audio)（Acquired）<br>AI Experts Debate: The AI Labs Are Lying To Everyone, Is There A 99% Chance Of Human Extinction?（The Diary Of A CEO）<br>Hard Fork Live: Robots, Revelry and the A.I. Revolution（Hard Fork） |
| 科学与健康 | 频道：HubermanLab、Peter Attia MD、Sam Harris、Sean Carroll、FoundMyFitness、StarTalk（trusted 科学/健康频道；TED 已单独成题，这里不再计入）；匹配方式：仅频道列表；时长 ≥ 600 秒 | 6 | 368 | 0 | 397 - Endometriosis and adenomyosis: diagnosis, fertility, reproductive aging, & emerging treatments（Peter Attia MD）<br>Dr. Brad Schoenfeld: Resistance Training for Time Efficiency, Body Composition & Maximum Hypertrophy（FoundMyFitness）<br>The Most Effective Weight Training, Cardio & Nutrition for Women \| Dr. Lauren Colenso-Semple（Andrew Huberman） |
| 人文社会 | 时长 ≥ 600 秒 | 14 | 589 | 1 | Psychiatry, Insane Asylums, Mental Illness, ECT, Lobotomies, Freud & Jung \| Lex Fridman Podcast #502（Lex Fridman）<br>Glenn Greenwald vs. Coleman Hughes Debate: Does Israel Control U.S. Foreign Policy?（Coleman Hughes）<br>Mindscape 323 \| Jacob Barandes on Indivisible Stochastic Quantum Mechanics（Sean Carroll） |
| 中文播客 | 频道：Zhang Xiaojun Podcast、最佳拍档、硅谷101视频专栏、howie.serious、硅谷101播客；匹配方式：仅频道列表；时长 ≥ 600 秒 | 5 | 310 | 0 | Lindon Gao / Dyna: Finding Clarity in the Fog of Robotics, Disagreements & Choice, and Wang Yangming（Zhang Xiaojun Podcast）<br>再访Dyna Robotics：被部署教训了300天后，找到机器人Scaling Law【101视频播客】（硅谷101）<br>E257｜对话Vitalik：AI安全背后的哲学思想，有效利他主义如何影响硅谷？（硅谷101播客） |

### 音乐

| 小主题 | 匹配规则摘要 | 频道数 | 主库存视频数 | 对应页当前条数 | 示例标题 |
| --- | --- | ---: | ---: | ---: | --- |
| Tiny Desk 现场 | 标题含：Tiny Desk Concert、Tiny Desk | 1 | 29 | 2 | Los Tigres del Norte: Tiny Desk Concert（NPR Music）<br>Cardi B: Tiny Desk Concert（NPR Music）<br>Richard O'Brien's 'The Rocky Horror Show': Tiny Desk Concert（NPR Music） |
| 日系现场 | 频道：THE FIRST TAKE（仅 THE FIRST TAKE 官方频道的一发摄演出）；标题含：THE FIRST TAKE、ファーストテイク；匹配方式：频道且关键词 | 1 | 38 | 3 | Original Love - 接吻 / THE FIRST TAKE（THE FIRST TAKE）<br>SiM - The Rumbling / THE FIRST TAKE（THE FIRST TAKE）<br>忘れらんねえよ - なんもねえ / THE FIRST TAKE（THE FIRST TAKE） |
| 欧美流行 | 频道：OliviaRodrigoVEVO、HarryStylesVEVO、U2VEVO（本地已有的官方 VEVO：Olivia Rodrigo、Harry Styles、U2）；匹配方式：仅频道列表 | 3 | 150 | 3 | U2 - The Greatest Show On Earth（U2VEVO）<br>Olivia Rodrigo - expectations (feat. Chappell Roan) (Official Music Video)（OliviaRodrigoVEVO）<br>Harry Styles - Coming Up Roses (Official Video)（HarryStylesVEVO） |
| K-pop | 频道：UC3IZKseVpdzPSBaWxBxundA、UCYDmx2Sfpnaxg488yBpZIGg、UCeLPm9yH_a_QH8n6445G-Ow、UCLkAepWjdylmXSltofFvsYQ、UCwgtORdDtUKhpjE1VBv6XfA、UCTQVIXvcHrR9jYoJ6qaBAow（韩流厂牌/节目频道，且标题须像演出/MV；排除 vlog、运动会、综艺）；标题含：MV、M/V、Official MV、Official Music Video、Visualizer、Stage CAM、Stage、Live、Concert、Music Bank、뮤뱅、뮤직뱅크…；匹配方式：频道且关键词 | 6 | 80 | 4 | KATSEYE (캣츠아이) “Unloveu” Visualizer（HYBE LABELS）<br>[뮤뱅 스테디캠 4K] A2O LITE 'NEON' 4k Bonus Ver. @뮤직뱅크(Music Bank) 261023（KBS Kpop）<br>IVE 아이브 'Looks Can Kill' MV（STARSHIP） |
| Hip-hop / 说唱 | 频道：Stones Throw（本地仅 Stones Throw 厂牌正片；中文说唱为 0，见补抓建议）；标题含：Official Music Video、Official Video、Dungeon Sessions、Visualizer、Jazz Cats、Crate Diggin、Whenimondamic、new music video、Official Audio；匹配方式：频道且关键词 | 1 | 13 | 0 | @sofieroyer  - AUTO - New music video out now on #StonesThrow. New tour dates on sale today, too.（Stones Throw）<br>Introducing @kiko. Watch her new music video "Feelin' Wee", out today. #StonesThrow（Stones Throw）<br>@BennySings x @elijahfoxmusic - “Real Person”. Watch the new visualizer today.（Stones Throw） |

需要补抓：

| 小主题 | 本地视频 | 原因 | 建议补抓频道（5–10） | 预估额度 |
| --- | ---: | --- | --- | ---: |
| 华语流行 | 0 | 本地库存没有可确认的华语流行正片（无滚石/杰威尔/相信音樂等频道，标题也无对应艺人）。 | 杰威尔音乐 JVR Music（high；周杰伦厂牌官方频道）<br>林俊傑 JJ Lin（high；艺人官方频道）<br>相信音樂 B'in Music（high；五月天等艺人厂牌官方频道）<br>滚石唱片 ROCK RECORDS（high；华语厂牌官方频道）<br>华纳音乐台湾 Warner Music Taiwan（high；华语发行官方频道；勿与欧美 Warner 主频道混淆）<br>台湾索尼音乐 Sony Music Taiwan（high；华语发行官方频道）<br>告五人 Accusefive（high；乐队官方频道）<br>毛不易（high；艺人官方频道） | 8 |
| 粤语 | 0 | 本地库存中粤语正片为 0（「beyond」等词会误伤英文标题，未采用）。 | 陳奕迅 Eason Chan（high；艺人官方频道）<br>環球音樂香港 Universal Music Hong Kong（high；港区发行官方频道）<br>英皇娛樂 EEG / Emperor Entertainment（high；港区厂牌官方频道）<br>寰亞音樂 Media Asia Music（high；港区厂牌官方频道）<br>林家謙 Terence Lam（high；当代粤语创作人官方频道）<br>張學友 Jacky Cheung（high；艺人官方频道）<br>Warner Music Hong Kong 華納音樂香港（high；港区发行官方频道）<br>陳卓賢 Ian Chan（medium；MIRROR 成员官方频道；若主页更偏综艺可改用其正片列表） | 8 |
| 独立 / 民谣 | 0 | 本地无可用的独立/民谣目录；Stones Throw 更偏地下嘻哈/厂牌花絮，不计入本主题。 | KEXP（high；现场录音会话，独立/另类为主）<br>Audiotree（high；Audiotree Live 官方频道）<br>Mahogany（high；Mahogany Sessions 官方频道）<br>陈粒（high；艺人官方频道）<br>万能青年旅店（high；乐队官方频道）<br>草東沒有派對 No Party For Cao Dong（high；乐队官方频道）<br>好妹妹乐队（high；组合官方频道）<br>新裤子 New Pants（high；乐队官方频道） | 8 |
| 爵士 / 古典 | 0 | 本地几乎没有爵士/古典正片（仅 Stones Throw 里偶有 Jazz 字样，不足且不对题）。 | Deutsche Grammophon（high；古典厂牌官方频道）<br>Berliner Philharmoniker（high；柏林爱乐官方频道）<br>Blue Note Records（high；爵士厂牌官方频道）<br>Jazz at Lincoln Center（high；爵士机构官方频道）<br>Classic FM（high；古典电台官方频道）<br>ECM Records（medium；爵士/当代古典厂牌；确认官方频道名后收录）<br>国家大剧院 NCPA（medium；频道名可能是「国家大剧院」或 NCPA China，收录前核对）<br>NPR Music（high；已在库中（Tiny Desk）；若只补爵士/古典，可不再重复抓，从已有缓存筛选即可） | 7 |
| R&B / Soul | 0 | 本地无可靠的 R&B/Soul 正片（soul 一词会被误伤）。 | SZA（high；SZA 或 SZAvevo 官方频道）<br>TheWeekndVEVO（high；The Weeknd 官方 VEVO）<br>方大同 Khalil Fong（high；华语 R&B 艺人官方频道）<br>陶喆 David Tao（high；华语 R&B 艺人官方频道）<br>COLORS（high；与说唱补抓共用，不重复计额度）<br>Mahogany（high；与独立/民谣补抓共用，不重复计额度）<br>Daniel Caesar（high；艺人官方频道）<br>蔡健雅 Tanya Chua（high；华语流行/R&B 艺人官方频道） | 6 |
| 电子 | 0 | 本地没有可确认的电子音乐目录（technology 等词会误伤科技频道）。 | Boiler Room（high；电子现场会话官方频道）<br>Cercle（high；电子现场官方频道）<br>Ninja Tune（high；电子/左翼厂牌官方频道）<br>Mixmag（high；电子媒体官方频道，以 DJ set 为主）<br>Defected Records（high；House 厂牌官方频道）<br>Anjunadeep（high；偏旋律的电子厂牌官方频道，比纯 EDM 大节更贴受众）<br>Resident Advisor（medium；电子媒体官方频道；内容含采访与 set，收录前可先看 uploads 构成）<br>Innervisions（medium；厂牌官方频道，确认全名后收录） | 8 |

补充：`Hip-hop / 说唱` 本地已够 8 条，但中文说唱仍是 0。建议另抓：

- COLORS（high，高质量现场/录音棚表演，也覆盖全球 hip-hop 与灵魂乐）
- 熱狗 MC HotDog（high，华语说唱艺人官方频道）
- 蛋堡 Soft Lipa（high，华语说唱艺人官方频道）
- 高爾宣 OSN（high，华语说唱艺人官方频道）
- 瘦子 E.SO（high，顽童成员官方频道）
- 張震嶽（high，艺人官方频道，华语嘻哈/摇滚）
- 法老 Pharaoh（medium，中文说唱艺人，频道名可能带厂牌后缀，收录前需核对）
- 頑童 MJ116（high，团体官方频道）
- 预估额度：8 单位（每频道 uploads 首页 1 次 playlistItems）。

### 社区推荐

| 小主题 | 匹配规则摘要 | 频道数 | 主库存视频数 | 对应页当前条数 | 示例标题 |
| --- | --- | ---: | ---: | ---: | --- |
| 经典演讲 | 频道名包含：Stanford、MIT OpenCourseWare、Carnegie Mellon、University of California Television、UCTV、UChicago、MIT Club of Northern California、Strange Loop Conference、ClojureTV、CppCon、Confreaks、GOTO Conferences、Google TechTalks、Talks at Google、DEFCONConference、Computer History Museum、Royal Society of Arts；标题含：last lecture、inventing on principle、you and your research、mother of all demos、structure and interpretation、how to speak、Steve Jobs、Randy Pausch、Richard Feynman、Richard Hamming、Alan Kay、Douglas Engelbart…；匹配方式：精选经典标记，或标题含人名/名篇，或（大学/会议频道且标题含 lecture/keynote 等）；时长 ≥ 300 秒 | 87 | 137 | 27 | Seminar with Alan Kay on Object Oriented Programming (VPRI 0246)（Yoshiki Ohshima (大島芳樹)）<br>Steve Jobs Unveils the NeXT Computer - October 12, 1988（The ReDiscovered Future）<br>the sham legacy of Richard Feynman（Angela Collier ） |
| 大学公开课 | 频道名包含：Stanford、MIT OpenCourseWare、Carnegie Mellon、University of California Television、UCTV、UChicago、MIT Club of Northern California；匹配方式：仅频道列表；时长 ≥ 300 秒 | 12 | 49 | 9 | Leonard Susskind \| "ER = EPR" or "What's Behind the Horizons of Black Holes?" - 1 of 2（Stanford Institute for Theoretical Physics）<br>Breakthrough in  Nuclear Fusion? - Prof. Dennis Whyte（MIT Club of Northern California）<br>21. Chaos and Reductionism（Stanford） |
| 科学科普 | 频道名包含：Veritasium、Kurzgesagt、CGP Grey、Tom Scott、3Blue1Brown、Numberphile、SmarterEveryDay、Computerphile；匹配方式：仅频道列表；时长 ≥ 60 秒 | 10 | 293 | 4 | A Million Dollars vs A Billion Dollars, Visualized: A Road Trip（Tom Scott）<br>I Was SCARED To Say This To NASA... (But I said it anyway) - Smarter Every Day 293（SmarterEveryDay）<br>Jim Simons (full length interview) - Numberphile（Numberphile2） |

## 补抓额度汇总（尚未执行）

方法：只做一次 uploads-first，每个新频道抓 uploads 播放列表第 1 页（约 50 条，`playlistItems` 1 单位）。COLORS、Mahogany 若在多个主题出现，只计一次。NPR Music 已在本地，不重复抓。

去重后新频道合计预估 **52 单位**。这只是第一页的成本；若某频道首页噪声多、需要再翻页，每加一页再 +1。

## 观察

- 欧美流行可以立刻做：本地已有 Olivia Rodrigo、Harry Styles、U2 三个官方 VEVO 频道缓存。
- Tiny Desk 与 THE FIRST TAKE 官方演出也足够立刻展示。K-pop 收紧后仍有足够 MV/舞台，但整体更偏大众，是否长期保留可以再定。
- 华语流行、粤语在现有音乐缓存里是空的，和当前音乐页来源（YouTube 热门）有关，不是词表没写全。
- Hip-hop 目前只能靠 Stones Throw 的部分正片；中文说唱需要另补。
- 「科技与 AI」不再收录 Lex 的非科技长谈；「人文社会」不再收录纯产业/模型长谈。TED 只在播客的 TED 小主题里计。

## 未做的事

- 没有改 UI、没有提交、没有请求 API、没有动生产库，也没有执行补抓。