# Alpha UI 打磨轮验收（最新）

日期：2026-11-08（Asia/Shanghai）。本轮仍只在 `alpha` 分支本地修改和提交，未推送、部署、修改数据库或安装任务。

## 本轮交付

- 我的空间默认显示视频分区，齿轮按钮按需打开紧凑栏目管理弹窗；复选、上下移动、移除与添加操作保留。
- 一级模式分段控件移至 header，二级标签随模式切换；我的空间标签按用户栏目顺序显示并可滚动定位。
- 390px 搜索左侧黑边消失，搜索行与模式控件间距实测 2px；公共标签完整可见且横向可滚动，没有原先大块空白。
- 内容池预加载；本地样本切换到视频出现耗时 61–81ms（非线上 SLA）。截图均等待视频卡片出现，未使用加载中占位画面。
- 保持全站初始入口为探索世界，不改变既定产品决策。

## 模型及发现的修复

主 UI 调整由 Codex **gpt-5.6-terra** 完成。两次窄范围跟进使用 **gpt-5.6-luna**：恢复探索世界初始默认；修复标签滚动时分区标题被 sticky header 遮挡。后者浏览器复测：390px 标题顶端 210px、header 底端 198px；768/1280 标题顶端 164px、header 底端 152px，均留 12px 间距。

## 最新验收

| 检查 | 结果 |
| --- | --- |
| Astro build（504 页，/youtuber） | 通过 |
| Python 全量测试 | 70 passed |
| Myspace schema / diff 格式 | 通过 |
| PUBLIC_ALPHA_MYSPACE=false 构建关闭新控件 | 通过，随后恢复默认构建 |
| 390 / 768 / 1280 完整浏览器清单 | 87 / 87 通过 |
| 打磨专项浏览器检查 | 25 / 25 通过 |
| 无刷新双模式 / 探索列表不变 | 通过 |
| 栏目选择、增删、排序、最多5项活动、刷新保留、异常数据回退 | 通过 |
| 模式标签随重排同步、跳转不被头部遮挡 | 通过 |
| 视频先显示、管理弹窗默认关闭、Esc关闭、弹窗在屏幕内 | 通过 |
| 手机登录单行、三个图标可见、无横向页面溢出 | 通过 |
| 搜索、视频详情官方iframe、本地历史/收藏/稍后看增删、关注切换、登录框 | 通过 |
| 用户操作不隐式改栏目、mode_switch / myspace_save stub | 通过 |
| 五张更新截图人工查看，另查看768px | 通过；无重叠，编辑器紧凑，视频可见 |

截图仍是下文列出的五个绝对路径，本轮覆盖更新。

剩余边界：未使用真实账号，没有验证真实认证往返、云同步、邮件或视频实际播放；只验证官方 iframe 挂载。探索模式原有外部头像偶发加载失败仍可见；我的空间使用字母头像回退。配置仍为当前浏览器本地保存。预览验收后停止，本次本地提交可独立 revert，生产上线仍需单独授权。

---

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
