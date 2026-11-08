# Alpha 评估（本地开发范围）

## 结论与边界

本 Alpha 保持 Astro 静态站及 `/youtuber` base，不改路由、Supabase schema、`library_items`、采集器、队列、配额账本或任何定时任务。`library_items` 现有 `kind` 是历史、收藏、稍后看和关注的同步协议；把栏目偏好塞入其中会改变既有语义和云端数据边界，故本次**仅本地保存**。

公共“社区推荐”当前来源为 Hacker News（不是 Reddit）。Alpha 的文档、注释和标识均以 Hacker News 表述；不会新增 Reddit 数据源或凭据。

## 已核查的最小改动面

| 文件 | 改动 |
| --- | --- |
| `site/src/lib/brand.mjs` | 集中站点、对话框、模式和栏目文案。 |
| `site/src/components/Header.astro` | 引用栏目文案，并修复 390px 头部布局。 |
| `site/src/components/VideoPage.astro` | 在既有公共栏目页面内加入无刷新模式切换和挂载点。 |
| `site/src/scripts/myspace.js` | 本地 schema、校验、编辑器、渲染和无 PII 事件。 |
| `docs/v2-*.md`、本文件、测试结果 | 修正 HN 术语并记录范围/验证。 |

## 本地数据契约与回滚

- key：`youtuber:myspace:v1`；值：`{version: 1, columns: [{id, source, enabled}]}`。
- `version` 必须为整数 `1`，`columns` 必须为数组；仅接受预定义 source，ID 必须唯一，最多读取配置的 5 个启用栏目。任何 JSON 损坏、未知版本、过期 source、类型错误或超限值均丢弃并回退默认值，不会影响任何 library key。
- 初始栏目是 全部、AI前沿、播客、音乐、社区推荐（最多推荐）；社区“最新入选”是可选既有子源。用户操作（启用、移除、上下移、来源选择）才写入该 key；观看、点击、收藏和历史绝不修改它。
- 回滚：还原本 Alpha 的本地 commit 即可去除 UI；遗留 key 是孤立、无害的浏览器数据。若要同时清除本机偏好，浏览器控制台执行 `localStorage.removeItem('youtuber:myspace:v1')`。不需要数据库回滚。

## 验收清单

- [ ] `PUBLIC_ALPHA_MYSPACE` 缺省开启，设为 `false` 时完全隐藏新控件。
- [ ] `探索世界` 与 `我的空间` 在同一页切换，无整页导航；探索排序保持原样。
- [ ] 可选全部五个既有栏目与社区两个既有排序子源；可上移、下移、移除/恢复，启用数至多 5。
- [ ] 刷新后配置仍在；无效/陈旧 localStorage 安全回退。
- [ ] 观看/历史/收藏不改变栏目；`mode_switch`、`myspace_save` 不含用户、邮件、搜索词或视频 ID。
- [ ] 390px 登录/注册单行且“稍后再看”入口不被裁切；768/1280 布局保持可用。
- [ ] 构建、静态预览及历史、收藏、稍后看、关注、搜索、视频播放的本地冒烟通过或明确标为未验证。

## 风险和不做事项

“我的空间”只重排现有静态内容池，不创建任意主题、不会调用 YouTube API，也不声称跨设备同步。真实认证、线上分析和外部播放器不使用测试账号；因此其线上往返只能列为未验证。后续若需要云端主题，应独立审查 RLS、迁移、限流及后台采集流程。
