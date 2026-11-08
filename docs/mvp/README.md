# Fewgood｜最小 MVP 验证报告

- 分支：`mvp-fewgood`（未合并到 master/main，未部署，没有改 Pages、Supabase、密钥或 workflow）
- 实验时间：2026-11-08 20:12:32–20:12:51（北京时间）。真实 API 只跑了 1 次，之后的调整都用 `select` 零调用重放。
- 代码全部由 Codex CLI 编写：
  - gpt-5.6-terra：管线、配置、Demo 和测试，以及一轮修复
  - gpt-5.6-luna：竖屏误判修复、报告生成脚本
  - 没有使用 sol，也没有使用 gpt-6.x
- 文档：[审计](audit.md) · [主题配置](topic-config.md) · [质量表](quality-tables.md) · [A/B 对比](ab-comparison.md) · [合规](compliance.md) · 初步判断数据 [preliminary-judgments.json](preliminary-judgments.json)

## 结论：Iterate（继续迭代，暂不扩展 Space）

管线、额度、去重和可解释性都达标。但只有 2/5 的主题达到“Top 6 至少 5/6 相关”，所以这一轮的结论是 Iterate，不是 Go。

| Go 条件 | 结果 |
| --- | --- |
| 五个细分主题都能正常运行 | ✅ 五个主题各 6 条 |
| Top 6 人工相关性 ≥ 5/6 | ⚠️ AI Agent 6/6、AI 编程 5/6；AI 模型与研究 4/6（另有 2 条部分相关）、AI 产品与应用 3/6（3 条部分相关）、AI 产业动态 3/6（3 条部分相关）。以上都是 Grok Bot 根据标题、频道和时长做的**初判，没有观看视频，待 Jason 复核** |
| 能缓存、去重、复用 | ✅ 复用已有站点数据 129 条（ai.json 全部加其他 feed 中标题命中主题词的记录）；合并后 587 条唯一视频，标题近似去重删掉 14 条；`select` 可零 API 重复执行 |
| 不超过 API 预算 | ✅ search.list 用了 15/15 次，其他端点 55/300 单位，没有出现 403 或 429 |
| 刷新和构建可重复 | ✅ `select` 加 `astro build` 都能重复执行，测试 79 项全部通过 |
| 不破坏正式网站 | ✅ 只在独立分支上，Demo 页面加了 noindex，首页没有链接 |
| 能解释入选原因 | ✅ 每条推荐都有可核验的推荐依据 |
| 没有未处理的关键合规风险 | ✅ 前提是不做评分，并在 30 天内刷新或删除数据。正式公开前还要补品牌标识和条款，见 compliance.md |

## 各主题发现（初判）
- **AI Agent（6/6）**：两组相关性打平，A 组同样是 6/6。B 组的优势是更新（中位 4.5 天，A 组 78 天），没有接近 Shorts 的短视频，还有 2 条 AI Engineer 的实践演讲。B 组的问题是有 2 条几乎同题的「20 分钟无代码做 Agent」入门教程。A 组则是播放量很高的常青入门讲解（例如 Jeff Su 的 560 万播放视频）。**所以还不能说 B 组一定更值得看，要看你想要“新”还是“讲得最清楚”。**
- **AI 编程（5/6）**：有 1 条误判。Ryo Lu 的演讲因为标题里有“ex-Cursor”命中了关键词 Cursor，实际内容不是 AI 编程。另有 3 条标题明显 clickbait 或带推广（"INSANE"、"FREE"、"Jailbroke"）。A 组（freeCodeCamp、Matt Pocock、IBM）质量看起来不比 B 组差，只是更旧。
- **AI 模型与研究（4/6）**：论文和研究向内容比较多（Hugging Face Journal Club 等），但有一个播放量极低的“AI Research Roundup”频道占了 2 条，另有 1 条信息安全播客和 1 条 Agent 论文。A 组以新闻和传闻为主（1/6）。
- **AI 产品与应用（3/6）**：B 组明显好于 A 组。A 组基线“AI products”返回的全是娱乐或骗局开箱（0/6）。B 组的问题是和 Agent、编程的边界不清，“在 ChatGPT 里做 Agent”“用 AI 工具做 App”都被归到了这里。
- **AI 产业动态（3/6）**：混进了传闻和泄露（AI Decode）、股市行情（FinnovationZ），还有一条 clickbait 的模型新闻（TheAIGRID）。

