# Alpha 本地测试结果

日期：2026-11-08（Asia/Shanghai）。验证位于 box 常规 Shell，worktree `/workspace/codex/yt-recommended-alpha`，分支 `alpha`。仅本地提交；未 push、部署、迁移数据库或安装定时任务。Codex 的沙盒限制不影响本轮常规 Shell 验证。

## 结果

- `npm run build`：通过，504 个静态页面，base `/youtuber`。
- `python3 -m pytest -q`：70 passed。
- `node --test tests/test_myspace_schema.mjs`：通过。
- `git diff --check`：通过。
- Playwright / Chromium headless，390、768、1280 × 900：75 个浏览器断言全部通过。使用全新隔离浏览器 context；Supabase、PostHog 和 Cloudflare 请求被拦截，不创建真实账号。

| 验收项 | 结果 | 说明 |
| --- | --- | --- |
| Alpha 默认开启 / 关闭开关 | 通过 | 默认显示；另以 `PUBLIC_ALPHA_MYSPACE=false` 构建，首页不存在新控件，随后恢复默认构建。 |
| 探索世界 / 我的空间无刷新切换 | 通过（三宽度） | window 标记保留、视图显隐正确。 |
| 选择、添加、移除现有栏目 | 通过（三宽度） | 包含社区最新入选；关闭显示不删除已有配置。 |
| 上移 / 下移 | 通过（三宽度） | 顺序变化后可反向恢复。 |
| 最多 5 个活动栏目 | 通过（三宽度） | 第 6 个可保留为不启用项；移除一个后可以启用它。 |
| 刷新保留配置 | 通过（三宽度） | localStorage 内容和启用项一致。 |
| 无效 / 陈旧配置回退 | 通过 | 浏览器测试未知版本回退；schema 自动测试覆盖未知来源和超限等情况。 |
| 探索内容排序不变 | 通过（三宽度） | 切换、编辑前后公共视频链接序列完全相同。 |
| 行为不修改兴趣 | 通过（三宽度） | 播放页、收藏、稍后看、历史、关注操作前后栏目配置不变。 |
| 手机头部 | 通过 | 390px 登录/注册单行，三个资料库入口及菜单可见，探索与我的空间都无横向滚动。 |
| 搜索 | 通过（三宽度） | 输入 AI，进入有结果的搜索页。 |
| 视频详情 / 嵌入 | 通过（三宽度） | 本地详情页成功打开，存在 youtube-nocookie.com 官方 embed iframe；不等于验证真实播放成功。 |
| 历史 | 通过（三宽度） | 进入视频后列表记录存在，移除后消失。 |
| 收藏 / 稍后看 | 通过（三宽度） | 添加后换页仍在对应本地列表，移除后消失。 |
| 关注 | 通过（三宽度） | 可关注和取消关注。 |
| 登录对话框 | 通过（三宽度） | 可打开、关闭；不提交认证请求。 |
| 分析事件 | 通过（三宽度） | 页面加载后 stub `window.posthog.capture`，捕获 mode_switch / myspace_save；payload 仅 mode / active_columns，无个人信息。 |
| 视觉验收 | 通过 | 逐张打开下列五张截图，另查看 768px；无内容重叠、裁切或编辑器错位，按钮样式一致。 |

## 发现和修复

本轮仅由 Codex CLI 修改产品代码，模型 **gpt-5.6-luna**（Alpha 原开发模型为 gpt-5.6-terra）：

1. 390px 原实现只露出一个资料库图标：修正手机头部规则，三个图标均显示；手机隐藏 logo 文字以腾出空间，保留图标。
2. 我的空间运行时生成的 DOM 没有得到 Astro scoped CSS：将相关编辑器样式正确作用于动态节点，补齐响应式布局。
3. 原分析模块直接调用导入实例，替换 window.posthog 无法观测：加入捕获 stub 接口，并禁止 localhost 初始化真实分析，避免本地测试污染线上数据。

早期测试脚本的选择器和异步等待问题已纠正；最终一轮全部通过。没有将测试脚本问题误作产品缺陷修改。

安全观测方式（不发送真实事件）：

```js
window.__events = [];
window.posthog = { capture: (...args) => window.__events.push(args) };
```

## 截图

- `/workspace/codex/yt-recommended-alpha/screenshots/alpha_explore_1280.png`
- `/workspace/codex/yt-recommended-alpha/screenshots/alpha_myspace_1280.png`
- `/workspace/codex/yt-recommended-alpha/screenshots/alpha_editor_1280.png`
- `/workspace/codex/yt-recommended-alpha/screenshots/alpha_header_390.png`
- `/workspace/codex/yt-recommended-alpha/screenshots/alpha_myspace_390.png`

## 范围、已知限制与回滚

- 没有验证真实 Google/密码登录、云同步、PostHog 后台入站或 YouTube 视频实际播放。只验证本地对话框、数据行为和嵌入挂载。外部图片存在偶发头像加载失败，桌面探索截图可见；未改动原有图片机制。
- Alpha 配置仅本地保存，不跨设备同步；不新增主题搜索、后台队列、数据库表或任务。
- Hacker News 是真实社区来源，没有新增 Reddit 数据源。
- 五张截图和本文随本地 Alpha commit 保存。回滚可在本地回退本次提交；也可使用 `PUBLIC_ALPHA_MYSPACE=false` 隐藏 Alpha UI。遗留 `youtuber:myspace:v1` 不影响原资料库，必要时仅删除该 key。
- 本地预览使用 `python3 -m http.server 4399 -d /tmp/alpha-serve`；验收完停止。生产上线仍需 Jason 单独授权。