## API 实际用量与可持续性
- 本次实验：**search.list 15 次**（A 组基线 5 次，主题搜索 10 次）；playlistItems 42 单位（其中 6 个频道返回 404）；videos.list 13 单位。**其他端点合计 55 单位。** 采集耗时 19.1 秒，筛选 1.7 秒。
- 明早 07:00 的正式刷新（约 30 次 search、约 3,344 单位）和本次实验在同一个太平洋日，合计约 45/100 次、约 3,400/10,000 单位。真实分配以 Cloud Console 为准，box 上无法核实。
- 如果做成每日任务，可以去掉 A 组的 5 次基线搜索，每天约 10 次 search 加约 60 单位。即使扩展到 20 个主题，大约是 40 次 search 加约 100 单位，再加上现有的 30 次，仍在 100 次以内，但余量会明显变小。**以后扩展应以可信频道 uploads 为主（每个频道 1 单位），search 只用来补充。**

## 下一步建议（不额外消耗配额）
1. 请你先做 C 组：看 [A/B 对比](ab-comparison.md)，尤其是 AI Agent 和 AI 产品与应用这两个主题，挑出 6 条你真愿意看的视频，并复核我的初判。
2. 第 2 轮规则迭代可以全部用 `select` 零 API 重放：
   - 标题 clickbait 或推广信号降权或排除（全大写的夸张词、INSANE/SHOCKED/FREE、rumor/leak、!!/??）；
   - 品牌词必须带上下文（例如 “ex-Cursor” 不算），频道自己的品牌词除外；
   - 理清主题边界：标题含 agent 的优先归入 AI Agent，“build an app with AI” 归入 AI 编程；
   - 每个主题扩充可信频道（如 ArjanCodes、IBM Technology、Matt Wolfe、Latent Space），并让可信频道的权重高于普通 tier1。
3. 第 2 轮的结果如果让 3 个以上主题达到 5/6，而且 C 组和 B 组的重合明显多于和 A 组的重合，就可以判 Go，再考虑 Space。否则继续调优精选算法，**暂不扩展 Space 功能**。

## 如何预览 Demo
- 截图（box 上）：`screenshots/fewgood_demo_1280.png`、`fewgood_demo_390.png`，以及展开了 AI Agent A/B 对比的 `fewgood_demo_1280_ai_agent_ab.png`、`fewgood_demo_390_ai_agent_ab.png`。
- box 上的本地预览地址 `http://localhost:4391/youtuber/demo/fewgood/` 只能在 box 内部访问，**你的电脑打不开**。
- 在你自己的电脑上预览：
  ```bash
  git clone https://github.com/ganghuxie/youtuber && cd youtuber   # 已有仓库就 git fetch
  git checkout mvp-fewgood
  cd site && npm ci && npx astro dev
  # 打开 http://localhost:4321/youtuber/demo/fewgood/
  ```
- 托管预览：Pages 只从 master/main 部署，合并后 Demo 会出现在正式域名的 `/youtuber/demo/fewgood/`（不在首页挂链接，加了 noindex），**这需要你单独授权**。另一个办法是用独立的预览托管，同样需要授权。

## 复现命令
```bash
python3 -m ytrec.fewgood run --dry-run    # 只打印调用计划，不联网
python3 -m ytrec.fewgood select           # 零 API，用 box 上保存的原始候选重新筛选
python3 -m ytrec.fewgood_report           # 重新生成质量表和 A/B 表
python3 -m ytrec.fewgood run              # 真实调用（硬上限 15 次 search、300 单位），请勿频繁运行
```
原始候选 `data/experiments/fewgood-mvp-raw.json`（4.3 MB）只保存在 box 上，没有提交到公开仓库（见合规第 4 条）。
